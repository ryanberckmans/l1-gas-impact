"""Bind the refreshed snapshot to reviewed evidence; preserve frozen baseline lineage."""
from pathlib import Path
from datetime import date,timedelta,datetime,timezone
from collections import defaultdict
import json,gzip,csv,io,hashlib,subprocess,zipfile
from acquire_refresh import R,OLD,ROOT,save,START,DELTA,END

BASELINE='8bf77555d837e9c7e92682ddfba0ce32341d3a70'
DATA=ROOT/'data';OUT=ROOT/'dist/data'
def historic(path):return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 checks={n:json.loads((R/(n+'.json')).read_text()) for n in ['aggregates-run','receipts-run','canonical-verification','supplement-verification','sample-verification','daily-reconciliation']}
 assert all(not checks[n]['errors'] for n in checks if n!='daily-reconciliation')
 assert not checks['daily-reconciliation']['mismatches']
 sources=[json.loads(p.read_text()) for p in (R/'aggregate-manifests').glob('*.json')]
 sources=[s for s in sources if s['product']!='solana']
 expected={s['source_id'] for s in json.loads((R/'aggregate-catalog.json').read_text())+json.loads((R/'new-catalog.json').read_text()) if s['product']!='solana'}
 assert expected=={s['source_id'] for s in sources} and all(s['complete'] for s in sources)
 inputs={name:[x for x in json.loads(historic('data/inputs/'+name+'.json')) if START<=x['date']<DELTA] for name in ['eth','uniswap','lighter','rollups','additional','expanded']}
 templates={x.get('source_id'):x for rows in inputs.values() for x in rows if x.get('source_id')}
 added=[]
 for s in sources:
  if s['group']=='eth' or (s['group']=='uniswap' and s['included']):
   for row in json.loads((R/s['file']).read_text())['data']:
    if s['group']=='eth':inputs['eth'].append({'date':row['date'],'project':'eth-transfers','bucket':'plain-eth-transfers','tx_count':row['count()'],'execution_gas':row['sum(gas_used)']})
    else:inputs['uniswap'].append({'date':row['date'],'product':'uniswap','source_id':s['source_id'],'bucket':templates[s['source_id']]['bucket'],'gas_used':row['sum(gas_used)'],'tx_count':row['count()']})
 core=json.loads((R/'accepted-core.json').read_text())
 supplemental=[]
 for p in (R/'supplement-verified').glob('*.json'):
  supplemental.extend(x for x in json.loads(p.read_text()) if x['product']!='solana')
 # Supplemental queries are disjoint by recipient, selector and chain/spender.
 all_rows=core+supplemental;assert len(all_rows)==len({r['transaction_hash'] for r in all_rows})
 supplemental_hashes={r['transaction_hash'] for r in supplemental}
 groups=defaultdict(lambda:[0,0])
 for r in all_rows:
  p=r['product'];name='lighter' if p=='lighter' else 'uniswap' if p=='uniswap' else 'expanded' if p in ['worldchain','unichain','op','ink'] else 'rollups'
  if r['transaction_hash'] in supplemental_hashes and name not in ['expanded']:name='additional'
  template=templates.get(r['source_id'],{});bucket=template.get('detail_bucket',template.get('bucket',r['activity']))
  key=(name,r['date'],p,r['source_id'],bucket);groups[key][0]+=r['gas_used'];groups[key][1]+=1
 for (name,day,p,sid,b),v in groups.items():inputs[name].append({'date':day,'product':p,'source_id':sid,'bucket':b,'gas_used':v[0],'tx_count':v[1]})
 config={'accepted_for_publication':True,'start_inclusive':START,'end_exclusive':END,'baseline_revision':BASELINE,'inputs':[]}
 for name,rows in inputs.items():
  rows.sort(key=lambda r:(r['date'],r.get('source_id',''),r.get('bucket',''),r.get('token','')))
  path=DATA/'inputs'/(name+'.json');save(path,rows)
  entry={'path':'inputs/'+name+'.json','sha256':digest(path)}
  if name=='eth':entry['source_id']='blockchair-plain-eth-transfer-benchmark'
  config['inputs'].append(entry)
 certificate={'complete':True,'start_inclusive':START,'end_exclusive':END,'products':list(json.loads((DATA/'products.json').read_text())),
  'baseline_revision':BASELINE,'overlap':'Validated historical observations retained from March 28 through September 14; no extrapolation.',
  'current_aggregate_queries':len(sources),'canonical_conflict_receipts':len(checks['canonical-verification']['results']),
  'daily_reconciliations':len(checks['daily-reconciliation']['sources']),'raw_supplemental_populations':len([x for x in checks['supplement-verification']['results'] if 'solana' not in x['source_id']]),
  'verification_sha256':{n:digest(R/(n+'.json')) for n in checks},'input_sha256':{x['path']:x['sha256'] for x in config['inputs']}}
 save(DATA/'refresh-verification.json',certificate);config['verification']={'path':'refresh-verification.json','sha256':digest(DATA/'refresh-verification.json')};save(DATA/'inputs.json',config)
 receipts={};download_meta={}
 for p in certificate['products']:
  if p in ['eth','uniswap']:continue
  raw=gzip.decompress(historic('dist/data/receipts-'+p+'.csv.gz')).decode();rows=[]
  for r in csv.DictReader(io.StringIO(raw)):
   if not START<=r['date']<DELTA:continue
   bucket=r.get('activity',r.get('bucket'));sid=r.get('source_id','lighter-receipts-'+bucket)
   status=r.get('status','failed' if r.get('failed')=='True' else 'success');status='success' if status=='1' else 'failed' if status=='0' else status
   rows.append({'date':r['date'],'product':p,'transaction_hash':r.get('transaction_hash',r.get('hash')),'block_number':int(r['block_number']),
    'gas_used':int(r['gas_used']),'sender':r.get('sender',''),'recipient':r.get('recipient',''),'activity':bucket,'source_id':sid,'selector':r['selector'],'status':status})
  rows.extend(r for r in core if r['product']==p)
  if p in ['worldchain','unichain','op','ink']:rows.extend(r for r in supplemental if r['product']==p)
  assert len(rows)==len({r['transaction_hash'] for r in rows})
  rows.sort(key=lambda r:(r['date'],r['block_number'],r['transaction_hash']));receipts[p]=rows
  stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  path=OUT/('receipts-'+p+'.csv.gz');path.write_bytes(gzip.compress(stream.getvalue().encode(),mtime=0))
  download_meta[p]={'url':'/data/'+path.name,'sha256':digest(path),'bytes':path.stat().st_size,'transactions':len(rows),'gas_used':sum(r['gas_used'] for r in rows),
   'scope':'All measured core and supplemental receipts.' if p in ['worldchain','unichain','op','ink'] else 'Core contract receipts. Separate token approval and shared-bridge query cohorts remain in dataset.json.',
   'source_ids':sorted({r['source_id'] for r in rows})}
 coverage={};included={r['transaction_hash'] for r in receipts['lighter']}
 for name in ['deposit','withdraw_claim']:
  old=json.loads(gzip.decompress((OLD/'lighter'/('all-'+name+'-logs.json.gz')).read_bytes()));old=old.get('result',old) if isinstance(old,dict) else old
  new=json.loads((R/'lighter-events'/(name+'-logs.json')).read_text());parents=set()
  for r in old+new:
   ts=r['timeStamp'];ts=int(ts,16) if str(ts).startswith('0x') else int(ts)
   day=datetime.fromtimestamp(ts,timezone.utc).date().isoformat()
   if START<=day<END:parents.add(r['transactionHash'])
  coverage[name]={'observed_parent_transactions':len(parents),'included_parent_transactions':len(parents&included),'included_parent_percent':len(parents&included)/len(parents)*100}
 save(DATA/'lighter-coverage.json',{'start_inclusive':START,'end_exclusive':END,'unit':'Parent transaction coverage, not gas coverage','populations':coverage})
 save(R/'staged-receipt-downloads.json',download_meta)
 print(json.dumps({'inputs':sum(map(len,inputs.values())),'receipt_exports':{p:len(v) for p,v in receipts.items()},'coverage':coverage}))
if __name__=='__main__':main()
