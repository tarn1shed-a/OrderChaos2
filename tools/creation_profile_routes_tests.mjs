// Runtime route contracts only; no resources, browser, saves or server.
import test from 'node:test';
import assert from 'node:assert/strict';
import {selectCreationProfile} from '../deploy/prepare_delivery.mjs';
import {creationPreviewPlan} from '../deploy/creation_plan.mjs';
const legacy=['manifest.json','manifest-v2.json','manifest-v3.json','manifest-races-v1.json'].map(n=>'/assets/source-creation-stage/'+n);
const next='/assets/source-creation-stage/manifest-conditional-v1.json';
const needed=['/character_creation_race_preview_v2.mjs','/creation_elf_source_ready.mjs',
 '/assets/source-creation-elf-conditional-v1/manifest.json','/assets/source-creation-elf-conditional-v1/assets/character.json'];
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
