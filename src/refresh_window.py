"""Checkpoint acquisition for a new snapshot, without accepting or publishing it.

Reuse the prior reviewed attribution catalogues. Every provider request and
response stays in the dated research directory; staging is a separate action.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from urllib.parse import parse_qs, urlencode, urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'extend', 'collect', 'events', 'supplements', 'canonical', 'classify'])
    parser.add_argument('--research-dir', type=Path, required=True)
    parser.add_argument('--prior-refresh', type=Path, required=True)
    parser.add_argument('--prior-coverage', type=Path, required=True)
    parser.add_argument('--baseline-research', type=Path, required=True)
    parser.add_argument('--through', type=date.fromisoformat, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    research = args.research_dir.resolve()
    research.mkdir(parents=True, exist_ok=True)
    sys.argv = [__file__, str(research), str(args.baseline_research.resolve())]
    import acquire_refresh as acquisition

    def read(path):
        return json.loads(path.read_text())

    baseline_path = research / 'baseline/data/inputs.json'
    config = read(baseline_path if baseline_path.exists() else root / 'data/inputs.json')
    delta = date.fromisoformat(config['end_exclusive'])
    end = args.through + timedelta(days=1)
    start = end - timedelta(days=184)
    assert delta < end and start < delta, 'Refresh must extend the baseline with overlap'
    request = {'start_inclusive': str(delta), 'delta_start': str(delta),
               'end_exclusive': str(end), 'snapshot_start': str(start),
               'baseline_inputs_sha256': hashlib.sha256(
                   (baseline_path if baseline_path.exists() else root / 'data/inputs.json').read_bytes()).hexdigest()}
    window_path = research / 'window.json'
    if window_path.exists():
        window = read(window_path)
        assert all(window[k] == v for k, v in request.items()), 'Research directory belongs to another snapshot'
    elif args.mode != 'prepare':
        raise ValueError('Prepare this dated research directory before collecting')

    def boundary(day, name, closest, previous_second=False):
        timestamp = int(datetime.combine(day, time(), timezone.utc).timestamp()) - int(previous_second)
        query = {'module': 'block', 'action': 'getblocknobytime',
                 'timestamp': timestamp, 'closest': closest}
        data, evidence = acquisition.fetch(
            'https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?' + urlencode(query),
            research / (name + '.json'))
        return int(data['result']), evidence

    if args.mode == 'prepare':
        if (research / 'account-catalog.json').exists():
            print(json.dumps({'prepared': request, 'reused_existing_catalog': True}))
            return
        if not baseline_path.exists():
            shutil.copytree(root / 'data', research / 'baseline/data')
            shutil.copytree(root / 'dist/data', research / 'baseline/public-data')
        low, low_proof = boundary(delta, 'start-boundary', 'after')
        high, high_proof = boundary(end, 'boundary', 'before', True)
        full_low, full_proof = boundary(start, 'snapshot-start-boundary', 'after')
        window = {**request, 'start_block': low, 'end_block': high,
                  'snapshot_start_block': full_low,
                  'boundaries': [low_proof, high_proof, full_proof]}
        acquisition.save(window_path, window)
        core_path = args.prior_refresh / 'core-account-catalog.json'
        core_accounts = read(core_path if core_path.exists() else args.prior_refresh / 'account-catalog.json')
        # The preceding refresh kept newly introduced exclusive recipients in
        # a separate catalogue. They still require account receipt acquisition.
        core_by_address = {s['address']: s for s in core_accounts}
        for source in read(args.prior_refresh / 'new-catalog.json'):
            address = source['recipient']
            core_by_address.setdefault(address, {'address': address,
                'product': source['product'], 'name': source['name']})
        core_accounts = list(core_by_address.values())
        coverage = read(args.prior_coverage / 'catalog.json')
        # Previously accepted accounts now need only the new interval. Preserve
        # role activation bounds, but retire the previous acquisition window.
        for source in core_accounts + coverage:
            source.pop('start_inclusive', None)
            source.pop('start_block', None)
        accounts = {s['address']: s for s in core_accounts}
        assert not set(accounts).intersection(s['address'] for s in coverage), 'Overlapping core and coverage accounts'
        accounts.update({s['address']: s for s in coverage})
        aggregates = read(args.prior_refresh / 'aggregate-catalog.json')
        aggregates = [s for s in aggregates if s['group'] not in ['cctp', 'across', 'coverage'] and s['product'] != 'solana']
        aggregates += read(args.prior_refresh / 'new-catalog.json')
        aggregates = list({s['source_id']: s for s in aggregates}.values())
        for s in aggregates:
            s.pop('start_inclusive', None)
            s.pop('start_block', None)
            query = {k: v[0] for k, v in parse_qs(urlparse(s['url']).query).items()}
            query['q'], replacements = re.subn(r'time\([^)]*\)', f'time({delta}..{args.through})', query['q'])
            assert replacements == 1
            s['url'] = 'https://api.blockchair.com/ethereum/transactions?' + urlencode(query)
        for s in coverage:
            query = {'q': f'time({delta}..{args.through}),recipient({s["address"]})',
                     'a': 'date,count(),sum(gas_used)', 'limit': 10000}
            aggregates.append({**s, 'source_id': 'coverage-' + s['address'], 'group': 'coverage',
                               'url': 'https://api.blockchair.com/ethereum/transactions?' + urlencode(query)})
        assert len(aggregates) == len({s['source_id'] for s in aggregates})
        acquisition.save(research / 'aggregate-catalog.json', aggregates)
        acquisition.save(research / 'account-catalog.json', list(accounts.values()))
        acquisition.save(research / 'core-account-catalog.json', core_accounts)
        prior_core = args.prior_refresh / 'core-catalog.json'
        acquisition.save(research / 'core-catalog.json', read(
            prior_core if prior_core.exists() else args.prior_refresh / 'catalog.json'))
        acquisition.save(research / 'catalog.json', coverage)
        new_ids = {s['source_id'] for s in read(args.prior_refresh / 'new-catalog.json')}
        acquisition.save(research / 'new-catalog.json', [s for s in aggregates if s['source_id'] in new_ids])
        for path in args.prior_refresh.glob('*-discovered.json'):
            shutil.copy2(path, research / path.name)
        for name in ['discovery', 'verified-abis']:
            shutil.copytree(args.prior_coverage / name, research / name, dirs_exist_ok=True)
        shutil.copy2(args.prior_coverage / 'zk-chain-identities.json', research / 'zk-chain-identities.json')
        print(json.dumps({'prepared': request, 'accounts': len(accounts), 'aggregate_queries': len(aggregates)}), flush=True)
        return

    # The optional supplement phase uses Blockchair while receipt acquisition
    # uses Routescan. Its separate checkpoint prevents cross-process clobbering.
    usage_path = research / ('provider-usage-supplements.json' if args.mode == 'supplements' else 'provider-usage.json')
    for checkpoint in [research / 'provider-usage.json', research / 'provider-usage-supplements.json']:
        if checkpoint.exists():
            for host, count in read(checkpoint)['requests'].items():
                acquisition.counters[host] = max(acquisition.counters.get(host, 0), count)

    if args.mode == 'extend':
        additions = read(root / 'data/cohort-updates.json')
        assert additions['classification_as_of'] <= str(args.through)
        existing = {s['address']: s for s in read(research / 'account-catalog.json')}
        coverage = {s['address']: s for s in read(research / 'catalog.json')}
        aggregates = {s['source_id']: s for s in read(research / 'aggregate-catalog.json')}
        sources = []
        for original in additions['accounts']:
            if original['address'] in existing:
                s = existing[original['address']]
                assert all(s.get(k) == v for k, v in original.items()), 'Cannot change an existing acquisition cohort'
            else:
                s = {**original, 'start_inclusive': str(start), 'start_block': window['snapshot_start_block']}
            existing[s['address']] = coverage[s['address']] = s
            for role in s['roles']:
                discovery = role['discovery']
                project = discovery.removesuffix('-current-discovered.json')
                url = f'https://raw.githubusercontent.com/l2beat/l2beat/{additions["revision"]}/packages/config/src/projects/{project}/discovered.json'
                _, proof = acquisition.fetch(url, research / 'discovery' / discovery)
                sources.append(proof)
            sid = 'coverage-' + s['address']
            query = {'q': f'time({s.get("start_inclusive", str(delta))}..{args.through}),recipient({s["address"]})',
                     'a': 'date,count(),sum(gas_used)', 'limit': 10000}
            aggregates[sid] = {**s, 'source_id': sid, 'group': 'coverage',
                               'url': 'https://api.blockchair.com/ethereum/transactions?' + urlencode(query)}
        acquisition.save(research / 'account-catalog.json', list(existing.values()))
        acquisition.save(research / 'catalog.json', list(coverage.values()))
        acquisition.save(research / 'aggregate-catalog.json', list(aggregates.values()))
        core = read(research / 'core-catalog.json')
        for change in additions.get('sender_updates', []):
            matches = [s for s in core if s['recipient'] == change['recipient'] and s['product'] == change['product']]
            assert len(matches) == 1 and matches[0]['kind'] == 'batch'
            matches[0].update(senders=change['senders'], sender_intervals=change['sender_intervals'])
        acquisition.save(research / 'core-catalog.json', core)
        acquisition.save(research / 'cohort-updates.json', {**additions, 'sources': sources})
        acquisition.save(usage_path, {'requests': dict(acquisition.counters)})
        print(json.dumps({'extended_accounts': len(additions['accounts']), 'accounts': len(existing)}))
        return

    def parallel(jobs, worker, max_workers=3):
        results, errors = [], []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(worker, s): s for s in jobs}
            for future in as_completed(futures):
                item = futures[future]
                identity = item.get('source_id', item.get('address')) if isinstance(item, dict) else item
                try:
                    results.append({'source': identity, 'result': future.result()})
                except Exception as exc:
                    error = {'source': identity, 'error': str(exc)}
                    errors.append(error)
                    print(json.dumps(error), flush=True)
                acquisition.save(usage_path, {'requests': dict(acquisition.counters)})
                if (len(results) + len(errors)) % 25 == 0:
                    print(json.dumps({'completed': len(results), 'errors': len(errors),
                                      'total': len(jobs)}), flush=True)
        return results, errors

    if args.mode == 'collect':
        aggregates = read(research / 'aggregate-catalog.json')
        accounts = read(research / 'account-catalog.json')
        results, errors = parallel(aggregates, acquisition.aggregate)
        acquisition.save(research / 'aggregates-run.json', {'results': results, 'errors': errors})
        assert not errors, errors
        pending = [s for s in accounts if not (research / 'receipt-manifests' / (s['address'] + '.json')).exists()]
        results, errors = parallel(pending, lambda s: acquisition.receipts(s, window['end_block']))
        acquisition.save(research / 'receipts-run.json', {'results': results, 'errors': errors})
        assert not errors, errors
        print(json.dumps({'collected_accounts': len(accounts), 'aggregate_queries': len(aggregates),
                          'provider_requests': acquisition.counters}), flush=True)
        return

    if args.mode == 'events':
        for name in ['deposit', 'withdraw_claim']:
            prior = read(args.prior_refresh / 'lighter-events' / (name + '-manifest.json'))
            query = {k: v[0] for k, v in parse_qs(urlparse(prior['pages'][0]['url']).query).items()}
            low = window['snapshot_start_block']
            events, proofs = {}, []
            for page in range(100):
                query.update(fromBlock=low, toBlock=window['end_block'], page=1, offset=10000)
                obj, proof = acquisition.fetch(
                    'https://api.routescan.io/v2/network/mainnet/evm/1/etherscan/api?' + urlencode(query),
                    research / 'lighter-events' / (name + '-' + str(low) + '.json.gz'))
                rows = obj['result']
                assert isinstance(rows, list)
                proofs.append(proof)
                for row in rows:
                    assert not row.get('removed', False)
                    key = (row['transactionHash'], row['logIndex'])
                    if key in events:
                        assert events[key] == row, 'Conflicting log pagination overlap'
                    events[key] = row
                acquisition.save(usage_path, {'requests': dict(acquisition.counters)})
                if len(rows) < 10000:
                    break
                high = max(int(row['blockNumber'], 16) for row in rows)
                assert high > low, 'Single-block log overflow requires explicit continuation'
                low = high
            else:
                raise AssertionError('Event pagination budget reached')
            acquisition.save(research / 'lighter-events' / (name + '-logs.json'), list(events.values()))
            acquisition.save(research / 'lighter-events' / (name + '-manifest.json'), {
                'pages': proofs, 'events': len(events), 'complete': True,
                'parents': len({r['transactionHash'] for r in events.values()}),
                'start_inclusive': window['snapshot_start'], 'end_exclusive': window['end_exclusive']})
        print(json.dumps({'event_populations': 2, 'provider_requests': acquisition.counters}), flush=True)
        return

    import verify_refresh
    if args.mode != 'supplements':
        jobs = verify_refresh.conflict_jobs()
        samples = research / 'required-canonical-samples.json'
        if samples.exists():
            jobs = sorted(set(jobs) | set(read(samples)))
        # Small RPC responses are latency-bound. This does not raise the shared
        # two-request-per-second transport limit or cumulative provider budget.
        results, errors = parallel(jobs, verify_refresh.canonical, max_workers=12)
        canonical = {'results': [r['result'] for r in results], 'errors': errors}
        acquisition.save(research / 'canonical-verification.json', canonical)
        acquisition.save(research / 'canonical-run.json', canonical)
        assert not errors, errors
        if args.mode == 'canonical':
            print(json.dumps({'canonical_receipts': len(results), 'provider_requests': acquisition.counters}), flush=True)
            return
        import classify_coverage
        classify_coverage.main()
        import classify_expansion
        classify_expansion.CAT = read(research / 'core-catalog.json')
        import classify_refresh
        classify_refresh.main()
    else:
        aggregates_run = read(research / 'aggregates-run.json')
        assert not aggregates_run['errors'] and len(aggregates_run['results']) == len(read(research / 'aggregate-catalog.json'))
    jobs = [read(p) for p in (research / 'aggregate-manifests').glob('*.json')]
    jobs = [s for s in jobs if s['group'] == 'approvals']

    def supplement(source):
        if source['tx_count'] < 10000:
            return verify_refresh.supplement(source)
        # Partition the independently observed daily population before hitting
        # the provider's 10,000-result offset window. No date may be omitted.
        rows = read(research / source['file'])['data']
        daily = {}
        for row in rows:
            daily[row['date']] = daily.get(row['date'], 0) + row['count()']
        partitions, current, count = [], [], 0
        for day, transactions in sorted(daily.items()):
            assert transactions < 9000, 'A single-day supplement requires finer partitioning'
            if count + transactions >= 9000:
                partitions.append(current); current, count = [], 0
            current.append(day); count += transactions
        if current:
            partitions.append(current)
        accepted, reports = [], []
        for days in partitions:
            expected = [row for row in rows if row['date'] in days]
            sid = source['source_id'] + '-part-' + days[0]
            query = {k: v[0] for k, v in parse_qs(urlparse(source['url']).query).items()}
            query['q'] = re.sub(r'time\([^)]*\)', f'time({days[0]}..{days[-1]})', query['q'])
            part = {**source, 'source_id': sid, 'expected_daily': expected,
                    'tx_count': sum(row['count()'] for row in expected),
                    'url': 'https://api.blockchair.com/ethereum/transactions?' + urlencode(query)}
            reports.append(verify_refresh.supplement(part))
            accepted.extend(read(research / 'supplement-verified' / (sid + '.json')))
        assert sum(item['transactions'] for item in reports) == source['tx_count']
        assert len(accepted) == len({row['transaction_hash'] for row in accepted})
        for row in accepted:
            row['source_id'] = source['source_id']
        acquisition.save(research / 'supplement-verified' / (source['source_id'] + '.json'), accepted)
        return {'source_id': source['source_id'], 'transactions': source['tx_count'],
                'accepted': len(accepted), 'gas_used': sum(row['gas_used'] for row in accepted),
                'raw_sources': [p for report in reports for p in report['raw_sources']],
                'excluded': [e for report in reports for e in report['excluded']],
                'daily_count_and_gas_match': True, 'date_partitions': partitions}

    results, errors = parallel(jobs, supplement)
    acquisition.save(research / 'supplement-verification.json', {'results': [r['result'] for r in results], 'errors': errors})
    assert not errors, errors
    if args.mode == 'supplements':
        return
    import sample_refresh
    sample_refresh.main()
    acquisition.save(usage_path, {'requests': dict(acquisition.counters)})


if __name__ == '__main__':
    main()
