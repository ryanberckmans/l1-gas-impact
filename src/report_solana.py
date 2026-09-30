"""Assemble separate, auditable Solana research. Never writes to public output."""
from pathlib import Path
from datetime import date,timedelta
from collections import defaultdict,Counter
import sys,json,csv,gzip,hashlib,io

START='2026-03-28';END='2026-09-28'
def main():
 sol,refresh,destination=map(Path,sys.argv[1:4]);destination.mkdir(parents=True,exist_ok=True)
 for base,name in [(sol,'acquisition'),(sol,'canonical-verification'),(sol,'supplement-verification'),(sol,'sample-verification'),(refresh,'supplement-verification')]:
  assert not json.loads((base/(name+'.json')).read_text())['errors'],name
 assert not json.loads((sol/'core-verification.json').read_text())['mismatches']
 rows=json.loads((sol/'core-accepted.json').read_text());inputs=[sol/'core-accepted.json']
 for base in [sol,refresh]:
  catalog=json.loads((base/'aggregate-catalog.json').read_text())
  sources=[s for s in catalog if s['product']=='solana' and s['group'] in ['cctp','across']]
  for s in sources:
   path=base/'supplement-verified'/(s['source_id']+'.json');inputs.append(path)
   for r in json.loads(path.read_text()):
    rows.append({k:r[k] for k in ['date','transaction_hash','gas_used','block_number','source_id','selector','status']}|{
     'protocol':'Circle CCTP' if s['group']=='cctp' else 'Across',
     'direction':'Solana → Ethereum' if s.get('direction')=='receive' else 'Ethereum → Solana'})
 assert len(rows)==len({r['transaction_hash'] for r in rows}), 'Overlapping Solana cohorts'
 assert all(START<=r['date']<END and isinstance(r['gas_used'],int) and r['gas_used']>=21000 for r in rows)
 rows.sort(key=lambda r:(r['date'],r['block_number'],r['transaction_hash']))
 windows={}
 for days in [184,30,7]:
  start=(date.fromisoformat(END)-timedelta(days=days)).isoformat();selected=[r for r in rows if r['date']>=start]
  byprotocol=defaultdict(lambda:{'gas_used':0,'transactions':0});bydirection=defaultdict(lambda:{'gas_used':0,'transactions':0})
  for r in selected:
   for d,key in [(byprotocol,r['protocol']),(bydirection,r['direction'])]:d[key]['gas_used']+=r['gas_used'];d[key]['transactions']+=1
  gas=sum(r['gas_used'] for r in selected)
  windows[str(days)]={'start_inclusive':start,'end_exclusive':END,'days':days,'gas_used':gas,'transactions':len(selected),'mean_gas_per_day':gas/days,'equivalent_21000_gas_transfers':gas/21000,'protocols':dict(byprotocol),'directions':dict(bydirection)}
 summary={'metric':'Ethereum L1 receipt gasUsed exclusively attributable to decoded Solana routes','scope':'Verified lower bound for selected direct bridge entrypoints; not native Solana execution, fees, or a complete Solana footprint.',
  'start_inclusive':START,'end_exclusive':END,'windows':windows,'failed_transactions_included':sum(r['status']=='failed' for r in rows),
  'coverage':['Wormhole Token Bridge: chain-specific outbound calls, successful authenticated incoming Solana VAAs, and Solana token administration.','deBridge DLN: Solana-specific source orders; verified ERC20/no-callback fills on Ethereum; exclusively Solana order unlock, cancellation and patch operations.','Circle CCTP v1/v2: burns to domain 5 and authenticated messages from domain 5 to Ethereum token messengers.','Across: direct Ethereum deposits targeting Solana chain identifier 34268394551451.'],
  'exclusions':['Native Solana compute and transaction fees.','Shared bridge settlements, mixed-destination batches and common governance.','Unresolved wrappers and aggregator parents; assigning them in full would overstate exclusive gas.','Unverified native-ETH withdrawal callbacks, DLN external calls and unreviewed methods.','Undiscovered protocols/contracts and unmeasured associated token approvals.'],
  'verification':{'account_daily_populations':3,'account_provider_comparison':'Routescan transaction receipts vs Blockchair daily count and gas; exact agreement after documented historical duplicate-index repair.','canonical_conflicts':len(json.loads((sol/'canonical-verification.json').read_text())['results']),'supplemental_sources':len(inputs)-1,'independent_supplemental_receipt_samples':len(json.loads((sol/'sample-verification.json').read_text())['results']),'supplemental_reconciliation':'Every requested source fully paginated and decoded; daily counts and gas match its aggregate. Large incoming CCTPv2 cohort collected in disjoint months.'},
  'input_sha256':{str(p.relative_to(sol.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}}
 (destination/'solana-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 stream=io.StringIO(newline='');w=csv.DictWriter(stream,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (destination/'solana-included-receipts.csv.gz').write_bytes(gzip.compress(stream.getvalue().encode(),mtime=0))
 daily=defaultdict(lambda:[0,0])
 for r in rows:daily[(r['date'],r['protocol'],r['direction'])][0]+=r['gas_used'];daily[(r['date'],r['protocol'],r['direction'])][1]+=1
 with (destination/'solana-daily.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['date_utc','protocol','direction','execution_gas_used','transaction_count'])
  for key,v in sorted(daily.items()):w.writerow([*key,*v])
 report=['# Solana-linked Ethereum L1 execution gas','',f'March 28–September 27, 2026 UTC. This is separate research and is not included in L1 Gas Impact.','',summary['scope'],'','| Window | Execution gas | Included transactions | Mean gas/day |','|---|---:|---:|---:|']
 for days,v in windows.items():report.append(f'| {days} days | {v["gas_used"]:,} | {v["transactions"]:,} | {v["mean_gas_per_day"]:,.2f} |')
 report+=['','## Six-month protocol breakdown','','| Protocol | Execution gas | Included transactions | Share of measured gas |','|---|---:|---:|---:|']
 for p,v in sorted(windows['184']['protocols'].items(),key=lambda x:-x[1]['gas_used']):report.append(f'| {p} | {v["gas_used"]:,} | {v["transactions"]:,} | {v["gas_used"]/windows["184"]["gas_used"]*100:.2f}% |')
 report+=['','## Attribution','']+['- '+x for x in summary['coverage']]+['','## Exclusions','']+['- '+x for x in summary['exclusions']]
 report+=['','## Evidence','',f'Three complete account populations reconcile daily across two providers. Three disputed transaction hashes were resolved against canonical receipts and block membership. All 12 supplemental predicates were fully collected, decoded and reconciled; six independently checked receipts cover all nonempty supplemental selectors. Historical index duplicates are repaired only for proven affected blocks. No full independent Ethereum recount is claimed. {summary["failed_transactions_included"]:,} failed but attributable transactions are included.','', 'The included receipt CSV contains unique transaction hashes and exact integer gas. The summary JSON binds input checksums; daily CSV records product-level protocol/direction aggregates. The raw evidence archive retains successful provider responses, query metadata, exclusions and correction records.','', 'Identity references: [Circle contracts/domains](https://developers.circle.com/cctp/references/contract-addresses), [Wormhole contracts](https://wormhole.com/docs/reference/contract-addresses/), [deBridge DLN contracts](https://docs.debridge.com/dln-details/overview/deployed-contracts), [Across contracts](https://docs.across.to/chains-and-contracts).','']
 (destination/'Solana-L1-Gas-Research.md').write_text('\n'.join(report))
 print(json.dumps({k:{x:v[x] for x in ['gas_used','transactions','mean_gas_per_day']} for k,v in windows.items()}))
if __name__=='__main__':main()
