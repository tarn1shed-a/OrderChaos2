import {test} from 'node:test';
import assert from 'node:assert/strict';
import {CREATION_STAGES_PROFILE_V2,CREATION_STAGES_PROFILE_V3,CREATION_STAGES_DELIVERY_FORMAT,
 STAGE_CONTRACT_URL,STAGE_CONTRACT_SHA256,RACE_PROFILE,SHARED_STAGE_POLICY,SHARED_STAGE_REGISTRY,
 SHARED_POLICY_SHA,SHARED_REGISTRY_SHA,validateCreationStagesDelivery} from '../deploy/creation_stages_profile.mjs';
import {selectCreationProfile} from '../deploy/prepare_delivery.mjs';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {webcrypto} from 'node:crypto';
import {createSharedStageGuard} from './creation_batch/stage_guard.mjs';
import {selectStageIdentity} from './creation_class_stage/stage_switch.mjs';

function profile(){return {format:CREATION_STAGES_DELIVERY_FORMAT,mapId:7,sourceSelectionRegion:211,freshStartOnly:true,
 createsPlayableRole:false,wholeCreationRestored:false,raceProfileURL:RACE_PROFILE,contractURL:STAGE_CONTRACT_URL,
 contractSHA256:STAGE_CONTRACT_SHA256,actorVersion:3,
 sharedGeometry:{version:1,policyURL:SHARED_STAGE_POLICY,policySHA256:SHARED_POLICY_SHA,
  registryURL:SHARED_STAGE_REGISTRY,registrySHA256:SHARED_REGISTRY_SHA,initialSourceIdleOnly:true,fullClassQueueRestored:false},
 candidates:Object.fromEntries([0,1,2,3,4].map(index=>['1:0:1:'+index,{baseURL:'/assets/source-creation-stages/actors/fixture-'+index+'/',sourceKey:'fixture-'+index,provider:'shared-source-geometry-v1'}]))};}

test('shared geometry requires an explicit new profile and all five checked source routes',()=>{
 const p=profile();assert.equal(validateCreationStagesDelivery(p,{profileURL:CREATION_STAGES_PROFILE_V3}),p);
 assert.throws(()=>validateCreationStagesDelivery(p,{profileURL:CREATION_STAGES_PROFILE_V2}),/policy/);
 const missing=profile();delete missing.candidates['1:0:1:2'];assert.throws(()=>validateCreationStagesDelivery(missing),/incomplete/);
 assert.throws(()=>validateCreationStagesDelivery({...p,sharedGeometry:undefined},{profileURL:CREATION_STAGES_PROFILE_V3}),/absent/);
});
test('foreign policies, claims of full restoration and unproved bodies remain rejected',()=>{
 for(const change of [{policyURL:'https://foreign.invalid/policy.json'},{policySHA256:'0'.repeat(64)},
  {registryURL:'/assets/source-other/registry.json'},{registrySHA256:'0'.repeat(64)},
  {fullClassQueueRestored:true},{initialSourceIdleOnly:false},{version:2}]){
  const p=profile();Object.assign(p.sharedGeometry,change);assert.throws(()=>validateCreationStagesDelivery(p),/policy/);
 }
 const p=profile();p.candidates['1:1:0:0']={...p.candidates['1:0:1:0']};assert.throws(()=>validateCreationStagesDelivery(p),/Unproved/);
 p.candidates=profile().candidates;p.candidates['1:0:1:0'].provider='unproved';assert.throws(()=>validateCreationStagesDelivery(p),/Unproved/);
 assert.throws(()=>validateCreationStagesDelivery({...profile(),createsPlayableRole:true}),/scope/);
});
test('new source profile wins only when present; old bundle selection remains unchanged',()=>{
 const files={[CREATION_STAGES_PROFILE_V2]:{},[STAGE_CONTRACT_URL]:{}};
 assert.equal(selectCreationProfile(files),CREATION_STAGES_PROFILE_V2);
 assert.equal(selectCreationProfile({...files,[CREATION_STAGES_PROFILE_V3]:{}}),CREATION_STAGES_PROFILE_V3);
 assert.throws(()=>selectCreationProfile({[CREATION_STAGES_PROFILE_V3]:{}}),/incomplete/);
});
test('appearance routes remain a complete separate stage',()=>{
 const p=profile();
 for(let index=0;index<5;index++)p.candidates['2:0:1:'+index]={...p.candidates['1:0:1:'+index]};
 assert.equal(validateCreationStagesDelivery(p),p);
 delete p.candidates['2:0:1:3'];
 assert.throws(()=>validateCreationStagesDelivery(p),/Part routes incomplete/);
});

test('both original five-profession stages pass one guard; foreign Part rigs and typed exceptions fail',
 {skip:!process.env.OC2_SHARED_SOURCE_ROOT},async()=>{
 const root=resolve(process.env.OC2_SHARED_SOURCE_ROOT);
 const json=async p=>JSON.parse(await readFile(resolve(root,p),'utf8'));
 const guard=await createSharedStageGuard({
  policyBytes:new Uint8Array(await readFile(resolve(root,'analysis/raw/creation-human-female-batch-20261116/stage-policy-v2.json'))),
  registryBytes:new Uint8Array(await readFile(resolve(root,'analysis/raw/creation-capability-batch-20261116/projection-v1/registry.json'))),crypto:webcrypto});
 const contract=await json('analysis/raw/creation-class-entry-20261116/source-v1/contract-runtime.json');
 let last;
 for(const [panel,stage,folder]of [[1,'CharacterChooseClass','creation-human-female-batch-20261116/candidates-v2'],[2,'CharacterChoosePart','creation-human-female-part-20261116/candidates-v1']]){
  for(let index=0;index<5;index++){
   const base='analysis/raw/'+folder+'/class-'+index+'/';
   const manifest=await json(base+'manifest.json'),data=await json(base+manifest.model.replace(/^\.\//,''));
   const identity=selectStageIdentity(contract,{screen:stage,race:0,gender:1,professionIndex:index});
   assert.equal(guard.checkedStageModel(manifest,data,identity),manifest);
   last={manifest,data,identity};
  }
 }
 const badRig=structuredClone(last.data);badRig.rig.nodes[0].name+='-foreign';
 assert.throws(()=>guard.checkedStageModel(last.manifest,badRig,last.identity));
 const badPart=structuredClone(last.manifest);badPart.sourceIndependentEffectGate={unproved:true};
 assert.throws(()=>guard.checkedStageModel(badPart,last.data,last.identity));
 guard.dispose();assert.throws(()=>guard.checkedStageModel(last.manifest,last.data,last.identity),/disposed/);
});
