import React,{useState,useEffect,useMemo} from 'react';
import {locales,readView,viewUrl,summarize,comparisonRows,chainGroups} from './view-state.mjs';

import {History} from './history-chart.jsx';
import {Seal} from './seal.jsx';
import {RepositoryLink} from './repository-link.jsx';
export {Seal} from './seal.jsx';
export {RepositoryLink} from './repository-link.jsx';

const buckets=['operations','bridge','approvals','governance','defi','transfers','other'];
const color=b=>`var(--color-${b})`;

export function GasApp({data:D,labels:T,locale:L,initialView,initialComparisons}){
  const [view,setView]=useState(initialView),[theme,setTheme]=useState('system'),[ready,setReady]=useState(false);
  const {product:selected,days,day}=view,dates=D.dates.slice(-days);
  const names={...D.product_names,eth:T.plainTransfers,uniswap:T.uniswapName,lighter:T.lighterName,all_l2_rollups:T.allL2Rollups,all_l2_non_rollups:T.allL2NonRollups,all_alt:T.allAltL1s};
  for(const [p,group] of Object.entries(D.product_groups||{}))if(group==='app')names[p]=T.l1AppName.replace('{app}',D.product_names[p].replace(/ on L1$/,''));
  const formats=useMemo(()=>({numbers:[0,1,2].map(maximumFractionDigits=>new Intl.NumberFormat(L,{maximumFractionDigits})),compact:new Intl.NumberFormat(L,{notation:'compact',maximumFractionDigits:2}),date:new Intl.DateTimeFormat(L,{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'})}),[L]);
  const fmt=(n,digits=0)=>n===null?T.noData:formats.numbers[digits].format(n);
  const compact=n=>n===null?T.noData:formats.compact.format(n);
  const dateFmt=d=>formats.date.format(new Date(d+'T00:00:00Z'));
  const period=`${dateFmt(dates[0])} – ${dateFmt(dates.at(-1))} · ${days} ${T.daysUnit}`;
  const ranked=useMemo(()=>initialComparisons?.[days]??comparisonRows(D,dates),[D,days,initialComparisons]),sums=Object.fromEntries(ranked.map(r=>[r.id,r]));
  const visibleRows=ready?ranked:ranked.filter((row,i)=>i<1||row.id===selected||row.synthetic);
  const max=Math.max(...Object.values(sums).map(s=>s.average??0),1),s=sums[selected];
  const last=summarize(D.series[selected],D.dates.slice(-30)),prior=summarize(D.series[selected],D.dates.slice(-60,-30));
  const change=last.complete&&prior.complete&&prior.gas>0?(last.gas/prior.gas-1)*100:null;
  const prefix=selected==='eth'?'':'≥ ';
  const rowIndex=Object.fromEntries(D.series[selected].map(r=>[r.date,r]));

  useEffect(()=>{
    setReady(true);
    const sync=()=>setView(readView(location.href,D));
    sync();window.addEventListener('popstate',sync);
    setTheme(window.GAS_THEME?.mode||'system');
    const changed=()=>setTheme(window.GAS_THEME?.mode||'system');
    window.addEventListener('storage',changed);
    // The root is the neutral entry point. Product/locale URLs are always explicit.
    if(location.pathname==='/'&&!location.search&&!location.hash){
      try{const pref=localStorage.getItem('l1-gas-language');if(pref&&pref!=='en'&&Object.hasOwn(locales,pref))location.replace(viewUrl({...initialView,locale:pref}));}catch{}
    }
    return()=>{window.removeEventListener('popstate',sync);window.removeEventListener('storage',changed);};
  },[D,initialView]);
  function navigate(event,next){
    if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    event.preventDefault();const validDates=D.dates.slice(-next.days);
    const v={...next,day:validDates.includes(next.day)?next.day:validDates.at(-1)};
    if(next.days!==view.days||!validDates.includes(v.from)||!validDates.includes(v.to)){delete v.from;delete v.to;}
    const reveal=next.product!==view.product&&window.matchMedia('(max-width:1000px)').matches;
    history.pushState(null,'',viewUrl(v)+(reveal?'#detail-title':''));setView(v);
    if(reveal)requestAnimationFrame(()=>document.getElementById('detail-title').scrollIntoView({block:'start'}));
  }
  function inspect(day){
    const next={...view,day};setView(next);history.replaceState(null,'',viewUrl(next));
  }
  function chartWindow(from,to){
    const next={...view,from:from||null,to:to||null};
    if(from&&to&&(next.day<from||next.day>to))next.day=to;
    setView(next);history.replaceState(null,'',viewUrl(next));
  }
  const group=D.product_groups?.[selected]||(chainGroups.l2.includes(selected)?'l2':chainGroups.alt.includes(selected)?'alt':'app');
  const scope=(D.scope_labels?.[selected]?T.scopeIncludes.replace('{scope}',D.scope_labels[selected])+' ':'')+(T['scope_'+selected]||T['scope_'+group+'_generic']||T.scope_app_generic);
  return <>
    <a className="skip" href="#comparison">{T.backToTop}</a>
    <header><a className="brand" href={L==='en'?'/':`/${L}/`}>L1 GAS IMPACT</a>
      <div className="preferences"><RepositoryLink labels={T}/><div className="theme"><label htmlFor="theme">{T.theme}</label><select id="theme" disabled={!ready} value={theme} onChange={e=>{window.GAS_THEME.set(e.target.value);setTheme(e.target.value);}}>{['system','light','dark'].map(m=><option value={m} key={m}>{T['theme_'+m]}</option>)}</select></div>
        <div className="language"><label htmlFor="language">{T.language}</label><select id="language" disabled={!ready} value={L} onChange={e=>{try{localStorage.setItem('l1-gas-language',e.target.value);}catch{}location.assign(viewUrl({...view,locale:e.target.value}));}}>{Object.entries(locales).map(([l,n])=><option value={l} key={l}>{n}</option>)}</select></div><Seal labels={T}/></div>
      <noscript><nav aria-label={T.language}>{Object.entries(locales).map(([l,n])=><a key={l} href={viewUrl({...view,locale:l})}>{n} </a>)}</nav></noscript>
    </header>
    <main><div className="intro"><h1>{T.headline}</h1><p>{T.intro}</p><p className="mobile-result"><strong>{names[selected]}: {s.average===null?T.noData:prefix+compact(s.average)} {T.gasPerDay}</strong><span>{days} {T.daysUnit} · {T.through} {D.end} UTC</span></p><div className="date-line">{T.snapshot} · {T.through} {D.end} UTC</div></div>
      <div className="toolbar"><nav className="periods" aria-label={T.period}>{[[7,T.days7],[30,T.days30],[D.dates.length,T.months6]].map(([n,label])=><a key={n} href={viewUrl({...view,days:n,day:null,from:null,to:null})} data-days={n} aria-current={n===days?'page':undefined} onClick={e=>navigate(e,{...view,days:n})}>{label}</a>)}</nav><div className="toolbar-links"><a href="#methodology">{T.methodology}</a><a href="/data/l1-gas-daily.csv" download>{T.download}</a></div></div>
      <div className="workspace"><section id="comparison" aria-labelledby="comparison-title"><div className="section-top"><h2 id="comparison-title">{T.comparison}</h2></div><div className="period-label" id="period-label">{period}</div><p className="axis-label">{T.axis}</p>
        <div className="overview">{visibleRows.map(v=>{const p=v.id,Tag=v.synthetic?'div':'a';return <Tag key={p} {...(v.synthetic?{}:{href:viewUrl({...view,product:p}),onClick:e=>navigate(e,{...view,product:p})})} className={'compare-row'+(p===selected?' active':'')+(v.synthetic?' synthetic-row':'')} data-product={p} aria-current={!v.synthetic&&p===selected?'page':undefined} aria-label={`${names[p]}: ${v.average===null?T.noData:(p==='eth'?'':T.atLeast+' ')+fmt(v.average)+' '+T.gasPerDay}`}>
          <span className={'product-label'+(v.synthetic?' aggregate-label':'')}><span>{names[p]}</span>{v.synthetic&&<small>{T.coveredChains.replace('{count}',fmt(v.members.length))}</small>}</span><span className="bar-value">{v.average===null?T.noData:(p==='eth'?'':'≥ ')+fmt(v.average/1e6,2)}</span><span className="bar-track" aria-hidden="true"><span className="bar">{v.complete&&buckets.filter(b=>v.buckets[b]).map(b=><span key={b} style={{width:`${v.buckets[b]/days/max*100}%`,background:color(b)}}/>)}</span></span>
        </Tag>;})}</div><noscript><p><a href={(L==='en'?'/':'/'+L+'/')+'catalogue.html'}>{T.comparison} · {T.product}</a></p></noscript><div className="scale" aria-hidden="true"><span>0</span><span id="scale-max">{fmt(max/1e6)}</span></div>
        <p className="aggregate-note">{T.aggregateNote} <a href="/data/l2-classification.json">{T.l2Classification}</a></p>
        <p className="scope-warning">{T.scopeWarning}</p><div className="legend">{buckets.map(b=><span key={b}><span className="swatch" style={{background:color(b)}}/>{T[b]}</span>)}</div><p className="small">{T.choose}</p>
      </section>
      <section className="detail" aria-labelledby="detail-title"><div className="detail-heading"><h2 id="detail-title">{names[selected]}</h2><span className="badge">{T.selected}</span></div>
        <div className="metrics"><div><span className="metric-label">{T.periodTotal}</span><span className="metric-value" id="total-gas" title={fmt(s.gas)}>{s.gas===null?T.noData:prefix+compact(s.gas)}</span></div><div><span className="metric-label">{T.transactions}</span><span className="metric-value" id="tx-count" title={fmt(s.tx)}>{compact(s.tx)}</span></div><div><span className="metric-label">{T.equivalent}</span><span className="metric-value" id="equivalent-count">{s.average===null?T.noData:prefix+fmt(s.average/21000)}</span></div><div><span className="metric-label">{T.change}</span><span className="metric-value" id="change-value">{change===null?T.noData:(change>0?'+':'')+fmt(change,1)+'%'}</span></div></div>
        <div className="ratio-context" id="ratio-context">{selected!=='eth'&&[['eth',T.ofEthGas],['uniswap',T.ofUniswapGas]].filter(([p])=>p!==selected&&s.complete&&sums[p].complete&&sums[p].gas>0).map(([p,label])=><span key={p}>{fmt(s.gas/sums[p].gas*100,2)}% {label}</span>)}</div>
        <div className="chart-heading"><h3>{T.history}<span className="small"> / {T.millionGas}</span></h3><span className="chart-key"><i/>{T.rolling}</span></div>
        <History data={D} view={view} names={names} labels={T} locale={L} ready={ready} navigate={navigate} onWindow={chartWindow} onInspect={inspect}/>
        <div className="detail-grid"><div><h3>{T.breakdown.replace('{product}',names[selected]).replace('{period}',days===D.dates.length?T.months6:fmt(days)+' '+T.daysUnit)}</h3><table><thead><tr><th>{T.detailsHeading}</th><th>{T.gas}</th><th>%</th></tr></thead><tbody id="breakdown-body">{s.complete&&s.gas===0&&<tr><td colSpan="3">{T.noActivity}</td></tr>}{s.complete&&Object.entries(s.details).filter(([,v])=>v).sort((a,b)=>b[1]-a[1]).map(([b,v])=><tr key={b}><th scope="row"><span className="swatch" style={{background:color(D.detail_categories[b]||b)}}/>{T[b]||T.other}</th><td>{fmt(v)}</td><td>{fmt(v/s.gas*100,1)}%</td></tr>)}</tbody></table></div>
        <div><h3>{T.coverage}</h3><p id="scope-copy">{scope.replace(/\{(\w+)\}/g,(_,key)=>fmt(D.coverage_values?.[key]??null))}</p><p className="note">{T.equivalentNote}</p><a href="/data/query-manifest.json">{T.sources}</a></div></div>
        {ready&&<details><summary>{T.daily} · {T.exactData}</summary><div className="daily-table-wrap"><table><caption id="daily-caption">{names[selected]} · {period}</caption><thead><tr><th>{T.date}</th><th>{T.gas}</th><th>{T.transactions}</th></tr></thead><tbody id="daily-body">{dates.map(d=><tr key={d}><th scope="row">{d}</th><td>{fmt(rowIndex[d]?.gas??null)}</td><td>{fmt(rowIndex[d]?.tx??null)}</td></tr>)}</tbody></table></div></details>}
      </section></div>
      {ready&&<details><summary>{T.comparison} · {T.exactData}</summary><div className="table-scroll"><table><thead><tr><th>{T.product}</th><th>{T.total}</th><th>{T.average}</th><th>{T.transactions}</th></tr></thead><tbody id="exact-body">{ranked.filter(r=>!r.synthetic).map(({id:p})=><tr key={p}><th scope="row">{names[p]}</th><td>{fmt(sums[p].gas)}</td><td>{fmt(sums[p].average,2)}</td><td>{fmt(sums[p].tx)}</td></tr>)}</tbody></table></div></details>}
      <section id="methodology" className="methodology"><h2>{T.methodology}</h2>{ready&&<div className="method-grid">{['measurement','attribution','limits','verification'].map(k=><div key={k}><h3>{T[k+'Heading']}</h3><p>{T[k+'Body']}</p></div>)}</div>}<div className="download-links">{[['l1-gas-daily.csv','dailyCsv'],['dataset.json','jsonData'],['l1-gas-evidence.zip','dataArchive'],['query-manifest.json','queryManifest'],['methodology.md','methodology'],['receipt-index.json','receiptIndex']].map(([file,label])=><a key={file} href={'/data/'+file} download={/\.csv|\.zip/.test(file)||undefined}>{T[label]}{file.endsWith('.md')?' (English)':''}</a>)}</div><p className="note">{T.sourceNote}</p></section>
    </main><footer><span>{T.freshness}<br/>{D.start} – {D.end} UTC · Ethereum mainnet (1)</span><a href="#comparison">{T.backToTop}</a></footer>
  </>;
}
