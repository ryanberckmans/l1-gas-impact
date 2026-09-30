"""Generate consistent public evidence for the accepted expanded snapshot."""
from pathlib import Path
from collections import defaultdict
import json,hashlib,zipfile,io
from acquire_refresh import R,OLD,ROOT,save,START,END
from stage_coverage import historic,BASELINE

def encoded(obj):return (json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode()
def main():
 data=ROOT/'data';out=ROOT/'dist/data'
 d=json.loads((data/'summary.json').read_text());dataset=json.loads((out/'dataset.json').read_text())
 baseline=json.loads(historic('dist/data/query-manifest.json'));report=json.loads((R/'classification-verification.json').read_text());proof=json.loads((data/'coverage-verification.json').read_text())
 assert report['complete'] and proof['complete']
 catalog={s['address']:s for s in json.loads((R/'catalog.json').read_text())};by_address={s['address']:s for s in report['sources']}
 totals=defaultdict(lambda:{'gas_used':0,'tx_count':0,'days_with_activity':set()});index={}
 for r in dataset['records']:
  v=totals[r['source_id']];v['gas_used']+=r['gas_used'];v['tx_count']+=r['tx_count'];v['days_with_activity'].add(r['date'])
 for sid,v in totals.items():
  v['days_with_activity']=len(v['days_with_activity'])
  if sid.startswith('coverage-'):
   a=sid.removeprefix('coverage-');s=by_address[a];source=json.loads((R/'aggregate-manifests'/(sid+'.json')).read_text())
   index[sid]={'current_accepted_observations':v,'recipient':a,'roles':catalog[a]['roles'],'independent_aggregate':{k:source[k] for k in ['url','sha256_uncompressed','retrieved_at','tx_count','gas_used','complete']},
    'full_account_transactions':s['transactions'],'accepted_account_transactions':s['accepted'],'daily_count_and_gas_match':s['daily_count_and_gas_match'],
    'receipt_ledger_sha256':s['ledger_sha256'],'classified_receipts_sha256':s['classified_sha256'],'exclusions_by_reason':s['excluded'],'excluded_gas_by_reason':s['excluded_gas'],
    'canonical_repairs':s['canonical_repairs'],'documented_ETH4_duplicates_removed':s['documented_ETH4_duplicates_removed'],'rejected_noncanonical':s.get('rejected_noncanonical',[]),'evidence':'coverage/classification-verification.json'}
  else:
   assert sid in baseline['source_index'];index[sid]={'current_accepted_observations':v,'baseline_capture':baseline['source_index'][sid],'evidence':'baseline-release-6/query-manifest.json'}
 downloads=json.loads((data/'receipt-exports.json').read_text());coverage=json.loads((data/'lighter-coverage.json').read_text());cv=coverage['populations']
 limits={
 'all_products':'Unequal lower-bound coverage of selected Ethereum-side populations, not exhaustive footprints or native-chain gas.',
 'uniswap':'Selected Ethereum routers, liquidity entrypoints and approvals; not Uniswap on other chains. Unknown, bridge and utility-only commands in the latest Universal Router are excluded.',
 'lighter':'Primary instance only, excluding Lighter on Robinhood and unresolved wrappers. Parent-transaction coverage is not gas coverage.',
 'aave':'Direct reviewed V2 and V3 pool methods; flash loans, V4 and wider callback-bearing or aggregator routes excluded.',
 'compound':'Direct reviewed Comet USDC, WETH and USDT market methods; other deployments and routers excluded.',
 'morpho':'Direct Morpho Blue methods, with empty callback data where applicable; vault wrappers and nonempty callbacks excluded.',
 'curve':'Selected Ethereum non-lending ERC20 legacy pools from the official registry. Factory-wide pools, routers, underlying lending routes and native-ETH callbacks excluded.',
 'lido':'Selected stETH/wstETH, withdrawal-request and oracle contracts. Token transfers included; unverified native-ETH withdrawal claims and wider staking modules excluded.',
 'etherfi':'Selected LiquidityPool, eETH/weETH, withdrawal and oracle contracts. Only reviewed methods and token transfers included; wider deployments and callbacks excluded.',
 'ethena':'Selected Ethereum USDe/sUSDe and ENA/sENA token and staking contracts, with reviewed methods. Aggregator routes and arbitrary callbacks excluded.',
 'sky':'Selected Maker/Sky DAI/USDS/SKY, savings and migration contracts. Wider vault, auction and governance deployments excluded.',
 'aztecnetwork':'Current v5 and previous v4 rollup contracts and selected operator, governance and deposit methods. Earlier Ignition deployments, legacy zk.money, arbitrary execution and unresolved routes excluded.',
 'starknet':'Direct state updates and selected bridges; shared SHARP proof transactions excluded without proportional allocation.',
 'zksync2':'Identified direct-chain settlement and bridges; shared Gateway proofs and settlement excluded.',
 'hyperliquid':'Ethereum-side CCTP, Across, Wormhole and DLN routes for Hyperliquid/HyperEVM. Native Hyperliquid execution and its Arbitrum bridge excluded; no allocation of Arbitrum settlement.',
 'polygon':'Polygon PoS checkpoints, reviewed staking and deposits, plus decoded bridges. Sidechain grouped with other non-L2 chains; unverified exits and arbitrary state messages excluded.',
 'edge':'Ethereum-side bridge activity only. EDGE is an L3 settling via Arbitrum, excluded from both synthetic group subtotals.',
 'other_chains':'Selected dedicated contracts, sender-specific inboxes and/or decoded chain-specific shared bridges, as listed per source. A chain with only bridge coverage is not assigned hypothetical settlement gas.',
 'shared_bridges':'CCTP, Across, Wormhole and DLN: require a known source/destination chain and reviewed method. Incoming authenticated token-only routes included; mixed settlements, shared fills and arbitrary L1 callbacks excluded.'}
 manifest={'snapshot_id':d['snapshot_id'],'publication_ready':True,'period':{'start_inclusive':START+'T00:00:00Z','end_exclusive':END+'T00:00:00Z','complete_days':len(d['dates'])},
 'metric':'Observed Ethereum mainnet receipt gasUsed, including intrinsic gas and blob-transaction execution; excludes blob gas, prices, fees and native execution on other chains.',
 'scope':limits['all_products'],'products':d['product_names'],'product_groups':d['product_groups'],'source_index':index,'receipt_downloads':downloads,
 'coverage_verification':proof,'baseline_verification':baseline['refresh_verification'],'lighter_event_coverage':coverage,'coverage_limits':limits,
 'synthetic_rows':{'location':'Primary comparison table only; never exported observations','all_l2':'Sum of covered rollups, validiums and optimiums','all_alt':'Sum of covered other L1s and Polygon PoS','excluded_from_both':'EDGE Chain (L3)','overlap':'Subtotals overlap their member rows. The ETH-transfer benchmark is contextual; do not sum all comparison rows.'},
 'identity_registries':['https://github.com/l2beat/l2beat/tree/main/packages/config/src/projects','https://developers.circle.com/cctp/cctp-supported-blockchains','https://docs.across.to/chains-and-contracts','https://github.com/wormhole-foundation/wormhole/blob/main/sdk/vaa/structs.go','https://docs.debridge.finance/dln-details/overview/supported-chains'],
 'methodology':'/data/methodology.md','evidence_archive':'/data/l1-gas-evidence.zip','raw_data_note':'The evidence archive contains aggregate responses, verification records and dated baseline evidence. Full bulky receipt/page corpora are preserved separately; not every referenced raw file is bundled.'}
 save(out/'query-manifest.json',manifest)
 new_counts=len(report['sources']);new_txs=report['source_transactions']
 sections='\n\n'.join('**'+d['product_names'].get(p,p.replace('_',' ').title())+'.** '+t for p,t in limits.items() if p!='all_products')
 methodology=f'''# L1 Gas Impact: measurement and coverage

Snapshot **{START}–{d['end']} UTC**, {len(d['dates'])} complete days. Ethereum mainnet, chain 1. Snapshot `{d['snapshot_id']}`. This is a fixed snapshot, not a live index.

## What the numbers mean

Actual transaction receipt `gasUsed`, including intrinsic gas and the L1 execution portion of blob transactions. Blob gas, gas limits, prices, fees and native execution on any other chain are excluded. Failed product transactions are included only where attribution is established. The plain ETH benchmark requires success, positive ETH value, empty input and exactly 21,000 gas.

All {len(d['product_order'])-1} product figures are lower bounds for selected populations. They are not complete footprints, a ranking of all Ethereum activity, or estimates of omitted gas. Ethereum-side activity for Solana, Hyperliquid, BSC and other chains is measured in the same Ethereum gas unit as every other row.

Count a full parent receipt only when its operation is exclusively attributable to the selected product. Do not allocate shared proofs, shared bridge settlements, unknown callbacks or mixed routes by association. Each included receipt hash occurs in only one product population. Native token costs on different chains are not comparable to this metric and are not added.

## Coverage by product

{sections}

Lighter's included core receipts cover **{cv['deposit']['included_parent_transactions']:,} of {cv['deposit']['observed_parent_transactions']:,}** observed deposit parent transactions and **{cv['withdraw_claim']['included_parent_transactions']:,} of {cv['withdraw_claim']['observed_parent_transactions']:,}** withdrawal-claim parents. These are transaction coverage counts, not gas coverage; unresolved deposit wrappers remain a material gap.

## Verification and lineage

The prior release's validated observations for this same interval are preserved, except that its CCTP/Across cohorts are replaced by complete, decoded account histories. Replacement populations are compared against the removed totals and deduplicated; they are never added twice. Some prior Base and Arbitrum bridge figures decrease slightly because full decoding excludes deprecated or unreviewed methods and incoming messages addressed to unreviewed L1 contracts. Each decrease is reconciled to identified receipts; no omitted gas is estimated.

The expansion acquires **{new_counts} account populations**, covering **{new_txs:,} source transactions**, and reconciles each population's daily gas and count between Routescan histories and Blockchair aggregates. Overlapping pagination is deduplicated by hash. Conflicting index entries are checked against canonical Ethereum receipts and block membership. Documented April 16 duplicate-index repairs apply only to affected ETH4 responses; clean ETH3 responses remain unchanged. Incorrectly attributed contract creations, noncanonical entries and missing receipts are resolved using canonical receipts, transaction data and block membership. The exact corrections, accepted methods and exclusions are recorded in the evidence. Attribution-bearing ABI fields are decoded; opaque proof arrays in successful, reviewed settlement calls are not interpreted when the dedicated recipient or decoded chain identifier establishes exclusive attribution.

Original baseline aggregate-only populations retain their sampled verification, while original core and supplemental cohorts retain their full reconciliation records. The evidence distinguishes these scopes. This is not a full independent recount of Ethereum. A missing query or failed reconciliation blocks acceptance; completed queries with no matching activity can legitimately yield zero. Excluded or undiscovered activity is not represented as a measured zero.

## Interface and exports

The primary table is sorted by selected-period **million Ethereum gas per day**, descending, for every duration. “All L2s” and “All alt L1s” sum only their covered members and exist in this table's view layer, never as data records. L2s includes covered rollups, validiums and optimiums. Polygon PoS is grouped with the non-L2 chains. EDGE is an L3 and belongs to neither subtotal. Group totals overlap their members; the ETH benchmark may overlap incidental product-related ETH transfers. Do not sum all rows.

Daily history bars show observed gas. The line is a trailing seven-day arithmetic mean with seven complete observations, including history before a zoomed window. Date controls, drag zoom, hover/touch inspection and keyboard controls operate on the daily chart. A custom chart window does not change the separately labeled main comparison interval. Product, duration, date and chart window are addressable in the URL. The change metric always compares the latest 30 days with the preceding 30. ETH-transfer equivalents divide gas by 21,000; they do not compare usefulness.

CSV, JSON, all eight language views and social metadata derive from this accepted snapshot and its current scope. Receipt downloads are split into bounded files where needed, with checksums and exact population coverage in the query manifest. They include every newly included receipt and previously published core receipts. Original supplemental approvals outside those core exports remain documented in the structured dataset. No synthetic aggregate receipt is created.

The public evidence ZIP includes dated prior-release provenance and current aggregate responses and checks. Historical files describe their own snapshots; they are not current totals. Full raw page corpora are preserved separately. Application source, private notes and conversation text are not part of the public deliverable.
'''
 (out/'methodology.md').write_text(methodology)
 files={'README.md':f'Current snapshot {START} through {d["end"]} UTC.\nRead methodology.md and query-manifest.json for current totals and limits.\nThe baseline-release-6/ directory contains immutable dated evidence, not current derived totals.\nFull raw page corpora are preserved separately.\n'.encode()}
 for n in ['dataset.json','l1-gas-daily.csv','query-manifest.json','methodology.md']:files[n]=(out/n).read_bytes()
 files['lighter-event-coverage.json']=(data/'lighter-coverage.json').read_bytes()
 with zipfile.ZipFile(io.BytesIO(historic('dist/data/l1-gas-evidence.zip'))) as z:
  for n in z.namelist():files['baseline-release-6/'+n]=z.read(n)
 files['baseline-release-6/query-manifest.json']=historic('dist/data/query-manifest.json')
 for n in ['catalog.json','classification-verification.json','accepted-methods.json','integration-verification.json','canonical-run.json','canonical-extra.json','canonical-corrections.json','bridge-replacement-review.json','discrepancy-assessment.json','discrepancy-assessment-phase1.json','zk-chain-identities.json']:
  if (R/n).exists():files['coverage/'+n]=(R/n).read_bytes()
 files['coverage/certificate.json']=(data/'coverage-verification.json').read_bytes()
 for p in sorted((R/'aggregates').glob('*.json')):files['coverage/aggregates/'+p.name]=p.read_bytes()
 for p in sorted((R/'canonical').glob('*receipt.json')):files['coverage/canonical/'+p.name]=p.read_bytes()
 for p in sorted((R/'disputed-blocks').glob('*')):
  if p.is_file():files['coverage/disputed-blocks/'+p.name]=p.read_bytes()
 files['CONTENTS.json']=encoded([{'file':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(files.items())])
 with zipfile.ZipFile(out/'l1-gas-evidence.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,b in sorted(files.items()):z.writestr(n,b)
 print(json.dumps({'snapshot':d['snapshot_id'],'products':len(d['product_order']),'source_ids':len(index),'evidence_bytes':(out/'l1-gas-evidence.zip').stat().st_size}))
if __name__=='__main__':
 main()
 from aggregate_classification import publish_classification
 publish_classification(ROOT,json.loads((ROOT/'data/summary.json').read_text()))
 from compact_evidence import publish_compact
 publish_compact()
