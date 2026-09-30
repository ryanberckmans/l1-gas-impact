"""Generate current public methodology and evidence from the accepted snapshot."""
from pathlib import Path
from collections import defaultdict
import json,zipfile,hashlib,io,gzip
from acquire_refresh import R,OLD,ROOT,save,START,END
from stage_refresh import historic,digest

def main():
 data=ROOT/'data';out=ROOT/'dist/data'
 d=json.loads((data/'summary.json').read_text());dataset=json.loads((out/'dataset.json').read_text())
 historical=json.loads(historic('dist/data/query-manifest.json'))
 downloads=json.loads((R/'staged-receipt-downloads.json').read_text())
 coverage=json.loads((data/'lighter-coverage.json').read_text());cv=coverage['populations']
 # Use placeholders in translations so coverage can never become a stale copy constant.
 oldnums={'13820':'depositIncluded','88588':'depositTotal','33146':'withdrawIncluded','34571':'withdrawTotal'}
 values={'depositIncluded':cv['deposit']['included_parent_transactions'],'depositTotal':cv['deposit']['observed_parent_transactions'],
  'withdrawIncluded':cv['withdraw_claim']['included_parent_transactions'],'withdrawTotal':cv['withdraw_claim']['observed_parent_transactions']}
 for loc in d['locales']:
  labels=json.loads((data/'locales'/(loc+'.json')).read_text())
  for digits,key in oldnums.items():
   for sep in [',','.','\u202f',' ']:
    value=f'{int(digits):,}'.replace(',',sep);labels['scope_lighter']=labels['scope_lighter'].replace(value,'{'+key+'}')
  save(data/'locales'/(loc+'.json'),labels)
 d['coverage_values']=values;save(data/'summary.json',d)
 current=defaultdict(lambda:{'gas_used':0,'tx_count':0,'days_with_activity':set()})
 for r in dataset['records']:
  v=current[r['source_id']];v['gas_used']+=r['gas_used'];v['tx_count']+=r['tx_count'];v['days_with_activity'].add(r['date'])
 refresh={json.loads(p.read_text())['source_id']:json.loads(p.read_text()) for p in (R/'aggregate-manifests').glob('*.json') if 'solana' not in p.name}
 index={}
 for sid,v in current.items():
  v['days_with_activity']=len(v['days_with_activity']);entry={'current_accepted_observations':v}
  if sid in historical['source_index']:entry['historical_capture']={'snapshot_id':historical['snapshot_id'],'period':historical['period'],'source_id':sid,'evidence':'historical-baseline/query-manifest.json'}
  if sid in refresh:
   s=refresh[sid];entry['refresh_capture']={k:s[k] for k in ['url','file','sha256_uncompressed','retrieved_at','tx_count','gas_used','complete']};entry['refresh_capture']['file']='refresh/'+entry['refresh_capture']['file']
  else:entry['refresh_capture']={'measurement':'Hash-deduplicated and decoded receipt gasUsed; see core classification and full receipt exports.','evidence':'refresh/classification-summary.json'}
  index[sid]=entry
 manifest={'snapshot_id':d['snapshot_id'],'publication_ready':True,'period':{'start_inclusive':START+'T00:00:00Z','end_exclusive':END+'T00:00:00Z','complete_days':len(d['dates'])},
  'metric':historical['metric'],'scope':historical['scope'],'products':d['product_names'],'source_index':index,'receipt_downloads':downloads,
  'refresh_verification':json.loads((data/'refresh-verification.json').read_text()),'lighter_event_coverage':coverage,
  'methodology':'/data/methodology.md','evidence_archive':'/data/l1-gas-evidence.zip',
  'historical_baseline':{'snapshot_id':historical['snapshot_id'],'period':historical['period'],'reuse_window':{'start_inclusive':START,'end_inclusive':'2026-09-14'},'evidence':'historical-baseline/query-manifest.json'},
  'coverage_limits':{'uniswap':'Selected Ethereum routers, liquidity entrypoints and token approvals. Latest universal-router transactions are command-decoded; bridge and utility-only executions are excluded.',
   'lighter':'Primary instance only; excludes Lighter on Robinhood and unresolved parent wrappers. Event-parent coverage is a transaction-count measure, not a gas-coverage estimate.',
   'rollups':'Dedicated L1 contracts, verified inbox senders, decoded canonical token withdrawals, selected token approvals, and chain-specific Across/CCTP calls. Unverified native ETH finalizations, arbitrary callbacks and shared settlements remain excluded.'}}
 save(out/'query-manifest.json',manifest)
 methodology=f'''# L1 Gas Impact: measurement and coverage

Snapshot: **{START} through {d['end']} UTC**, {len(d['dates'])} complete days, Ethereum mainnet (chain 1). Snapshot ID: `{d['snapshot_id']}`.

## Metric

Actual transaction receipt `gasUsed`, including intrinsic gas and the L1 execution portion of blob-carrying transactions. Blob gas, gas limits, gas prices, fees and execution on other chains are excluded. Failed product transactions consume gas and are included when their attribution can be established. The plain ETH-transfer benchmark requires success, positive ETH value, empty input and exactly 21,000 gas.

## Attribution and limitations

The product figures are **verified lower bounds for selected populations**, not exhaustive footprints or a ranking of all Ethereum activity. Count a full parent receipt only when the whole operation is exclusively attributable to the selected product. Do not allocate shared bridge settlement, an arbitrary callback or a mixed router transaction by association alone. Product populations are disjoint; the contextual ETH-transfer benchmark must not be summed with product rows.

Uniswap on L1 covers selected Ethereum routers, liquidity entrypoints and approvals. It excludes Uniswap execution on rollups and unresolved pool or aggregator routes. The latest Universal Router is decoded recursively: bridge commands, unknown commands and utility-only executions are excluded.

Lighter means its primary instance. It includes direct users, settlement, proofs, execution, exclusive helpers and administration linked to the primary deployment. It excludes Lighter on Robinhood. Included receipts cover **{values['depositIncluded']:,} of {values['depositTotal']:,}** observed deposit parent transactions and **{values['withdrawIncluded']:,} of {values['withdrawTotal']:,}** withdrawal-claim parents in this snapshot. These are transaction coverage counts, not gas coverage percentages; unresolved deposit wrappers are a material gap.

Rollups cover dedicated L1 contracts, reviewed operator-to-inbox traffic, selected approvals and decoded bridge activity. Incoming CCTP messages require successful authentication, the expected source domain and Ethereum token-messenger recipient. Native ETH withdrawal finalizations with unverified callbacks remain excluded. Newly discovered contracts are queried over the full snapshot; discovery alone never implies nonzero activity.

## Verification

Validated March 28–September 14 observations are retained from the previous snapshot. September 15–27 observations are newly acquired. All required queries completed; source population and input checksums gate the build, so a missing source cannot silently become zero.

The refresh reconciles **128 contract query populations by daily count and gas across Routescan and Blockchair**. It resolves **140 conflicting indexed transaction hashes against canonical Ethereum receipts and blocks**. Supplemental approvals and chain-specific bridge queries are fully paginated and ABI-decoded. Seventeen current samples independently check receipt gas, block and recipient for the larger aggregate-only populations and supplemental protocol variants. Sampling is not a full independent recount of Ethereum. Historical index repairs retain their original dated evidence, including the April 16 duplicate-index correction; they are never reapplied to unaffected new responses.

Daily CSV, JSON, receipt downloads and query metadata are generated from the same accepted observations. Receipt exports for Lighter, Base, Arbitrum One and Robinhood cover core contract cohorts; their separate supplemental query cohorts are in the structured dataset. The four other rollup receipt exports cover all of their measured cohorts. Zero means no observed activity inside a completed queried population. Unresolved or undiscovered activity is excluded, not treated as zero.

## Reading the charts

Comparison bars show the selected interval's mean gas per day on a common linear scale beginning at zero. History bars show actual daily gas, and the line shows a trailing seven-day mean only where seven observations exist. The change metric always compares the latest 30 days with the preceding 30. ETH-transfer equivalents divide gas by 21,000; they compare gas demand, not transaction usefulness. Displayed rounded values are accompanied by exact tables and downloads.

The evidence ZIP contains current source responses and checks, plus a clearly separated historical baseline. Historical files describe their own observation window; they are provenance for the reused overlap, not current totals. Full raw research archives are retained separately. This is a fixed snapshot, not a live feed.
'''
 (out/'methodology.md').write_text(methodology)
 files={'README.md':('Current snapshot '+START+' through '+d['end']+' UTC.\nCurrent totals are in dataset.json and query-manifest.json.\nThe historical-baseline/ directory is immutable, dated provenance only.\nNo application source or private working notes are included.\n').encode()}
 for n in ['dataset.json','l1-gas-daily.csv','query-manifest.json','methodology.md']:files[n]=(out/n).read_bytes()
 files['lighter-event-coverage.json']=(data/'lighter-coverage.json').read_bytes()
 with zipfile.ZipFile(io.BytesIO(historic('dist/data/l1-gas-evidence.zip'))) as z:
  for n in z.namelist():files['historical-baseline/'+n]=z.read(n)
 files['historical-baseline/query-manifest.json']=historic('dist/data/query-manifest.json')
 for sid,s in refresh.items():files['refresh/'+s['file']]=(R/s['file']).read_bytes()
 for n in ['daily-reconciliation.json','classification-summary.json','canonical-verification.json']:
  files['refresh/'+n]=(R/n).read_bytes()
 for n in ['sample-verification.json','supplement-verification.json']:
  obj=json.loads((R/n).read_text());obj['results']=[s for s in obj['results'] if 'solana' not in s.get('source_id','')]
  for key in ['errors','resolved_errors']:
   if key in obj:obj[key]=[s for s in obj[key] if 'solana' not in json.dumps(s)]
  files['refresh/'+n]=(json.dumps(obj,indent=2)+'\n').encode()
 allowed_hashes={s['hash'] for s in json.loads((R/'canonical-verification.json').read_text())['results']}
 allowed_hashes.update(s['hash'] for s in json.loads((R/'sample-verification.json').read_text())['results'] if 'solana' not in s['source_id'] and 'hash' in s)
 for p in (R/'canonical').glob('*receipt.json'):
  if p.name.removesuffix('-receipt.json') in allowed_hashes:files['refresh/canonical/'+p.name]=p.read_bytes()
 contents=[{'file':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(files.items())]
 files['CONTENTS.json']=(json.dumps(contents,indent=2)+'\n').encode()
 with zipfile.ZipFile(out/'l1-gas-evidence.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,b in sorted(files.items()):z.writestr(n,b)
 # Retire superseded derived summaries while preserving original acquisition templates.
 historical_dir=data/'historical-2026-03-15_to_2026-09-14';historical_dir.mkdir(exist_ok=True)
 for name in ['expanded-methods.json','expanded-review.json','expanded-receipt-exports.json']:
  p=data/name
  if p.exists():p.replace(historical_dir/name)
 print(json.dumps({'snapshot':d['snapshot_id'],'source_ids':len(index),'evidence_bytes':(out/'l1-gas-evidence.zip').stat().st_size,'coverage':values}))
if __name__=='__main__':main()
