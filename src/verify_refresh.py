"""Resolve index conflicts against canonical RPC receipts; decode supplemental flows."""
from pathlib import Path
from urllib.parse import urlencode,urlparse,parse_qs
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from collections import defaultdict
import json,gzip,sys,re
from eth_abi import decode,encode
from acquire_refresh import R,OLD,fetch,save,counters

API='https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?'
def checked(types,raw):
 v=decode(types,raw);assert raw.startswith(encode(types,v)),'Noncanonical ABI';return v
def rpc(action,params,path):
 obj,_=fetch(API+urlencode({'module':'proxy','action':action,**params}),path)
 assert obj.get('result') is not None,(action,obj)
 return obj['result']
def canonical(h):
 r=rpc('eth_getTransactionReceipt',{'txhash':h},R/'canonical'/(h+'-receipt.json'))
 assert r['transactionHash'].lower()==h
 b=rpc('eth_getBlockByNumber',{'tag':r['blockNumber'],'boolean':'false'},R/'canonical'/(h+'-block.json'))
 assert r['blockHash']==b['hash'] and h in b['transactions']
 t=rpc('eth_getTransactionByHash',{'txhash':h},R/'canonical'/(h+'-transaction.json'))
 assert t['hash'].lower()==h and t['blockHash']==r['blockHash']
 return {'hash':h,'gasUsed':str(int(r['gasUsed'],16)),'blockNumber':str(int(r['blockNumber'],16)),
  'blockHash':r['blockHash'],'timeStamp':str(int(b['timestamp'],16)),'isError':str(1-int(r['status'],16)),
  'from':r['from'],'to':r['to'],'input':t['input'],'value':str(int(t['value'],16))}
def conflict_jobs():
 hashes=set()
 for p in (R/'receipt-manifests').glob('*.json'):
  j=json.loads(p.read_text());hashes.update(c['hash'] for c in j.get('unresolved_index_conflicts',[]))
 return sorted(hashes)
def supplement(s):
 sid=s['source_id'];rows={};pages=[]
 query=parse_qs(urlparse(s['url']).query)['q'][0]
 for offset in range(0,10000,100):
  if not s['tx_count']:break
  url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':query,'s':'id(desc)','limit':100,'offset':offset})
  obj,provenance=fetch(url,R/'raw-supplement'/f'{sid}-{offset}.json.gz')
  pages.append({**provenance,'rows':len(obj['data']),'pre_rows':obj['context'].get('pre_rows')})
  for r in obj['data']:
   if r['hash'] in rows:
    # Market-price enrichments can change between pages; compare chain facts only.
    keys=['hash','block_id','date','time','failed','sender','recipient','gas_used','input_hex','value']
    assert all(r.get(k)==rows[r['hash']].get(k) for k in keys),('Conflicting supplemental duplicate',r['hash'])
   rows[r['hash']]=r
  if offset+obj['context'].get('pre_rows',len(obj['data']))>=obj['context']['total_rows']:break
 else:raise AssertionError('Supplemental pagination budget reached')
 expected=defaultdict(lambda:[0,0]);actual=defaultdict(lambda:[0,0])
 for r in s.get('expected_daily',json.loads((R/s['file']).read_text())['data']):
  expected[r['date']][0]+=r['sum(gas_used)'];expected[r['date']][1]+=r['count()']
 for r in rows.values():actual[r['date']][0]+=r['gas_used'];actual[r['date']][1]+=1
 repaired_dates=[]
 if actual!=expected and s.get('repair_by_date'):
  # Different index replicas can shift an offset around a historical duplicate.
  # Recollect only the discrepant UTC dates, then require exact clean-index totals.
  affected=[d for d in actual.keys()|expected.keys() if actual.get(d,[0,0])!=expected.get(d,[0,0])]
  assert len(affected)<=8,'Daily repair budget reached'
  for d in sorted(affected):
   assert expected[d][1]<1000,'Daily repair page budget would be exceeded'
   day_query=re.sub(r'time\([^)]*\)',f'time({d}..{d})',query);day_rows={}
   for offset in range(0,1000,100):
    url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':day_query,'s':'id(desc)','limit':100,'offset':offset})
    obj,prov=fetch(url,R/'raw-supplement'/f'{sid}-repair-{d}-{offset}.json.gz')
    pages.append({**prov,'rows':len(obj['data']),'repair_date':d})
    for row in obj['data']:
     assert row['date']==d
     if row['hash'] in day_rows:
      assert all(row.get(k)==day_rows[row['hash']].get(k) for k in ['block_id','date','time','failed','sender','recipient','gas_used','input_hex','value'])
     day_rows[row['hash']]=row
    if offset+obj['context'].get('pre_rows',len(obj['data']))>=obj['context']['total_rows']:break
   else:raise AssertionError('Daily repair pagination incomplete')
   assert [sum(r['gas_used'] for r in day_rows.values()),len(day_rows)]==expected[d],('Daily repair mismatch',d)
   rows={h:r for h,r in rows.items() if r['date']!=d};rows.update(day_rows);repaired_dates.append(d)
  actual=defaultdict(lambda:[0,0])
  for r in rows.values():actual[r['date']][0]+=r['gas_used'];actual[r['date']][1]+=1
 assert actual==expected,('Supplement daily reconciliation',sid,len(rows),s['tx_count'])
 accepted=[];excluded=[]
 for r in rows.values():
  try:
   assert re.match('^'+s['pattern'].replace('_','.'),r['input_hex'])
   raw=bytes.fromhex(r['input_hex'][8:])
   if s['group']=='approvals':
    assert r['recipient'] in s['tokens'];args=checked(['address','uint256'],raw);assert args[0]==s['spender']
   else:
    assert r['recipient']==s['recipient']
    types=s['signature'].split('(',1)[1][:-1].split(',');args=checked(types,raw)
    if s['group']=='across':assert args[s['chain_word']]==s['domain']
    elif s['direction']=='burn':assert args[1]==s['domain']
    else:
     assert not r['failed'];message=args[0]
     assert int.from_bytes(message[4:8],'big')==s['domain'] and int.from_bytes(message[8:12],'big')==0
     version=int.from_bytes(message[:4],'big');assert version==int(s['version'][1:])-1
     offset=52 if version==0 else 76
     recipient='0x'+message[offset+12:offset+32].hex()
     assert recipient==('0xbd3fa81b58ba92a82136038b25adec7066af3155' if version==0 else '0x28b5a0e9c621a5badaa536219b3a228c8168cf5d')
  except Exception as exc:
   excluded.append({'hash':r['hash'],'gas_used':r['gas_used'],'reason':str(exc) or type(exc).__name__});continue
  accepted.append({'date':r['date'],'product':s['product'],'transaction_hash':r['hash'],'block_number':r['block_id'],
   'gas_used':r['gas_used'],'sender':r['sender'],'recipient':r['recipient'],'activity':s.get('detail_bucket',{'approvals':'token_approvals','cctp':'cctp_bridge','across':'across_bridge'}[s['group']]),
   'source_id':sid,'selector':'0x'+r['input_hex'][:8],'status':'failed' if r['failed'] else 'success'})
 save(R/'supplement-verified'/(sid+'.json'),accepted)
 return {'source_id':sid,'transactions':len(rows),'accepted':len(accepted),'gas_used':sum(r['gas_used'] for r in accepted),'raw_sources':pages,'excluded':excluded,'daily_count_and_gas_match':True,'documented_index_corrections':s.get('documented_index_corrections',[]),'recollected_dates':repaired_dates}
def main():
 mode=sys.argv[3];errors=[];results=[]
 if mode=='canonical':jobs=conflict_jobs();task=canonical
 elif mode=='supplement':
  jobs=[json.loads(p.read_text()) for p in (R/'aggregate-manifests').glob('*.json')]
  jobs=[s for s in jobs if s['group'] in ['approvals','cctp','across']];task=supplement
 else:raise ValueError(mode)
 with ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(task,s):s for s in jobs}
  for f in as_completed(futures):
   try:
    result=f.result();results.append(result)
    save(R/'verification-checkpoints'/mode/(str(result.get('source_id',result.get('hash')))+'.json'),result)
    if len(results)%10==0:print(json.dumps({'mode':mode,'completed':len(results),'total':len(jobs)}),flush=True)
   except Exception as exc:errors.append({'source':futures[f] if isinstance(futures[f],str) else futures[f]['source_id'],'error':str(exc)})
 save(R/(mode+'-verification.json'),{'results':results,'errors':errors,'request_counts':counters})
 print(json.dumps({'mode':mode,'completed':len(results),'errors':errors}),flush=True)
 assert not errors
if __name__=='__main__':main()
