"""Independent receipt samples for current aggregate-only cohorts."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlencode,urlparse,parse_qs
import json
from verify_refresh import R,fetch,save,canonical

def sample(s):
 query=parse_qs(urlparse(s['url']).query)['q'][0]
 url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':query,'s':'id(desc)','limit':1})
 obj,proof=fetch(url,R/'samples'/(s['source_id']+'.json'))
 if not obj['data']:return {'source_id':s['source_id'],'empty_population':True}
 r=obj['data'][0];c=canonical(r['hash'])
 assert int(c['gasUsed'])==r['gas_used'] and int(c['blockNumber'])==r['block_id']
 assert c['to']==r['recipient'] and c['from']==r['sender']
 if s['group']=='eth':assert r['gas_used']==21000 and int(r['value'])>0 and r['input_hex']=='' and not r['failed']
 return {'source_id':s['source_id'],'hash':r['hash'],'gas_used':r['gas_used'],'block_number':r['block_id'],'canonical_receipt_match':True,'raw_query':proof}
def main():
 all_sources=[json.loads(p.read_text()) for p in (R/'aggregate-manifests').glob('*.json')]
 jobs=[s for s in all_sources if s['group'] in ['eth','uniswap'] and s['tx_count']]
 used=set()
 for s in all_sources:
  key=(s['group'],s.get('version'),s.get('direction'))
  if s['group'] in ['approvals','cctp','across'] and s['tx_count'] and key not in used:
   jobs.append(s);used.add(key)
 results=[];errors=[]
 with ThreadPoolExecutor(max_workers=3) as pool:
  for f in as_completed([pool.submit(sample,s) for s in jobs]):
   try:results.append(f.result())
   except Exception as e:errors.append(str(e))
 save(R/'sample-verification.json',{'results':results,'errors':errors,'scope':'At least one independently checked transaction per nonempty Uniswap aggregate and per supplemental protocol/version/direction; ETH-transfer predicate also checked. Not a full independent recount.'})
 print(json.dumps({'samples':len(results),'errors':errors}));assert not errors
if __name__=='__main__':main()
