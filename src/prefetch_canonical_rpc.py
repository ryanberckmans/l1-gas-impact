"""Prefetch canonical RPC evidence in bounded batches; acceptance stays separate.

The ordinary verifier rechecks these cache files before classification. Existing
files are never overwritten, so this can accompany a slow canonical verifier.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from urllib.request import Request, urlopen

ENDPOINT = 'https://ethereum-rpc.publicnode.com'
BATCH_SIZE = 100
MAX_CALLS = 5000
MAX_SECONDS = 1800
SECONDS_PER_CALL = 0.2  # Local operating choice, not an advertised provider limit.


def checked_batch(requests, responses, allow_missing_receipts=False):
    assert isinstance(responses, list), 'Expected a JSON-RPC batch response'
    expected = {r['id'] for r in requests}
    assert len(expected) == len(requests)
    assert len(responses) == len(expected), 'Missing or extra RPC responses'
    actual = {r.get('id') for r in responses}
    assert actual == expected, 'Mismatched RPC response IDs'
    methods = {r['id']: r['method'] for r in requests}
    assert all(r.get('jsonrpc') == '2.0' and 'error' not in r and 'result' in r and
               (r['result'] is not None or
                (allow_missing_receipts and methods[r['id']] == 'eth_getTransactionReceipt'))
               for r in responses), 'RPC errors or missing canonical data'
    return {r['id']: r for r in responses}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('research_dir', type=Path)
    parser.add_argument('baseline_research', type=Path)
    args = parser.parse_args()
    root = args.research_dir.resolve()
    import sys
    sys.argv = [__file__, str(root), str(args.baseline_research.resolve())]
    from verify_refresh import canonical, conflict_jobs
    window = json.loads((root / 'window.json').read_text())
    jobs = set(conflict_jobs())
    samples = root / 'required-canonical-samples.json'
    if samples.exists():
        jobs.update(json.loads(samples.read_text()))
    jobs = sorted(jobs, reverse=True)
    raw_dir, cache_dir = root / 'canonical-rpc-raw', root / 'canonical'
    raw_dir.mkdir(exist_ok=True); cache_dir.mkdir(exist_ok=True)
    state_path = root / 'canonical-rpc-prefetch.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {
        'provider': ENDPOINT, 'logical_calls': 0, 'http_requests': 0, 'complete': False}
    assert state['provider'] == ENDPOINT
    assert not state.get('stopped_reason'), 'Resolve the recorded provider stop before resuming'
    started, next_request, sequence = time.monotonic(), 0.0, state['logical_calls']
    verified = set()
    missing_receipts = set(state.get('unavailable_receipts', []))

    def checkpoint():
        tmp = state_path.with_suffix('.partial')
        tmp.write_text(json.dumps(state, indent=2) + '\n'); tmp.replace(state_path)

    def fetch_batch(calls):
        nonlocal sequence, next_request
        assert 0 < len(calls) <= BATCH_SIZE
        assert time.monotonic() - started < MAX_SECONDS, 'Prefetch time budget reached'
        assert state['logical_calls'] + len(calls) <= MAX_CALLS, 'Prefetch call budget reached'
        assert shutil.disk_usage(root).free >= 3_000_000_000, 'Prefetch disk reserve reached'
        requests = []
        for method, params in calls:
            sequence += 1
            requests.append({'jsonrpc': '2.0', 'id': sequence, 'method': method, 'params': params})
        delay = max(0.0, next_request - time.monotonic())
        if delay:
            time.sleep(delay)
        next_request = time.monotonic() + len(calls) * SECONDS_PER_CALL
        state['logical_calls'] += len(calls); state['http_requests'] += 1; checkpoint()
        payload = json.dumps(requests, separators=(',', ':')).encode()
        request = Request(ENDPOINT, data=payload, headers={
            'Content-Type': 'application/json', 'User-Agent': 'L1-Gas-Impact-Research/1.0'})
        # A refusal is terminal. No automatic retries, endpoint rotation or rate-limit evasion.
        with urlopen(request, timeout=45) as response:
            assert response.geturl().rstrip('/') == ENDPOINT
            raw = response.read(80_000_001)
        assert len(raw) <= 80_000_000, 'RPC response size budget reached'
        responses = json.loads(raw)
        filename = hashlib.sha256(payload).hexdigest() + '.json.gz'
        evidence = {'provider': ENDPOINT, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'requests': requests, 'responses': responses}
        (raw_dir / filename).write_bytes(gzip.compress(json.dumps(evidence).encode(), mtime=0))
        indexed = checked_batch(requests, responses, allow_missing_receipts=True)
        return [{**indexed[r['id']], 'provenance': {
                    'provider': ENDPOINT, 'method': r['method'], 'params': r['params'],
                    'batch': str((raw_dir / filename).relative_to(root)),
                    'batch_sha256': hashlib.sha256((raw_dir / filename).read_bytes()).hexdigest()}}
                for r in requests]

    def cache(path, value):
        # link() publishes atomically only if no verifier has already filled it.
        temp = path.with_name(path.name + '.rpc-prefetch')
        temp.write_text(json.dumps(value, separators=(',', ':')) + '\n')
        try:
            os.link(temp, path)
        except FileExistsError:
            pass
        finally:
            temp.unlink()

    control = fetch_batch([('eth_chainId', []), ('eth_blockNumber', [])])
    assert int(control[0]['result'], 16) == 1
    assert int(control[1]['result'], 16) >= window['end_block']
    for offset in range(0, len(jobs), 100):
        group = jobs[offset:offset + 100]
        pending = []
        for h in group:
            for kind, method in [('receipt', 'eth_getTransactionReceipt'),
                                 ('transaction', 'eth_getTransactionByHash')]:
                path = cache_dir / (h + '-' + kind + '.json')
                if not path.exists() and not (kind == 'receipt' and h in missing_receipts):
                    pending.append((path, method, [h]))
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            results = fetch_batch([(m, p) for _, m, p in batch])
            for (path, _, _), result in zip(batch, results):
                if result['result'] is None:
                    missing_receipts.add(result['provenance']['params'][0])
                else:
                    cache(path, result)
            state['unavailable_receipts'] = sorted(missing_receipts)
            checkpoint()
        blocks = {}
        for h in group:
            path = cache_dir / (h + '-block.json')
            if not path.exists():
                transaction = json.loads((cache_dir / (h + '-transaction.json')).read_text())['result']
                blocks.setdefault(transaction['blockNumber'], []).append(path)
        numbers = sorted(blocks)
        for start in range(0, len(numbers), BATCH_SIZE):
            batch = numbers[start:start + BATCH_SIZE]
            results = fetch_batch([('eth_getBlockByNumber', [n, False]) for n in batch])
            for number, result in zip(batch, results):
                assert result['result']['number'] == number
                for path in blocks[number]:
                    cache(path, result)
        for h in group:
            if all((cache_dir / (h + '-' + kind + '.json')).exists()
                   for kind in ['receipt', 'block', 'transaction']):
                canonical(h)  # Same acceptance checks, never accept partial evidence.
                verified.add(h)
        state['verified_transactions'] = len(verified)
        checkpoint()
        print(json.dumps({'canonical_prefetched': len(verified), 'total': len(jobs),
                          'logical_calls': state['logical_calls'], 'http_requests': state['http_requests']}), flush=True)
    state.update(complete=True, verified_transactions=len(verified),
                 scope='Prefetch completed; unavailable receipts remain for the ordinary verifier. Only complete triples receive canonical checks. Classification and release acceptance are separate.')
    checkpoint()


if __name__ == '__main__':
    main()
