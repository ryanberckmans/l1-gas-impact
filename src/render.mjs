import React from 'react';
import {renderToString} from 'react-dom/server';
import {build,transform} from 'esbuild';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {comparisonRows} from './view-state.mjs';
await mkdir('.build',{recursive:true});
await writeFile('.build/theme.min.js',(await transform(await readFile('src/theme.js','utf8'),{minify:true,target:'es2022'})).code);
await build({entryPoints:['src/app.jsx'],bundle:true,platform:'node',format:'esm',packages:'external',outfile:'.build/app.mjs'});
await build({entryPoints:['src/client.jsx'],bundle:true,minify:true,format:'iife',target:['es2022'],define:{'process.env.NODE_ENV':'"production"'},legalComments:'none',outfile:'dist/assets/app.js'});
await writeFile('dist/assets/app.js','/*! L1 Gas Impact: MIT. Notices: /LICENSE and /THIRD_PARTY_NOTICES */\n'+await readFile('dist/assets/app.js','utf8'));
const {GasApp,Seal,RepositoryLink}=await import(pathToFileURL(resolve('.build/app.mjs')));
const data=JSON.parse(await readFile('data/summary.json','utf8'));
const initialComparisons=Object.fromEntries([7,30,data.dates.length].map(days=>[days,comparisonRows(data,data.dates.slice(-days))]));
const result={};
for(const locale of data.locales){
 const labels=JSON.parse(await readFile(`data/locales/${locale}.json`,'utf8'));
 result[`${locale}/seal`]=renderToString(React.createElement(Seal,{labels}));
 result[`${locale}/repository`]=renderToString(React.createElement(RepositoryLink,{labels}));
 for(const product of data.product_order)for(const days of [7,30,data.dates.length]){
  const initialView={locale,product,days,day:data.dates.at(-1)};
  result[`${locale}/${product}/${days}`]=renderToString(React.createElement(GasApp,{data,labels,locale,initialView,initialComparisons}));
 }
}
await writeFile('.build/bodies.json',JSON.stringify(result));
