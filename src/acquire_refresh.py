"""Bounded, checkpointed acquisition; this stage never accepts data for publication.

Usage: acquire_refresh.py RESEARCH_DIR BASELINE_RESEARCH [aggregates|receipts]
All times are UTC. Provider responses are immutable and content hashed.
"""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import json, gzip, hashlib, time, sys, shutil

ROOT=Path(__file__).resolve().parents[1]
R=Path(sys.argv[1]); OLD=Path(sys.argv[2])
START='2026-03-28'; DELTA='2026-09-15'; END='2026-09-28'
LOW_BLOCK=25979137
HOSTS={'api.routescan.io','api.blockchair.com','raw.githubusercontent.com'}
lock=Lock(); counters={}; next_at={}; begun=time.monotonic()
LIMITS={'api.routescan.io':1200,'api.blockchair.com':1200,'raw.githubusercontent.com':60}
class TerminalProviderError(RuntimeError):pass

def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.partial');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.replace(path)

def fetch(url,path,kind='json'):
    host=urlparse(url).hostname
    assert host in HOSTS and urlparse(url).scheme=='https'
    if path.exists():raw=gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes()
    else:
        if shutil.disk_usage(R).free<3*1024**3:raise TerminalProviderError('Workspace reserve reached; stop before downloading')
        for attempt in range(3):
            with lock:
                assert time.monotonic()-begun<2700,'Acquisition wall-clock budget reached'
                counters[host]=counters.get(host,0)+1
                assert counters[host]<=LIMITS[host],'Provider request budget reached'
                delay=max(0,next_at.get(host,0)-time.monotonic());next_at[host]=time.monotonic()+delay+.5
            time.sleep(delay)
            try:
                with urlopen(Request(url,headers={'User-Agent':'L1-Gas-Impact-Research/1.0'}),timeout=45) as response:
                    final=urlparse(response.geturl())
                    if final.scheme!='https' or final.hostname not in HOSTS:raise TerminalProviderError('Unapproved redirect destination')
                    raw=response.read(80_000_001)
                    if len(raw)>80_000_000:raise TerminalProviderError('Response size budget reached')
                if kind=='json':
                    obj=json.loads(raw)
                    if isinstance(obj,dict) and 'context' in obj and obj['context'].get('code')!=200:
                        code=obj['context'].get('code')
                        if code in [408,425,500,502,503,504]:raise RuntimeError('Transient provider response: '+str(code))
                        raise TerminalProviderError('Provider refused request: '+str(code))
                    if isinstance(obj,dict) and obj.get('status')=='0' and obj.get('message')!='No transactions found':raise TerminalProviderError('Provider rejected query')
                break
            except TerminalProviderError:raise
            except HTTPError as exc:
                if exc.code not in [408,425,500,502,503,504]:raise
                if attempt==2:raise
                time.sleep(2**attempt)
            except Exception:
                if attempt==2:raise
                time.sleep(2**attempt)
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_name(path.name+'.partial');tmp.write_bytes(gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw);tmp.replace(path)
    return (json.loads(raw) if kind=='json' else raw.decode()),{'url':url,'file':str(path.relative_to(R)),'sha256_uncompressed':hashlib.sha256(raw).hexdigest(),'retrieved_at':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()}

def date_query(url,start=DELTA):
    q=parse_qs(urlparse(url).query)
    q={k:v[0] for k,v in q.items()}
    q['q']=q['q'].replace('2026-03-15..2026-09-14',start+'..2026-09-27')
    return 'https://api.blockchair.com/ethereum/transactions?'+urlencode(q)

def catalog():
    c=json.loads((ROOT/'data/cohort-sources.json').read_text())
    agg=[];accounts={}
    def account(address,product,name):
        if address:accounts.setdefault(address.lower(),{'address':address.lower(),'product':product,'name':name})
    def add(s,url,product,group):
        agg.append({**s,'url':date_query(url),'product':product,'group':group})
    add({'source_id':'blockchair-plain-eth-transfer-benchmark'},c['eth']['source_url'],'eth','eth')
    for s in c['uniswap']['contracts']:
        add(s,s['query_url'],'uniswap','uniswap')
        if not s['included']:account(s['address'],'uniswap',s['contract'])
    for s in c['rollups_included']:
        url=s.get('queryUrl')
        if url:add(s,url,s.get('project',s.get('product')),'rollups')
        account(s.get('recipient'),s.get('project',s.get('product')),s.get('name',''))
    for s in c['rollups_excluded']:account(s.get('recipient'),s['project'],s.get('name','excluded'))
    for group in ['approvals','cctp','across']:
        for s in c[group]['series']:add(s,s['url'],s['product'],group)
    for path in sorted((OLD/'expanded/supplement-manifests').glob('*.json')):
        s=json.loads(path.read_text());add(s,s['url'],s['product'],s['group'])
    for s in json.loads((OLD/'expanded/catalog.json').read_text()):
        account(s['recipient'],s['product'],s['name'])
        url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':f'time(2026-03-15..2026-09-14),recipient({s["recipient"]})','a':'date,count(),sum(gas_used)','limit':10000})
        add(s,url,s['product'],'expanded')
    lm=json.loads((OLD/'lighter/sources-and-methodology.json').read_text())
    for role,addr in lm['primaryRoles'].items():account(addr,'lighter',role)
    for s in lm['dedicatedWrappers']:account(s['address'],'lighter',s['name'])
    for addr in ['0x16dd80d93c88549c5f774691cb66ddffae6a7972']:account(addr,'lighter','withdrawal_helper')
    # Include previously decoded shared parents and validator populations.
    for p in ['base','arbitrum','robinhood']:
        f=OLD/'rollups'/('base-portal-transactions.json' if p=='base' else p+'-outbox-transactions.json')
        data=json.loads(f.read_text());data=data.get('transactions',data.get('result',data)) if isinstance(data,dict) else data
        if data:account(data[0]['to'],p,'decoded_withdrawals')
    data=json.loads((OLD/'rollups/arbitrum-validator-window.json').read_text());data=data.get('result',data) if isinstance(data,dict) else data
    if data:account(data[0]['to'],'arbitrum','validator')
    # Original refresh retained Solana as a separate output. The later coverage
    # expansion explicitly authorizes it as a site product via its own pipeline.
    for s in c['cctp']['series']:
        if s['product']!='base':continue
        p=s['pattern'][:-16]+'0000000500000000' if s['direction']=='receive' else s['pattern'][:-64]+f'{5:064x}'
        parts=[f'time({START}..2026-09-27)',f'recipient({s["recipient"]})',f'input_hex(^{p})']
        if s['direction']=='receive':parts.append('failed(false)')
        url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':','.join(parts),'a':'date,count(),sum(gas_used)','limit':10000})
        agg.append({**s,'source_id':s['source_id'].replace('base','solana'),'product':'solana','group':'cctp','domain':5,'pattern':p,'url':url})
    # Independent daily totals also cover exclusive primary and wrapper histories.
    known={s.get('recipient',s.get('address')) for s in agg}
    for a,s in accounts.items():
        if a in known:continue
        url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':f'time({DELTA}..2026-09-27),recipient({a})','a':'date,count(),sum(gas_used)','limit':10000})
        agg.append({**s,'source_id':'refresh-account-'+a,'group':'crosscheck','url':url})
    ids=[s['source_id'] for s in agg];assert len(ids)==len(set(ids)), 'Duplicate source catalog'
    save(R/'aggregate-catalog.json',agg);save(R/'account-catalog.json',list(accounts.values()))
    return agg,list(accounts.values())

def aggregate(s):
    obj,prov=fetch(s['url'],R/'aggregates'/(s['source_id']+'.json'))
    assert isinstance(obj.get('data'),list)
    assert len(obj['data'])==obj['context']['total_rows'],'Incomplete aggregate'
    result={**s,**prov,'tx_count':sum(r['count()'] for r in obj['data']),'gas_used':sum(r['sum(gas_used)'] for r in obj['data']),'complete':True,'context':obj['context']}
    save(R/'aggregate-manifests'/(s['source_id']+'.json'),result)
    print(json.dumps({'aggregate':s['source_id'],'tx':result['tx_count']}),flush=True)

def boundary():
    ts=int(datetime.fromisoformat(END).replace(tzinfo=timezone.utc).timestamp())-1
    u='https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?'+urlencode({'module':'block','action':'getblocknobytime','timestamp':ts,'closest':'before'})
    obj,_=fetch(u,R/'boundary.json');return int(obj['result'])

def receipts(s,high):
    address=s['address'];pages=[];conflicts=[];seen={}
    page_size=s.get('page_size',10000)
    assert isinstance(page_size,int) and 100<=page_size<=10000
    path=R/'ledgers'/(address+'.jsonl.gz');path.parent.mkdir(exist_ok=True)
    partial=path.with_name(path.name+'.partial')
    # Keep only fixed-size fingerprints in memory and stream original rows to a
    # compressed atomic checkpoint. No database or uncompressed corpus is needed.
    keys=['blockNumber','blockHash','timeStamp','from','to','gasUsed','input','value','isError']
    try:
        with partial.open('wb') as file,gzip.GzipFile(fileobj=file,mode='wb',mtime=0,compresslevel=6) as output:
            for page in range(120):
                if shutil.disk_usage(R).free<3*1024**3 or partial.stat().st_size>1536*1024**2:
                    raise TerminalProviderError('Pagination storage budget reached')
                u='https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?'+urlencode({'module':'account','action':'txlist','address':address,'startblock':LOW_BLOCK,'endblock':high,'page':1,'offset':page_size,'sort':'desc'})
                suffix='' if page_size==10000 else '-size-'+str(page_size)
                obj,prov=fetch(u,R/'raw-receipts'/f'{address}-{high}{suffix}.json.gz');rs=obj['result'];assert isinstance(rs,list)
                pages.append({**prov,'rows':len(rs)})
                for r in rs:
                    fingerprint=hashlib.sha256(json.dumps([r.get(k) for k in keys],separators=(',',':')).encode()).digest()
                    prior=seen.get(r['hash'])
                    if prior is not None:
                        if prior!=fingerprint:conflicts.append({'hash':r['hash'],'changes':{'chain_facts_sha256':[prior.hex(),fingerprint.hex()]}})
                    else:
                        seen[r['hash']]=fingerprint
                        stored=r
                        if s.get('calldata_in_pages'):
                            stored={k:v for k,v in r.items() if k!='input'}
                            stored['input_sha256']=hashlib.sha256(r['input'].encode()).hexdigest()
                            stored['input_page']=prov['file']
                        output.write((json.dumps(stored,separators=(',',':'))+'\n').encode())
                if len(rs)<page_size:break
                lo=min(int(r['blockNumber']) for r in rs);assert lo<high,'Single-block overflow requires explicit continuation';high=lo
            else:raise AssertionError('Account page budget reached')
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    save(R/'receipt-manifests'/(address+'.json'),{**s,'pages':pages,'transactions':len(seen),'ledger':str(path.relative_to(R)),'complete':True,'unresolved_index_conflicts':conflicts})
    print(json.dumps({'account':s['product']+'/'+s['name'],'tx':len(seen)}),flush=True)

def main():
    mode=sys.argv[3] if len(sys.argv)>3 else 'aggregates'
    if (R/'account-catalog.json').exists():
        agg=json.loads((R/'aggregate-catalog.json').read_text());accounts=json.loads((R/'account-catalog.json').read_text())
    else:agg,accounts=catalog()
    errors=[]
    if mode=='receipts':high=boundary();jobs=accounts;task=lambda s:receipts(s,high)
    elif mode=='aggregates':jobs=agg;task=aggregate
    else:raise ValueError(mode)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(task,s):s for s in jobs}
        for f in as_completed(futures):
            try:f.result()
            except Exception as e:
                err={'source':futures[f].get('source_id',futures[f].get('address')),'error':str(e)};errors.append(err);print(json.dumps(err),flush=True)
    save(R/(mode+'-run.json'),{'started_window':DELTA,'end_exclusive':END,'errors':errors,'request_counts':counters,'duration_seconds':time.monotonic()-begun})
    assert not errors,errors

if __name__=='__main__':main()
