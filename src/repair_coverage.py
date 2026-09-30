"""Apply bounded canonical corrections to a completed full classification pass.

Reclassifies each changed transaction with the same decoder, reconciles affected
source populations, then rebuilds all accepted totals and checks hash uniqueness.
Original provider responses and the pre-correction report remain immutable.
"""
from pathlib import Path
from collections import defaultdict,Counter
import json,gzip,re,hashlib
from acquire_refresh import R,OLD,ROOT,save,START,END
from classify_coverage import day
import coverage_decode as C

def main():
    report=json.loads((R/'classification-verification-phase1.json').read_text())
    extra=json.loads((R/'canonical-extra.json').read_text());assert not extra['errors'] and not report['missing']
    fixes={x['hash']:x for x in extra['results']};rejected={x['hash']:x for x in extra.get('rejected_noncanonical',[])};targets=set(fixes)|set(rejected)
    prior={}
    for p in [OLD.parents[1]/'solana/canonical-verification.json',OLD.parents[1]/'refresh/canonical-verification.json',R/'canonical-run.json']:
        if p.exists():prior.update({x['hash']:x for x in json.loads(p.read_text())['results']})
    decls,all_decl=C.declarations(R)
    for s in json.loads((ROOT/'data/cohort-sources.json').read_text())['across']['series']:
        sel,item=C.parse(s['signature']);C.METHODS[sel]=item
    catalog={s['address']:s for s in json.loads((R/'catalog.json').read_text())}
    corrections=json.loads((OLD/'audit/canonical_correction_transactions.json').read_text());changes=[]
    addresses={s['address'] for s in report['sources'] if s['differences']}|{(x.get('to') or '').lower() for x in fixes.values()}
    def classify(r,s):
        try:
            p,a,rule=C.select(r,s,decls,all_decl)
            return {'date':day(r),'product':p,'activity':a,'transaction_hash':r['hash'],'block_number':int(r['blockNumber']),'gas_used':int(r['gasUsed']),'source_id':'coverage-'+s['address'],'selector':r['input'][:10],'status':'failed' if r['isError']=='1' else 'success','rule':rule},None
        except (AssertionError,KeyError,ValueError,IndexError,OverflowError) as e:return None,str(e) or type(e).__name__
        except Exception as e:
            if type(e).__module__.startswith('eth_abi'):return None,type(e).__name__
            raise
    def qualifies(r,a):return r is not None and START<=day(r)<END and (r.get('to') or '').lower()==a
    for source in report['sources']:
        a=source['address']
        if a not in addresses:continue
        s=catalog[a];original={};ledger=R/'ledgers'/(a+'.jsonl.gz')
        assert hashlib.sha256(ledger.read_bytes()).hexdigest()==source['ledger_sha256']
        with gzip.open(ledger,'rt') as f:
            for line in f:
                h=re.search(r'"hash":"(0x[0-9a-f]+)"',line[:1500])[1]
                if h in targets:original[h]=json.loads(line)
        for h,r in original.items():
            if 'input' not in r:
                page=json.loads(gzip.decompress((R/r['input_page']).read_bytes()))
                full=next(t for t in page['result'] if t['hash']==h)
                assert hashlib.sha256(full['input'].encode()).hexdigest()==r['input_sha256']
                r['input']=full['input']
            r.update(prior.get(h,{}))
        candidates=set(original)|{h for h,r in fixes.items() if qualifies(r,a)}
        if not candidates:continue
        aggregate=json.loads((R/'aggregates'/('coverage-'+a+'.json')).read_text())
        expected={v['date']:[v['sum(gas_used)'],v['count()']] for v in aggregate['data']}
        if 'ETH4' in aggregate['context']['servers']:
            for r in corrections:
                if r['recipient']==a and START<=r['date']<END:expected[r['date']][0]-=r['gas_used'];expected[r['date']][1]-=1
        actual={d:v.copy() for d,v in expected.items()}
        for d,v in source['differences'].items():actual[d]=v['receipts'].copy()
        accepted_updates={};accepted_before={}
        for h in sorted(candidates):
            before=original.get(h);after=None if h in rejected else fixes.get(h,before)
            for sign,r in [(-1,before),(1,after)]:
                if not qualifies(r,a):continue
                d=day(r);g=int(r['gasUsed']);v=actual.setdefault(d,[0,0]);v[0]+=sign*g;v[1]+=sign
                source['transactions']+=sign
                sel=r['input'][:10];m=source['methods'].setdefault(sel,{'tx':0,'gas':0,'provider_label':r.get('functionName','')});m['tx']+=sign;m['gas']+=sign*g
                accepted,reason=classify(r,s)
                if reason:
                    source['excluded'][reason]=source['excluded'].get(reason,0)+sign
                    source['excluded_gas'][reason]=source['excluded_gas'].get(reason,0)+sign*g
                else:
                    source['accepted']+=sign;source['accepted_gas']+=sign*g
                    (accepted_before if sign==-1 else accepted_updates)[h]=accepted
            source['canonical_repairs']=sorted(set(source['canonical_repairs'])|({h} if h in fixes else set()))
            changes.append({'address':a,'hash':h,'original':{k:before.get(k) for k in ['blockNumber','timeStamp','to','gasUsed','isError']} if before else None,'canonical':{k:after.get(k) for k in ['blockNumber','timeStamp','to','gasUsed','isError']} if after else None,'action':'reject noncanonical' if h in rejected else 'correct' if before else 'add missing receipt'})
        source['differences']={d:{'receipts':actual.get(d,[0,0]),'aggregate':expected.get(d,[0,0])} for d in actual.keys()|expected.keys() if actual.get(d,[0,0])!=expected.get(d,[0,0])}
        source['daily_count_and_gas_match']=not source['differences']
        for k in ['excluded','excluded_gas']:source[k]={r:n for r,n in source[k].items() if n};assert all(n>=0 for n in source[k].values())
        source['methods']={k:v for k,v in source['methods'].items() if v['tx']};assert all(v['tx']>0 and v['gas']>0 for v in source['methods'].values())
        source['rejected_noncanonical']=[h for h in candidates if h in rejected]
        dest=R/'classified'/(a+'.jsonl.gz');backup=R/'classification-before-corrections'/dest.name;backup.parent.mkdir(exist_ok=True)
        if not backup.exists():backup.write_bytes(dest.read_bytes())
        assert hashlib.sha256(backup.read_bytes()).hexdigest()==source['classified_sha256'],'Changed completed classification input'
        found=set();tmp=dest.with_name(dest.name+'.partial')
        with gzip.open(backup,'rt') as inp,gzip.open(tmp,'wt',compresslevel=6) as out:
            for line in inp:
                r=json.loads(line);h=r['transaction_hash']
                if h in candidates:
                    assert r==accepted_before[h],('Changed original classification',h);found.add(h)
                else:out.write(line)
            for r in accepted_updates.values():out.write(json.dumps(r,separators=(',',':'))+'\n')
        assert found==set(accepted_before);tmp.replace(dest);source['classified_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
        print(json.dumps({'source':a,'changed_records':len(candidates),'remaining_differences':source['differences']}),flush=True)
    # Independently rebuild every accepted total and assert global hash uniqueness.
    daily=defaultdict(lambda:[0,0]);methods=Counter();products=Counter();seen=set()
    for source in report['sources']:
        path=R/'classified'/(source['address']+'.jsonl.gz');assert hashlib.sha256(path.read_bytes()).hexdigest()==source['classified_sha256']
        n=gas=0
        with gzip.open(path,'rt') as f:
            for line in f:
                r=json.loads(line);h=r['transaction_hash'];assert h not in seen;seen.add(h);n+=1;gas+=r['gas_used']
                key=(r['date'],r['product'],r['activity'],r['source_id']);v=daily[key];v[0]+=r['gas_used'];v[1]+=1
                products[r['product']]+=r['gas_used'];methods[(r['product'],r['selector'],r['rule'])]+=1
        assert [n,gas]==[source['accepted'],source['accepted_gas']]
    report.update({'complete':all(s['daily_count_and_gas_match'] for s in report['sources']),'source_transactions':sum(s['transactions'] for s in report['sources']),'accepted_transactions':len(seen),'products_gas':dict(products),'canonical_correction_pass':{'input_report_sha256':hashlib.sha256((R/'classification-verification-phase1.json').read_bytes()).hexdigest(),'decoder_sha256':hashlib.sha256((ROOT/'src/coverage_decode.py').read_bytes()).hexdigest(),'changed_records':len(changes),'all_accepted_totals_rebuilt':True,'all_accepted_hashes_unique':True}})
    save(R/'canonical-corrections.json',changes)
    save(R/'daily.json',[{'date':k[0],'product':k[1],'detail_bucket':k[2],'source_id':k[3],'gas_used':v[0],'tx_count':v[1]} for k,v in sorted(daily.items())])
    save(R/'accepted-methods.json',[{'product':p,'selector':s,'signature':m,'transactions':n} for (p,s,m),n in sorted(methods.items())])
    save(R/'classification-verification.json',report)
    print(json.dumps({'complete':report['complete'],'source_transactions':report['source_transactions'],'accepted_transactions':report['accepted_transactions']}))
    assert report['complete'],'Canonical corrections do not fully reconcile'

if __name__=='__main__':main()
