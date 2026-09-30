"""Validate and publish a sourced, fixed architecture cohort without changing receipts."""
import json

ANNEX = """## L2 aggregate classification

“All L2 rollups” and “All L2 non-rollups” are fixed cohorts by data-availability design at the end of this snapshot (2026-09-27). Rollups publish the data needed to reconstruct state to Ethereum. Non-rollups use external data availability. This distinction is not a security-stage or decentralization rating. [The classification file](/data/l2-classification.json) lists every covered L2, sources and migration notes.

Historical gas stays with the end-of-snapshot cohort, even before a migration. Mantle changed to Ethereum-only data availability on April 16 and Arbitrum Nova disabled DAC mode on August 31. These totals therefore compare the tracked footprints of fixed cohorts, not gas consumed exclusively under each historical architecture. Codex has unverified data availability and is excluded from both L2 sums; its individual observations remain available. It has no included gas in the latest 7- or 30-day window.

“All alt L1s” retains covered non-L2 chains, including Polygon PoS. EDGE is an L3 and is excluded from all three subtotals. Subtotals overlap their members and never become observations or receipts. The original evidence archive remains dated acquisition evidence; this classification annex is the current presentation taxonomy. Ratios of observed lower bounds are not themselves lower bounds. Execution-gas comparisons exclude blob gas and do not directly measure network effects or establish causation.
"""


def publish_classification(root, summary):
    meta = json.loads((root / 'data/l2-classification.json').read_text())
    entries = meta['products']
    expected = {p for p, group in summary['product_groups'].items() if group == 'l2'}
    assert set(entries) == expected, 'Every L2 needs an explicit classification, including unknowns'
    assert meta['snapshot_id'] == summary['snapshot_id']
    assert meta['classification_as_of'] == summary['end']
    assert all(v['category'] in {'rollup', 'non_rollup', 'unknown'} and v['sources'] for v in entries.values())
    summary['l2_classification'] = {p: v['category'] for p, v in entries.items()}
    summary['l2_classification_as_of'] = meta['classification_as_of']
    out = root / 'dist/data'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'l2-classification.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    manifest_path = out / 'query-manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        manifest['synthetic_rows'] = {
            'location': 'Primary comparison table only; never exported observations',
            'all_l2_rollups': 'Covered L2s with Ethereum data availability at snapshot end',
            'all_l2_non_rollups': 'Covered L2s with external data availability at snapshot end',
            'all_alt': 'Covered non-L2 chains, including Polygon PoS',
            'excluded': 'EDGE (L3) from every subtotal; unclassified Codex from both L2 subtotals',
            'history_policy': meta['history_policy'],
            'classification': '/data/l2-classification.json',
            'overlap': 'Subtotals overlap their members. Do not sum all comparison rows.'}
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    path = out / 'methodology.md'
    if path.exists():
        text = path.read_text().split('## L2 aggregate classification')[0].rstrip()
        old = '“All L2s” and “All alt L1s” sum only their covered members and exist in this table\'s view layer, never as data records. L2s includes covered rollups, validiums and optimiums.'
        text = text.replace(old, '“All L2 rollups”, “All L2 non-rollups” and “All alt L1s” sum only their classified, covered members and exist in this table\'s view layer, never as data records. The dated classification is detailed below.')
        text = text.replace('belongs to neither subtotal', 'belongs to none of the three subtotals')
        path.write_text(text + '\n\n' + ANNEX)
