"""Explain changes from the prior aggregate predicates to full ABI classification."""
from collections import defaultdict
import json,gzip,re,subprocess
from acquire_refresh import R,OLD,ROOT,save,START,END
from classify_coverage import day
import coverage_decode as C

def main():
    cohorts=json.loads((ROOT/'data/cohort-sources.json').read_text());catalog={s['address']:s for s in json.loads((R/'catalog.json').read_text())}
    decls,all_decl=C.declarations(R)
    for s in cohorts['across']['series']:
        sel,item=C.parse(s['signature']);C.METHODS[sel]=item
    filters=defaultdict(list)
    for group in ['cctp','across']:
        for s in cohorts[group]['series']:
            if s['product'] in ['base','arbitrum']:filters[s['recipient']].append((s,re.compile('^'+s['pattern'].replace('_','.')),group+'_bridge'))
    old=defaultdict(lambda:[0,0]);same_predicate=defaultdict(lambda:[0,0]);accepted=defaultdict(lambda:[0,0]);excluded=[];added=[]
    for r in json.loads(subprocess.check_output(['git','show','aca14fde12cca3f2830d85c2b5d10293aed97ace:data/inputs/additional.json'],cwd=ROOT)):
        if r['bucket'] in ['cctp_bridge','across_bridge']:
            v=old[(r['product'],r['bucket'],r['date'])];v[0]+=r['gas_used'];v[1]+=r['tx_count']
    repairs={}
    for f in [OLD.parents[1]/'solana/canonical-verification.json',OLD.parents[1]/'refresh/canonical-verification.json',R/'canonical-run.json',R/'canonical-extra.json']:
        if f.exists():repairs.update({r['hash']:r for r in json.loads(f.read_text())['results']})
    extra=json.loads((R/'canonical-extra.json').read_text());rejected={r['hash'] for r in extra.get('rejected_noncanonical',[])}
    for address,patterns in filters.items():
        selected={}
        with gzip.open(R/'classified'/(address+'.jsonl.gz'),'rt') as f:
            for line in f:
                r=json.loads(line)
                if r['product'] in ['base','arbitrum']:selected[r['transaction_hash']]=r
        population={}
        with gzip.open(R/'ledgers'/(address+'.jsonl.gz'),'rt') as f:
            for line in f:
                r=json.loads(line);h=r['hash']
                if h in rejected:continue
                r.update(repairs.get(h,{}))
                if not START<=day(r)<END or (r.get('to') or '').lower()!=address:continue
                matches=[(s,g) for s,pattern,g in patterns if (s['direction']!='receive' or r['isError']=='0') and pattern.match(r['input'][2:])]
                assert len(matches)<=1,'Overlapping old predicates'
                if matches:
                    s,g=matches[0];k=(s['product'],g,day(r));v=same_predicate[k];v[0]+=int(r['gasUsed']);v[1]+=1
                    if h not in selected:
                        try:C.select(r,catalog[address],decls,all_decl);reason='Different decoded product'
                        except Exception as e:reason=str(e) or type(e).__name__
                        excluded.append({'hash':h,'date':day(r),'product':s['product'],'activity':g,'gas_used':int(r['gasUsed']),'reason':reason,'source_id':s['source_id']})
                elif h in selected:added.append(selected[h])
                population[h]=True
        for h,r in selected.items():
            v=accepted[(r['product'],r['activity'],r['date'])];v[0]+=r['gas_used'];v[1]+=1
            if h not in population:added.append(r)
    differences=[{'product':k[0],'activity':k[1],'date':k[2],'prior_aggregate':old.get(k,[0,0]),'canonical_same_predicate':same_predicate.get(k,[0,0]),'new_decoded':accepted.get(k,[0,0])} for k in old.keys()|same_predicate.keys()|accepted.keys() if old.get(k,[0,0])!=accepted.get(k,[0,0])]
    # Exact signed decomposition; remaining historical index differences stay explicit.
    result={'differences':sorted(differences,key=lambda x:(x['product'],x['activity'],x['date'])),'excluded_by_full_decoding':excluded,'added_by_broader_reviewed_methods_or_canonical_recovery':added,'prior_aggregate_predicate_differences':[x for x in differences if x['prior_aggregate']!=x['canonical_same_predicate']]}
    save(R/'bridge-replacement-review.json',result)
    print(json.dumps({'changed_days':len(differences),'excluded':len(excluded),'added':len(added),'prior_predicate_mismatches':len(result['prior_aggregate_predicate_differences'])}))

if __name__=='__main__':main()
