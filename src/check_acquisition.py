"""Transport-boundary checks for cached acquisition and finite failure recovery."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
import sys,io,json,gzip
from types import SimpleNamespace
from threading import Lock,Barrier
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout

with TemporaryDirectory() as tmp:
 sys.argv=['check',tmp,tmp]
 import acquire_refresh as a
 url='https://api.blockchair.com/ethereum/transactions?q=test'
 class Response(io.BytesIO):
  def geturl(self):return url
 def reset():
  a.counters.clear();a.next_at.clear();a.begun=0
 scenarios=[]
 with patch.object(a.time,'monotonic',return_value=1),patch.object(a.time,'sleep'):
  reset()
  with patch.object(a,'urlopen',return_value=Response(b'{"context":{"code":200},"data":[]}')) as transport:
   a.fetch(url,Path(tmp)/'cold.json');a.fetch(url,Path(tmp)/'cold.json')
   assert transport.call_count==1 and a.counters['api.blockchair.com']==1
  scenarios.append('Cold read and repeat share one successful response')
  reset()
  with patch.object(a,'urlopen',return_value=Response(b'[{"type":"function","name":"deposit"}]')) as transport:
   value,_=a.fetch(url,Path(tmp)/'abi.json')
   assert isinstance(value,list) and transport.call_count==1
  scenarios.append('A valid top-level ABI array is accepted in one request')
  for status in [400,401,403,429]:
   reset()
   with patch.object(a,'urlopen',side_effect=HTTPError(url,status,'refused',{},None)) as transport:
    try:a.fetch(url,Path(tmp)/(str(status)+'.json'));raise AssertionError('Expected stop')
    except HTTPError:pass
    assert transport.call_count==1 and not (Path(tmp)/(str(status)+'.json')).exists()
   scenarios.append(f'HTTP {status} stops after one attempt without a checkpoint')
  reset()
  with patch.object(a,'urlopen',side_effect=HTTPError(url,502,'transient',{},None)) as transport:
   try:a.fetch(url,Path(tmp)/'transient.json');raise AssertionError('Expected finite failure')
   except HTTPError:pass
   assert transport.call_count==3 and a.counters['api.blockchair.com']==3
  scenarios.append('Transient failures stop at three emitted requests')
  reset()
  with patch.object(a,'urlopen',return_value=Response(b'{"context":{"code":429}}')) as transport:
   try:a.fetch(url,Path(tmp)/'logical-refusal.json');raise AssertionError('Expected logical refusal')
   except a.TerminalProviderError:pass
   assert transport.call_count==1
  scenarios.append('Provider refusal inside HTTP 200 is terminal')
  reset()
  with patch.object(a.shutil,'disk_usage',return_value=SimpleNamespace(free=1024)),patch.object(a,'urlopen') as transport:
   try:a.fetch(url,Path(tmp)/'low-space.json');raise AssertionError('Expected reserve stop')
   except a.TerminalProviderError:pass
   a.fetch(url,Path(tmp)/'cold.json')
   assert transport.call_count==0 and not (Path(tmp)/'low-space.json').exists()
  scenarios.append('Low disk reserve blocks new requests while allowing immutable cached reads')
  reset()
  with patch.object(a,'urlopen',return_value=Response(b' '*80_000_001)) as transport:
   try:a.fetch(url,Path(tmp)/'oversized.json');raise AssertionError('Expected size stop')
   except a.TerminalProviderError:pass
   assert transport.call_count==1 and not (Path(tmp)/'oversized.json').exists()
  scenarios.append('Oversized responses stop after one request without a checkpoint')
  reset();a.counters['api.blockchair.com']=a.LIMITS['api.blockchair.com']
  with patch.object(a,'urlopen') as transport:
   try:a.fetch(url,Path(tmp)/'budget.json');raise RuntimeError('Budget not enforced')
   except AssertionError as e:assert 'budget' in str(e)
   assert transport.call_count==0
  scenarios.append('Host budget blocks further transport')
  reset()
  with patch.object(a.time,'monotonic',return_value=2701),patch.object(a,'urlopen') as transport:
   try:a.fetch(url,Path(tmp)/'time-budget.json');raise RuntimeError('Time budget not enforced')
   except AssertionError as e:assert 'wall-clock' in str(e)
   assert transport.call_count==0
  scenarios.append('Wall-clock budget blocks further transport')
  reset();guard=Lock();barrier=Barrier(3);state={'active':0,'peak':0,'calls':0}
  jobs=[{'source_id':f'bounded-{i}','url':url+'&cohort='+str(i),'product':'test','group':'test'} for i in range(6)]
  def concurrent_transport(*args,**kwargs):
   with guard:
    state['active']+=1;state['calls']+=1;state['peak']=max(state['peak'],state['active'])
   barrier.wait(timeout=5)
   with guard:state['active']-=1
   return Response(b'{"context":{"code":200,"total_rows":0},"data":[]}')
  with patch.object(a,'catalog',return_value=(jobs,[])),patch.object(a,'urlopen',side_effect=concurrent_transport),redirect_stdout(io.StringIO()):
   a.main();a.main()
  assert state['peak']==3 and state['calls']==6,'A repeated complete operation must use checkpoints; first operation is capped at three concurrent transports'
  scenarios.append('Complete six-source operation caps concurrency at three; repeat emits zero requests')
  address='0x'+'1'*40
  population=[{'hash':'0x'+format(i,'064x'),'blockNumber':str(200-i),'gasUsed':'21000','input':'0x','from':'0x'+'2'*40,'to':address,'timeStamp':'1','value':'0','isError':'0','blockHash':'0x'+'3'*64} for i in range(100)]
  duplicate={**population[-1],'gasUsed':'22000'}
  final={**population[-1],'hash':'0x'+format(100,'064x'),'blockNumber':'100'}
  replies=[({'result':population},{'url':'first','file':'first'}),({'result':[duplicate,final]},{'url':'last','file':'last'})]
  with patch.object(a,'fetch',side_effect=replies) as transport,redirect_stdout(io.StringIO()):
   a.receipts({'address':address,'name':'bounded-test','product':'test','page_size':100},300)
  manifest=json.loads((Path(tmp)/'receipt-manifests'/(address+'.json')).read_text())
  with gzip.open(Path(tmp)/manifest['ledger'],'rt') as stream:restored=[json.loads(line) for line in stream]
  assert len(restored)==101 and manifest['transactions']==101 and len(manifest['unresolved_index_conflicts'])==1
  assert restored[99]['gasUsed']=='21000' and all('offset=100&' in call.args[0] for call in transport.call_args_list)
  assert not list((Path(tmp)/'receipt-work').rglob('*.sqlite')),'Scratch databases must be removed after each population'
  scenarios.append('Streaming pagination deduplicates overlaps, bounds fingerprint memory and preserves conflicts for canonical review')
  with patch.object(a,'fetch',side_effect=replies),redirect_stdout(io.StringIO()):
   a.receipts({'address':address,'name':'compact-test','product':'test','page_size':100,'calldata_in_pages':True},300)
  with gzip.open(Path(tmp)/manifest['ledger'],'rt') as stream:compact=[json.loads(line) for line in stream]
  assert len(compact)==101 and all('input' not in row and 'input_sha256' in row and 'input_page' in row for row in compact)
  scenarios.append('Bulky calldata remains referenced in original pages instead of duplicated in receipt checkpoints')
 print(json.dumps({'passed':True,'scenarios':scenarios}))
