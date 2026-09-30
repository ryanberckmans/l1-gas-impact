"""Checkpoint public provider responses for the four-rollup extension.

Acquisition only: classification and acceptance are separate release gates.
Usage: python src/acquire_expansion.py /absolute/research/expanded
"""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from urllib.request import urlopen
import json, gzip, hashlib, sys, time, tomllib

R = Path(sys.argv[1])
END_BLOCK = 25979136
START = int(datetime(2026, 3, 15, tzinfo=timezone.utc).timestamp())
END = int(datetime(2026, 9, 15, tzinfo=timezone.utc).timestamp())
PROJECTS = {'worldchain':'worldchain','unichain':'unichain','op':'optimism','ink':'ink'}

def save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2)+'\n')

def fetch(url, path):
    if path.exists():
        raw=gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes()
        return json.loads(raw), raw
    for attempt in range(5):
        try:
            raw=urlopen(url, timeout=100).read()
            obj=json.loads(raw)
            assert isinstance(obj,dict) and isinstance(obj.get('result',obj.get('data')),list), str(obj)[:300]
            if 'context' in obj: assert obj['context']['code']==200
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw)
            return obj,raw
        except Exception:
            if attempt==4: raise
            time.sleep(2*(attempt+1))

def catalog():
    result=[]
    for p,alias in PROJECTS.items():
        registry=tomllib.loads((R/(p+'-registry.toml')).read_text())
        discovery=json.loads((R/(alias+'-discovered.json')).read_text())
        entries=[e for e in discovery['entries'] if e['address'].startswith('eth:')]
        system=next(e for e in entries if e.get('name')=='SystemConfig')
        vals=system['values']
        inboxes={registry['batch_inbox_addr'].lower(),vals['batchInbox'].split(':')[-1].lower()}
        senders={registry['genesis']['system_config']['batcherAddress'].lower(),vals['batcherHash'].split(':')[-1].lower()}
        def add(name,address,kind,extra=None):
            address=address.split(':')[-1].lower()
            result.append({'product':p,'name':name,'recipient':address,'kind':kind,
                'source_id':f'expanded-{p}-{address}',
                'identity_sources':[f'https://raw.githubusercontent.com/ethereum-optimism/superchain-registry/main/superchain/configs/mainnet/{p}.toml',f'https://raw.githubusercontent.com/l2beat/l2beat/main/packages/config/src/projects/{alias}/discovered.json'],
                **(extra or {})})
        for addr in sorted(inboxes):add('BatchInbox',addr,'batch',{'senders':sorted(senders)})
        for e in entries:
            name=e.get('name','')
            # Shared implementations, generic safes and Superchain administration excluded.
            kind={'DisputeGameFactory':'settlement','AnchorStateRegistry':'settlement',
                'SystemConfig':'governance','OptimismPortal2':'portal','L1CrossDomainMessenger':'messenger',
                'L1StandardBridge':'canonical_bridge','L1ERC721Bridge':'canonical_bridge',
                'OptimismMintableERC20Factory':'canonical_bridge',
                'L1OpUSDCBridgeAdapter':'dedicated_token_bridge','L1ERC20TokenBridge':'dedicated_token_bridge',
                'L1DAITokenBridge':'dedicated_token_bridge','wstETHEscrow':'dedicated_token_bridge'}.get(name)
            if kind:add(name,e['address'],kind)
        # Historical Ink settlement registries in the project's official contract list.
        if p=='ink':add('AnchorStateRegistry (historical)','0xde744491bcf6b2dd2f32146364ea1487d75e2509','settlement',{'identity_sources':['https://docs.inkonchain.com/useful-information/contracts']})
    assert len({s['recipient'] for s in result})==len(result),'Shared recipient requires separate decoding'
    save(R/'catalog.json',result)
    return result

def receipts(s):
    tag=s['product']+'-'+s['recipient']; manifest=R/'receipt-manifests'/(tag+'.json')
    if manifest.exists():return json.loads(manifest.read_text())
    hi=END_BLOCK;seen=set();pages=[];ledger=[];done=False
    while not done:
        q={'module':'account','action':'txlist','address':s['recipient'],'startblock':0,'endblock':hi,'page':1,'offset':10000,'sort':'desc'}
        url='https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?'+urlencode(q)
        path=R/'raw-receipts'/f'{tag}-{hi}.json.gz'
        obj,raw=fetch(url,path);rows=obj['result']
        pages.append({'url':url,'file':str(path.relative_to(R)),'sha256_uncompressed':hashlib.sha256(raw).hexdigest(),'rows':len(rows)})
        for r in rows:
            h=r['hash'].lower()
            if h in seen:continue
            seen.add(h)
            if START<=int(r['timeStamp'])<END and r['to'].lower()==s['recipient']:
                ledger.append(r)
        done=len(rows)<10000 or min((int(r['timeStamp']) for r in rows),default=0)<START
        if not done:
            lower=min(int(r['blockNumber']) for r in rows)
            # Include the boundary block again, deduplicate hashes; never skip a partial block.
            assert lower<hi,('Single-block pagination requires manual handling',s['recipient'],hi)
            hi=lower
    path=R/'ledgers'/(tag+'.jsonl.gz');path.parent.mkdir(exist_ok=True)
    with gzip.open(path,'wt') as f:
        for r in ledger:f.write(json.dumps(r,separators=(',',':'))+'\n')
    result={**s,'provider':'Routescan','pages':pages,'receipts':len(ledger),'gas_used_unclassified':sum(int(r['gasUsed']) for r in ledger),'ledger':str(path.relative_to(R)),'period_start':START,'period_end_exclusive':END,'complete_query_population':True}
    save(manifest,result)
    print(json.dumps({'receipts':s['product']+'/'+s['name'],'count':len(ledger),'pages':len(pages)}),flush=True)
    return result

def aggregate(s):
    query=f'time(2026-03-15..2026-09-14),recipient({s["recipient"]})'
    url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':query,'a':'date,count(),sum(gas_used)','limit':10000})
    path=R/'raw-aggregates'/(s['product']+'-'+s['recipient']+'.json')
    obj,raw=fetch(url,path)
    assert len(obj['data'])<=184 and obj['context'].get('total_rows',len(obj['data']))==len(obj['data'])
    result={**s,'url':url,'raw_file':str(path.relative_to(R)),'sha256':hashlib.sha256(raw).hexdigest(),'context':obj['context'],'gas_used':sum(r['sum(gas_used)'] for r in obj['data']),'tx_count':sum(r['count()'] for r in obj['data'])}
    save(R/'aggregate-manifests'/(s['product']+'-'+s['recipient']+'.json'),result)
    print(json.dumps({'aggregate':s['product']+'/'+s['name'],'count':result['tx_count']}),flush=True)
    return result

if __name__=='__main__':
    sources=catalog(); mode=sys.argv[2] if len(sys.argv)>2 else 'receipts'
    task=receipts if mode=='receipts' else aggregate
    errors=[]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(task,s):s for s in sources}
        for f in as_completed(futures):
            try:f.result()
            except Exception as exc:
                errors.append({'source':futures[f]['source_id'],'error':str(exc)});print(json.dumps(errors[-1]),flush=True)
    save(R/(mode+'-errors.json'),errors)
    assert not errors,errors
