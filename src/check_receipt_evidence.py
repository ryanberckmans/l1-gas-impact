"""Check that detached receipt evidence fails closed when its bindings change."""
from pathlib import Path
from tempfile import TemporaryDirectory
import copy,json,shutil
from receipt_evidence import ROOT,bindings,reconcile,verify_certificate

manifest=json.loads((ROOT/'dist/data/query-manifest.json').read_text())
verify_certificate(manifest)
def rejected(action):
 try:action()
 except (AssertionError,FileNotFoundError):return
 raise AssertionError('Changed or missing receipt evidence was accepted')

changed=copy.deepcopy(manifest)
next(iter(changed['receipt_downloads'].values()))['files'][0]['sha256']='0'*64
rejected(lambda:verify_certificate(changed))
with TemporaryDirectory() as temporary:
 root=Path(temporary)
 names=['data/'+n for n in bindings(manifest)['accepted_inputs']]
 names+=['data/receipt-validation.json','src/receipt_evidence.py']
 for name in names:
  path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,path)
 verify_certificate(manifest,root)
 input_file=root/'data/inputs/coverage.json';original=input_file.read_bytes()
 input_file.write_bytes(original+b'\n')
 rejected(lambda:verify_certificate(manifest,root));input_file.write_bytes(original)
 verifier=root/'src/receipt_evidence.py';verifier.write_bytes(verifier.read_bytes()+b'\n')
 rejected(lambda:verify_certificate(manifest,root))
 rejected(lambda:reconcile(manifest,root/'missing-ledgers'))
print(json.dumps({'passed':True,'cases':['unchanged_certificate','changed_receipt_checksum','changed_accepted_input','changed_verifier','missing_receipt_ledger']}))
