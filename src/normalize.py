"""Assemble only explicitly accepted, disjoint source populations. See CONTRACTS."""
from pathlib import Path
from datetime import date,timedelta
from collections import defaultdict
import json,csv,hashlib,sys

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
BUCKETS=['operations','bridge','approvals','governance','defi','transfers','other']
DETAIL_CATEGORIES={
 'operations':'operations','batch_submission':'operations','settlement':'operations','commit_batch':'operations','verify_batch':'operations','execute_batch':'operations',
 'withdrawal_proofs':'bridge','bridge':'bridge','deposits':'bridge','withdrawals':'bridge','withdrawal_requests':'bridge','withdrawal_claims':'bridge','exclusive_wrappers':'bridge','emergency':'other','account_controls':'other','canonical_bridge':'bridge','dedicated_token_bridge':'bridge','cctp_bridge':'bridge','across_bridge':'bridge','deployments':'governance',
 'approvals':'approvals','token_approvals':'approvals','governance_token':'governance','governance':'governance',
 'v2_router':'defi','v3_router':'defi','mixed_router':'defi','liquidity':'defi','pool_creation':'defi','defi':'defi','transfers':'transfers','other':'other'
}
DETAIL_CATEGORIES.update({'wormhole_bridge':'bridge','dln_bridge':'bridge','lending':'defi','staking':'defi','token_activity':'governance'})
ALIASES={'plain-eth-transfers':'transfers','plain_eth_transfers':'transfers','universal_router':'mixed_router','v2_v3_router':'mixed_router'}
def main():
 config=json.loads((DATA/'inputs.json').read_text())
 assert config['accepted_for_publication'] or '--review' in sys.argv, 'Publication requires completion of inclusion review'
 start=date.fromisoformat(config['start_inclusive']);end=date.fromisoformat(config['end_exclusive'])
 dates=[(start+timedelta(days=i)).isoformat() for i in range((end-start).days)]
 proof=DATA/config['verification']['path']
 assert hashlib.sha256(proof.read_bytes()).hexdigest()==config['verification']['sha256'],'Verification certificate changed'
 review=json.loads(proof.read_text())
 assert review['complete'] and review['start_inclusive']==start.isoformat() and review['end_exclusive']==end.isoformat()
 product_names=json.loads((DATA/'products.json').read_text())
 products=list(product_names)
 assert review['products']==products,'Product coverage certificate mismatch'
 series={p:{d:{'date':d,'gas':0,'tx':0,'buckets':{},'details':{}} for d in dates} for p in products}
 records=[];seen=set()
 for entry in config['inputs']:
  assert hashlib.sha256((DATA/entry['path']).read_bytes()).hexdigest()==entry['sha256']==review['input_sha256'][entry['path']],'Unverified source population'
  source=json.loads((DATA/entry['path']).read_text())
  if isinstance(source,dict):source=source[entry.get('rows_key','rows')]
  assert isinstance(source,list)
  for raw in source:
   p=raw.get('product',entry.get('product'))
   if p is None and raw.get('project')=='eth-transfers':p='eth'
   bucket=raw.get('detail_bucket',raw.get('bucket'));detail=ALIASES.get(bucket,bucket)
   detail=entry.get('bucket_map',{}).get(detail,detail)
   assert detail in DETAIL_CATEGORIES,(entry['path'],detail)
   category=DETAIL_CATEGORIES[detail]
   gas=raw.get('gas_used',raw.get('execution_gas'));tx=raw.get('tx_count')
   assert isinstance(gas,int) and gas>=0 and isinstance(tx,int) and tx>=0
   assert (gas==0)==(tx==0),(p,raw)
   day=raw['date'];assert day in dates and p in products
   sid=raw.get('source_id',entry.get('source_id'))
   assert sid,'All measurements require a source reference'
   # An aggregate query can yield several token rows; retain that partition key.
   part=raw.get('token','')
   key=(p,day,sid,part,detail)
   assert key not in seen,('duplicate observation',key)
   seen.add(key)
   rec={'date':day,'product':p,'bucket':category,'activity':detail,'gas_used':gas,'tx_count':tx,'source_id':sid}
   if part:rec['token']=part
   records.append(rec)
   row=series[p][day];row['gas']+=gas;row['tx']+=tx;row['buckets'][category]=row['buckets'].get(category,0)+gas;row['details'][detail]=row['details'].get(detail,0)+gas
 for p in products:
  assert any(r['gas'] for r in series[p].values()),('Missing product population',p)
  for row in series[p].values():assert row['gas']==sum(row['buckets'].values())==sum(row['details'].values())
 for row in series['eth'].values():assert row['gas']==row['tx']*21000
 records.sort(key=lambda r:(r['date'],r['product'],r['activity'],r['source_id'],r.get('token','')))
 identity=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
 summary={'snapshot_id':identity,'publication_ready':config['accepted_for_publication'],'unit':'Ethereum L1 receipt gasUsed','chain_id':1,'start':dates[0],'end':dates[-1],'dates':dates,'product_order':products,'product_names':product_names,'locales':['en','es','pt-BR','fr','de','zh-CN','ja','ko'],'detail_categories':DETAIL_CATEGORIES,'series':{p:list(series[p].values()) for p in products}}
 if 'product_groups' in config:summary['product_groups']=config['product_groups']
 from aggregate_classification import publish_classification
 publish_classification(ROOT,summary)
 if 'scope_labels' in config:summary['scope_labels']=config['scope_labels']
 if (DATA/'receipt-exports.json').exists():summary['receipt_exports']=json.loads((DATA/'receipt-exports.json').read_text())
 coverage=json.loads((DATA/'lighter-coverage.json').read_text())
 assert coverage['start_inclusive']==start.isoformat() and coverage['end_exclusive']==end.isoformat()
 cv=coverage['populations'];summary['coverage_values']={'depositIncluded':cv['deposit']['included_parent_transactions'],'depositTotal':cv['deposit']['observed_parent_transactions'],'withdrawIncluded':cv['withdraw_claim']['included_parent_transactions'],'withdrawTotal':cv['withdraw_claim']['observed_parent_transactions']}
 DATA.mkdir(exist_ok=True)
 (DATA/'summary.json').write_text(json.dumps(summary,separators=(',',':'))+'\n')
 metadata={'snapshot_id':identity,'start_inclusive':start.isoformat()+'T00:00:00Z','end_exclusive':end.isoformat()+'T00:00:00Z','chain_id':1,'measurement':'Ethereum transaction receipt gasUsed; blob gas excluded','scope':'Conservative direct-attribution baseline; not exhaustive product totals','zero_policy':'Zero within the completed queried populations is a measured absence; excluded/unresolved activity is not represented as zero.','overlap_policy':'Product cohorts use disjoint query populations. ETH-transfer context can overlap incidental product-related ETH movements; comparison rows must not be summed. Table-only group summaries overlap their members and are absent from this dataset.','verification':'See query-manifest.json and evidence archive for per-population completeness, independent checks and reconciliations.'}
 public=ROOT/'dist/data';public.mkdir(parents=True,exist_ok=True)
 (public/'dataset.json').write_text(json.dumps({'metadata':metadata,'records':records},separators=(',',':'))+'\n')
 combined=defaultdict(lambda:[0,0])
 for r in records:
  v=combined[(r['date'],r['product'],r['activity'])];v[0]+=r['gas_used'];v[1]+=r['tx_count']
 with (public/'l1-gas-daily.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['date_utc','product','activity','execution_gas_used','transaction_count'])
  for k,v in sorted(combined.items()):w.writerow([*k,*v])
 (DATA/'analysis.json').write_text(json.dumps({p:{str(n):{'gas':sum(r['gas'] for r in list(series[p].values())[-n:]),'transactions':sum(r['tx'] for r in list(series[p].values())[-n:]),'average_gas_per_day':sum(r['gas'] for r in list(series[p].values())[-n:])/n} for n in [7,30,len(dates)]} for p in products},indent=2)+'\n')
 print(json.dumps({'records':len(records),'snapshot':identity,'products':len(products),'days':len(dates)}))
if __name__=='__main__':main()
