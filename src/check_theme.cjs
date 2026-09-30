const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const code=fs.readFileSync(path.join(root,'src/theme.js'),'utf8');
let scenarios=0;
function setup({dark=false,stored=null,denied=false,noMedia=false}={}) {
  const listeners={},changes=[];
  const media={matches:dark,addEventListener(name,fn){assert.equal(name,'change');changes.push(fn);}};
  const tint={setAttribute(name,value){this[name]=value;}};
  let selector=null;
  const document={documentElement:{dataset:{}},querySelector(){return tint;},getElementById(){return selector;}};
  const saved=new Map(stored===null?[]:[['l1-gas-theme',stored]]);
  const storage={getItem(key){if(denied)throw Error('Storage denied');return saved.get(key)??null;},setItem(key,value){if(denied)throw Error('Storage denied');saved.set(key,value);}};
  const window={addEventListener(name,fn){listeners[name]=fn;},...(noMedia?{}:{matchMedia(query){assert.equal(query,'(prefers-color-scheme: dark)');return media;}})};
  vm.runInNewContext(code,{window,document,localStorage:storage});
  return {window,document,tint,saved,mount(){selector={value:null};return selector;},os(value){media.matches=value;changes.forEach(fn=>fn({matches:value}));},storage(value,key='l1-gas-theme'){listeners.storage({key,newValue:value});}};
}
for(const dark of [false,true])for(const stored of [null,'system','light','dark','invalid']){
  const s=setup({dark,stored});const mode=['light','dark'].includes(stored)?stored:'system';
  assert.equal(s.window.GAS_THEME.mode,mode);
  assert.equal(s.document.documentElement.dataset.theme,mode==='system'?(dark?'dark':'light'):mode,'Resolved before body mount');
  const selector=s.mount();s.os(!dark);
  assert.equal(s.document.documentElement.dataset.theme,mode==='system'?(!dark?'dark':'light'):mode);
  assert.equal(selector.value,mode);
  for(const choice of ['light','dark','system']){
    s.window.GAS_THEME.set(choice);assert.equal(s.saved.get('l1-gas-theme'),choice);assert.equal(selector.value,choice);
    s.os(true);assert.equal(s.document.documentElement.dataset.theme,choice==='system'?'dark':choice);
    s.os(false);assert.equal(s.document.documentElement.dataset.theme,choice==='system'?'light':choice);
    const reloaded=setup({dark:true,stored:s.saved.get('l1-gas-theme')});assert.equal(reloaded.window.GAS_THEME.mode,choice);
  }
  s.storage('dark');assert.equal(s.document.documentElement.dataset.theme,'dark');
  s.storage('light','unrelated');assert.equal(s.window.GAS_THEME.mode,'dark');
  s.storage(null,null);assert.equal(s.window.GAS_THEME.mode,'system');
  scenarios++;
}
const denied=setup({dark:true,denied:true});assert.equal(denied.document.documentElement.dataset.theme,'dark');denied.window.GAS_THEME.set('light');assert.equal(denied.document.documentElement.dataset.theme,'light');
assert.equal(setup({noMedia:true}).document.documentElement.dataset.theme,'light');
function luminance(hex){const c=hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2];}
function contrast(a,b){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
const css=fs.readFileSync(path.join(root,'src/style.css'),'utf8');
for(const [name,selector] of [['light',/:root\{([^}]+)\}/],['dark',/:root\[data-theme=dark\]\{([^}]+)\}/]]){
  const vars=Object.fromEntries([...css.match(selector)[1].matchAll(/(--[\w-]+):(#\w{6})/g)].map(m=>[m[1],m[2]]));
  for(const foreground of ['--ink','--muted','--body-copy','--ratio','--blue']) for(const background of ['--paper','--surface'])assert(contrast(vars[foreground],vars[background])>=4.5,`${name}: ${foreground}/${background} contrast`);
  for(const foreground of ['--chart-bar','--focus',...Object.keys(vars).filter(k=>k.startsWith('--color-'))])assert(contrast(vars[foreground],vars['--paper'])>=3,`${name}: ${foreground} contrast`);
}
console.log(JSON.stringify({passed:true,theme_scenarios:scenarios+2,first_paint:true,live_system_changes:true,persisted_overrides:true,storage_denial:true,palette_contrast:true}));
