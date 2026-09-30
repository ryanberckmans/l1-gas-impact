export const locales={en:'English',es:'Español','pt-BR':'Português',fr:'Français',de:'Deutsch','zh-CN':'简体中文',ja:'日本語',ko:'한국어'};
export function readView(url,data){
  const u=new URL(url,'https://example.invalid'),parts=u.pathname.split('/').filter(Boolean);
  const locale=Object.hasOwn(locales,parts[0])?parts.shift():'en';
  const product=data.product_order.includes(parts[0])?parts[0]:'lighter';
  const days=[7,30,data.dates.length].includes(Number(parts[1]))?Number(parts[1]):30;
  const dates=data.dates.slice(-days),day=dates.includes(u.searchParams.get('date'))?u.searchParams.get('date'):dates.at(-1);
  const from=u.searchParams.get('from'),to=u.searchParams.get('to');
  const window=dates.includes(from)&&dates.includes(to)&&from<=to?{from,to}:{};
  return {locale,product,days,day,...window};
}
export function viewUrl(view){
  const path=`/${view.locale==='en'?'':view.locale+'/'}${view.product}/${view.days}/`;
  const q=new URLSearchParams();
  if(view.day)q.set('date',view.day);
  if(view.from&&view.to){q.set('from',view.from);q.set('to',view.to);}
  return path+(q.size?'?'+q:'');
}

// Synthetic summaries exist only in the comparison presentation, never observations.
export const chainGroups={
  l2:['lighter','base','arbitrum','robinhood','worldchain','unichain','op','ink','starknet','zksync2','scroll','linea','taiko','blast','mantle','metis','mode','zora','abstract','katana','nova','bob','celo','codex','plume','morph','xlayer'],
  alt:['solana','hyperliquid','bsc','polygon','avalanche','sui','aptos','sonic','monad','sei','noble','stellar','xdc','injective','cronos','plasma','near','ton','bitcoin','gnosis','fantom','kaia','moonbeam']
};
export function comparisonRows(data,dates){
  const rows=data.product_order.map(id=>({id,...summarize(data.series[id],dates)}));
  // @cc: Each classified L2 enters exactly one fixed cohort; unknown is not non-rollup.
  const groups={l2_rollups:'rollup',l2_non_rollups:'non_rollup',alt:null};
  for(const [group,category] of Object.entries(groups)){
    const members=rows.filter(r=>!r.synthetic&&r.id!=='eth'&&(group==='alt'
      ?data.product_groups?.[r.id]==='alt'
      :data.product_groups?.[r.id]==='l2'&&data.l2_classification?.[r.id]===category));
    const complete=members.length>0&&members.every(r=>r.complete);
    const buckets={},details={};
    for(const r of members){for(const [k,v] of Object.entries(r.buckets))buckets[k]=(buckets[k]||0)+v;for(const [k,v] of Object.entries(r.details))details[k]=(details[k]||0)+v;}
    const gas=complete?members.reduce((n,r)=>n+r.gas,0):null;
    rows.push({id:'all_'+group,synthetic:true,members:members.map(r=>r.id),complete,gas,tx:complete?members.reduce((n,r)=>n+r.tx,0):null,average:complete?gas/dates.length:null,buckets,details});
  }
  return rows.sort((a,b)=>(b.average??-Infinity)-(a.average??-Infinity)||(a.id<b.id?-1:a.id>b.id?1:0));
}
export function summarize(rows,dates){
  const selected=rows.filter(r=>dates.includes(r.date));
  const complete=selected.length===dates.length&&new Set(selected.map(r=>r.date)).size===dates.length&&selected.every(r=>Number.isSafeInteger(r.gas)&&r.gas>=0&&Number.isSafeInteger(r.tx)&&r.tx>=0);
  const buckets={},details={};let gas=0,tx=0;
  for(const r of selected){gas+=r.gas??0;tx+=r.tx??0;for(const [k,v] of Object.entries(r.buckets))buckets[k]=(buckets[k]||0)+v;for(const [k,v] of Object.entries(r.details))details[k]=(details[k]||0)+v;}
  return {gas:complete?gas:null,tx:complete?tx:null,average:complete?gas/dates.length:null,buckets,details,complete};
}
