import {readFile,readdir,writeFile,lstat} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve,relative,sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=resolve(fileURLToPath(new URL('..',import.meta.url)));
const manifestName='data/static-build-manifest.json';
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
async function files(directory,base){
  const result=[];
  for(const entry of await readdir(directory,{withFileTypes:true})){
    const path=resolve(directory,entry.name);
    if(entry.isDirectory())result.push(...await files(path,base));
    else if(entry.isFile())result.push(relative(base,path).split(sep).join('/'));
    else throw new Error('Static build must contain only regular files');
  }
  return result.sort();
}
async function hashes(base,names){
  const result={};
  for(const name of names){
    if(name.startsWith('/')||name.split('/').includes('..'))throw new Error('Invalid build path');
    const path=resolve(base,name);
    if(!(await lstat(path)).isFile())throw new Error('Build file is not regular: '+name);
    result[name]=digest(await readFile(path));
  }
  return result;
}
export async function verifyStaticBuild(base=root){
  const manifest=JSON.parse(await readFile(resolve(base,manifestName),'utf8'));
  const output=await files(resolve(base,'dist'),base);
  if(JSON.stringify(output)!==JSON.stringify(Object.keys(manifest.output).sort()))throw new Error('Static output file set changed');
  for(const group of ['inputs','output']){
    const observed=await hashes(base,Object.keys(manifest[group]));
    for(const [name,sha] of Object.entries(manifest[group]))if(observed[name]!==sha)throw new Error('Stale static build: '+name);
  }
  const validation=JSON.parse(await readFile(resolve(base,'data/release-validation.json'),'utf8'));
  if(!validation.passed||validation.snapshot_id!==manifest.snapshot_id)throw new Error('Static snapshot has not passed validation');
  return {passed:true,snapshot_id:manifest.snapshot_id,verified_files:output.length};
}
async function seal(){
  const validation=JSON.parse(await readFile(resolve(root,'data/release-validation.json'),'utf8'));
  if(!validation.passed)throw new Error('Validate the generated release before sealing');
  const inputs=['.openai/hosting.json','AGENTS.md','CONTRACTS','README.md','package.json','package-lock.json',...await files(resolve(root,'src'),root),...await files(resolve(root,'data'),root)].filter(p=>p!==manifestName&&!p.includes('__pycache__/')&&!p.endsWith('.pyc')).sort();
  const output=await files(resolve(root,'dist'),root);
  const manifest={snapshot_id:validation.snapshot_id,inputs:await hashes(root,inputs),output:await hashes(root,output)};
  await writeFile(resolve(root,manifestName),JSON.stringify(manifest,null,2)+'\n');
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  if(process.argv.includes('--seal'))await seal();
  console.log(JSON.stringify(await verifyStaticBuild()));
}
