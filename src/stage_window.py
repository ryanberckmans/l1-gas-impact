"""Stage a reconciled incremental snapshot and rebuild its detached receipt set."""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('research_dir', type=Path)
    parser.add_argument('--prior-receipts', type=Path, required=True)
    args = parser.parse_args()
    research = args.research_dir.resolve()
    window = read(research / 'window.json')
    start, delta, end = window['snapshot_start'], window['delta_start'], window['end_exclusive']
    baseline = research / 'baseline/data'
    config = read(baseline / 'inputs.json')
    assert digest(baseline / 'inputs.json') == window['baseline_inputs_sha256']
    for name in ['aggregates-run', 'receipts-run', 'canonical-verification',
                 'supplement-verification', 'sample-verification']:
        assert not read(research / (name + '.json'))['errors'], name
    assert not read(research / 'daily-reconciliation.json')['mismatches']
    classification = read(research / 'classification-verification.json')
    if (research / 'canonical-extra.json').exists():
        assert not read(research / 'canonical-extra.json')['errors']
    assert classification['complete'] and not classification['missing']
    assert (classification['start_inclusive'], classification['end_exclusive']) == (delta, end)
    coverage = read(research / 'catalog.json')
    assert {s['address'] for s in classification['sources']} == {s['address'] for s in coverage}
    for source in classification['sources']:
        assert digest(research / 'ledgers' / (source['address'] + '.jsonl.gz')) == source['ledger_sha256']
        assert digest(research / 'classified' / (source['address'] + '.jsonl.gz')) == source['classified_sha256']
    catalog = read(research / 'aggregate-catalog.json')
    manifests = {p.stem: read(p) for p in (research / 'aggregate-manifests').glob('*.json')}
    assert {s['source_id'] for s in catalog} == set(manifests)
    assert all(manifests[s['source_id']]['url'] == s['url'] for s in catalog)
    for manifest in manifests.values():
        assert manifest['complete']
        raw = (research / manifest['file']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest['sha256_uncompressed']
        response = json.loads(raw)
        assert int(response['context']['state']) >= window['end_block'], 'Provider has not indexed the cutoff'
        source_start=manifest.get('start_inclusive',delta)
        assert start<=source_start<=delta
        assert all(source_start <= row['date'] < end for row in response['data'])
    accounts = read(research / 'account-catalog.json')
    assert {s['recipient'] for s in read(research / 'new-catalog.json')} <= {s['address'] for s in accounts}
    assert all(read(research / 'receipt-manifests' / (s['address'] + '.json'))['complete'] for s in accounts)
    required_canonical = {conflict['hash'] for source in accounts
                          for conflict in read(research / 'receipt-manifests' /
                              (source['address'] + '.json')).get('unresolved_index_conflicts', [])}
    required_samples = research / 'required-canonical-samples.json'
    if required_samples.exists():
        required_canonical.update(read(required_samples))
    verified_canonical = read(research / 'canonical-verification.json')['results']
    assert {r['hash'] for r in verified_canonical} == required_canonical, 'Incomplete canonical conflict checks'
    assert len(verified_canonical) == len(required_canonical), 'Duplicate canonical checks'
    names = read(baseline / 'products.json')
    inputs, templates = {}, {}
    for entry in config['inputs']:
        assert digest(baseline / entry['path']) == entry['sha256']
        old_rows = read(baseline / entry['path'])
        inputs[entry['path']] = [r for r in old_rows if start <= r['date'] < delta]
        templates.update({r['source_id']: r for r in old_rows if 'source_id' in r})
    for s in manifests.values():
        if s['group'] not in ['eth', 'uniswap'] or (s['group'] == 'uniswap' and not s['included']):
            continue
        for row in read(research / s['file'])['data']:
            if s['group'] == 'eth':
                assert row['sum(gas_used)'] == row['count()'] * 21000
                item = {'date': row['date'], 'project': 'eth-transfers', 'bucket': 'plain-eth-transfers',
                        'tx_count': row['count()'], 'execution_gas': row['sum(gas_used)']}
            else:
                item = {'date': row['date'], 'product': 'uniswap', 'source_id': s['source_id'],
                        'bucket': templates[s['source_id']]['bucket'], 'gas_used': row['sum(gas_used)'],
                        'tx_count': row['count()']}
            inputs['inputs/' + s['group'] + '.json'].append(item)
    core = read(research / 'accepted-core.json')
    supplements = [r for s in manifests.values() if s['group'] == 'approvals'
                   for r in read(research / 'supplement-verified' / (s['source_id'] + '.json'))]
    assert len(core) + len(supplements) == len({r['transaction_hash'] for r in core + supplements})
    grouped = defaultdict(lambda: [0, 0])
    expanded = {'worldchain', 'unichain', 'op', 'ink'}
    for supplemental, rows in [(False, core), (True, supplements)]:
        for row in rows:
            p = row['product']
            assert p in names and delta <= row['date'] < end
            path = 'lighter' if p == 'lighter' else 'uniswap' if p == 'uniswap' else 'expanded' if p in expanded else 'rollups'
            if supplemental and p not in expanded:
                path = 'additional'
            template = templates.get(row['source_id'], {})
            activity = template.get('detail_bucket', template.get('bucket', row['activity']))
            value = grouped[(path, row['date'], p, row['source_id'], activity)]
            value[0] += row['gas_used']; value[1] += 1
    for (path, day, product, sid, activity), (gas, count) in grouped.items():
        inputs['inputs/' + path + '.json'].append({'date': day, 'product': product, 'source_id': sid,
                                                 'bucket': activity, 'gas_used': gas, 'tx_count': count})
    inputs['inputs/coverage.json'].extend(r for r in read(research / 'daily.json') if r['product'] in names)
    downloads = read(baseline / 'receipt-exports.json')
    receipt_dir = research / 'receipt-work'
    receipt_dir.mkdir(exist_ok=True)
    expected, observed = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for product, download in downloads.items():
        for path in download['input_paths']:
            for row in inputs[path]:
                if row['product'] == product:
                    value = expected[(product, row['date'])]
                    value[0] += row['gas_used']; value[1] += row['tx_count']
    fields = ['date', 'product', 'transaction_hash', 'block_number', 'gas_used', 'activity', 'source_id', 'selector', 'status']
    seen, lighter_hashes = set(), set()
    counts, writers, handles, files, part_counts = Counter(), {}, {}, defaultdict(list), Counter()

    def finish(product):
        if product not in handles:
            return
        handles.pop(product).close()
        path = receipt_dir / files[product][-1]['file']
        files[product][-1].update(sha256=digest(path), bytes=path.stat().st_size,
                                 transactions=part_counts[product])
        assert path.stat().st_size < 20 * 1024 * 1024

    def emit(row):
        product, day, tx = row['product'], row['date'], row['transaction_hash']
        if not start <= day < end:
            return
        assert product in downloads and tx not in seen, ('Overlapping exported receipt', product, tx)
        seen.add(tx)
        gas = int(row['gas_used'])
        assert gas >= 21000
        if product == 'lighter':
            lighter_hashes.add(tx)
        if counts[product] % 200000 == 0:
            finish(product)
            name = 'receipts-' + product + '-' + str(len(files[product]) + 1) + '.csv.gz'
            handle = io.TextIOWrapper(gzip.GzipFile(filename=str(receipt_dir / name), mode='wb', mtime=0), newline='')
            handles[product] = handle
            writers[product] = csv.DictWriter(handle, fields, extrasaction='ignore')
            writers[product].writeheader(); part_counts[product] = 0
            files[product].append({'file': name})
        writers[product].writerow(row); counts[product] += 1; part_counts[product] += 1
        observed[(product, day)][0] += gas; observed[(product, day)][1] += 1

    old_archive = read(baseline / 'receipt-archive.json')
    assert digest(args.prior_receipts) == old_archive['sha256'], 'Wrong baseline receipt archive'
    with ZipFile(args.prior_receipts) as archive:
        for product, download in downloads.items():
            for part in download['files']:
                payload = archive.read(part.get('file') or part['url'].removeprefix('/data/'))
                assert hashlib.sha256(payload).hexdigest() == part['sha256']
                with io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(payload))) as source:
                    for row in csv.DictReader(source):
                        assert row['date'] < delta
                        emit(row)
    for row in core:
        if row['product'] in downloads:
            emit(row)
    for row in supplements:
        if row['product'] in expanded:
            emit(row)
    for path in sorted((research / 'classified').glob('*.jsonl.gz')):
        with gzip.open(path, 'rt') as source:
            for line in source:
                row = json.loads(line)
                if row['product'] in downloads:
                    emit(row)
    for product in list(handles):
        finish(product)
    expected = {k: v for k, v in expected.items() if v != [0, 0]}
    assert dict(observed) == expected, 'Merged historical and new receipts do not match accepted daily totals'
    for product, download in downloads.items():
        download.update(files=files[product], transactions=counts[product],
                        gas_used=sum(v[0] for (p, _), v in observed.items() if p == product))
    coverage = {}
    for name in ['deposit', 'withdraw_claim']:
        manifest = read(research / 'lighter-events' / (name + '-manifest.json'))
        assert manifest['complete'] and (manifest['start_inclusive'], manifest['end_exclusive']) == (start, end)
        parents = set()
        for row in read(research / 'lighter-events' / (name + '-logs.json')):
            value = row['timeStamp']
            timestamp = int(value, 16) if str(value).startswith('0x') else int(value)
            day = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
            if start <= day < end:
                parents.add(row['transactionHash'])
        included = len(parents & lighter_hashes)
        coverage[name] = {'observed_parent_transactions': len(parents), 'included_parent_transactions': included,
                          'included_parent_percent': included / len(parents) * 100 if parents else 0}
    staged = research / 'staged/data'
    entries = []
    for entry in config['inputs']:
        path, rows = entry['path'], inputs[entry['path']]
        assert all(start <= r['date'] < end for r in rows)
        rows.sort(key=lambda r: (r['date'], r.get('product', ''), r.get('source_id', ''), r.get('bucket', ''), r.get('token', '')))
        save(staged / path, rows); entries.append({**entry, 'sha256': digest(staged / path)})
    proof = {'complete': True, 'start_inclusive': start, 'end_exclusive': end, 'products': list(names),
             'baseline_inputs_sha256': window['baseline_inputs_sha256'], 'retained_overlap': [start, delta],
             'new_observations': [delta, end], 'input_sha256': {e['path']: e['sha256'] for e in entries},
             'full_window_backfilled_accounts': [s['address'] for s in accounts if s.get('start_inclusive') == start],
             'reconciled_accounts': len(accounts), 'aggregate_queries': len(catalog),
             'exported_receipts': dict(counts), 'hashes_unique_across_receipt_exports': True,
             'verification_sha256': {p: digest(research / (p + '.json')) for p in [
                 'classification-verification', 'canonical-verification', 'daily-reconciliation',
                 'supplement-verification', 'sample-verification', 'canonical-extra',
                 'discrepancy-assessment', 'boundary-review'] if (research / (p + '.json')).exists()}}
    save(staged / 'snapshot-verification.json', proof)
    save(staged / 'inputs.json', {**config, 'start_inclusive': start, 'end_exclusive': end, 'inputs': entries,
         'verification': {'path': 'snapshot-verification.json', 'sha256': digest(staged / 'snapshot-verification.json')}})
    save(staged / 'receipt-exports.json', downloads)
    save(staged / 'lighter-coverage.json', {'start_inclusive': start, 'end_exclusive': end,
         'unit': 'Parent transaction coverage, not gas coverage', 'populations': coverage})
    for path in staged.rglob('*.json'):
        target = ROOT / 'data' / path.relative_to(staged)
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(path, target)
    save(research / 'staging-result.json', {'products': len(names), 'receipts': dict(counts),
         'start_inclusive': start, 'end_exclusive': end, 'merged_receipts_reconciled': True})
    print(json.dumps({'products': len(names), 'receipts': sum(counts.values()), 'start': start, 'end_exclusive': end}))


if __name__ == '__main__':
    main()
