import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync}from'node:fs';
import {CREATION_STAGES_PROFILE,CREATION_STAGES_PROFILE_V2,CREATION_STAGES_DELIVERY_FORMAT,STAGE_CONTRACT_URL,STAGE_CONTRACT_SHA256,RACE_PROFILE,validateCreationStagesDelivery}from'../deploy/creation_stages_profile.mjs';
import {prepareCreationStagesDelivery}from'../deploy/creation_stages_delivery.mjs';
import {selectCreationProfile}from'../deploy/prepare_delivery.mjs';
import {creationPreviewPlan}from'../deploy/creation_plan.mjs';
const profile=()=>({format:CREATION_STAGES_DELIVERY_FORMAT,mapId:7,sourceSelectionRegion:211,freshStartOnly:true,
 createsPlayableRole:false,wholeCreationRestored:false,raceProfileURL:RACE_PROFILE,contractURL:STAGE_CONTRACT_URL,contractSHA256:STAGE_CONTRACT_SHA256,
 candidates:{'1:0:0:1':{baseURL:'/assets/source-creation-stages/actors/fixture/',sourceKey:'fixture'}}});
test('stage metadata is explicitly opt-in and never grants a playable identity',()=>{
 const p=profile();assert.equal(validateCreationStagesDelivery(p),p);
 for(const patch of [{createsPlayableRole:true},{wholeCreationRestored:true},{mapId:1},{sourceSelectionRegion:4},{freshStartOnly:false},
  {contractSHA256:'0'.repeat(64)},{contractURL:'/assets/other.json'},{raceProfileURL:'https://external.invalid/'}])
  assert.throws(()=>validateCreationStagesDelivery({...p,...patch}),/scope/);
});
test('source candidate routes reject unknown panels, impossible gender, and external/traversal paths',()=>{
 for(const key of ['0:0:0:0','3:0:0:0','1:4:1:0','1:0:0:5','1:0:0:01','1:0:0:true'])
  assert.throws(()=>validateCreationStagesDelivery({...profile(),candidates:{[key]:profile().candidates['1:0:0:1']}}),/route/);
 for(const baseURL of ['https://external.invalid/','/assets/source-x/../private/','/assets/source-x//models/','/assets/source-x/file.json'])
  assert.throws(()=>validateCreationStagesDelivery({...profile(),candidates:{'1:0:0:1':{sourceKey:'fixture',baseURL}}}),/route/);
 assert.throws(()=>validateCreationStagesDelivery({...profile(),candidates:{}}),/scope/);
});
test('old bundles do not require the new helpers or resources',async()=>{
 const files={'/assets/source-creation-stage/manifest.json':{}};
 assert.equal(await prepareCreationStagesDelivery('/absent-source',files),false);
 assert.equal(selectCreationProfile(files),'/assets/source-creation-stage/manifest.json');
 assert.throws(()=>selectCreationProfile({...files,[CREATION_STAGES_PROFILE]:{}}),/incomplete/);
 assert.equal(selectCreationProfile({...files,[CREATION_STAGES_PROFILE]:{},[STAGE_CONTRACT_URL]:{}}),CREATION_STAGES_PROFILE);
});
test('new profile explicitly opts into complete rigid ancestors while old profile keeps its own factory',()=>{
 const old=profile(),next={...profile(),actorVersion:3,candidates:{'2:0:0:1':profile().candidates['1:0:0:1']}};
 assert.equal(validateCreationStagesDelivery(old,{profileURL:CREATION_STAGES_PROFILE}),old);
 assert.equal(validateCreationStagesDelivery(next,{profileURL:CREATION_STAGES_PROFILE_V2}),next);
 assert.throws(()=>validateCreationStagesDelivery(next,{profileURL:CREATION_STAGES_PROFILE}),/version/);
 assert.throws(()=>validateCreationStagesDelivery(old,{profileURL:CREATION_STAGES_PROFILE_V2}),/version/);
 assert.throws(()=>validateCreationStagesDelivery({...next,actorVersion:4}),/scope/);
 const files={[CREATION_STAGES_PROFILE]:{},[STAGE_CONTRACT_URL]:{}};
 assert.equal(selectCreationProfile(files),CREATION_STAGES_PROFILE);
 assert.equal(selectCreationProfile({...files,[CREATION_STAGES_PROFILE_V2]:{}}),CREATION_STAGES_PROFILE_V2);
});
test('new previews remain on demand; game map/NPC/task loading order is preserved',()=>{
 const preview=['/__delivery/creation_stages.mjs','/__delivery/creation_stages_profile.mjs','/__delivery/creation_class_stage/actor_v2.mjs',
  '/assets/source-creation-stages/contract.json','/assets/source-creation-stages/actors/fixture/assets/character.json'];
 const game=['/assets/source-ordinary-quest-map1/manifest.json','/assets/source-ordinary-quest-actors/profile.json','/assets/ordinary-quests/profile.json'];
 const p={critical:[game[0],...preview,game[1]],background:[game[2]],scope:{old:true}},before=structuredClone(p);
 const next=creationPreviewPlan(p,[...p.critical,...p.background]);
 assert.deepEqual(next.critical,game.slice(0,2));assert.deepEqual(next.background,[game[2]]);assert.deepEqual(p,before);
 assert.equal(next.scope.creationPreviewChangesPlayableRaces,false);
});
test('Docker source closure includes reviewed runtime helpers without original asset globs',()=>{
 const root=new URL('../',import.meta.url),ignore=readFileSync(new URL('.dockerignore',root),'utf8'),pack=readFileSync(new URL('tools/package_deployment.py',root),'utf8');
 for(const n of ['stage_switch.mjs','actor_v2.mjs','actor_v3.mjs','material_v2.mjs']){
  assert(ignore.includes('!tools/creation_class_stage/'+n));assert(pack.includes('tools/creation_class_stage/'+n));
 }
 assert(!ignore.includes('!analysis/raw/'));assert(!ignore.includes('!game-data/'));
});
