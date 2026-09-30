import React,{useState,useMemo,useRef,useEffect} from 'react';
import {viewUrl} from './view-state.mjs';

/** Small bounded daily series; hover state stays here, outside the comparison. */
export function History({data:D,view,names,labels:T,locale:L,ready,navigate,onWindow,onInspect}){
  const available=D.dates.slice(-view.days),from=view.from||available[0],to=view.to||available.at(-1);
  const dates=available.filter(d=>d>=from&&d<=to);
  const index=useMemo(()=>Object.fromEntries(D.series[view.product].map(r=>[r.date,r])),[D,view.product]);
  const mean=useMemo(()=>Object.fromEntries(D.dates.map((d,i)=>{
    const v=D.dates.slice(Math.max(0,i-6),i+1).map(x=>index[x]?.gas);
    return [d,v.length===7&&v.every(x=>Number.isSafeInteger(x))?v.reduce((a,b)=>a+b,0)/7:null];
  })),[D,index]);
  const [hover,setHover]=useState(null),[drag,setDrag]=useState(null),[selection,setSelection]=useState(null);
  const frame=useRef(null),pending=useRef(null),svg=useRef(null);
  const formats=useMemo(()=>({integer:new Intl.NumberFormat(L,{maximumFractionDigits:0}),decimal:new Intl.NumberFormat(L,{maximumFractionDigits:2}),date:new Intl.DateTimeFormat(L,{month:'short',day:'numeric',year:'numeric',timeZone:'UTC'})}),[L]);
  const fmt=(n,d=0)=>n===null||n===undefined?T.noData:(d?formats.decimal:formats.integer).format(n);
  const date=d=>formats.date.format(new Date(d+'T00:00:00Z'));
  const peak=Math.max(1,...dates.map(d=>index[d]?.gas??0),...dates.map(d=>mean[d]??0));
  const unit=10**Math.floor(Math.log10(peak)),max=Math.ceil(peak/unit)*unit;
  const W=640,H=230,x=i=>(i+.5)/dates.length*W,y=v=>H-v/max*(H-10);
  const coordinate=v=>Math.round(v*100)/100;
  const bars=dates.map((d,i)=>{const gas=index[d]?.gas;if(gas===null||gas===undefined)return '';const left=coordinate(x(i)-W/dates.length*.36),top=coordinate(y(gas)),width=coordinate(W/dates.length*.72);return `M${left} ${top}h${width}V${H}h${-width}Z`;}).join('');
  let line='';dates.forEach((d,i)=>{const v=mean[d];if(v!==null)line+=`${i===0||mean[dates[i-1]]===null?'M':'L'}${coordinate(x(i))},${coordinate(y(v))} `;});
  const pinned=dates.indexOf(view.day),active=hover===null?(pinned<0?dates.length-1:pinned):Math.min(hover,dates.length-1),row=index[dates[active]];
  const custom=from!==available[0]||to!==available.at(-1);
  useEffect(()=>{setHover(null);setDrag(null);setSelection(null);},[view.product,from,to]);
  useEffect(()=>()=>{if(frame.current!==null)cancelAnimationFrame(frame.current);},[]);
  function at(e){const box=e.currentTarget.getBoundingClientRect();return Math.max(0,Math.min(dates.length-1,Math.floor((e.clientX-box.left)/box.width*dates.length)));}
  function move(e){
    const i=at(e);pending.current=i;
    if(frame.current===null)frame.current=requestAnimationFrame(()=>{setHover(pending.current);frame.current=null;});
    if(drag!==null)setSelection(i);
  }
  function finish(e){
    if(drag===null)return;
    const i=at(e);
    if(Math.abs(i-drag)>=2)onWindow(dates[Math.min(i,drag)],dates[Math.max(i,drag)]);
    else onInspect(dates[i]);
    setDrag(null);setSelection(null);
    if(e.currentTarget.hasPointerCapture(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
  }
  function shift(direction){
    const n=dates.length,start=available.indexOf(from),next=Math.max(0,Math.min(available.length-n,start+direction*n));
    onWindow(available[next],available[next+n-1]);
  }
  function key(e){
    let i=active;
    if(e.key==='ArrowLeft')i=Math.max(0,i-1);
    else if(e.key==='ArrowRight')i=Math.min(dates.length-1,i+1);
    else if(e.key==='Home')i=0;
    else if(e.key==='End')i=dates.length-1;
    else if(e.key==='Escape'){setHover(null);return;}
    else return;
    e.preventDefault();setHover(i);onInspect(dates[i]);
  }
  return <div className="history-interactive">
    <div className="chart-controls"><nav className="periods chart-periods" aria-label={T.chartPeriod}>{[[7,T.days7],[30,T.days30],[D.dates.length,T.months6]].map(([n,label])=><a key={n} href={viewUrl({...view,days:n,from:null,to:null,day:null})} aria-current={view.days===n?'page':undefined} onClick={e=>navigate(e,{...view,days:n,from:null,to:null})}>{label}</a>)}</nav>
      <div className="window-actions"><button type="button" disabled={!ready||!custom||from===available[0]} onClick={()=>shift(-1)} aria-label={T.earlierWindow}>‹</button><button type="button" disabled={!ready||!custom||to===available.at(-1)} onClick={()=>shift(1)} aria-label={T.laterWindow}>›</button><button type="button" disabled={!ready||!custom} onClick={()=>onWindow(null,null)}>{T.resetZoom}</button></div></div>
    <div className="chart-dates"><label>{T.fromDate}<input type="date" disabled={!ready} min={available[0]} max={to} value={from} onChange={e=>{if(available.includes(e.target.value)&&e.target.value<=to)onWindow(e.target.value,to);}}/></label><label>{T.toDate}<input type="date" disabled={!ready} min={from} max={available.at(-1)} value={to} onChange={e=>{if(available.includes(e.target.value)&&e.target.value>=from)onWindow(from,e.target.value);}}/></label></div>
    <div className="chart-box interactive-chart"><div className="y-axis" aria-hidden="true">{[4,3,2,1,0].map(i=><span key={i}>{fmt(max*i/4/1e6,2)}</span>)}</div>
      <div className="plot-area"><svg ref={svg} id="history-chart" role="group" tabIndex={ready?0:undefined} aria-label={`${names[view.product]} · ${T.history} · ${date(dates[0])} – ${date(dates.at(-1))}`} aria-describedby="chart-help" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" onPointerMove={move} onPointerLeave={()=>{if(drag===null)setHover(null);}} onPointerDown={e=>{if(!ready||e.button!==0)return;const i=at(e);setDrag(i);setSelection(i);setHover(i);e.currentTarget.setPointerCapture(e.pointerId);}} onPointerUp={finish} onPointerCancel={()=>{setDrag(null);setSelection(null);}} onKeyDown={key} onDoubleClick={()=>onWindow(null,null)}>
        <title>{`${names[view.product]} · ${T.history}`}</title><desc>{T.chartHelp}</desc>
        {[0,1,2,3,4].map(i=><line key={i} x1="0" x2={W} y1={y(max*i/4)} y2={y(max*i/4)} stroke="var(--chart-grid)" vectorEffect="non-scaling-stroke"/>)}
        <path className="daily-bars" d={bars} fill="var(--chart-bar)"/>
        <path d={line} fill="none" stroke="var(--blue)" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
        {drag!==null&&selection!==null&&<rect x={Math.min(x(drag),x(selection))} y="0" width={Math.abs(x(drag)-x(selection))} height={H} fill="var(--blue)" opacity=".16"/>}
        {hover!==null&&<line x1={x(active)} x2={x(active)} y1="0" y2={H} stroke="var(--ink)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke"/>}
      </svg>
      {hover!==null&&<div className={'chart-tooltip'+(active>=dates.length/2?' leftward':'')} role="tooltip" style={{left:`${(active+.5)/dates.length*100}%`}}><strong>{date(dates[active])}</strong><span>{T.gas}: <b>{fmt(row?.gas)}</b></span><span>{T.transactions}: {fmt(row?.tx)}</span><span>{T.rolling}: {fmt(mean[dates[active]],2)}</span></div>}
      <div className="x-axis" aria-hidden="true"><span>{date(dates[0])}</span>{dates.length>1&&<span>{date(dates.at(-1))}</span>}</div></div></div>
    <p className="note" id="chart-help">{T.chartHelp}</p>
    <div className="inspect"><label htmlFor="day-slider">{T.inspect}</label><input type="range" id="day-slider" disabled={!ready} min="0" max={dates.length-1} value={active} onChange={e=>{const i=Number(e.target.value);setHover(i);onInspect(dates[i]);}} aria-valuetext={`${date(dates[active])}: ${fmt(row?.gas)} ${T.gas}`}/><output id="date-readout" htmlFor="day-slider">{date(dates[active])}: {fmt(row?.gas)} {T.gas}</output></div>
  </div>;
}
