"""Release gate for numeric consistency, public boundaries, and static routes."""
from pathlib import Path
from collections import defaultdict
from html.parser import HTMLParser
from urllib.parse import urlparse
import argparse,json,csv,zipfile,gzip,re,subprocess,hashlib
from receipt_evidence import reconcile,verify_certificate

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'dist'
class Page(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=[];self.lang=None;self.canonical=None;self.alternates=0;self.meta={}
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='meta':self.meta[a.get('property',a.get('name',''))]=a.get('content')
  if 'id'in a:self.ids.append(a['id'])
  if tag=='html':self.lang=a.get('lang')
  for key in ['href','src']:
   if key in a:self.links.append(a[key])
  if tag=='link' and a.get('rel')=='canonical':self.canonical=a.get('href')
  if tag=='link' and a.get('rel')=='alternate':self.alternates+=1

def main(receipt_dir=None):
 files=[p for p in OUT.rglob('*') if p.is_file()]
 directories=[p for p in OUT.rglob('*') if p.is_dir()]
 expanded_bytes=sum(p.stat().st_size for p in files)
 # The host limits the decompressed TAR stream, including headers and padding.
 # The static packager adds the root and a small hosting manifest under .openai.
 archive_blocks=sum((p.stat().st_size+511)//512 for p in files)+len(files)+len(directories)+6
 estimated_archive_bytes=((archive_blocks*512+10239)//10240)*10240
 assert estimated_archive_bytes<256*1024*1024,('Publication exceeds hosting archive limit',estimated_archive_bytes)
 config=json.loads((ROOT/'data/inputs.json').read_text());assert config['accepted_for_publication']
 d=json.loads((OUT/'data/summary.json').read_text());assert d['publication_ready']
 source=json.loads((OUT/'data/dataset.json').read_text());assert source['metadata']['snapshot_id']==d['snapshot_id']
 manifest=json.loads((OUT/'data/query-manifest.json').read_text());assert manifest['publication_ready']
 assert manifest['snapshot_id']==d['snapshot_id']
 source_ids={r['source_id'] for r in source['records']};assert source_ids.issubset(set(manifest['source_index'])),source_ids-set(manifest['source_index'])
 totals=defaultdict(lambda:[0,0]);detail_totals=defaultdict(lambda:[0,0])
 for r in source['records']:
  assert isinstance(r['gas_used'],int) and 0<=r['gas_used']<2**53
  t=totals[(r['product'],r['date'])];t[0]+=r['gas_used'];t[1]+=r['tx_count']
  t=detail_totals[(r['date'],r['product'],r['activity'])];t[0]+=r['gas_used'];t[1]+=r['tx_count']
 for product,rows in d['series'].items():
  assert len(rows)==len(d['dates']) and [r['date'] for r in rows]==d['dates']
  for r in rows:
   assert totals[(product,r['date'])]==[r['gas'],r['tx']]
   assert r['gas']==sum(r['buckets'].values())==sum(r['details'].values())
 with (OUT/'data/l1-gas-daily.csv').open() as f:
  exported=list(csv.DictReader(f))
 assert len(exported)==len(detail_totals)
 for r in exported:assert detail_totals[(r['date_utc'],r['product'],r['activity'])]==[int(r['execution_gas_used']),int(r['transaction_count'])]
 social=json.loads((ROOT/'src/social-card.json').read_text())
 english=json.loads((ROOT/'data/locales/en.json').read_text())
 assert social['reviewed_copy']=={k:english[k] for k in ['title','headline','intro']}
 assert hashlib.sha256((OUT/social['image']).read_bytes()).hexdigest()==social['sha256']
 catalogues={}
 for target in OUT.rglob('index.html'):
  text=target.read_text();p=Page();p.feed(text);locale=p.lang
  assert locale in d['locales']
  assert 'class="daily-bars"' in text and 'id="breakdown-body"><tr' in text,'Missing prerendered detail content'
  assert p.lang==locale and p.alternates==(0 if target.parent.name in ['7','30',str(len(d['dates']))] else 9)
  labels=json.loads((ROOT/'data/locales'/f'{locale}.json').read_text())
  assert p.meta['description']==p.meta['og:description']==p.meta['twitter:description']==labels['intro']
  social_title=labels['title']+' — '+labels['headline']
  assert p.meta['og:title']==p.meta['twitter:title']==social_title
  assert p.meta['og:image:alt']==p.meta['twitter:image:alt']==social_title
  assert p.meta['og:image']==p.meta['twitter:image']=='https://l1-gas-impact.zqnm.chatgpt.site/'+social['image']
  assert p.meta['og:image:width']==str(social['width']) and p.meta['og:image:height']==str(social['height'])
  assert 'id="theme"' in text and text.index('window.GAS_THEME')<text.index('href="/assets/style.css"')
  for mode in ['system','light','dark']:assert labels['theme_'+mode] in text
  assert len(p.ids)==len(set(p.ids)),('Duplicate HTML id',locale)
  assert p.canonical=='https://l1-gas-impact.zqnm.chatgpt.site'+('/' if locale=='en' else '/'+locale+'/')
  for link in p.links:
   if link.startswith('data:'):continue
   uri=urlparse(link)
   if uri.scheme:continue
   if uri.path:
    path=OUT/uri.path.lstrip('/') if uri.path.startswith('/') else target.parent/uri.path
    if path.is_dir():path=path/'index.html'
    assert path.is_file(),(target,link)
   elif uri.fragment:assert uri.fragment in p.ids,(locale,link)
  catalogue_url=('/' if locale=='en' else '/'+locale+'/')+'catalogue.html'
  assert catalogue_url in p.links,'Missing native catalogue link'
  if locale not in catalogues:
   catalogue=Page();catalogue.feed((OUT/catalogue_url.lstrip('/')).read_text())
   assert catalogue.lang==locale and catalogue.meta['description']==labels['intro']
   for product in d['series']:
    for days in [7,30,len(d['dates'])]:
     href=('/' if locale=='en' else '/'+locale+'/')+product+'/'+str(days)+'/'
     assert href in catalogue.links and (OUT/href.lstrip('/')/'index.html').is_file(),'Missing native product navigation'
   catalogues[locale]=catalogue
 # Allow only the canonical repository address through the privacy check.
 repository_url=json.loads((ROOT/'src/repository.json').read_text())['url']
 assert repository_url=='https://github.com/ryanberckmans/l1-gas-impact'
 forbidden=re.compile(r'@cc\s|/workspace/|source_repository_credential|token_expires_at|BEGIN (?:RSA |EC )?PRIVATE KEY|git\.chatgpt-team\.site|berckmans|safe\.ryanb|account-wide|user prompt|system prompt|sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.-]{15,}',re.I)
 for p in OUT.rglob('*'):
  if p.is_file():
   assert p.stat().st_size<20*1024*1024,('Split oversized public asset',p)
   if p.suffix in ['.html','.js','.json','.md','.txt','.css','.csv'] or p.name in ['LICENSE','THIRD_PARTY_NOTICES']:
    public_text=p.read_text().replace(repository_url,'')
    if p==OUT/'LICENSE':public_text=public_text.replace('Copyright (c) 2026 Ryan Berckmans','')
    assert not forbidden.search(public_text),('Private content in public output',p)
   if p.suffix=='.gz':
    with gzip.open(p,'rt') as f:assert not forbidden.search(f.read()),('Private content in compressed output',p)
 with zipfile.ZipFile(OUT/'data/l1-gas-evidence.zip') as z:
  assert z.testzip() is None
  assert 'README.md' in z.namelist()
  contents=json.loads(z.read('CONTENTS.json'))
  assert set(z.namelist())=={r['file'] for r in contents}|{'CONTENTS.json'}
  for entry in contents:
   b=z.read(entry['file'])
   assert len(b)==entry['bytes'] and hashlib.sha256(b).hexdigest()==entry['sha256'],('Evidence checksum',entry['file'])
  for n in z.namelist():
   assert not n.endswith(('.py','.js','.ts','.tsx')) and '..' not in Path(n).parts
   payload=z.read(n)
   if n.endswith('.gz'):payload=gzip.decompress(payload)
   assert not forbidden.search(payload.decode('utf-8')),('Private content in evidence archive',n)
 assert len(list(OUT.rglob('index.html')))==len(d['locales'])*(1+3*len(d['product_order']))
 assert {'solana','hyperliquid','bsc','polygon'}<=set(d['product_order'])
 assert not any(p.startswith('all_') for p in d['product_order'])
 assert all(not r['product'].startswith('all_') for r in source['records'])
 assert d['receipt_exports']==manifest['receipt_downloads']
 assert not (OUT/'__audit_preview.html').exists(),'Remove private preview harness'
 if (ROOT/'data/receipt-archive.json').exists():
  certificate=verify_certificate(manifest)
  assert manifest['receipt_archive']==json.loads((ROOT/'data/receipt-archive.json').read_text())
  assert json.loads((OUT/'data/receipt-index.json').read_text())['products']==manifest['receipt_downloads']
  assert (OUT/'data/receipt-validation.json').read_bytes()==(ROOT/'data/receipt-validation.json').read_bytes()
  assert not list((OUT/'data').glob('receipts-*.csv.gz')),'Bulk receipts must stay outside the release'
  if receipt_dir is not None:assert reconcile(manifest,receipt_dir)==certificate,'Detached receipt recount changed'
  receipt_counts=certificate['reconciled_receipts']
  receipt_mode='full_recount' if receipt_dir is not None else 'checksum_bound_previous_full_recount'
 else:
  certificate=reconcile(manifest,receipt_dir or OUT/'data')
  receipt_counts=certificate['reconciled_receipts'];receipt_mode='full_recount'
 for p in (OUT/'assets').glob('*.js'):subprocess.run(['node','--check',str(p)],check=True,capture_output=True)
 subprocess.run(['node',str(ROOT/'src/check_theme.cjs')],check=True,capture_output=True)
 perf={p:len(gzip.compress((OUT/p).read_bytes())) for p in ['index.html','assets/style.css','assets/app.js','assets/snapshot.js','assets/labels-en.js']}
 result={'passed':True,'social_card_copy_and_metadata_consistent':True,'reconciled_receipts':receipt_counts,'receipt_hashes_disjoint':True,'evidence_checksums_verified':True,'compressed_exports_privacy_scan':True,'products':len(d['series']),'days':len(d['dates']),'locales':len(d['locales']),'source_records':len(source['records']),'csv_rows':len(exported),'snapshot_id':d['snapshot_id'],'static_views':len(list(OUT.rglob('index.html'))),'compressed_initial_assets_bytes':sum(perf.values()),'performance_scope':'Payload measurement only; no field Web Vitals claim','browser_qa':'Actual rendered and interaction review is recorded in the separate private audit; this report covers automated artifact checks.'}
 result['receipt_verification_mode']=receipt_mode
 result['expanded_public_bytes']=expanded_bytes
 result['estimated_expanded_archive_bytes']=estimated_archive_bytes
 (ROOT/'data/release-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--receipt-dir',type=Path,help='Extracted separate receipt archive for a fresh full recount')
 main(parser.parse_args().receipt_dir)
