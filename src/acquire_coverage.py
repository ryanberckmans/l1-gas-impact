"""Bounded full-window account acquisition for the coverage expansion.

Usage: acquire_coverage.py RESEARCH_DIR BASELINE_RESEARCH [collect|canonical]
Reuses the tested transport, immutable response cache, three-worker ceiling,
per-provider request caps, 45-minute budget, and terminal refusal handling.
Acquisition does not authorize inclusion.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
import json, sys
import acquire_refresh as A

def main():
    catalog=json.loads((A.R/'catalog.json').read_text())
    mode=sys.argv[3] if len(sys.argv)>3 else 'collect'
    A.DELTA=A.START
    start=json.loads((A.R/'start-boundary.json').read_text())
    A.LOW_BLOCK=int(start['result'])
    high=int(json.loads((A.R/'boundary.json').read_text())['result'])
    errors=[]
    if mode=='canonical':
        from verify_refresh import canonical,conflict_jobs
        jobs=conflict_jobs();task=canonical
    else:
        jobs=catalog
        def task(s):
            query=f'time({A.START}..2026-09-27),recipient({s["address"]})'
            url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':query,'a':'date,count(),sum(gas_used)','limit':10000})
            A.aggregate({**s,'source_id':'coverage-'+s['address'],'url':url})
            if not (A.R/'receipt-manifests'/(s['address']+'.json')).exists():
                A.receipts(s,high)
            return {'address':s['address'],'complete':True}
    results=[]
    with ThreadPoolExecutor(max_workers=int(sys.argv[4]) if len(sys.argv)>4 else 3) as pool:
        futures={pool.submit(task,s):s for s in jobs}
        for f in as_completed(futures):
            try:results.append(f.result())
            except Exception as e:
                err={'source':futures[f],'error':str(e)}
                errors.append(err);print(json.dumps(err),flush=True)
    A.save(A.R/(mode+'-run.json'),{'errors':errors,'results':results,'request_counts':A.counters,'start_inclusive':A.START,'end_exclusive':A.END})
    assert not errors,errors

if __name__=='__main__':main()
