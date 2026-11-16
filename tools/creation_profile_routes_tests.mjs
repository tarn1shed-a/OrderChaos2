// Runtime route contracts only; no resources, browser, saves or server.
import test from 'node:test';
import assert from 'node:assert/strict';
import {selectCreationProfile} from '../deploy/prepare_delivery.mjs';
import {creationPreviewPlan} from '../deploy/creation_plan.mjs';
import {prepareQuestDelivery} from '../deploy/quest_delivery.mjs';
import {CREATION_STAGES_PROFILE_V4,CREATION_STAGES_PROFILE_V6} from '../deploy/creation_stages_profile.mjs';
import {CREATION_ENTRY_PROFILES,isCreationEntryProfile} from '../deploy/creation_routes.mjs';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,copyFileSync,rmSync} from 'node:fs';
import {join} from 'node:path';
import {tmpdir} from 'node:os';
import {fileURLToPath} from 'node:url';
const legacy=['manifest.json','manifest-v2.json','manifest-v3.json','manifest-races-v1.json'].map(n=>'/assets/source-creation-stage/'+n);
const next='/assets/source-creation-stage/manifest-conditional-v1.json';
const needed=['/character_creation_race_preview_v2.mjs','/creation_elf_source_ready.mjs',
 '/assets/source-creation-elf-conditional-v1/manifest.json','/assets/source-creation-elf-conditional-v1/assets/character.json'];
test('both server entry overlays share explicit legacy and current source profile routes',()=>{
 assert.equal(CREATION_ENTRY_PROFILES.length,11);
 for(const url of [...legacy,next,CREATION_STAGES_PROFILE_V4,CREATION_STAGES_PROFILE_V6])assert.equal(isCreationEntryProfile(url),true);
 for(const url of [null,'https://external.invalid/profile','/assets/source-creation-stage/manifest-stages-v7.json'])assert.equal(isCreationEntryProfile(url),false);
});
test('existing bundles keep their old creation profile; incomplete conditional bundles are refused',()=>{
 for(let mask=0;mask<16;mask++){
  const files=Object.fromEntries(legacy.filter((_,i)=>mask&(1<<i)).map(k=>[k,{}]));
  const expected=[...legacy].reverse().find(k=>files[k])||legacy[0];assert.equal(selectCreationProfile(files),expected);
  const full={...files,[next]:{},...Object.fromEntries(needed.map(k=>[k,{}]))};assert.equal(selectCreationProfile(full),next);
  for(const missing of needed){const broken={...full};delete broken[missing];assert.throws(()=>selectCreationProfile(broken),/incomplete/);}
 }
});
test('conditional previews remain on demand and cannot move map, NPC or task inputs out of preload',()=>{
 const original={critical:['/explore-map.js','/assets/ordinary-quests/profile.json','/character_creation_race_preview_v2.mjs'],
  background:['/assets/source-ordinary-quest-actors/profile.json','/creation_elf_source_ready.mjs','/assets/source-creation-elf-conditional-v1/assets/character.json'],scope:{original:true}};
 const before=structuredClone(original),files=[...original.critical,...original.background];const plan=creationPreviewPlan(original,files);
 assert.deepEqual(original,before);assert.deepEqual(plan.critical,original.critical.slice(0,2));
 assert.deepEqual(plan.background,[original.background[0]]);assert.equal(plan.scope.creationPreviewChangesPlayableRaces,false);
});

test('actual task delivery opts into the same verified preview and never rewrites the source world',async()=>{
 // Host file-inventory fixture; no original model or task contents fabricated.
 const directory=mkdtempSync(join(tmpdir(),'oc2-quest-preview-')),root=join(directory,'source'),destination=join(directory,'built');
 mkdirSync(join(root,'deploy'),{recursive:true});mkdirSync(destination);
 const originals={};for(const n of ['quest_world.mjs','quest_ui.mjs','quest_tracking.mjs','character_choice_skills.mjs','quest_ui.css','quest_tracking.css']){
  const p=fileURLToPath(new URL('../deploy/'+n,import.meta.url));originals[n]=readFileSync(p);copyFileSync(p,join(root,'deploy',n));
 }
 const html=join(directory,'entry.html');writeFileSync(html,'<html lang="zh-CN"><script type="module" src="/explore-map.js"></script></html>');
 const required=['/assets/ordinary-quests/profile.json','/assets/source-ordinary-quest-map1/manifest.json','/assets/source-ordinary-quest-actors/profile.json',
 '/assets/source-quest/quest-ui.json','/assets/source-mission-optional/optional-assets.json','/assets/ordinary-quests/program-v1.json',
 '/mission_program.mjs','/ordinary-quest-scene.mjs','/source-ordinary-quest-actors.mjs'];
 const fixture=()=>({...Object.fromEntries(required.map(k=>[k,{}])),'/explore-map.html':{path:html},[next]:{}});
 try{
  const legacy=fixture();await prepareQuestDelivery(root,destination,legacy);assert.equal(readFileSync(legacy['/__delivery/quest_world.mjs'].path,'utf8'),originals['quest_world.mjs'].toString());
  const current=fixture();await prepareQuestDelivery(root,destination,current,{creationProfile:next});const derived=readFileSync(current['/__delivery/quest_world.mjs'].path,'utf8');
  for(const name of ['quest_ui.css','quest_tracking.css']){
   assert.equal(current['/__delivery/'+name].type,'text/css; charset=utf-8');
   assert.deepEqual(readFileSync(current['/__delivery/'+name].path),originals[name]);
  }
  assert(derived.includes('entry=createSourceEntry({connect,previewURL:'+JSON.stringify(next)+'});'));
  assert.equal(derived.replace(',previewURL:'+JSON.stringify(next),''),originals['quest_world.mjs'].toString());
  const batch=fixture();batch[CREATION_STAGES_PROFILE_V4]={};
  await prepareQuestDelivery(root,destination,batch,{creationProfile:CREATION_STAGES_PROFILE_V4});
  const staged=readFileSync(batch['/__delivery/quest_world.mjs'].path,'utf8');
  assert(staged.includes('entry=createSourceEntry({connect,previewURL:'+JSON.stringify(CREATION_STAGES_PROFILE_V4)+'});'));
  assert.equal(staged.replace(',previewURL:'+JSON.stringify(CREATION_STAGES_PROFILE_V4),''),originals['quest_world.mjs'].toString());
  const newest=fixture();newest[CREATION_STAGES_PROFILE_V6]={};
  await prepareQuestDelivery(root,destination,newest,{creationProfile:CREATION_STAGES_PROFILE_V6});
  assert(readFileSync(newest['/__delivery/quest_world.mjs'].path,'utf8').includes('previewURL:'+JSON.stringify(CREATION_STAGES_PROFILE_V6)));
  await assert.rejects(prepareQuestDelivery(root,destination,fixture(),{creationProfile:'https://external.invalid/profile'}),/unavailable/);
  const absent=fixture();delete absent[next];await assert.rejects(prepareQuestDelivery(root,destination,absent,{creationProfile:next}),/unavailable/);
  for(const[n,bytes]of Object.entries(originals))assert.deepEqual(readFileSync(join(root,'deploy',n)),bytes);
 }finally{rmSync(directory,{recursive:true,force:true});}
});
