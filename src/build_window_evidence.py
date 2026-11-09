"""Build factual provenance for a staged incremental research snapshot."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import sys
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def main(research):
    out = ROOT / 'dist/data'
    summary = read(ROOT / 'data/summary.json')
    dataset = read(out / 'dataset.json')
    window = read(research / 'window.json')
    baseline = read(research / 'baseline/public-data/query-manifest.json')
    proof = read(ROOT / 'data/snapshot-verification.json')
    classification = read(research / 'classification-verification.json')
    canonical = read(research / 'canonical-verification.json')
    indexed_exceptions = sum(r.get('receipt_verification') ==
        'independent-indexed-receipts-and-canonical-membership' for r in canonical['results'])
    exception_note = (f' {indexed_exceptions} simple 21,000-gas inbox transaction required an explicitly documented receipt-source exception: the receipt RPC returned an error, so actual gas-used and status records from both Routescan and Blockchair were matched, followed by the same canonical transaction and block-membership checks. Gas limits were not substituted for gas used. The exact source records and exception manifest are included in the evidence archive.' if indexed_exceptions else '')
    manifests = {p.stem: read(p) for p in (research / 'aggregate-manifests').glob('*.json')}
    totals = defaultdict(lambda: {'gas_used': 0, 'tx_count': 0, 'days': set()})
    for row in dataset['records']:
        value = totals[row['source_id']]
        value['gas_used'] += row['gas_used']; value['tx_count'] += row['tx_count']; value['days'].add(row['date'])
    sources = {}
    for sid, total in totals.items():
        entry = {'current_accepted_observations': {k: v for k, v in total.items() if k != 'days'},
                 'days_with_activity': len(total['days']),
                 'new_observation_interval': [manifests.get(sid, {}).get('start_inclusive', window['delta_start']), window['end_exclusive']]}
        if sid in baseline['source_index']:
            entry['retained_history'] = baseline['source_index'][sid]
        if sid in manifests:
            m = manifests[sid]
            entry['current_query'] = {k: m[k] for k in ['url', 'sha256_uncompressed', 'retrieved_at', 'tx_count', 'gas_used', 'complete']}
        entry['verification'] = ('current/classification-verification.json' if sid.startswith('coverage-')
                                 else 'current/core-and-supplement-verification.json')
        sources[sid] = entry
    limits = dict(baseline['coverage_limits'])
    limits['aztecnetwork'] = 'Reviewed Aztec v4, v5 and v6 rollup contracts and selected operator, governance and deposit methods. Legacy zk.money, arbitrary execution and unresolved routes remain excluded.'
    limits['codex'] = 'Reviewed prior and current Ethereum batch inboxes, canonical bridge deposits, withdrawal proofs, dispute-game creation and decoded shared bridge routes. Batch senders and applicable inbox activation intervals are checked. Continuing submissions to the prior dedicated inbox are retained even after the registry changed its DA tracking. Arbitrary L1 finalizations and unreviewed methods remain excluded.'
    coverage = read(ROOT / 'data/lighter-coverage.json')
    manifest = {'snapshot_id': summary['snapshot_id'], 'publication_ready': True,
                'period': {'start_inclusive': summary['start'] + 'T00:00:00Z',
                           'end_exclusive': window['end_exclusive'] + 'T00:00:00Z', 'complete_days': len(summary['dates'])},
                'metric': baseline['metric'], 'scope': baseline['scope'], 'products': summary['product_names'],
                'product_groups': summary['product_groups'], 'source_index': sources,
                'receipt_downloads': read(ROOT / 'data/receipt-exports.json'), 'snapshot_verification': proof,
                'lighter_event_coverage': coverage, 'coverage_limits': limits,
                'identity_registries': baseline['identity_registries'],
                'current_identity_review': read(research / 'identity-review.json'),
                'methodology': '/data/methodology.md', 'evidence_archive': '/data/l1-gas-evidence.zip',
                'raw_data_note': 'Original provider responses and full receipt exports are preserved separately; compact factual evidence is included here.'}
    (out / 'query-manifest.json').write_bytes(encoded(manifest))
    detail = '\n\n'.join('**' + summary['product_names'].get(p, p.replace('_', ' ').title()) + '.** ' + note
                         for p, note in limits.items() if p != 'all_products')
    cv = coverage['populations']
    text = f'''# L1 Gas Impact: measurement and coverage

Snapshot **{summary['start']}–{summary['end']} UTC**, {len(summary['dates'])} complete days. Ethereum mainnet, chain 1. Snapshot `{summary['snapshot_id']}`. This is a fixed research snapshot.

## Measurement

Receipt and log data from [Routescan](https://routescan.io), canonical RPC evidence from Routescan and [PublicNode](https://ethereum.publicnode.com/), and independent aggregate data from [Blockchair](https://blockchair.com).

Actual Ethereum transaction receipt `gasUsed`, including intrinsic gas and the execution portion of blob transactions. Blob gas, gas limits, prices, fees and native execution on other chains are excluded. Failed product transactions count only when exclusive attribution is established. The ETH benchmark requires a successful positive-value transfer with empty input and exactly 21,000 gas.

These are lower bounds for selected directly attributable populations, not complete product footprints. A shared router or operator alone does not establish attribution. Unknown methods, mixed routes and unresolved callbacks remain excluded. Receipt hashes are deduplicated across the exported populations. A completed query with no activity can yield zero; missing or failed collection cannot.

## Coverage

{detail}

Lighter's included core receipts cover **{cv['deposit']['included_parent_transactions']:,} of {cv['deposit']['observed_parent_transactions']:,}** observed deposit parent transactions and **{cv['withdraw_claim']['included_parent_transactions']:,} of {cv['withdraw_claim']['observed_parent_transactions']:,}** withdrawal-claim parents. These are transaction counts, not gas-coverage percentages. The event populations were recollected across the complete current window.

## Acquisition, reconciliation and retained history

Verified historical observations from {summary['start']} through the day before {window['delta_start']} are retained from the preceding release. New observations cover {window['delta_start']} through {summary['end']}. Newly identified recipient cohorts are additionally backfilled to {summary['start']}; their independent queries identify that full interval. No interpolation, extrapolation or native-chain gas is used. The cutoff is bound to Ethereum block {window['end_block']:,}.

New account populations are collected from Routescan and reconciled by daily gas and count against Blockchair. Pagination overlaps are deduplicated. Conflicts are checked against canonical receipt, transaction and block membership evidence.{exception_note} Reviewed ABI methods and attribution-bearing fields determine inclusion. Successful closed settlement methods may retain opaque proof bytes without decoding their mathematical contents. Original aggregate-only cohorts retain their documented scope and receive new canonical receipt samples. Supplemental token approvals are fully enumerated and decoded. This is not a full independent recount of Ethereum.

The current acceptance certificate binds all input hashes, {proof['reconciled_accounts']} acquired account populations, {proof['aggregate_queries']} aggregate queries and the separate classification and reconciliation results. The merged receipt archive is recounted against the complete current daily totals before release. Dated historical evidence describes its own earlier interval; it is not substituted for new observations.

## Interface and exports

The comparison is sorted by selected-period million Ethereum gas per day. The 7-day and 30-day views end at the snapshot cutoff; the six-month view contains {len(summary['dates'])} daily observations. Group subtotals overlap their members and are not added to exported observations. The ETH-transfer benchmark is contextual and may overlap incidental product-related movements. Do not sum all comparison rows. Ratios of lower bounds are not themselves lower bounds.

Daily chart bars show observed gas. The line is a trailing seven-day arithmetic mean, including available history before a zoomed window. Chart zoom does not change the separately labelled main comparison interval. The change metric compares the latest 30 days with the previous 30. ETH-transfer equivalents divide gas by 21,000 without comparing transaction usefulness.

CSV, JSON, all eight language views and social metadata derive from this accepted snapshot and its current scope. Bulk receipt CSVs are preserved in a separate checksummed archive. The compact query manifest identifies included populations and their evidence.

The public evidence ZIP contains factual query responses, verification results and dated prior evidence. Identical canonical RPC responses are stored once by SHA-256 in current/canonical-responses.json, as exact UTF-8 response strings. current/canonical-index.json maps every original response filename to its checksum and byte length; UTF-8 encoding the corresponding string reconstructs the original bytes. Full provider response pages are preserved separately. Application source and private review records are not part of the data downloads.
'''
    (out / 'methodology.md').write_text(text)
    from aggregate_classification import publish_classification
    publish_classification(ROOT, summary)
    files = {'README.md': f'Current snapshot: {summary["start"]} through {summary["end"]} UTC.\nRead methodology.md and query-manifest.json first. historical-baseline/ contains dated preceding-release evidence.\n'.encode()}
    for name in ['dataset.json', 'l1-gas-daily.csv', 'query-manifest.json', 'methodology.md', 'l2-classification.json']:
        files[name] = (out / name).read_bytes()
    with ZipFile(research / 'baseline/public-data/l1-gas-evidence.zip') as previous:
        for name in previous.namelist():
            if name != 'CONTENTS.json':
                files['historical-baseline/' + name] = previous.read(name)
    files['current/window.json'] = encoded(window)
    files['current/snapshot-verification.json'] = encoded(proof)
    files['current/classification-verification.json'] = encoded(classification)
    files['current/canonical-verification.json'] = encoded(canonical)
    for name in ['canonical-extra.json', 'discrepancy-assessment.json', 'boundary-review.json']:
        if (research / name).exists():
            files['current/' + name] = (research / name).read_bytes()
    files['current/catalog.json'] = (research / 'catalog.json').read_bytes()
    files['current/cohort-updates.json'] = (research / 'cohort-updates.json').read_bytes()
    files['current/identity-review.json'] = (research / 'identity-review.json').read_bytes()
    for item in read(research / 'identity-review.json')['discovery_files']:
        payload = (research / 'current-identities' / item['file']).read_bytes()
        assert len(payload) == item['bytes'] and hashlib.sha256(payload).hexdigest() == item['sha256']
        files['current/discovery/' + item['file']] = payload
    files['current/codex-continuity-review.json'] = (research / 'codex-continuity-review.json').read_bytes()
    files['current/aggregate-catalog.json'] = (research / 'aggregate-catalog.json').read_bytes()
    prefetch = research / 'canonical-rpc-prefetch.json'
    if prefetch.exists():
        files['current/canonical-rpc-prefetch.json'] = prefetch.read_bytes()
        files['current/canonical-rpc-raw-index.json'] = encoded([
            {'file': str(path.relative_to(research)), 'bytes': path.stat().st_size,
             'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted((research / 'canonical-rpc-raw').glob('*.json.gz'))])
    files['current/core-and-supplement-verification.json'] = encoded({
        'core': read(research / 'classification-summary.json'),
        'daily_reconciliation': read(research / 'daily-reconciliation.json'),
        'supplement': read(research / 'supplement-verification.json'),
        'samples': read(research / 'sample-verification.json')})
    canonical_index, canonical_responses = [], {}
    # Group response types for ordinary ZIP compression, retaining exact bytes.
    for path in sorted((research / 'canonical').glob('*.json'),
                       key=lambda p: (p.name.rsplit('-', 1)[-1], p.name)):
        payload = path.read_bytes()
        sha = hashlib.sha256(payload).hexdigest()
        response = payload.decode('utf-8')
        assert sha not in canonical_responses or canonical_responses[sha] == response
        canonical_responses[sha] = response
        canonical_index.append({'original_file': 'current/canonical/' + path.name,
                                'bytes': len(payload), 'sha256': sha})
    files['current/canonical-index.json'] = encoded(canonical_index)
    files['current/canonical-responses.json'] = json.dumps(
        {'encoding': 'UTF-8', 'responses': canonical_responses},
        ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    for directory, pattern in [('aggregates', '*.json'), ('samples', '*.json'),
                               ('canonical-fallbacks', '*.json'), ('disputed-blocks', '*.json*'),
                               ('boundary-review', '*.json')]:
        for path in sorted((research / directory).glob(pattern)):
            files['current/' + directory + '/' + path.name] = path.read_bytes()
    contents = [{'file': name, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
                for name, payload in sorted(files.items())]
    with ZipFile(out / 'l1-gas-evidence.zip', 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in sorted(files.items()):
            archive.writestr(name, payload)
        archive.writestr('CONTENTS.json', encoded(contents))
    print(json.dumps({'snapshot_id': summary['snapshot_id'], 'source_populations': len(sources),
                      'evidence_bytes': (out / 'l1-gas-evidence.zip').stat().st_size}))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
