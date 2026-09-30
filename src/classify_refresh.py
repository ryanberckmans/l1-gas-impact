"""Reconcile the refresh, preserving historical evidence and strict parent attribution."""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict,Counter
import json,gzip,sys
from eth_abi import decode,encode
from eth_utils import keccak
from acquire_refresh import R,OLD,ROOT,save,START,DELTA,END
from classify_expansion import classify,withdrawal,checked

ZERO='0x'+'0'*40
def day(r):return datetime.fromtimestamp(int(r['timeStamp']),timezone.utc).date().isoformat()
def selector(s):return '0x'+keccak(text=s)[:4].hex()
def rec(r,p,b,sid):
 return {'date':day(r),'product':p,'transaction_hash':r['hash'],'block_number':int(r['blockNumber']),
 'gas_used':int(r['gasUsed']),'sender':r['from'].lower(),'recipient':r['to'].lower(),
 'activity':b,'source_id':sid,'selector':r['input'][:10],'status':'failed' if r['isError']=='1' else 'success'}
def universal(r):
 sel=r['input'][:10];raw=bytes.fromhex(r['input'][10:])
 assert sel in ['0x3593564c','0x24856bc3'],'Not a reviewed execute method'
 args=checked(['bytes','bytes[]','uint256'] if sel=='0x3593564c' else ['bytes','bytes[]'],raw)
 def commands(cmds,inputs,depth=0):
  assert depth<8 and len(cmds)==len(inputs)
  protocol=False
  for code,inp in zip(cmds,inputs):
   c=code&0x7f
   assert c in set(range(15))|{16,17,18,19,20,33},'Bridge or unreviewed command'
   if c==33:
    inner=checked(['bytes','bytes[]'],inp);protocol|=commands(*inner,depth+1)
   elif c in [0,1,8,9,18,19,20]:protocol=True
   elif c==16:
    actions,params=checked(['bytes','bytes[]'],inp);assert len(actions)==len(params)
    protocol|=any(a in [0,1,2,3,6,7,8,9] for a in actions)
  return protocol
 assert commands(args[0],args[1]),'Utility-only execution'
 return 'mixed_router'
def arbitrum_withdrawal(r,p):
 assert r['input'][:10]=='0x08635a95','Unreviewed outbox method'
 a=checked(['bytes32[]','uint256','address','address','uint256','uint256','uint256','uint256','bytes'],bytes.fromhex(r['input'][10:]))
 assert a[7]==0,'Native ETH or arbitrary-value finalization'
 j=json.loads((R/(p+'-discovered.json')).read_text());targets={}
 for e in j['entries']:
  if 'Gateway' in (e.get('name') or ''):
   v=e.get('values',{});remote=v.get('counterpartGateway')
   if remote and e['address'].startswith('eth:'):targets[e['address'].split(':')[-1].lower()]=remote.split(':')[-1].lower()
 assert targets.get(a[3])==a[2],'Unreviewed gateway pair'
 assert a[8][:4].hex()=='2e567b36','Unreviewed token finalization'
 checked(['address','address','address','uint256','bytes'],a[8][4:])
 return 'withdrawal_claims'
def safe_leaves(r):
 assert r['input'][:10]=='0x6a761202','Unreviewed Safe method'
 a=checked(['address','uint256','bytes','uint8','uint256','uint256','uint256','address','address','bytes'],bytes.fromhex(r['input'][10:]))
 assert a[6]==0 and a[7]==ZERO and a[8]==ZERO,'Potentially unrelated Safe refund'
 if a[3]==0:return [(a[0],a[1],a[2])]
 assert a[3]==1 and a[0] in ['0xa238cbeb142c10ef7ad8442c6d1f9e89e07e7761','0x9641d764fc13c8b624c04430c7356c1c7c8102e2'] and a[2][:4].hex()=='8d80ff0a','Unreviewed delegatecall'
 raw=checked(['bytes'],a[2][4:])[0];i=0;leaves=[]
 while i<len(raw):
  assert i+85<=len(raw) and raw[i]==0,'Unreviewed nested operation'
  target='0x'+raw[i+1:i+21].hex();value=int.from_bytes(raw[i+21:i+53],'big');size=int.from_bytes(raw[i+53:i+85],'big')
  assert i+85+size<=len(raw);leaves.append((target,value,raw[i+85:i+85+size]));i+=85+size
 assert leaves
 return leaves
def main():
 canonical=json.loads((R/'canonical-verification.json').read_text());assert not canonical['errors']
 repairs={r['hash']:r for r in canonical['results']}
 ledgers={};reconciliations=[];mismatches=[]
 for f in (R/'receipt-manifests').glob('*.json'):
  m=json.loads(f.read_text());rows=[json.loads(l) for l in gzip.open(R/m['ledger'],'rt')]
  for r in rows:
   if r['hash'] in repairs:r.update(repairs[r['hash']])
  assert len(rows)==len({r['hash'] for r in rows})
  ledgers[m['address']]=rows
 sources=[json.loads(f.read_text()) for f in (R/'aggregate-manifests').glob('*.json')]
 for s in sources:
  address=s.get('recipient',s.get('address'))
  if s['group'] not in ['crosscheck','expanded','rollups','new-exclusive'] or address not in ledgers:continue
  actual=defaultdict(lambda:[0,0]);expected=defaultdict(lambda:[0,0])
  start=START if s['group']=='new-exclusive' else DELTA
  for r in ledgers[address]:
   if not start<=day(r)<END or r['to'].lower()!=address:continue
   if s.get('sender') and r['from'].lower()!=s['sender']:continue
   if s.get('selector') and not r['input'].startswith(s['selector']):continue
   actual[day(r)][0]+=int(r['gasUsed']);actual[day(r)][1]+=1
  for r in json.loads((R/s['file']).read_text())['data']:
   expected[r['date']][0]+=r['sum(gas_used)'];expected[r['date']][1]+=r['count()']
  same=dict(actual)==dict(expected)
  result={'source_id':s['source_id'],'daily_count_and_gas_match':same,'transactions':sum(v[1] for v in actual.values()),'gas_used':sum(v[0] for v in actual.values())}
  reconciliations.append(result)
  if not same:mismatches.append({**result,'differences':{d:{'receipts':actual.get(d,[0,0]),'aggregate':expected.get(d,[0,0])} for d in actual.keys()|expected.keys() if actual.get(d,[0,0])!=expected.get(d,[0,0])}})
 save(R/'daily-reconciliation.json',{'sources':reconciliations,'mismatches':mismatches})
 accepted=[];excluded=[];seen=set()
 def add(r,p,b,sid):
  assert r['hash'] not in seen,('Cross-source duplicate',r['hash'],sid)
  seen.add(r['hash']);accepted.append(rec(r,p,b,sid))
 def reject(r,p,sid,exc):excluded.append({'product':p,'source_id':sid,'hash':r['hash'],'gas_used':int(r['gasUsed']),'reason':str(exc) or type(exc).__name__})
 cohorts=json.loads((ROOT/'data/cohort-sources.json').read_text())
 for s in cohorts['rollups_included']:
  p=s['project'];sid=s['source_id']
  for r in ledgers[s['recipient']]:
   if not DELTA<=day(r)<END or r['to'].lower()!=s['recipient']:continue
   if s.get('sender') and r['from'].lower()!=s['sender']:continue
   if s.get('selector') and not r['input'].startswith(s['selector']):continue
   add(r,p,s['bucket'],sid)
 for s in json.loads((OLD/'expanded/catalog.json').read_text()):
  for r in ledgers[s['recipient']]:
   if not DELTA<=day(r)<END:continue
   try:b=classify(s,r)
   except Exception as exc:reject(r,s['product'],s['source_id'],exc);continue
   add(r,s['product'],b,s['source_id'])
 for s in json.loads((R/'new-catalog.json').read_text()):
  for r in ledgers[s['recipient']]:
   if START<=day(r)<END:add(r,s['product'],s['bucket'],s['source_id'])
 for p,a in [('base','0x49048044d57e1c92a77f79988d21fa8faf74e97e'),('arbitrum','0x0b9857ae2d4a3dbe74ffe1d7df045bb7f96e4840'),('robinhood','0xf0ce991ea4a0d2400a4ab49b20ae333f6dce3de9')]:
  sid='routescan-decoded-'+p+('-portal' if p=='base' else '-outbox')
  for r in ledgers[a]:
   if r['hash'] in seen or not DELTA<=day(r)<END:continue
   try:
    if p=='base':
     assert r['input'][:10] in ['0x8c3152e9','0x43ca1c50'];b=withdrawal(p,bytes.fromhex(r['input'][10:]),r['input'][:10])
    else:b=arbitrum_withdrawal(r,p)
   except Exception as exc:reject(r,p,sid,exc);continue
   add(r,p,b,sid)
 sid='routescan-arbitrum-validator-decoded'
 for r in ledgers['0x1b2988478be18a69de983ca50eaf21ef8de1248b']:
  try:
   assert r['input'][:10]=='0x097da1f8'
   a=checked(['address','bytes','address','uint256'],bytes.fromhex(r['input'][10:]))
   assert a[0]==ZERO and a[2]=='0x4dceb440657f21083db8add07665f8ddbe1dcfc0' and a[3]==0 and a[1][:4].hex() in ['10b98a35','3b86de19']
  except Exception as exc:reject(r,'arbitrum',sid,exc);continue
  add(r,'arbitrum','operations',sid)
 lm=json.loads((OLD/'lighter/sources-and-methodology.json').read_text());roles=lm['primaryRoles'];primary=roles['primary_proxy']
 details={'settlement_data':'batch_submission','settlement_proofs':'verify_batch','settlement_state':'execute_batch','user_deposits':'deposits','user_controls':'account_controls','emergency_exits':'emergency','other_direct':'other'}
 for r in ledgers[primary]:
  key=lm['primarySelectors'].get(r['input'][:10],'other_direct');add(r,'lighter',details.get(key,key),'lighter-receipts-'+key)
 for a in dict.fromkeys([x['address'] for x in lm['dedicatedWrappers']]+['0x16dd80d93c88549c5f774691cb66ddffae6a7972']):
  for r in ledgers[a]:add(r,'lighter','exclusive_wrappers','lighter-receipts-exclusive_wrappers')
 exclusive={roles[k] for k in ['primary_proxy','governance','upgrade_gatekeeper','verifier_proxy','desert_verifier']};upgrade_payloads=[]
 for role,address in roles.items():
  if role=='primary_proxy' or role=='implementation_deployer':continue
  for r in ledgers[address]:
   try:
    leaves=safe_leaves(r) if role.endswith('_safe') else [(address,0,bytes.fromhex(r['input'][2:]))]
    assert all(t in exclusive and value==0 for t,value,data in leaves),'Safe has a nonexclusive terminal call'
    upgrade_payloads.extend(data.hex() for t,v,data in leaves)
   except Exception as exc:reject(r,'lighter','lighter-receipts-governance_admin',exc);continue
   add(r,'lighter','governance','lighter-receipts-governance_admin')
 for r in ledgers[roles['implementation_deployer']]:
  created=r.get('contractAddress','').lower()
  if created and any(created[2:] in payload for payload in upgrade_payloads):add(r,'lighter','deployments','lighter-receipts-deployments')
  else:reject(r,'lighter','lighter-receipts-deployments','No exclusive primary upgrade linkage')
 sid='routescan-uniswap-universal-v211-decoded'
 for r in ledgers['0x4c82d1fbfe28c977cbb58d8c7ff8fcf9f70a2cca']:
  try:b=universal(r)
  except Exception as exc:reject(r,'uniswap',sid,exc);continue
  add(r,'uniswap',b,sid)
 save(R/'accepted-core.json',accepted);save(R/'excluded-core.json',excluded)
 save(R/'classification-summary.json',{'transactions':len(accepted),'gas_used':sum(r['gas_used'] for r in accepted),'excluded_reasons':dict(Counter(r['reason'] for r in excluded)),'reconciliation_mismatches':len(mismatches)})
 print(json.dumps({'accepted':len(accepted),'excluded':len(excluded),'mismatches':mismatches}));assert not mismatches
if __name__=='__main__':main()
