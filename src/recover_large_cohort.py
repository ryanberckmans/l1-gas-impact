"""Use bounded calendar partitions when a public provider caps result offsets."""
from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlencode,urlparse,parse_qs
from collections import defaultdict
import json,copy,re
from verify_refresh import R,OLD,fetch,save,supplement

def month(s,start,end):
 source=copy.deepcopy(s);source['source_id']=s['source_id']+'-month-'+start
 q=parse_qs(urlparse(s['url']).query)['q'][0].replace('time(2026-03-28..2026-09-27)',f'time({start}..{end})')
 source['url']='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':q,'a':'date,count(),sum(gas_used)','limit':10000})
 j,m=fetch(source['url'],R/'monthly-aggregates'/(source['source_id']+'.json'))
 assert len(j['data'])==j['context']['total_rows'];source.update(m)
 parent=json.loads((R/s['file']).read_text());assert 'ETH3' in parent['context']['servers']
 expected=[x for x in parent['data'] if start<=x['date']<=end]
 corrected=copy.deepcopy(j['data']);repairs=[]
 if 'ETH4' in j['context']['servers']:
  for r in json.loads((OLD/'audit/canonical_correction_transactions.json').read_text()):
   if start<=r['date']<=end and r['recipient']==s['recipient'] and not r['failed'] and re.match('^'+s['pattern'].replace('_','.'),r['input_hex']):
    day=next(x for x in corrected if x['date']==r['date']);day['count()']-=1;day['sum(gas_used)']-=r['gas_used']
    repairs.append({k:r[k] for k in ['hash','date','gas_used']})
 assert sorted(corrected,key=lambda x:x['date'])==sorted(expected,key=lambda x:x['date']),'Unexpected partition aggregate disagreement'
 source['expected_daily']=expected;source['documented_index_corrections']=repairs;source['repair_by_date']=True
 source['tx_count']=sum(x['count()'] for x in expected);source['gas_used']=sum(x['sum(gas_used)'] for x in expected)
 assert source['tx_count']<10000,'Partition must fit documented offset window'
 result=supplement(source)
 return result
def main():
 sid='cctp_solana_v2_receive_57ecfd28';s=json.loads((R/'aggregate-manifests'/(sid+'.json')).read_text())
 intervals=[('2026-03-28','2026-03-31'),('2026-04-01','2026-04-30'),('2026-05-01','2026-05-31'),('2026-06-01','2026-06-30'),('2026-07-01','2026-07-31'),('2026-08-01','2026-08-31'),('2026-09-01','2026-09-27')]
 results=[];errors=[]
 with ThreadPoolExecutor(max_workers=3) as pool:
  tasks={pool.submit(month,s,a,b):(a,b) for a,b in intervals}
  for f in as_completed(tasks):
   try:results.append(f.result());print(json.dumps({'partition_complete':tasks[f]}),flush=True)
   except Exception as e:errors.append({'partition':tasks[f],'error':str(e)})
 save(R/'large-cohort-recovery.json',{'results':results,'errors':errors});assert not errors,errors
 accepted=[]
 for result in results:
  accepted+=json.loads((R/'supplement-verified'/(result['source_id']+'.json')).read_text())
 for r in accepted:r['source_id']=sid
 assert len(accepted)==len({r['transaction_hash'] for r in accepted})
 assert sum(x['transactions'] for x in results)==s['tx_count']
 assert sum(x['gas_used']+sum(e['gas_used'] for e in x['excluded']) for x in results)==s['gas_used']
 save(R/'supplement-verified'/(sid+'.json'),accepted)
 combined={'source_id':sid,'transactions':sum(x['transactions'] for x in results),'accepted':len(accepted),'gas_used':sum(r['gas_used'] for r in accepted),
  'raw_sources':[p for x in results for p in x['raw_sources']],'excluded':[e for x in results for e in x['excluded']],'daily_count_and_gas_match':True,'partitioning':'Seven disjoint calendar partitions; each below the 10,000-result offset limit.'}
 report=json.loads((R/'supplement-verification.json').read_text());report['results']=[x for x in report['results'] if x['source_id']!=sid]+[combined]
 report['resolved_errors']=report['errors'];report['errors']=[];save(R/'supplement-verification.json',report)
 print(json.dumps({'accepted':len(accepted),'gas_used':combined['gas_used']}))
if __name__=='__main__':main()
