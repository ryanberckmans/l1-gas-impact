"""Canonical checks for observed account-index discrepancies; bounded to 16 blocks.

Retains both providers' original evidence. Does not decide publication acceptance.
"""
from pathlib import Path
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from acquire_refresh import R, fetch, save, counters
from verify_refresh import canonical, conflict_jobs, rpc, API

def main():
    previous=json.loads((R/'canonical-extra.json').read_text()) if (R/'canonical-extra.json').exists() else {}
    assessment=json.loads((R/'discrepancy-assessment.json').read_text())
    blocks={(s['address'],b) for s in assessment['results'] for b in s.get('mismatched_blocks',{})}
    assert len(blocks)<=16,'Disputed-block budget exceeded'
    records=previous.get('blockchair_records',[]);provenance=previous.get('provenance',[]);hashes=set()
    for address,block in sorted(blocks):
        u='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':f'block_id({block}),recipient({address})','limit':100})
        obj,prov=fetch(u,R/'disputed-blocks'/f'{address}-{block}-transactions.json.gz')
        assert len(obj['data'])==obj['context']['total_rows'],'Disputed block requires explicit pagination review'
        records.extend(obj['data']);provenance.append(prov)
        hashes.update(t['hash'] for t in obj['data'])
    for s in assessment['results']:
        hashes.update(t['hash'] for t in s.get('local_records',[]) if str(t['block_number']) in s.get('mismatched_blocks',{}))
    old=json.loads((R/'canonical-run.json').read_text())
    hashes.update(set(conflict_jobs())-{r['hash'] for r in old['results']})
    hashes-={r['hash'] for r in previous.get('results',[])}|{r['hash'] for r in previous.get('rejected_noncanonical',[])}
    assert len(hashes)<=100,'Canonical follow-up budget exceeded'
    results=previous.get('results',[]);errors=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(canonical,h):h for h in sorted(hashes)}
        for f in as_completed(futures):
            try:results.append(f.result())
            except Exception as e:errors.append({'hash':futures[f],'error':str(e)})
    rejected=previous.get('rejected_noncanonical',[]);remaining=[]
    local_by_hash={t['hash']:t for s in assessment['results'] for t in s.get('local_records',[])}
    for error in errors:
        h=error['hash'];receipt_path=R/'canonical'/(h+'-receipt.json')
        if h not in local_by_hash or not receipt_path.exists() or json.loads(receipt_path.read_text()).get('result','missing') is not None:
            remaining.append(error);continue
        block=local_by_hash[h]['block_number']
        b=rpc('eth_getBlockByNumber',{'tag':hex(block),'boolean':'false'},R/'canonical'/(h+'-claimed-block.json'))
        obj,prov=fetch(API+urlencode({'module':'proxy','action':'eth_getTransactionByHash','txhash':h}),R/'canonical'/(h+'-transaction.json'))
        if h not in b['transactions'] and obj.get('result','missing') is None:
            rejected.append({'hash':h,'claimed_block':block,'canonical_block_hash':b['hash'],'reason':'No canonical receipt or transaction; absent from canonical claimed block','transaction_provenance':prov})
        else:remaining.append(error)
    errors=remaining
    save(R/'canonical-extra.json',{'results':results,'errors':errors,'rejected_noncanonical':rejected,'blockchair_records':records,'provenance':provenance,'request_counts':counters})
    print(json.dumps({'checked':len(results),'errors':errors,'requests':counters}),flush=True)
    assert not errors

if __name__=='__main__':main()
