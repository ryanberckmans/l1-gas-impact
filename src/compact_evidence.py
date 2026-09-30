"""Preserve bulk receipts outside the repo; keep compact public provenance consistent."""
from pathlib import Path
import argparse,hashlib,json,shutil,zipfile
from receipt_evidence import ROOT,receipt_name,reconcile,verify_certificate

DATA=ROOT/'data';OUT=ROOT/'dist/data'
def encoded(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def save(path,value):path.write_bytes(encoded(value))
def publish_compact():
 if not (DATA/'receipt-archive.json').exists():return
 archive=json.loads((DATA/'receipt-archive.json').read_text())
 downloads=json.loads((DATA/'receipt-exports.json').read_text())
 manifest=json.loads((OUT/'query-manifest.json').read_text())
 manifest['receipt_downloads']=downloads;manifest['receipt_archive']=archive
 manifest['receipt_validation']='/data/receipt-validation.json'
 manifest['raw_data_note']='Compact aggregate responses, dated baseline evidence and verification records are bundled. Transaction receipt CSVs are preserved in a separate archive, indexed by filename, checksum and population coverage in receipt-index.json; they are not included in this site or source repository. Full original provider page corpora are preserved separately.'
 certificate=verify_certificate(manifest)
 index={'snapshot_id':manifest['snapshot_id'],'period':manifest['period'],'archive':archive,
  'products':downloads,'validation':'/data/receipt-validation.json'}
 save(OUT/'query-manifest.json',manifest);save(OUT/'receipt-index.json',index)
 save(OUT/'receipt-validation.json',certificate)
 for path in [DATA/'summary.json',OUT/'summary.json']:
  if path.exists():
   summary=json.loads(path.read_text());summary['receipt_exports']=downloads;save(path,summary)
 method=OUT/'methodology.md';text=method.read_text()
 start=text.index('CSV, JSON, all eight language views and social metadata derive')
 end=text.index('\n\n',start)
 paragraph='CSV, JSON, all eight language views and social metadata derive from this accepted snapshot and its current scope. The bulk transaction receipt CSVs are preserved in a separate archive and are not hosted with the app or included in its source repository. receipt-index.json retains every file checksum, transaction count and exact population coverage; receipt-validation.json records the full reconciliation, bound to the accepted inputs and verifier. To repeat the receipt recount, obtain the separate archive and run the documented validation command. These ledgers include every newly included receipt and previously published core receipts. Original supplemental approvals outside those core exports remain documented in the structured dataset. No synthetic aggregate receipt is created.'
 method.write_text(text[:start]+paragraph+text[end:])
 with zipfile.ZipFile(OUT/'l1-gas-evidence.zip') as old:
  files={n:old.read(n) for n in old.namelist() if n!='CONTENTS.json'}
 for name in ['dataset.json','l1-gas-daily.csv','query-manifest.json','methodology.md','receipt-index.json','receipt-validation.json']:files[name]=(OUT/name).read_bytes()
 note=b'\nBulk receipt CSVs are preserved in a separate archive, outside this ZIP and the app repository. See receipt-index.json for checksums and receipt-validation.json for reconciliation.\n'
 if note not in files['README.md']:files['README.md']+=note
 contents=[{'file':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(files.items())]
 temporary=OUT/'evidence-compact.tmp'
 with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name,payload in sorted(files.items()):z.writestr(name,payload)
  z.writestr('CONTENTS.json',encoded(contents))
 with zipfile.ZipFile(temporary) as z:assert z.testzip() is None
 temporary.replace(OUT/'l1-gas-evidence.zip')

def detach(receipt_dir,archive_path):
 assert not archive_path.is_relative_to(ROOT) and not receipt_dir.is_relative_to(ROOT),'Keep bulk receipt work and archives outside the repository'
 receipt_dir.mkdir(parents=True,exist_ok=True)
 downloads=json.loads((DATA/'receipt-exports.json').read_text())
 for download in downloads.values():
  download['availability']='separate_archive'
  for part in download['files']:
   name=receipt_name(part);source=OUT/name;target=receipt_dir/name
   if source.exists():shutil.copyfile(source,target)
   assert target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==part['sha256']
   part.pop('url',None);part['file']=name
 save(DATA/'receipt-exports.json',downloads)
 manifest=json.loads((OUT/'query-manifest.json').read_text());manifest['receipt_downloads']=downloads
 certificate=reconcile(manifest,receipt_dir)
 save(DATA/'receipt-validation.json',certificate)
 archive_path.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(archive_path,'w',zipfile.ZIP_STORED) as z:
  z.writestr('README.md','Transaction receipt ledgers for snapshot '+manifest['snapshot_id']+'.\nExtract this archive and run python3 src/validate_release.py --receipt-dir /path/to/extracted/archive from the matching app repository.\nThe JSON index records exact gzip bytes and each population. Application source is not included.\n')
  z.writestr('receipt-index.json',encoded({'snapshot_id':manifest['snapshot_id'],'period':manifest['period'],'products':downloads}))
  for download in downloads.values():
   for part in download['files']:
    name=receipt_name(part);z.write(receipt_dir/name,name)
 with zipfile.ZipFile(archive_path) as z:assert z.testzip() is None
 save(DATA/'receipt-archive.json',{'file':archive_path.name,'bytes':archive_path.stat().st_size,
  'sha256':hashlib.sha256(archive_path.read_bytes()).hexdigest(),'availability':'separate_archive',
  'index':'/data/receipt-index.json','note':'Preserved separately. Receipt CSVs are absent from the site and source repository.'})
 publish_compact()
 # Remove only after the exact ledgers are copied, fully reconciled and archived.
 for download in downloads.values():
  for part in download['files']:(OUT/receipt_name(part)).unlink(missing_ok=True)
 print(json.dumps({'receipt_files':certificate['receipt_parts'],'transactions':sum(certificate['reconciled_receipts'].values()),'archive_bytes':archive_path.stat().st_size}))

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--receipt-dir',type=Path,required=True)
 parser.add_argument('--archive-path',type=Path,required=True)
 args=parser.parse_args();detach(args.receipt_dir.resolve(),args.archive_path.resolve())
