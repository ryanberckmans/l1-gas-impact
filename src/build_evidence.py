"""Package public observations and provenance, never application source."""
from pathlib import Path
import argparse,json,hashlib,zipfile,shutil,re

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'research'
OUT=ROOT/'dist/data'
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,str):return re.sub(r'/workspace/(?:scratch|sites)/[^/]+/','',x.replace(str(R)+'/', '').replace(str(ROOT)+'/', ''))
 return x
def encoded(x):return (json.dumps(clean(x),ensure_ascii=False,indent=2)+'\n').encode()
def main():
 if (ROOT/'data/expanded-methods.json').exists():
  from extend_evidence import main as extend_evidence
  return extend_evidence(R/'expanded')
 s=read(ROOT/'data/summary.json');cohorts=read(ROOT/'data/cohort-sources.json')
 index={'blockchair-plain-eth-transfer-benchmark':cohorts['eth']}
 for c in cohorts['uniswap']['contracts']:
  if c.get('included'):index[c['source_id']]=c
 c=cohorts['uniswap']['decoded_shared_router'];index[c['source_id']]=c
 for c in cohorts['rollups_included']:
  if 'source_id' in c:index[c['source_id']]=c
 for c in read(R/'rollups/rollups-decoded-source-manifest.json'):index[c['source_id']]=c
 for group in ['approvals','cctp','across']:
  for c in cohorts[group]['series']:index[c['source_id']]=c
 receipt_files={'lighter':R/'lighter/lighter-transaction-receipts.csv.gz'}
 receipt_files.update({p:R/'rollups/exports'/f'{p}-ethereum-gas-receipts.csv.gz' for p in ['base','arbitrum','robinhood']})
 downloads={}
 for p,f in receipt_files.items():
  target=OUT/f'receipts-{p}.csv.gz';shutil.copyfile(f,target)
  downloads[p]={'url':f'/data/{target.name}','bytes':target.stat().st_size,'sha256':digest(target),'scope':'Included core contract receipts; separate aggregate approval/bridge cohorts are in dataset.json.'}
 records=read(OUT/'dataset.json')['records']
 for sid in {r['source_id'] for r in records if r['product']=='lighter' and r['source_id'].startswith('lighter-receipts-')}:
  index[sid]={'product':'lighter','classification':sid.removeprefix('lighter-receipts-'),'receipts':downloads['lighter'],'provenance':'lighter/lighter-normalized.json; lighter/routescan-manifest.json; lighter/validation.json in evidence archive','metadata':cohorts['lighter']}
 missing={r['source_id'] for r in records}-set(index);assert not missing,missing
 manifest={'snapshot_id':s['snapshot_id'],'publication_ready':s['publication_ready'],'period':{'start_inclusive':'2026-03-15T00:00:00Z','end_exclusive':'2026-09-15T00:00:00Z','complete_days':184},'metric':'Ethereum mainnet transaction receipt gasUsed. Excludes blob gas, prices, fees and L2 execution.','scope':'Verified included lower bounds; coverage differs by product. Do not treat absent populations as zero or sum the contextual ETH benchmark with product totals.','source_index':index,'cohort_methods':cohorts,'rollup_metadata':read(R/'rollups/rollups-metadata.json'),'supplemental_metadata':read(R/'additional/additional_metadata.json'),'receipt_downloads':downloads,'provider_corrections':{'blockchair':'ETH4 duplicates in blocks 24890807–24890838 removed only from affected original cohorts; clean ETH3 unchanged.','routescan':'Missing indexed transactions restored from canonical block membership and gas-reconciled block populations; repaired cohorts documented individually.'},'evidence_archive':'/data/l1-gas-evidence.zip','methodology':'/data/methodology.md','raw_data_note':'Compact original provider responses, per-population manifests and canonical verification are in the public evidence archive. Complete bulky receipt/page corpora are separately preserved in the research deliverables. Raw gas-price or fee fields may occur in unmodified provider responses; they are not used in this analysis.'}
 (OUT/'query-manifest.json').write_bytes(encoded(manifest))
 selected=set()
 def add(folder,patterns):
  for pattern in patterns:selected.update(p for p in (R/folder).glob(pattern) if p.is_file())
 add('eth_transfers',['eth_transfers_daily_raw.json','eth_transfers_daily_raw.url','summary.json','index_correction.json','eth_transfers_nonempty_check.json','eth_transfers_type_check.json','sample_*.json','*_receipt.json'])
 add('benchmarks',['raw/*.json','uniswap_manifest.json','uniswap_summary.json','ur211_decoded.json','ur211_repair*.json'])
 add('additional',['raw_approvals/*.json','raw_cctp/*.json','raw_across/*.json','*_manifest_corrected.json','additional_metadata.json','sample_verification.json','provider_duplicate_correction.json'])
 add('lighter',['blockchair-raw/*.json','blockchair-manifest.json','routescan-manifest.json','lighter-normalized.json','validation.json','event-coverage.json','primary-methods.json','admin-attribution.json','deployment-attribution.json','wrapper-reconciliation.json','withdraw-helper-*-review.json','withdraw-helper-bytecode-proof.json','withdraw-helper-manifest.json','rpc-supplement-transactions.json','reconciliation.json','sources-and-methodology.json','withdraw-helper-creation-proof.json'])
 add('rollups',['blockchair-*.json','rollups-*-sources.json','rollups-decoded-source-manifest.json','rollups-metadata.json','rollups-summary.json','full-receipt-manifest.json','exports/receipt-export-manifest.json','recovered-omissions*.json'])
 add('audit',['canonical_correction_transactions.json','canonical_correction_manifest.json','canonical_correction_verification.json','daily_discrepancies.json','duplicated_blocks.json','canonical_daily_blocks.json','canonical_daily_blocks.url','canonical_daily_transactions.json','canonical_daily_transactions.url'])
 method=R/'audit/PUBLIC-METHODOLOGY.md';assert method.exists(),'Public methodology must be final'
 shutil.copyfile(method,OUT/'methodology.md')
 readme='''# L1 Gas Impact — evidence snapshot

Period: March 15 through September 14, 2026 inclusive, Ethereum mainnet, UTC.
Unit: actual receipt gasUsed; blob gas, gas prices, fees and L2 execution excluded.

Product totals are measured exclusive lower bounds. Coverage differs. Read METHODOLOGY.md and query-manifest.json before comparing totals. The ETH-transfer benchmark can overlap incidental product-related ETH transfers; do not sum all rows.

The archive contains selected original provider aggregate responses, final cohort manifests, and canonical verification evidence. Receipt-level CSV downloads for the four rollups are linked in query-manifest.json. Complete large original page corpora are preserved separately. Manifests may reference those larger files; a reference does not imply that every raw page is bundled here. Application source is not included.

Original provider aggregate responses can contain the documented April 16 duplication. Final gas values are the corrected dataset values, not naive sums of all original responses. CONTENTS.json hashes identify the exact bundled bytes; source manifests separately retain original provider file checksums. Local working-directory prefixes in derived provenance files are removed for portability.
'''
 contents=[]
 with zipfile.ZipFile(OUT/'l1-gas-evidence.zip','w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  def put(name,data):
   z.writestr(name,data);contents.append({'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
  put('README.md',readme.encode());put('METHODOLOGY.md',method.read_bytes())
  put('query-manifest.json',(OUT/'query-manifest.json').read_bytes())
  for p in sorted(selected):
   data=p.read_bytes()
   if b'/workspace/' in data and p.suffix=='.json':data=encoded(read(p))
   assert b'/workspace/' not in data,p
   put(str(p.relative_to(R)),data)
  put('CONTENTS.json',encoded(contents))
 with zipfile.ZipFile(OUT/'l1-gas-evidence.zip') as z:assert z.testzip() is None
 print(json.dumps({'source_ids':len(index),'bundled_files':len(contents),'evidence_bytes':(OUT/'l1-gas-evidence.zip').stat().st_size,'receipt_downloads':downloads}))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--research-dir',type=Path,default=R,help='Directory containing the historical evidence corpus')
 R=parser.parse_args().research_dir.expanduser().resolve()
 main()
