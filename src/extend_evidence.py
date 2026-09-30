"""Update the combined factual evidence bundle, preserving historical responses."""
from pathlib import Path
import json,zipfile,hashlib,sys
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'dist/data'
def read(p):return json.loads(p.read_text())
def encoded(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
def main(research_dir=None):
    R=Path(research_dir if research_dir is not None else sys.argv[1])
    d=read(ROOT/'data/summary.json');assert d['publication_ready']
    manifest=read(OUT/'query-manifest.json');expansion=read(ROOT/'data/expanded-methods.json')
    manifest['snapshot_id']=d['snapshot_id'];manifest['products']=d['product_names']
    manifest['receipt_downloads'].update(expansion['receipt_exports'])
    manifest['expanded_rollups']=expansion
    for source in expansion['contract_reconciliation']['sources']:manifest['source_index'][source['source_id']]=source
    checks={v['source_id']:v for v in expansion['supplement_reconciliation']}
    for path in sorted((R/'supplement-manifests').glob('*.json')):
        s=read(path);s['transaction_verification']=checks[s['source_id']]
        s['included_gas_used']=checks[s['source_id']]['gas_used'];s['included_transactions']=checks[s['source_id']]['accepted']
        manifest['source_index'][s['source_id']]=s
    expected={r['source_id'] for r in read(OUT/'dataset.json')['records']}
    assert expected.issubset(manifest['source_index'])
    (OUT/'query-manifest.json').write_bytes(encoded(manifest))
    archive=OUT/'l1-gas-evidence.zip'
    with zipfile.ZipFile(archive) as old:
        keep={n:old.read(n) for n in old.namelist() if not n.startswith('expanded/') and n not in ['CONTENTS.json','query-manifest.json','METHODOLOGY.md','README.md']}
    keep['query-manifest.json']=(OUT/'query-manifest.json').read_bytes()
    keep['METHODOLOGY.md']=(OUT/'methodology.md').read_bytes()
    keep['README.md']=('''# L1 Gas Impact — evidence snapshot

Ethereum mainnet, March 15–September 14, 2026 inclusive (UTC).
Actual receipt gasUsed; no blob gas, fees, gas prices or L2 execution.

The comparison covers nine selected products and a contextual ETH-transfer benchmark. Product measurements are exclusive lower bounds with unequal coverage. Read METHODOLOGY.md and query-manifest.json. Do not sum the ETH benchmark with the products.

Original provider aggregate responses, chain identity snapshots, receipt samples and reconciliation records are preserved. The expanded/ directory documents World Chain, Unichain, OP Mainnet and Ink. All their included core, approval and Across/CCTP transactions are in the separate receipt CSV downloads. The original four rollup receipt downloads cover their core populations; supplemental aggregates are identified separately.

Bulky original transaction-page corpora are preserved in separate research archives. A manifest reference does not mean every raw page is bundled here. Original responses may contain the documented index duplicates; use the corrected published dataset, not naive raw sums. CONTENTS.json hashes the bundled bytes. Historical provider records retain their original factual scope. Application source is not included.
''').encode()
    patterns=['*-registry.toml','*-discovered.json','catalog.json','classification-manifest.json','supplement-verification.json','receipt-sample-verification.json',
        'canonical-block-*.json','*-omitted.json','*-omitted-rpc.json','raw-aggregates/*.json','aggregate-manifests/*.json',
        'receipt-manifests/*.json','raw-supplement/*.json','supplement-manifests/*.json','receipt-checks/*.json']
    for pattern in patterns:
        for p in sorted(R.glob(pattern)):
            keep['expanded/'+str(p.relative_to(R))]=p.read_bytes()
    contents=[{'file':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for name,b in sorted(keep.items())]
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,b in sorted(keep.items()):z.writestr(name,b)
        z.writestr('CONTENTS.json',encoded(contents))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps({'files':len(contents)+1,'bytes':archive.stat().st_size,'snapshot':d['snapshot_id']}))

if __name__=='__main__':main()
