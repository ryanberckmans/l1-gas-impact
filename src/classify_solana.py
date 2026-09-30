"""Ethereum receipt gas attributable to decoded Solana routes; separate research only."""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict,Counter
import json,gzip,sys
from eth_utils import keccak
from verify_refresh import checked
from acquire_refresh import R,OLD,save,START,END

SOL=7565164
ORDER='(uint64,bytes,uint256,bytes,uint256,uint256,bytes,uint256,bytes,bytes,bytes,bytes,bytes,bytes)'
CREATION='(address,uint256,bytes,uint256,uint256,bytes,address,bytes,bytes,bytes,bytes)'
def method(name,types):return ('0x'+keccak(text=name+'('+','.join(types)+')')[:4].hex(),(name,types))
METHODS=dict([
 method('transferTokens',['address','uint256','uint16','bytes32','uint256','uint32']),
 method('transferTokensWithPayload',['address','uint256','uint16','bytes32','uint32','bytes']),
 method('wrapAndTransferETH',['uint16','bytes32','uint256','uint32']),
 method('wrapAndTransferETHWithPayload',['uint16','bytes32','uint32','bytes']),
 *[method(n,['bytes']) for n in ['completeTransfer','completeTransferWithPayload','createWrapped','updateWrapped']],
 method('createOrder',[CREATION,'bytes','uint32','bytes']),
 method('createSaltedOrder',[CREATION,'uint64','bytes','uint32','bytes','bytes']),
 method('fulfillOrder',[ORDER,'uint256','bytes32','bytes','address']),
 method('fulfillOrder',[ORDER,'uint256','bytes32','bytes','address','address']),
 method('sendBatchSolanaUnlock',[ORDER+'[]','bytes32','uint256','uint64','uint64']),
 method('sendSolanaUnlock',[ORDER,'bytes32','uint256','uint64','uint64']),
 method('sendSolanaOrderCancel',[ORDER,'bytes32','uint256','uint64','uint64']),
 method('patchOrderTake',[ORDER,'uint256'])])
def day(r):return datetime.fromtimestamp(int(r['timeStamp']),timezone.utc).date().isoformat()
def select(r,address):
 name,types=METHODS[r['input'][:10]];a=checked(types,bytes.fromhex(r['input'][10:]))
 if address=='0x3ee18b2214aff97000d974cf647e7c347e8fa585':
  if name.startswith('transferTokens'):assert a[2]==1;return 'Wormhole','Ethereum → Solana'
  if name.startswith('wrapAndTransferETH'):assert a[0]==1;return 'Wormhole','Ethereum → Solana'
  assert name in ['completeTransfer','completeTransferWithPayload','createWrapped','updateWrapped'] and r['isError']=='0'
  v=a[0];assert len(v)>6 and v[0]==1
  body=v[6+66*v[5]:];assert len(body)>51 and int.from_bytes(body[8:10],'big')==1,'Non-Solana VAA emitter'
  payload=body[51:]
  if name in ['createWrapped','updateWrapped']:
   assert len(payload)==100 and payload[0]==2 and int.from_bytes(payload[33:35],'big')==1
   return 'Wormhole','Solana token administration'
  assert payload[0] in [1,3] and int.from_bytes(payload[99:101],'big')==2
  return 'Wormhole','Solana → Ethereum'
 if address=='0xef4fb24ad0916217251f553c0596f8edc630eb66':
  assert name in ['createOrder','createSaltedOrder'] and a[0][4]==SOL
  return 'deBridge DLN','Ethereum → Solana'
 assert address=='0xe7351fd770a37282b91d153ee690b63579d6dd7f'
 if name=='fulfillOrder':
  order=a[0];assert order[2]==SOL and order[5]==1
  assert order[13]==b'' and order[6]!=b'\0'*20,'Unverified external or native-ETH callback'
  return 'deBridge DLN','Solana → Ethereum'
 if name in ['sendSolanaUnlock','sendBatchSolanaUnlock','sendSolanaOrderCancel','patchOrderTake']:
  orders=a[0] if name=='sendBatchSolanaUnlock' else [a[0]]
  assert orders and all(o[2]==SOL and o[5]==1 for o in orders),'Mixed destination batch'
  return 'deBridge DLN','Solana order administration'
 raise AssertionError('Unreviewed method')
def main():
 canonical=json.loads((R/'canonical-verification.json').read_text());assert not canonical['errors'];repairs={x['hash']:x for x in canonical['results']}
 correction=json.loads((OLD/'audit/canonical_correction_transactions.json').read_text())
 accepted=[];excluded=[];reconciliation=[];mismatches=[]
 for s in json.loads((R/'account-catalog.json').read_text()):
  address=s['address'];rows=[json.loads(l) for l in gzip.open(R/'ledgers'/(address+'.jsonl.gz'),'rt')]
  for r in rows:
   if r['hash'] in repairs:r.update(repairs[r['hash']])
  rows=[r for r in rows if START<=day(r)<END and r['to'].lower()==address]
  actual=defaultdict(lambda:[0,0]);expected=defaultdict(lambda:[0,0])
  obj=json.loads((R/'aggregates'/('solana-account-'+address+'.json')).read_text())
  for r in obj['data']:expected[r['date']]=[r['sum(gas_used)'],r['count()']]
  corrections=[]
  if 'ETH4' in obj['context']['servers']:
   for r in correction:
    if r['recipient']==address:expected[r['date']][0]-=r['gas_used'];expected[r['date']][1]-=1;corrections.append(r['hash'])
  for r in rows:actual[day(r)][0]+=int(r['gasUsed']);actual[day(r)][1]+=1
  result={'address':address,'transactions':len(rows),'gas_used':sum(x[0] for x in actual.values()),'daily_count_and_gas_match':dict(actual)==dict(expected),'documented_ETH4_duplicates_removed':corrections}
  reconciliation.append(result)
  if actual!=expected:mismatches.append({**result,'differences':{d:{'actual':actual.get(d,[0,0]),'expected':expected.get(d,[0,0])} for d in actual.keys()|expected.keys() if actual.get(d,[0,0])!=expected.get(d,[0,0])}})
  for r in rows:
   try:protocol,direction=select(r,address)
   except Exception as e:
    excluded.append({'hash':r['hash'],'gas_used':int(r['gasUsed']),'selector':r['input'][:10],'reason':str(e) or type(e).__name__});continue
   accepted.append({'date':day(r),'transaction_hash':r['hash'],'gas_used':int(r['gasUsed']),'block_number':int(r['blockNumber']),'protocol':protocol,'direction':direction,'source_id':'solana-account-'+address,'selector':r['input'][:10],'status':'failed' if r['isError']=='1' else 'success'})
 save(R/'core-accepted.json',accepted);save(R/'core-excluded.json',excluded)
 save(R/'core-verification.json',{'sources':reconciliation,'mismatches':mismatches,'accepted':len(accepted),'excluded':len(excluded),'excluded_reasons':dict(Counter(x['reason'] for x in excluded))})
 print(json.dumps({'accepted':len(accepted),'mismatches':mismatches,'protocols':dict(Counter(x['protocol'] for x in accepted))}));assert not mismatches
if __name__=='__main__':main()
