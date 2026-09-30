"""Retrieve complete matching supplemental transactions and verify ABI attribution."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from collections import defaultdict
from datetime import datetime,timezone
import json,re,sys,csv,gzip
from eth_abi import decode,encode
from acquire_expansion import R,fetch,save

def decoded(types,raw):
    v=decode(types,raw);assert raw.startswith(encode(types,v)),'Noncanonical ABI';return v

def verify(s):
    if not s['tx_count']:return {'source_id':s['source_id'],'transactions':0,'accepted':0,'gas_used':0,'raw_sources':[],'excluded':[]}
    rows={};pages=[]
    for offset in range(0,10000,100):
        url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':s['filter'],'s':'id(desc)','limit':100,'offset':offset})
        path=R/'raw-supplement-transactions'/f'{s["source_id"]}-{offset}.json.gz'
        obj,raw=fetch(url,path)
        pages.append({'url':url,'file':str(path.relative_to(R)),'rows':len(obj['data'])})
        for r in obj['data']:
            if r['hash'] in rows:assert r==rows[r['hash']]
            rows[r['hash']]=r
        # The provider may collapse duplicate indexed rows inside a page.
        # A short returned page is not end-of-query when pre_rows still fills it.
        if offset+obj['context'].get('pre_rows',len(obj['data']))>=obj['context']['total_rows']:break
    else:raise AssertionError('Raw query pagination did not reach its end')
    assert len(rows)==s['tx_count'] and sum(r['gas_used'] for r in rows.values())==s['gas_used'],('Supplemental receipt reconciliation',s['source_id'],len(rows),s['tx_count'])
    accepted=[];excluded=[]
    for r in rows.values():
        try:
            assert re.match('^'+s['pattern'].replace('_','.'),r['input_hex'])
            raw=bytes.fromhex(r['input_hex'][8:])
            if s['group']=='approvals':
                assert r['recipient'] in s['tokens'];args=decoded(['address','uint256'],raw);assert args[0]==s['spender']
            else:
                assert r['recipient']==s['recipient']
                types=s['signature'].split('(',1)[1][:-1].split(',');args=decoded(types,raw)
                if s['group']=='across':assert args[s['chain_word']]==s['domain']
                elif s['direction']=='burn':assert args[1]==s['domain']
                else:
                    assert not r['failed'];message=args[0]
                    assert int.from_bytes(message[4:8],'big')==s['domain'] and int.from_bytes(message[8:12],'big')==0
                    version=int.from_bytes(message[:4],'big');assert version==int(s['version'][1:])-1
                    offset=52 if version==0 else 76
                    recipient='0x'+message[offset+12:offset+32].hex()
                    expected='0xbd3fa81b58ba92a82136038b25adec7066af3155' if version==0 else '0x28b5a0e9c621a5badaa536219b3a228c8168cf5d'
                    assert recipient==expected,'Authenticated message to non-token target'
        except Exception as e:
            excluded.append({'hash':r['hash'],'gas_used':r['gas_used'],'reason':str(e) or type(e).__name__});continue
        accepted.append({'date':r['date'],'product':s['product'],'transaction_hash':r['hash'],'block_number':r['block_id'],
            'gas_used':r['gas_used'],'sender':r['sender'],'recipient':r['recipient'],'activity':s['detail_bucket'],
            'source_id':s['source_id'],'selector':'0x'+r['input_hex'][:8],'status':'failed' if r['failed'] else 'success'})
    path=R/'supplement-verified'/(s['source_id']+'.json');save(path,accepted)
    manifest={'source_id':s['source_id'],'transactions':len(rows),'accepted':len(accepted),'gas_used':sum(r['gas_used'] for r in accepted),'raw_sources':pages,'excluded':excluded,'raw_matches_corrected_aggregate':True}
    print(json.dumps({k:manifest[k] for k in ['source_id','transactions','accepted']}),flush=True)
    return manifest

if __name__=='__main__':
    manifest=[];errors=[]
    sources=[json.loads(p.read_text()) for p in sorted((R/'supplement-manifests').glob('*.json'))]
    with ThreadPoolExecutor(max_workers=6) as pool:
        tasks={pool.submit(verify,s):s for s in sources}
        for f in as_completed(tasks):
            try:manifest.append(f.result())
            except Exception as e:errors.append({'source':tasks[f]['source_id'],'error':str(e)})
    save(R/'supplement-verification.json',manifest);save(R/'supplement-verification-errors.json',errors)
    assert not errors,errors
