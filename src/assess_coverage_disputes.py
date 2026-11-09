"""Locate independently reconciled coverage differences by block.

Usage: assess_coverage_disputes.py RESEARCH_DIR BASELINE_RESEARCH
Original responses remain immutable; this script does not accept corrections.
"""
import sys,json,gzip,re
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
from urllib.parse import urlencode
import acquire_refresh as A
R=A.R;OLD=A.OLD
for checkpoint in [R/'provider-usage.json',R/'provider-usage-supplements.json']:
 if checkpoint.exists():
  for host,count in json.loads(checkpoint.read_text())['requests'].items():A.counters[host]=max(A.counters.get(host,0),count)
prior=json.loads((R/'classification-verification.json').read_text());targets={s['address']:set(s['differences']) for s in prior['sources'] if s['differences']}
core=R/'daily-reconciliation.json'
if core.exists():
 catalog={s['source_id']:s for s in json.loads((R/'aggregate-catalog.json').read_text())}
 for mismatch in json.loads(core.read_text())['mismatches']:
  source=catalog[mismatch['source_id']];address=source.get('recipient',source.get('address'))
  targets.setdefault(address,set()).update(mismatch['differences'])
assert sum(len(dates) for dates in targets.values())<=32,'Disputed-date budget exceeded'
repairs={}
for f in [OLD.parents[1]/'solana/canonical-verification.json',OLD.parents[1]/'refresh/canonical-verification.json',R/'canonical-run.json',R/'canonical-extra.json']:
 if f.exists():repairs.update({s['hash']:s for s in json.loads(f.read_text())['results']})
extra=json.loads((R/'canonical-extra.json').read_text()) if (R/'canonical-extra.json').exists() else {}
rejected={x['hash'] for x in extra.get('rejected_noncanonical',[])}
corrections=json.loads((OLD/'audit/canonical_correction_transactions.json').read_text())
results=[];errors=[]
for a,dates in targets.items():
 local={d:{} for d in dates}
 with gzip.open(R/'ledgers'/(a+'.jsonl.gz'),'rt') as stream:
  for line in stream:
   h=re.search(r'"hash":"(0x[0-9a-f]+)"',line)[1];timestamp=re.search(r'"timeStamp":"([0-9]+)"',line)[1]
   if h in rejected:continue
   fix=repairs.get(h,{});date=datetime.fromtimestamp(int(fix.get('timeStamp',timestamp)),timezone.utc).date().isoformat()
   if date in dates:
    r=json.loads(line);r.update(fix)
    if (r.get('to') or '').lower()==a:local[date][h]={'hash':h,'block_number':int(r['blockNumber']),'gas_used':int(r['gasUsed']),'date':date}
 for h,r in repairs.items():
  date=datetime.fromtimestamp(int(r['timeStamp']),timezone.utc).date().isoformat()
  if date in dates and (r.get('to') or '').lower()==a:local[date][h]={'hash':h,'block_number':int(r['blockNumber']),'gas_used':int(r['gasUsed']),'date':date}
 aggregate_path=R/'aggregates'/('coverage-'+a+'.json')
 original=json.loads(aggregate_path.read_text()) if aggregate_path.exists() else None
 for d in sorted(dates):
  expected=next(([r['sum(gas_used)'],r['count()']] for r in original['data'] if r['date']==d),[0,0]) if original else None
  if original and 'ETH4' in original['context']['servers']:
   for r in corrections:
    if r['recipient']==a and r['date']==d:expected[0]-=r['gas_used'];expected[1]-=1
  actual=[sum(r['gas_used'] for r in local[d].values()),len(local[d])]
  if actual==expected:results.append({'address':a,'date':d,'resolved_by_existing_canonical_repairs':True});continue
  try:
   url='https://api.blockchair.com/ethereum/transactions?'+urlencode({'q':f'time({d}..{d}),recipient({a})','a':'block_id,count(),sum(gas_used)','limit':10000})
   j,p=A.fetch(url,R/'disputed-blocks'/f'{a}-{d}-aggregates.json');assert len(j['data'])==j['context']['total_rows']
   blocks={r['block_id']:[r['sum(gas_used)'],r['count()']] for r in j['data']};ours=defaultdict(lambda:[0,0])
   for r in local[d].values():v=ours[r['block_number']];v[0]+=r['gas_used'];v[1]+=1
   if 'ETH4' in j['context']['servers']:
    for r in corrections:
     if r['recipient']==a and r['date']==d:
      v=blocks[r['block_id']];v[0]-=r['gas_used'];v[1]-=1
   mismatch={b:{'routescan':ours.get(b,[0,0]),'blockchair':blocks.get(b,[0,0])} for b in ours.keys()|blocks.keys() if ours.get(b,[0,0])!=blocks.get(b,[0,0])}
   result={'address':a,'date':d,'original_aggregate':expected,'receipt_total':actual,'block_aggregate_total':[sum(v[0] for v in blocks.values()),sum(v[1] for v in blocks.values())],'mismatched_blocks':mismatch,'provenance':p,'local_records':list(local[d].values())}
   results.append(result);print(json.dumps({k:v for k,v in result.items() if k!='local_records'}),flush=True)
  except Exception as e:errors.append({'address':a,'date':d,'error':str(e)})
A.save(R/'discrepancy-assessment.json',{'results':results,'errors':errors,'request_counts':A.counters})
A.save(R/'provider-usage.json',{'requests':A.counters})
assert not errors,errors
