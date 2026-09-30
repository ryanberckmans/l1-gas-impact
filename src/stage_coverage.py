"""Publish only reconciled receipt cohorts; preserve release-6 baseline lineage.

Synthetic comparison rows never enter this stage. Receipt exports are checked
against independently assembled input populations and split at 200k records.
"""
from pathlib import Path
from collections import defaultdict,Counter
import json,gzip,csv,io,hashlib,subprocess
from acquire_refresh import R,OLD,ROOT,save,START,END
BASELINE='aca14fde12cca3f2830d85c2b5d10293aed97ace'
DATA=ROOT/'data';OUT=ROOT/'dist/data';REPLACED={'cctp_bridge','across_bridge'}
def historic(p):return subprocess.check_output(['git','show',BASELINE+':'+p],cwd=ROOT)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bucket(r):return r.get('detail_bucket',r.get('bucket',r.get('activity')))
def main():
 report=json.loads((R/'classification-verification.json').read_text())
 assert report['complete'] and not report['missing'],'Source reconciliation is incomplete'
 assert report['start_inclusive']==START and report['end_exclusive']==END
 base_config=json.loads(historic('data/inputs.json'));base_proof=json.loads(historic('data/'+base_config['verification']['path']))
 assert base_proof['complete']
 profile=json.loads((DATA/'coverage-products.json').read_text());base_names=json.loads(historic('data/products.json'))
 raw=json.loads((R/'daily.json').read_text());included=set(base_names)|({r['product'] for r in raw}&set(profile))
 new=sorted(included-set(base_names),key=lambda p:(-report['products_gas'][p],p));names={**base_names,**{p:profile[p]['name'] for p in new}}
 assert {'solana','hyperliquid','bsc','polygon','aave','lido','curve','ethena','sky','compound','morpho','etherfi'}<=included
 assert not any(p.startswith('all_') for p in included)
 inputs={};removed=[]
 for e in base_config['inputs']:
  b=historic('data/'+e['path']);assert hashlib.sha256(b).hexdigest()==e['sha256']==base_proof['input_sha256'][e['path']]
  rows=json.loads(b);inputs[e['path']]=[r for r in rows if bucket(r) not in REPLACED];removed.extend(r for r in rows if bucket(r) in REPLACED)
 inputs['inputs/coverage.json']=[r for r in raw if r['product'] in included]
 old_totals=Counter();new_totals=Counter()
 for r in removed:old_totals[(r['product'],bucket(r))]+=r['gas_used']
 for r in inputs['inputs/coverage.json']:
  if bucket(r) in REPLACED:new_totals[(r['product'],bucket(r))]+=r['gas_used']
 replacement=[{'product':p,'activity':a,'previous_gas':v,'replacement_gas':new_totals[(p,a)],'difference':new_totals[(p,a)]-v} for (p,a),v in sorted(old_totals.items())]
 integration={'baseline_revision':BASELINE,'shared_bridge_replacement':replacement,'research_only_products':sorted({r['product'] for r in raw}-included),'view_only_rows_absent':True}
 save(R/'integration-verification.json',integration)
 # A stricter reviewed scope can legitimately decrease a lower bound. Require
 # an exact transaction-level explanation for every reduced legacy day.
 review=json.loads((R/'bridge-replacement-review.json').read_text())
 reviewed={(x['product'],x['activity'],x['date']):x for x in review['differences']}
 old_daily=defaultdict(lambda:[0,0]);new_daily=defaultdict(lambda:[0,0]);excluded_daily=defaultdict(lambda:[0,0])
 for r in removed:
  v=old_daily[(r['product'],bucket(r),r['date'])];v[0]+=r['gas_used'];v[1]+=r['tx_count']
 for r in inputs['inputs/coverage.json']:
  if bucket(r) in REPLACED:
   v=new_daily[(r['product'],bucket(r),r['date'])];v[0]+=r['gas_used'];v[1]+=r['tx_count']
 for r in review['excluded_by_full_decoding']:
  v=excluded_daily[(r['product'],r['activity'],r['date'])];v[0]+=r['gas_used'];v[1]+=1
 explained=[]
 for k,old in old_daily.items():
  new=new_daily[k]
  if new[0]>=old[0]:continue
  check=reviewed[k];excluded=excluded_daily[k]
  assert check['canonical_same_predicate']==old,'Legacy predicate population differs from canonical receipts'
  assert [old[0]-excluded[0],old[1]-excluded[1]]==new,('Unexplained bridge reduction',k,old,new,excluded)
  explained.append({'product':k[0],'activity':k[1],'date':k[2],'previous':old,'current':new,'excluded_receipts':excluded[1],'excluded_gas':excluded[0]})
 integration['explained_legacy_reductions']=explained
 integration['reason']='Full ABI decoding and verified incoming TokenMessenger recipients exclude deprecated or unreviewed methods and unreviewed arbitrary message recipients previously matched by aggregate predicates.'
 save(R/'integration-verification.json',integration)
 # Input acceptance is written last, after all exports reconcile.
 save(DATA/'products.json',names)
 entries=[]
 for path,rows in inputs.items():
  save(DATA/path,rows);e={'path':path,'sha256':digest(DATA/path)}
  if path=='inputs/eth.json':e['source_id']='blockchair-plain-eth-transfer-benchmark'
  entries.append(e)
 fields=['date','product','transaction_hash','block_number','gas_used','activity','source_id','selector','status']
 receipts_dir=R/'public-receipt-work';receipts_dir.mkdir(exist_ok=True)
 writers={};handles={};seen=set();received=defaultdict(lambda:defaultdict(lambda:[0,0]));counts=Counter()
 def emit(row):
  p=row['product'];h=row.get('transaction_hash',row.get('hash'));assert p in names and h not in seen,('Overlapping receipt',p,h);seen.add(h)
  row={**row,'transaction_hash':h};g=int(row['gas_used']);date=row['date'];assert START<=date<END and g>=21000
  if p not in writers:
   f=(receipts_dir/(p+'.csv')).open('w',newline='');w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();writers[p]=w;handles[p]=f
  writers[p].writerow(row);received[p][date][0]+=g;received[p][date][1]+=1;counts[p]+=1
 expected=defaultdict(lambda:defaultdict(lambda:[0,0]));paths=defaultdict(list)
 for p in base_names:
  if p in ['eth','uniswap']:continue
  path='inputs/'+('lighter' if p=='lighter' else 'expanded' if p in ['worldchain','unichain','op','ink'] else 'rollups')+'.json';paths[p].append(path)
  for r in inputs[path]:
   if r.get('product')==p:expected[p][r['date']][0]+=r['gas_used'];expected[p][r['date']][1]+=r['tx_count']
  with gzip.GzipFile(fileobj=io.BytesIO(historic('dist/data/receipts-'+p+'.csv.gz'))) as f:
   for row in csv.DictReader(io.TextIOWrapper(f)):
    if bucket(row) not in REPLACED:emit(row)
 for r in inputs['inputs/coverage.json']:
  p=r['product'];expected[p][r['date']][0]+=r['gas_used'];expected[p][r['date']][1]+=r['tx_count']
 for p in {r['product'] for r in inputs['inputs/coverage.json']}:paths[p].append('inputs/coverage.json')
 for f in sorted((R/'classified').glob('*.jsonl.gz')):
  with gzip.open(f,'rt') as stream:
   for line in stream:
    r=json.loads(line)
    if r['product'] in included:emit(r)
 for f in handles.values():f.close()
 assert {p:dict(v) for p,v in received.items()}=={p:dict(v) for p,v in expected.items()},'Published receipt reconciliation failed'
 downloads={};MAX_ROWS=200000
 for p in names:
  if p not in counts:continue
  files=[];out=None;w=None;file_rows=0
  def finish():
   if out:
    out.close();assert target.stat().st_size<20*1024*1024
    files.append({'url':'/data/'+target.name,'sha256':digest(target),'bytes':target.stat().st_size,'transactions':file_rows})
  with (receipts_dir/(p+'.csv')).open() as source:
   for i,row in enumerate(csv.DictReader(source)):
    if i%MAX_ROWS==0:
     finish();part=i//MAX_ROWS+1
     target=OUT/(f'receipts-{p}.csv.gz' if counts[p]<=MAX_ROWS else f'receipts-{p}-{part}.csv.gz')
     out=gzip.open(target,'wt',newline='',compresslevel=9);w=csv.DictWriter(out,fieldnames=fields);w.writeheader();file_rows=0
    w.writerow(row);file_rows+=1
   finish()
  downloads[p]={'files':files,'transactions':counts[p],'gas_used':sum(v[0] for v in received[p].values()),'input_paths':paths[p],
   'scope':'All measured expanded receipt cohorts plus previously published core receipts, where applicable. Baseline supplemental approvals for Lighter, Base, Arbitrum One and Robinhood remain in the structured dataset, outside these receipt exports.'}
 # Retire superseded split or single-file downloads, after replacement is complete.
 keep={Path(f['url']).name for p in downloads.values() for f in p['files']}
 for path in OUT.glob('receipts-*.csv.gz'):
  if path.name not in keep:path.unlink()
 save(DATA/'receipt-exports.json',downloads)
 proof={'complete':True,'start_inclusive':START,'end_exclusive':END,'products':list(names),'baseline_revision':BASELINE,
  'baseline_certificate_sha256':base_config['verification']['sha256'],'catalog_sha256':digest(R/'catalog.json'),
  'classification_sha256':digest(R/'classification-verification.json'),'classification_rules_sha256':digest(ROOT/'src/coverage_decode.py'),
  'source_transactions':report['source_transactions'],'accepted_expansion_transactions':sum(s['accepted'] for s in report['sources']),
  'reconciled_source_accounts':len(report['sources']),'exported_receipts':dict(counts),'hashes_unique_across_receipt_exports':True,
  'replaced_shared_populations':replacement,'research_only_products':integration['research_only_products'],
  'input_sha256':{e['path']:e['sha256'] for e in entries}}
 save(DATA/'coverage-verification.json',proof)
 config={'accepted_for_publication':True,'start_inclusive':START,'end_exclusive':END,'baseline_revision':BASELINE,'inputs':entries,
  'product_groups':{p:profile[p]['group'] for p in names if p in profile},'scope_labels':{p:profile[p]['scope_label'] for p in names if p in profile and 'scope_label' in profile[p]},'verification':{'path':'coverage-verification.json','sha256':digest(DATA/'coverage-verification.json')}}
 save(DATA/'inputs.json',config)
 print(json.dumps({'products':len(names),'new_products':new,'receipt_counts':dict(counts),'research_only':integration['research_only_products']}))
if __name__=='__main__':main()
