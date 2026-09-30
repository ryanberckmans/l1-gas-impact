"""Exact-spender approvals and chain/domain-specific bridge aggregates.

Uses the existing reviewed ABI query templates; preserves unmodified responses.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
import json, re, hashlib, sys
from acquire_expansion import fetch, save, R

ROOT=Path(__file__).resolve().parents[1]
PRIOR=json.loads((ROOT/'data/cohort-sources.json').read_text())
DOMAINS={'worldchain':14,'unichain':10,'op':2,'ink':21}
CHAINS={'worldchain':480,'unichain':130,'op':10,'ink':57073}
CORRECTIONS=json.loads((R.parent/'reference/canonical_correction_transactions.json').read_text())

def sources():
    out=[]
    for group,ids in [('cctp',DOMAINS),('across',CHAINS)]:
        for p,domain in ids.items():
            for old in PRIOR[group]['series']:
                if old['product']!='base':continue
                s={k:old[k] for k in ['recipient','signature','selector','version','direction','name','chain_word','abi_source','identity_source'] if k in old}
                if group=='cctp' and old['direction']=='receive':
                    pattern=old['pattern'][:-16]+f'{domain:08x}'+'00000000'
                else:pattern=old['pattern'][:-64]+f'{domain:064x}'
                out.append({**s,'product':p,'domain':domain,'pattern':pattern,
                    'source_id':old['source_id'].replace('_base_',f'_{p}_'),
                    'detail_bucket':group+'_bridge','group':group,
                    'success_only':group=='cctp' and old['direction']=='receive',
                    'domain_source':'https://developers.circle.com/cctp/concepts/supported-chains-and-domains' if group=='cctp' else 'https://docs.across.to/chains-and-contracts'})
    common=['0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48','0xdac17f958d2ee523a2206206994597c13d831ec7','0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2','0x6b175474e89094c44da98b954eedeac495271d0f','0x2260fac5e5542a773aa44fbcfedf7c193bc2c599','0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0','0xae7ab96520de3a18e5e111b5eaab095312d7fe84']
    for c in json.loads((R/'catalog.json').read_text()):
        if c['name']=='L1StandardBridge':
            tokens=common+(['0x163f8c2467924be0ae7b5347228cabf260318753'] if c['product']=='worldchain' else [])
        elif c['name']=='L1OpUSDCBridgeAdapter':tokens=common[:1]
        elif c['name'] in ['wstETHEscrow','L1ERC20TokenBridge']:tokens=common[-2:]
        elif c['name']=='L1DAITokenBridge':tokens=[common[3]]
        else:continue
        for offset in range(0,len(tokens),3):
            out.append({'product':c['product'],'group':'approvals','detail_bucket':'approvals','spender':c['recipient'],
                'tokens':tokens[offset:offset+3],'pattern':'095ea7b3'+'0'*24+c['recipient'][2:],
                'source_id':f'expanded-approval-{c["product"]}-{c["recipient"]}-{offset}',
                'identity_sources':c['identity_sources'],'success_only':False})
    save(R/'supplement-catalog.json',out)
    return out

def get(s):
    parts=['time(2026-03-15..2026-09-14)',f'input_hex(^{s["pattern"]})']
    if s['success_only']:parts.append('failed(false)')
    if 'tokens' in s:parts.append(',or,'.join(f'recipient({t})' for t in s['tokens']))
    else:parts.append(f'recipient({s["recipient"]})')
    query=','.join(parts); agg='date,recipient,count(),sum(gas_used)' if 'tokens' in s else 'date,count(),sum(gas_used)'
    url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':query,'a':agg,'limit':10000})
    raw_path=R/'raw-supplement'/(s['source_id']+'.json');obj,raw=fetch(url,raw_path)
    assert obj['context']['total_rows']==len(obj['data']) and len(obj['data'])<10000
    normalized={(r['date'],r.get('recipient','')):[int(r['sum(gas_used)']),int(r['count()'])] for r in obj['data']}
    regex=re.compile('^'+s['pattern'].replace('_','.'))
    matches=[r for r in CORRECTIONS if r['recipient'] in s.get('tokens',[s.get('recipient')]) and regex.match(r['input_hex']) and (not s['success_only'] or not r['failed'])]
    removed=[]
    if 'ETH4' in obj['context'].get('servers',''):
        for r in matches:
            key=(r['date'],r['recipient'] if 'tokens' in s else '')
            assert key in normalized
            normalized[key][0]-=r['gas_used'];normalized[key][1]-=1;removed.append(r['hash'])
    rows=[]
    for (date,token),(gas,tx) in sorted(normalized.items()):
        assert gas>=0 and tx>=0 and (gas==0)==(tx==0)
        if tx:rows.append({'product':s['product'],'date':date,'bucket':s['detail_bucket'],'gas_used':gas,'tx_count':tx,'source_id':s['source_id'],**({'token':token} if token else {})})
    manifest={**s,'filter':query,'url':url,'raw_file':str(raw_path.relative_to(R)),'sha256':hashlib.sha256(raw).hexdigest(),
        'context':obj['context'],'original_gas_used':sum(r['sum(gas_used)'] for r in obj['data']),
        'gas_used':sum(r['gas_used'] for r in rows),'tx_count':sum(r['tx_count'] for r in rows),
        'provider_duplicate_hashes_removed':removed,'period_complete':True}
    save(R/'supplement-manifests'/(s['source_id']+'.json'),manifest)
    save(R/'supplement-series'/(s['source_id']+'.json'),rows)
    print(json.dumps({'source':s['source_id'],'tx':manifest['tx_count'],'gas':manifest['gas_used']}),flush=True)

if __name__=='__main__':
    errors=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(get,s):s for s in sources()}
        for f in as_completed(futures):
            try:f.result()
            except Exception as e:errors.append({'source_id':futures[f]['source_id'],'error':str(e)})
    save(R/'supplement-errors.json',errors);assert not errors,errors
