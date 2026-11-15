// Only a complete, checked preview closure activates the new stage renderer.
import {readFile}from'node:fs/promises';
import {resolve}from'node:path';
import {createHash}from'node:crypto';
import {CREATION_STAGES_PROFILES,CREATION_STAGES_PROFILE_V2,validateCreationStagesDelivery,stageCandidateChoice}from'./creation_stages_profile.mjs';
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
 for(const [key,row]of Object.entries(p.candidates)){
  const identity=selectStageIdentity(contract,stageCandidateChoice(key));
  const url=path=>new URL(stageResourceURL(row.baseURL,path,'http://oc2.invalid/')).pathname;
  const manifest=checkedStageCandidate(await read(url('manifest.json')),identity);
  if(!Array.isArray(manifest.materials)||!Array.isArray(manifest.attachments))throw Error('Original stage material/attachment closure absent');
  required(url(manifest.model));
  for(const attachment of manifest.attachments){required(url(attachment.model));if(!Array.isArray(attachment.materials))throw Error('Original weapon material closure absent');}
  for(const material of [...manifest.materials,...manifest.attachments.flatMap(a=>a.materials)]){
   if(!material.samplers||typeof material.samplers!=='object')throw Error('Original stage samplers absent');
   for(const path of Object.values(material.samplers))required(url(path));
  }
 }
 }
 const modules=[['creation_stages.mjs','deploy/creation_stages.mjs'],['creation_stages_profile.mjs','deploy/creation_stages_profile.mjs'],
  ['creation_class_stage/stage_switch.mjs','tools/creation_class_stage/stage_switch.mjs'],
  ['creation_class_stage/actor_v2.mjs','tools/creation_class_stage/actor_v2.mjs'],
  ['creation_class_stage/material_v2.mjs','tools/creation_class_stage/material_v2.mjs']];
 if(profiles.includes(CREATION_STAGES_PROFILE_V2))modules.push(['creation_class_stage/actor_v3.mjs','tools/creation_class_stage/actor_v3.mjs']);
 for(const [name,relative]of modules){const path=resolve(root,relative),raw=await readFile(path);files['/__delivery/'+name]={path,bytes:raw.length,sha256:digest(raw),type:'text/javascript; charset=utf-8'};}
 return true;
}
