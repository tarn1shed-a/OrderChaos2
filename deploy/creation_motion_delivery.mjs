// Validate checked source bytes without evaluating browser modules or retaining
// animation banks. V8 parses real static imports, including compact from syntax.
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {spawn} from 'node:child_process';
import {creationMotionResourceURL,CLASS_MOTION_MANIFEST,INITIAL_MOTION_MANIFEST,INITIAL_ALL_MOTION_MANIFEST,RACE_MOTION_MANIFEST,PARTIAL_MOTION_MANIFEST} from './creation_motion.mjs';

export async function sourceMotionStaticImports(rows){
 const compile=items=>items.map(({url,source})=>({url,imports:[...new vm.SourceTextModule(source,{identifier:url}).dependencySpecifiers]}));
 if(typeof vm.SourceTextModule==='function')return compile(rows);
 // Default Node need not enable VM modules for the game. One bounded parser
 // child compiles source text only; no link/evaluate, network or heap overrides.
 const program="import vm from 'node:vm';let input='';for await(const part of process.stdin)input+=part;const rows=JSON.parse(input);process.stdout.write(JSON.stringify(rows.map(({url,source})=>({url,imports:[...new vm.SourceTextModule(source,{identifier:url}).dependencySpecifiers]}))));";
 return new Promise((accept,reject)=>{
  const child=spawn(process.execPath,['--experimental-vm-modules','--input-type=module','-e',program],{stdio:['pipe','pipe','pipe']}),output=[],errors=[];
  const timer=setTimeout(()=>{child.kill();reject(Error('Bounded source module parse exceeded time'));},30000);
  child.stdout.on('data',p=>output.push(p));child.stderr.on('data',p=>errors.push(p));child.on('error',e=>{clearTimeout(timer);reject(e);});
  child.on('close',code=>{clearTimeout(timer);if(code!==0)return reject(Error('Source module parse failed: '+Buffer.concat(errors).toString()));try{accept(JSON.parse(Buffer.concat(output).toString()));}catch(error){reject(error);}});
  child.stdin.end(JSON.stringify(rows));
 });
}

export async function checkedCreationMotionDelivery(motion,{read,required}){
 const v2=motion?.version===2;
 if(!motion||![1,2].includes(motion.version)||motion.classManifestURL!==CLASS_MOTION_MANIFEST||motion.initialManifestURL!==(v2?INITIAL_ALL_MOTION_MANIFEST:INITIAL_MOTION_MANIFEST)||
  v2&&(motion.raceManifestURL!==RACE_MOTION_MANIFEST||motion.partialManifestURL!==PARTIAL_MOTION_MANIFEST))throw Error('Exact original motion version/URLs required');
 const resources=[],modules=new Set();
 function reference(base,row){
  if(!/^[0-9a-f]{64}$/.test(row?.sha256||''))throw Error('Original source motion reference differs');
  const url=creationMotionResourceURL(base,row.url),actual=required(url);
  if(actual.sha256!==row.sha256)throw Error('Original source motion digest differs: '+url);
  resources.push(url);if(url.endsWith('.mjs'))modules.add(url);return url;
 }
 const scopes=[['show',motion.classManifestURL,'oc2-all-class-safe-source-pose-assets-v1',43],
  ['initial',motion.initialManifestURL,v2?'oc2-creation-initial-all-browser-assets-v1':'oc2-creation-initial-idle-browser-assets-v1',v2?45:8],
  ...(v2?[['race',motion.raceManifestURL,'oc2-creation-race-source-control-assets-v1',9],['partial',motion.partialManifestURL,'oc2-creation-partial-class-browser-v1',2]]:[])];
 for(const[kind,url,format,count]of scopes){
  const manifest=await read(url);
  if(manifest?.format!==format||!manifest.profiles||Object.keys(manifest.profiles).length!==count||!manifest.banks)throw Error('Own source motion manifest coverage differs');
  for(const field of ['entry','core','numeric','queue','queueCore','runtimeQueue'])if(manifest[field])reference(url,manifest[field]);
  for(const row of Object.values(manifest.banks))reference(url,row);
  for(const row of Object.values(manifest.profiles)){if(!manifest.banks[row.bank])throw Error('Own source motion bank differs');reference(url,row);}
  if(manifest.requiredExistingBrowserFiles)for(const[url,row]of Object.entries(manifest.requiredExistingBrowserFiles))reference(url,{url,sha256:row.sha256});
  const queue=kind==='show'?(v2?'/assets/source-creation-partial-class-v1/modules/source_partial_class_runtime_v1.mjs':'/assets/source-creation-control-runtime-v1/modules/source_class_queue_runtime_v1.mjs'):
   v2?creationMotionResourceURL(url,manifest.runtimeQueue.url):'/assets/source-creation-control-runtime-v1/modules/source_initial_queue_runtime_v1.mjs';
  required(queue);modules.add(queue);
 }
 const scanned=new Set();
 while([...modules].some(url=>!scanned.has(url))){
  const rows=[];
  for(const url of modules)if(!scanned.has(url)){scanned.add(url);rows.push({url,source:await readFile(required(url).path,'utf8')});}
  for(const row of await sourceMotionStaticImports(rows))for(const path of row.imports){
   const url=creationMotionResourceURL(row.url,path);
   if(!url.endsWith('.mjs'))throw Error('Original motion module dependency is not a checked source module');
   required(url);modules.add(url);
  }
 }
 return resources;
}
