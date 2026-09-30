"""Prerender every supported view; preserve native navigation before hydration."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import json,html,hashlib,shutil,subprocess

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'dist'
DATA=ROOT/'data'
ORIGIN='https://l1-gas-impact.zqnm.chatgpt.site'
LOCALES={'en':'English','es':'Español','pt-BR':'Português','fr':'Français','de':'Deutsch','zh-CN':'简体中文','ja':'日本語','ko':'한국어'}
def esc(v):return html.escape(str(v),quote=True)
def loc_url(loc):return ORIGIN+('/' if loc=='en' else '/'+loc+'/')
def js(v):return json.dumps(v,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
def main():
 from compact_evidence import publish_compact
 publish_compact()
 d=json.loads((DATA/'summary.json').read_text())
 social=json.loads((ROOT/'src/social-card.json').read_text())
 labels={loc:json.loads((DATA/'locales'/f'{loc}.json').read_text()) for loc in LOCALES}
 assert all(set(t)==set(labels['en']) for t in labels.values())
 assert social['reviewed_copy']=={k:labels['en'][k] for k in ['title','headline','intro']},'Review social image whenever framing changes'
 assert hashlib.sha256((OUT/social['image']).read_bytes()).hexdigest()==social['sha256']
 (OUT/'assets').mkdir(parents=True,exist_ok=True)
 subprocess.run(['node','src/render.mjs'],cwd=ROOT,check=True)
 bodies=json.loads((ROOT/'.build/bodies.json').read_text())
 theme=(ROOT/'.build/theme.min.js').read_text()
 css=(ROOT/'src/style.css').read_text()
 critical=':root{color-scheme:light;--paper:#fff;--ink:#182235}:root[data-theme=dark]{color-scheme:dark;--paper:#111827;--ink:#edf2fa}@media(prefers-color-scheme:dark){:root:not([data-theme]){color-scheme:dark;--paper:#111827;--ink:#edf2fa}}body{margin:0;background:var(--paper);color:var(--ink);font:1rem/1.5 system-ui,sans-serif}'
 pages=0
 for loc,t in labels.items():
  (OUT/f'assets/labels-{loc}.js').write_text('window.GAS_LABELS='+js(t)+';')
  url=loc_url(loc)
  alternate=''.join(f'<link rel="alternate" hreflang="{l}" href="{loc_url(l)}">' for l in LOCALES)+f'<link rel="alternate" hreflang="x-default" href="{ORIGIN}/">'
  title=esc(t['title']+' — '+t['headline']);desc=esc(t['intro']);image=ORIGIN+'/'+social['image']
  head=f'''<!doctype html><html lang="{loc}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(t['title'])} — {esc(t['pageTitleSuffix'])}</title><meta name="description" content="{desc}"><link rel="canonical" href="{url}">{alternate}<meta property="og:type" content="website"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}"><meta property="og:url" content="{url}"><meta property="og:image" content="{image}"><meta property="og:image:width" content="{social['width']}"><meta property="og:image:height" content="{social['height']}"><meta property="og:image:type" content="image/png"><meta property="og:image:alt" content="{title}"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{title}"><meta name="twitter:description" content="{desc}"><meta name="twitter:image" content="{image}"><meta name="twitter:image:alt" content="{title}"><meta name="theme-color" content="#182235"><link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='5' fill='%23182335'/%3E%3Cpath d='M7 8h18v4H7zm0 6h13v4H7zm0 6h8v4H7z' fill='%235fa1ff'/%3E%3C/svg%3E"><style>{critical}</style><script>{theme}</script><link rel="stylesheet" href="/assets/style.css"></head><body>'''
  for product in d['product_order']:
   for days in [7,30,len(d['dates'])]:
    view={'locale':loc,'product':product,'days':days,'day':d['end']}
    key=f'{loc}/{product}/{days}'
    page=head+'<div id="app">'+bodies[key]+'</div><script src="/assets/labels-'+loc+'.js"></script><script>window.GAS_LOCALE='+js(loc)+';window.GAS_VIEW='+js(view)+';</script><script src="/assets/snapshot.js"></script><script src="/assets/app.js" defer></script></body></html>'
    dest=OUT/('' if loc=='en' else loc)/product/str(days)
    dest.mkdir(parents=True,exist_ok=True);(dest/'index.html').write_text(page.replace(alternate,''));pages+=1
    if product=='lighter' and days==30:
     parent=OUT/('' if loc=='en' else loc);(parent/'index.html').write_text(page);pages+=1
  names={**d['product_names'],'eth':t['plainTransfers'],'uniswap':t['uniswapName'],'lighter':t['lighterName']}
  for product,group in d['product_groups'].items():
   if group=='app':names[product]=t['l1AppName'].replace('{app}',d['product_names'][product].removesuffix(' on L1'))
  prefix='' if loc=='en' else loc+'/'
  rows=''.join('<tr><th scope="row">'+esc(names[product])+'</th>'+''.join(f'<td><a href="/{prefix}{product}/{days}/">{esc(label)}</a></td>' for days,label in [(7,t['days7']),(30,t['days30']),(len(d['dates']),t['months6'])])+'</tr>' for product in d['product_order'])
  catalogue=head+'<header><a class="brand" href="'+url+'">L1 GAS IMPACT</a><div class="preferences">'+bodies[f'{loc}/repository']+'<div id="seal-root">'+bodies[f'{loc}/seal']+'</div></div></header><main><h1>'+esc(t['comparison'])+'</h1><p>'+desc+'</p><div class="table-scroll"><table><thead><tr><th>'+esc(t['product'])+'</th><th>'+esc(t['days7'])+'</th><th>'+esc(t['days30'])+'</th><th>'+esc(t['months6'])+'</th></tr></thead><tbody>'+rows+'</tbody></table></div></main><script src="/assets/labels-'+loc+'.js"></script><script src="/assets/app.js" defer></script></body></html>'
  (OUT/('' if loc=='en' else loc)/'catalogue.html').write_text(catalogue)
 (OUT/'assets/snapshot.js').write_text('window.GAS_IMPACT={data:'+js(d)+',labels:window.GAS_LABELS,locale:window.GAS_LOCALE,initialView:window.GAS_VIEW};')
 shutil.copy(ROOT/'src/style.css',OUT/'assets/style.css')
 for notice in ['LICENSE','THIRD_PARTY_NOTICES']:shutil.copy(ROOT/notice,OUT/notice)
 for asset in (ROOT/'src/assets').glob('seal*.png'):shutil.copy(asset,OUT/'assets'/asset.name)
 shutil.copy(DATA/'summary.json',OUT/'data/summary.json')
 (OUT/'agents.md').write_text((ROOT/'src/data-guide.md').read_text().format(start=d['start'],end_exclusive=(datetime.fromisoformat(d['end'])+timedelta(days=1)).date().isoformat()))
 (OUT/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {ORIGIN}/sitemap.xml\n')
 stamp=datetime.now(timezone.utc).date().isoformat()
 (OUT/'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{loc_url(l)}</loc><lastmod>{stamp}</lastmod></url>' for l in LOCALES)+'</urlset>')
 print(json.dumps({'pages':pages,'dates':len(d['dates']),'snapshot':d['snapshot_id'],'rendering':'React, static and hydrated'}))
if __name__=='__main__':main()
