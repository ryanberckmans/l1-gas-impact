"""Reconcile external receipt ledgers and bind the result to exact accepted inputs."""
from pathlib import Path
from collections import defaultdict
import csv,gzip,hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
def encoded(value):return (json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def receipt_name(part):
 name=part.get('file') or part['url'].removeprefix('/data/')
 assert re.fullmatch(r'receipts-[a-z0-9-]+\.csv\.gz',name),'Invalid receipt archive path'
 return name
def bindings(manifest,root=ROOT):
 config=json.loads((root/'data/inputs.json').read_text())
 names={'inputs.json','receipt-exports.json',config['verification']['path']}
 names.update(item['path'] for item in config['inputs'])
 for download in manifest['receipt_downloads'].values():names.update(download['input_paths'])
 assert all(not name.startswith('/') and '..' not in Path(name).parts for name in names)
 return {'snapshot_id':manifest['snapshot_id'],'period':manifest['period'],
  'accepted_inputs':{name:digest(root/'data'/name) for name in sorted(names)},
  'receipt_index_sha256':hashlib.sha256(encoded(manifest['receipt_downloads'])).hexdigest(),
  'verifier_sha256':digest(root/'src/receipt_evidence.py')}

# @cc [label:data] Detached storage never relaxes hash uniqueness or daily reconciliation.
def reconcile(manifest,receipt_dir,root=ROOT):
 seen=set();counts={}
 for product,download in manifest['receipt_downloads'].items():
  observed=defaultdict(lambda:[0,0]);count=0
  for part in download['files']:
   path=receipt_dir/receipt_name(part)
   assert path.stat().st_size==part['bytes'] and digest(path)==part['sha256'],('Receipt checksum',path.name)
   part_count=0
   with gzip.open(path,'rt') as source:
    for row in csv.DictReader(source):
     tx=row['transaction_hash']
     assert row['product']==product and re.fullmatch(r'0x[0-9a-f]{64}',tx) and tx not in seen,('Duplicate or invalid receipt hash',product)
     seen.add(tx);gas=int(row['gas_used'])
     assert gas>=21000 and manifest['period']['start_inclusive'][:10]<=row['date']<manifest['period']['end_exclusive'][:10]
     observed[row['date']][0]+=gas;observed[row['date']][1]+=1;count+=1;part_count+=1
   assert part_count==part['transactions']
  expected=defaultdict(lambda:[0,0])
  for name in download['input_paths']:
   assert name.startswith('inputs/') and '..' not in Path(name).parts
   for row in json.loads((root/'data'/name).read_text()):
    if row['product']==product:
     expected[row['date']][0]+=row['gas_used'];expected[row['date']][1]+=row['tx_count']
  assert dict(observed)==dict(expected),('Receipt daily reconciliation',product)
  assert count==download['transactions'] and sum(v[0] for v in observed.values())==download['gas_used']
  counts[product]=count
 return {'schema_version':1,'passed':True,'bindings':bindings(manifest,root),
  'reconciled_receipts':counts,'receipt_hashes_disjoint':True,'daily_gas_and_count_reconciled':True,
  'receipt_parts':sum(len(d['files']) for d in manifest['receipt_downloads'].values()),
  'scope':'Full receipt reconciliation of the indexed exported cohorts; other aggregate-only cohorts retain their separate verification.'}

# @cc [label:release] Reuse is allowed only for unchanged inputs, receipt metadata and verifier.
def verify_certificate(manifest,root=ROOT):
 certificate=json.loads((root/'data/receipt-validation.json').read_text())
 assert certificate['schema_version']==1 and certificate['passed']
 assert certificate['bindings']==bindings(manifest,root),'Receipt evidence changed: reconcile the separate archive again'
 assert certificate['receipt_hashes_disjoint'] and certificate['daily_gas_and_count_reconciled']
 assert certificate['reconciled_receipts']=={p:d['transactions'] for p,d in manifest['receipt_downloads'].items()}
 assert certificate['receipt_parts']==sum(len(d['files']) for d in manifest['receipt_downloads'].values())
 return certificate
