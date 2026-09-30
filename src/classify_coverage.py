"""Reconcile complete source populations, then classify mutually exclusive receipts.

Usage: classify_coverage.py COVERAGE_DIR BASELINE_RESEARCH
Writes review artifacts only. The separate staging step authorizes publication.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict,Counter
import json,gzip,hashlib,sys
import coverage_decode as C
from acquire_refresh import R,OLD,save,START,END

def day(r):return datetime.fromtimestamp(int(r['timeStamp']),timezone.utc).date().isoformat()
def source_rows(manifest,ledger):
    if not manifest.get('calldata_in_pages'):
        with gzip.open(ledger,'rt') as stream:
            for line in stream:yield json.loads(line)
        return
    seen=set()
    for page in manifest['pages']:
        path=R/page['file'];raw=gzip.decompress(path.read_bytes())
        assert hashlib.sha256(raw).hexdigest()==page['sha256_uncompressed'],'Changed raw calldata page'
        rows=json.loads(raw)['result'];del raw
        assert len(rows)==page['rows']
        for row in rows:
            if row['hash'] in seen:continue
            seen.add(row['hash']);yield row
    assert len(seen)==manifest['transactions'],'Incomplete referenced calldata population'
def main():
    only=set(json.loads(Path(sys.argv[3]).read_text())) if len(sys.argv)>3 else None
    previous=json.loads((R/'classification-verification.json').read_text()) if only is not None else None
    previous_sources={s['address']:s for s in previous['sources']} if previous else {}
    decls,all_decl=C.declarations(R)
    # Match the published Across selectors; every resulting chain ID is decoded.
    cohorts=json.loads((Path(__file__).resolve().parents[1]/'data/cohort-sources.json').read_text())
    for s in cohorts['across']['series']:
        selector,item=C.parse(s['signature']);C.METHODS[selector]=item
    repairs={}
    for f in [OLD.parents[1]/'solana/canonical-verification.json',OLD.parents[1]/'refresh/canonical-verification.json',R/'canonical-run.json',R/'canonical-extra.json']:
        if f.exists():
            j=json.loads(f.read_text());assert not j.get('errors');repairs.update({x['hash']:x for x in j['results']})
    extra=json.loads((R/'canonical-extra.json').read_text()) if (R/'canonical-extra.json').exists() else {}
    rejected={x['hash'] for x in extra.get('rejected_noncanonical',[])}
    def repaired_rows(manifest,ledger,address):
        present=set()
        for row in source_rows(manifest,ledger):
            present.add(row['hash'])
            if row['hash'] not in rejected:yield row
        for row in extra.get('results',[]):
            if row['hash'] not in present and (row.get('to') or '').lower()==address:yield row.copy()
    corrections=json.loads((OLD/'audit/canonical_correction_transactions.json').read_text())
    sources=[];missing=[];seen=set();daily=defaultdict(lambda:[0,0]);products=Counter();methods=Counter()
    (R/'classified').mkdir(exist_ok=True)
    for s in json.loads((R/'catalog.json').read_text()):
        address=s['address'];ledger=R/'ledgers'/(address+'.jsonl.gz');manifest=R/'receipt-manifests'/(address+'.json')
        if not ledger.exists() or not manifest.exists():missing.append(address);continue
        if only is not None and address not in only:
            prior=previous_sources[address];dest=R/'classified'/(address+'.jsonl.gz')
            assert hashlib.sha256(ledger.read_bytes()).hexdigest()==prior['ledger_sha256']
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==prior['classified_sha256']
            n=gas=0
            with gzip.open(dest,'rt') as stream:
                for line in stream:
                    r=json.loads(line);assert r['transaction_hash'] not in seen;seen.add(r['transaction_hash']);n+=1;gas+=r['gas_used']
                    products[r['product']]+=r['gas_used'];methods[(r['product'],r['selector'],r['rule'])]+=1
                    v=daily[(r['date'],r['product'],r['activity'],r['source_id'])];v[0]+=r['gas_used'];v[1]+=1
            assert [n,gas]==[prior['accepted'],prior['accepted_gas']]
            sources.append(prior);continue
        m=json.loads(manifest.read_text());assert m['complete']
        obj=json.loads((R/'aggregates'/('coverage-'+address+'.json')).read_text())
        expected={x['date']:[x['sum(gas_used)'],x['count()']] for x in obj['data']};actual=defaultdict(lambda:[0,0]);index_fixes=[]
        if 'ETH4' in obj['context']['servers']:
            for r in corrections:
                if r['recipient']==address and START<=r['date']<END:
                    expected[r['date']][0]-=r['gas_used'];expected[r['date']][1]-=1;index_fixes.append(r['hash'])
        expected={d:v for d,v in expected.items() if v!=[0,0]}
        excluded=Counter();excluded_gas=Counter();count=0;accepted=0;gas=0;method_inventory={};canonical_used=[]
        dest=R/'classified'/(address+'.jsonl.gz')
        with gzip.open(dest,'wt',compresslevel=6) as output:
            for r in repaired_rows(m,ledger,address):
                if r['hash'] in repairs:r.update(repairs[r['hash']]);canonical_used.append(r['hash'])
                date=day(r)
                if not START<=date<END or (r.get('to') or '').lower()!=address:continue
                assert r['hash'] not in seen,('Overlapping account cohort',r['hash'])
                seen.add(r['hash']);count+=1;g=int(r['gasUsed']);actual[date][0]+=g;actual[date][1]+=1
                sel=r['input'][:10];inv=method_inventory.setdefault(sel,{'tx':0,'gas':0,'provider_label':r.get('functionName','')});inv['tx']+=1;inv['gas']+=g
                try:p,activity,rule=C.select(r,s,decls,all_decl)
                except (AssertionError,KeyError,ValueError,IndexError,OverflowError) as e:
                    reason=str(e) or type(e).__name__;excluded[reason]+=1;excluded_gas[reason]+=g;continue
                except Exception as e:
                    # ABI rejection is an exclusion, never acceptance. Preserve its class.
                    if type(e).__module__.startswith('eth_abi'):
                        reason=type(e).__name__;excluded[reason]+=1;excluded_gas[reason]+=g;continue
                    raise
                assert g>0
                accepted+=1;gas+=g;products[p]+=g;methods[(p,sel,rule)]+=1
                rec={'date':date,'product':p,'activity':activity,'transaction_hash':r['hash'],'block_number':int(r['blockNumber']),'gas_used':g,'source_id':'coverage-'+address,'selector':sel,'status':'failed' if r['isError']=='1' else 'success','rule':rule}
                output.write(json.dumps(rec,separators=(',',':'))+'\n')
                v=daily[(date,p,activity,rec['source_id'])];v[0]+=g;v[1]+=1
        differences={d:{'receipts':actual.get(d,[0,0]),'aggregate':expected.get(d,[0,0])} for d in actual.keys()|expected.keys() if actual.get(d,[0,0])!=expected.get(d,[0,0])}
        sources.append({'address':address,'roles':s['roles'],'transactions':count,'accepted':accepted,'accepted_gas':gas,'daily_count_and_gas_match':not differences,'differences':differences,'excluded':dict(excluded),'excluded_gas':dict(excluded_gas),'methods':method_inventory,'canonical_repairs':canonical_used,'documented_ETH4_duplicates_removed':index_fixes,'ledger_sha256':hashlib.sha256(ledger.read_bytes()).hexdigest(),'classified_sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
        print(json.dumps({'account':s['product']+'/'+s['name'],'accepted':accepted,'gas':gas,'mismatches':len(differences)}),flush=True)
    rows=[{'date':k[0],'product':k[1],'detail_bucket':k[2],'source_id':k[3],'gas_used':v[0],'tx_count':v[1]} for k,v in sorted(daily.items())]
    save(R/'daily.json',rows)
    report={'start_inclusive':START,'end_exclusive':END,'complete':not missing and all(s['daily_count_and_gas_match'] for s in sources),'missing':missing,'sources':sources,'products_gas':dict(products),'source_transactions':sum(s['transactions'] for s in sources),'accepted_transactions':sum(s['accepted'] for s in sources),'global_hash_deduplication':True,'input_calldata':'ABI-decoded attribution fields and reviewed signatures. Opaque proof arrays in successful closed settlement calls are not interpreted; the dedicated recipient or decoded chain identifier establishes attribution.'}
    if previous:
        report['incremental_verification']={'reclassified_accounts':sorted(only),'reused_accounts':len(sources)-len(only),'previous_report_sha256':hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest(),'classification_rules_sha256':hashlib.sha256(Path(C.__file__).read_bytes()).hexdigest(),'reuse_basis':'CCTP branch tightened; all affected accounts reclassified. Other decoder branches, source inputs and checksummed classifications unchanged. Every accepted total and hash uniqueness rebuilt.'}
    save(R/'classification-verification.json',report)
    save(R/'accepted-methods.json',[{'product':p,'selector':s,'signature':m,'transactions':n} for (p,s,m),n in sorted(methods.items())])
    print(json.dumps({k:report[k] for k in ['complete','missing','source_transactions','accepted_transactions','products_gas']}),flush=True)
if __name__=='__main__':main()
