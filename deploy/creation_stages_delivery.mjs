// Only a complete, checked preview closure activates the new stage renderer.
import {readFile}from'node:fs/promises';
import {resolve}from'node:path';
import {createHash,webcrypto}from'node:crypto';
import {CREATION_STAGES_PROFILES,CREATION_STAGES_PROFILE_V2,CREATION_STAGES_PROFILE_V3,CREATION_STAGES_PROFILE_V4,validateCreationStagesDelivery,stageCandidateChoice}from'./creation_stages_profile.mjs';
import {checkedStageContract,selectStageIdentity,checkedStageCandidate,stageResourceURL}from'../tools/creation_class_stage/stage_switch.mjs';
const digest=b=>createHash('sha256').update(b).digest('hex');
export async function prepareCreationStagesDelivery(root,files){
 const profiles=CREATION_STAGES_PROFILES.filter(url=>files[url]);
 if(!profiles.length)return false;
 const required=url=>{if(!files[url])throw Error('Original stage delivery incomplete: '+url);return files[url];};
 const read=async url=>{
  const row=required(url),raw=await readFile(row.path);
  if(raw.length!==row.bytes||digest(raw)!==row.sha256)throw Error('Original stage delivery bytes differ: '+url);
  return JSON.parse(raw);
 };
 for(const profileURL of profiles){
 const p=validateCreationStagesDelivery(await read(profileURL),{profileURL});
 if(required(p.contractURL).sha256!==p.contractSHA256)throw Error('Original stage contract differs');
 const contract=checkedStageContract(await read(p.contractURL));
 const race=await read(p.raceProfileURL);
 if(race.format!=='oc2-source-creation-preview-delivery-v5'||race.stages?.length!==1||race.stages[0]!=='CharacterChooseRace')throw Error('Original race profile differs');
 let shared;
 if(p.sharedGeometry){
  const s=p.sharedGeometry;
  if(required(s.registryURL).sha256!==s.registrySHA256)
   throw Error('Original shared stage data digest differs');
  const registryBytes=new Uint8Array(await readFile(required(s.registryURL).path));
  if(s.version===2){
   const policies={};
   for(const [key,row]of Object.entries(s.bodies)){
    if(required(row.policyURL).sha256!==row.policySHA256)throw Error('Original body policy digest differs');
    policies[key]=new Uint8Array(await readFile(required(row.policyURL).path));
   }
   const {createStageBatchGuard}=await import('../tools/creation_batch/stage_batch_guard.mjs');
   shared=await createStageBatchGuard({policies,registryBytes,crypto:webcrypto});
  }else{
   if(required(s.policyURL).sha256!==s.policySHA256)throw Error('Original shared stage data digest differs');
   const {createSharedStageGuard}=await import('../tools/creation_batch/stage_guard.mjs');
   shared=await createSharedStageGuard({policyBytes:new Uint8Array(await readFile(required(s.policyURL).path)),registryBytes,crypto:webcrypto});
  }
 }
 try{
 for(const [key,row]of Object.entries(p.candidates)){
  const identity=selectStageIdentity(contract,stageCandidateChoice(key));
  const url=path=>new URL(stageResourceURL(row.baseURL,path,'http://oc2.invalid/')).pathname;
  const manifest=checkedStageCandidate(await read(url('manifest.json')),identity);
  if(!Array.isArray(manifest.materials)||!Array.isArray(manifest.attachments))throw Error('Original stage material/attachment closure absent');
  required(url(manifest.model));
  if(['shared-source-geometry-v1','shared-source-geometry-v2'].includes(row.provider))shared.checkedStageModel(manifest,await read(url(manifest.model)),identity);
  for(const attachment of manifest.attachments){required(url(attachment.model));if(!Array.isArray(attachment.materials))throw Error('Original weapon material closure absent');}
  for(const material of [...manifest.materials,...manifest.attachments.flatMap(a=>a.materials)]){
   if(!material.samplers||typeof material.samplers!=='object')throw Error('Original stage samplers absent');
   for(const path of Object.values(material.samplers))required(url(path));
  }
 }
 }finally{shared?.dispose();}
 }
 const modules=[['creation_stages.mjs','deploy/creation_stages.mjs'],['creation_stages_profile.mjs','deploy/creation_stages_profile.mjs'],
  ['creation_class_stage/stage_switch.mjs','tools/creation_class_stage/stage_switch.mjs'],
  ['creation_class_stage/actor_v2.mjs','tools/creation_class_stage/actor_v2.mjs'],
  ['creation_class_stage/material_v2.mjs','tools/creation_class_stage/material_v2.mjs']];
 if([CREATION_STAGES_PROFILE_V2,CREATION_STAGES_PROFILE_V3,CREATION_STAGES_PROFILE_V4].some(p=>profiles.includes(p)))modules.push(['creation_class_stage/actor_v3.mjs','tools/creation_class_stage/actor_v3.mjs']);
 if([CREATION_STAGES_PROFILE_V3,CREATION_STAGES_PROFILE_V4].some(p=>profiles.includes(p))){
  modules.push(['creation_geometry.mjs','deploy/creation_geometry.mjs'],['creation_class_stage/actor_v6.mjs','tools/creation_class_stage/actor_v6.mjs']);
  for(const name of ['geometry_core','contracts','stage_guard','stage_adapters_v1','stage_adapter_core_v1','source_capabilities_v1'])modules.push(['creation_batch/'+name+'.mjs','tools/creation_batch/'+name+'.mjs']);
 }
 if(profiles.includes(CREATION_STAGES_PROFILE_V4))for(const name of ['stage_batch_guard','stage_adapters_all_v1','stage_adapters_v5','typed_armor_root'])modules.push(['creation_batch/'+name+'.mjs','tools/creation_batch/'+name+'.mjs']);
 for(const [name,relative]of modules){const path=resolve(root,relative),raw=await readFile(path);files['/__delivery/'+name]={path,bytes:raw.length,sha256:digest(raw),type:'text/javascript; charset=utf-8'};}
 return true;
}
