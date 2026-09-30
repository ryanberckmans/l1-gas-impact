"""Separate research collection. Nothing from this directory enters the app."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor,as_completed
import json,sys
import acquire_refresh as A
R=A.R
def main():
 A.DELTA=A.START
 ts=int(datetime.fromisoformat(A.START).replace(tzinfo=timezone.utc).timestamp())
 u='https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?'+urlencode({'module':'block','action':'getblocknobytime','timestamp':ts,'closest':'after'})
 j,_=A.fetch(u,R/'start-boundary.json');A.LOW_BLOCK=int(j['result'])
 high=A.boundary()
 accounts=[{'address':a,'name':n,'product':'solana'} for a,n in [
  ('0x3ee18b2214aff97000d974cf647e7c347e8fa585','Wormhole token bridge'),
  ('0xef4fb24ad0916217251f553c0596f8edc630eb66','DLN source'),
  ('0xe7351fd770a37282b91d153ee690b63579d6dd7f','DLN destination')]]
 A.save(R/'account-catalog.json',accounts)
 agg=[]
 for s in accounts:
  url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':f'time({A.START}..2026-09-27),recipient({s["address"]})','a':'date,count(),sum(gas_used)','limit':10000})
  agg.append({**s,'source_id':'solana-account-'+s['address'],'group':'crosscheck','url':url})
 for s in json.loads((A.ROOT/'data/cohort-sources.json').read_text())['across']['series']:
  if s['product']!='base':continue
  pattern=s['pattern'][:-64]+f'{34268394551451:064x}'
  query=f'time({A.START}..2026-09-27),recipient({s["recipient"]}),input_hex(^{pattern})'
  url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':query,'a':'date,count(),sum(gas_used)','limit':10000})
  agg.append({**s,'product':'solana','group':'across','source_id':s['source_id'].replace('base','solana'),'domain':34268394551451,'pattern':pattern,'url':url})
 A.save(R/'aggregate-catalog.json',agg)
 errors=[]
 with ThreadPoolExecutor(max_workers=3) as pool:
  tasks=[pool.submit(A.receipts,s,high) for s in accounts]+[pool.submit(A.aggregate,s) for s in agg]
  for f in as_completed(tasks):
   try:f.result()
   except Exception as e:errors.append(str(e))
 A.save(R/'acquisition.json',{'errors':errors,'start_block':A.LOW_BLOCK,'end_block':high,'request_counts':A.counters})
 print(json.dumps({'errors':errors}));assert not errors
if __name__=='__main__':main()
