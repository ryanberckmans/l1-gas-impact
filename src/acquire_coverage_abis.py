"""Bounded ABI/source retrieval for verified deployment addresses, at most two hops."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlencode
import json
import acquire_refresh as A
BASE='https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?'
def collect(s):
 address=s['address'];out=[];seen=set()
 for hop in range(2):
  if address in seen:break
  seen.add(address)
  obj,provenance=A.fetch(BASE+urlencode({'module':'contract','action':'getsourcecode','address':address}),A.R/'contract-source'/(address+'.json.gz'))
  assert isinstance(obj['result'],list) and len(obj['result'])==1
  source=obj['result'][0];abi=json.loads(source['ABI']);assert isinstance(abi,list)
  out.append({'address':address,'contract_name':source.get('ContractName'),'abi':abi,'provenance':provenance})
  implementation=source.get('Implementation','')
  if not implementation or int(implementation,16)==0:break
  address=implementation.lower()
 A.save(A.R/'verified-abis'/(s['address']+'.json'),out)
 return {'address':s['address'],'abi_sources':len(out)}
def main():
 jobs=[s for s in json.loads((A.R/'catalog.json').read_text()) if s['roles'][0]['kind'] in ['aave','compound','morpho','lido','polygon','curve','ethena','sky','etherfi','cctp-fee','across']]
 results=[];errors=[]
 with ThreadPoolExecutor(max_workers=2) as pool:
  fs={pool.submit(collect,s):s for s in jobs}
  for f in as_completed(fs):
   try:results.append(f.result())
   except Exception as e:errors.append({'address':fs[f]['address'],'error':str(e)})
 A.save(A.R/'abi-run.json',{'results':results,'errors':errors,'request_counts':A.counters});print(json.dumps({'complete':len(results),'errors':errors}),flush=True)
if __name__=='__main__':main()
