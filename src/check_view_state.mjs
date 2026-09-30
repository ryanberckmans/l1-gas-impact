import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {readView,viewUrl,summarize,comparisonRows} from './view-state.mjs';
const d=JSON.parse(await readFile(new URL('../data/summary.json',import.meta.url),'utf8'));
let count=0;
for(const locale of d.locales)for(const product of d.product_order)for(const days of [7,30,d.dates.length]){
 const v={locale,product,days,day:d.dates.at(-Math.min(days,3))};
 assert.deepEqual(readView(viewUrl(v),d),v);count++;
 const s=summarize(d.series[product],d.dates.slice(-days));assert(s.complete&&Number.isSafeInteger(s.gas));
}
const invalid=readView('/base/30/?date=1900-01-01',d);assert.equal(invalid.day,d.end);
assert.equal(readView('/%3Cscript%3E/NaN/',d).product,'lighter');
const rows=[{date:'a',gas:21000,tx:1,buckets:{transfers:21000},details:{transfers:21000}}];
assert.equal(summarize(rows,['a','b']).gas,null,'Missing day must not become zero');
assert.equal(summarize([...rows,...rows],['a','b']).gas,null,'Duplicate day cannot replace a missing day');
assert.equal(summarize([{...rows[0],gas:null}],['a']).gas,null,'Null must not become zero');
assert.equal(summarize([{...rows[0],gas:0,tx:0,buckets:{},details:{}}],['a']).gas,0,'Measured zero remains valid');
const custom={locale:'en',product:'lighter',days:d.dates.length,day:d.end,from:d.dates[10],to:d.dates[20]};
assert.deepEqual(readView(viewUrl(custom),d),custom,'Chart window must survive a copied URL');
assert.equal(readView('/lighter/7/?from=1900-01-01&to=2999-01-01',d).from,undefined);
const point=(date,gas)=>({date,gas,tx:1,buckets:{operations:gas},details:{operations:gas}});
const fixture={product_groups:{base:'l2',solana:'alt',uniswap:'app'},l2_classification:{base:'rollup'},product_order:['base','solana','uniswap'],series:{base:[point('a',900),point('b',10)],solana:[point('a',100),point('b',200)],uniswap:[point('a',10),point('b',100)]}};
const unchanged=JSON.stringify(fixture);
assert.equal(comparisonRows(fixture,['a','b']).filter(r=>!r.synthetic)[0].id,'base');
assert.equal(comparisonRows(fixture,['b']).filter(r=>!r.synthetic)[0].id,'solana','Ranking must change with the selected interval');
assert.equal(comparisonRows(fixture,['b']).find(r=>r.id==='all_l2_rollups').average,10);
assert.equal(comparisonRows(fixture,['b']).find(r=>r.id==='all_alt').average,200);
assert.equal(JSON.stringify(fixture),unchanged,'Synthetic summaries must not mutate observations');
const taxonomy={...fixture,product_groups:{base:'l2',solana:'alt',uniswap:'l3'}};
assert.equal(comparisonRows(taxonomy,['b']).find(r=>r.id==='all_l2_rollups').gas,10);
assert.equal(comparisonRows(taxonomy,['b']).find(r=>r.id==='all_alt').gas,200,'An L3 must not enter either subtotal');
const missingChain={...fixture,series:{...fixture.series,base:[point('a',900)]}};
assert.equal(comparisonRows(missingChain,['a','b']).find(r=>r.id==='all_l2_rollups').gas,null,'An incomplete chain must not produce a partial numeric subtotal');
const noL2={...fixture,product_groups:{base:'l3'}};
assert.equal(comparisonRows(noL2,['b']).find(r=>r.id==='all_l2_rollups').gas,null,'An empty chain group is missing');
for(const n of [7,30,d.dates.length]){
 const ranked=comparisonRows(d,d.dates.slice(-n));
 assert(ranked.every((r,i)=>!i||ranked[i-1].average>=r.average));
 const summaries=ranked.filter(r=>r.synthetic);
 assert.deepEqual(summaries.map(r=>r.id).sort(),['all_alt','all_l2_non_rollups','all_l2_rollups'],'Only the three chain summaries belong in the comparison');
 assert.equal(ranked.length,d.product_order.length+3);
 for(const summary of summaries){
  assert(!summary.members.includes('eth')&&!summary.members.includes('edge'));
  assert.equal(summary.gas,summary.members.reduce((gas,p)=>gas+d.series[p].slice(-n).reduce((sum,r)=>sum+r.gas,0),0));
 }
}
console.log(JSON.stringify({passed:true,restored_views:count,missing_data_preserved:true}));

const unknown={...fixture,l2_classification:{base:'unknown'}};
assert.equal(comparisonRows(unknown,['b']).find(r=>r.id==='all_l2_non_rollups').gas,null,'Unknown must not become non-rollup');
const nonRollup={...fixture,l2_classification:{base:'non_rollup'}};
assert.equal(comparisonRows(nonRollup,['b']).find(r=>r.id==='all_l2_non_rollups').gas,10);
for(const n of [7,30,d.dates.length]){
 const rs=comparisonRows(d,d.dates.slice(-n)).filter(r=>r.synthetic&&r.id!=='all_alt');
 assert.equal(new Set(rs.flatMap(r=>r.members)).size,rs.reduce((n,r)=>n+r.members.length,0),'L2 groups must be disjoint');
 const classified=d.product_order.filter(p=>d.product_groups[p]==='l2'&&d.l2_classification[p]!=='unknown');
 assert.equal(rs.reduce((n,r)=>n+r.gas,0),classified.reduce((total,p)=>total+d.series[p].slice(-n).reduce((m,r)=>m+r.gas,0),0));
}
