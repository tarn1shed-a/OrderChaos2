// Check the private motion closure without retaining all animation JSON in heap.
import {readFile} from 'node:fs/promises';
export async function checkedCreationMotionDelivery(motion,{read,required}){
 const resources=[];
 function reference(base,row){
  if(typeof row?.url!=='string'||!/^\.\/[A-Za-z0-9_./-]+$/.test(row.url)||row.url.includes('..')||row.url.includes('//')||!/^([0-9a-f]{64})$/.test(row.sha256||''))throw Error('Original source motion reference differs');
  const url=base.slice(0,base.lastIndexOf('/')+1)+row.url.slice(2),actual=required(url);
  if(actual.sha256!==row.sha256)throw Error('Original source motion digest differs: '+url);
  resources.push(url);return url;
 }
 for(const [kind,url,format,count]of [
  ['show',motion.classManifestURL,'oc2-all-class-safe-source-pose-assets-v1',43],
  ['initial',motion.initialManifestURL,'oc2-creation-initial-idle-browser-assets-v1',8],
 ]){
  const manifest=await read(url);
  if(manifest?.format!==format||!manifest.profiles||Object.keys(manifest.profiles).length!==count||!manifest.banks)throw Error('Own source motion manifest coverage differs');
  reference(url,manifest.entry);reference(url,manifest.core);if(manifest.numeric)reference(url,manifest.numeric);
  for(const row of Object.values(manifest.banks))reference(url,row);
  for(const row of Object.values(manifest.profiles)){
   if(!manifest.banks[row.bank])throw Error('Own source motion bank differs');reference(url,row);
  }
  const queue=kind==='show'?'/assets/source-creation-control-runtime-v1/modules/source_class_queue_runtime_v1.mjs':'/assets/source-creation-control-runtime-v1/modules/source_initial_queue_runtime_v1.mjs';
  const queueSource=await readFile(required(queue).path,'utf8');
  for(const [,relative]of queueSource.matchAll(/from ['"](.+?)['"]/g)){
   if(!relative.startsWith('./')||relative.includes('..'))throw Error('Original queue dependency differs');
   required(queue.slice(0,queue.lastIndexOf('/')+1)+relative.slice(2));
  }
 }
 return resources;
}
