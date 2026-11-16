import {test}from'node:test';
import assert from'node:assert/strict';
import {CREATION_STAGES_PROFILE_V3,CREATION_STAGES_PROFILE_V4,SHARED_STAGE_REGISTRY,SHARED_REGISTRY_SHA,
 SHARED_BODY_POLICIES,sharedBodyPolicyURL,validateCreationStagesDelivery}from'../deploy/creation_stages_profile.mjs';
import {selectCreationProfile}from'../deploy/prepare_delivery.mjs';
const legacy=new Set(['1:0:0:0','1:0:0:1','1:2:1:1','1:2:1:4','2:0:0:0','2:0:0:1']);
function profile(){
 const candidates={};
 for(const body of Object.keys(SHARED_BODY_POLICIES))for(const panel of[1,2])for(let index=0;index<5;index++){
  const key=`${panel}:${body}:${index}`;
  candidates[key]={baseURL:'/assets/source-creation-stages/actors/fixture-'+key.replaceAll(':','-')+'/',sourceKey:'fixture',
   ...legacy.has(key)?{}:{provider:body==='0:1'?'shared-source-geometry-v1':'shared-source-geometry-v2'}};
 }
 return {format:'oc2-source-creation-stages-delivery-v1',mapId:7,sourceSelectionRegion:211,freshStartOnly:true,
  createsPlayableRole:false,wholeCreationRestored:false,actorVersion:3,
  raceProfileURL:'/assets/source-creation-stage/manifest-conditional-v1.json',
  contractURL:'/assets/source-creation-stages/contract.json',contractSHA256:'26ad805cd6b9abb68026e30996b8344e100673b37fb41a230cc9f30e1017a8ba',
  sharedGeometry:{version:2,registryURL:SHARED_STAGE_REGISTRY,registrySHA256:SHARED_REGISTRY_SHA,
   fullClassQueueRestored:false,initialSourceIdleOnly:true,
   bodies:Object.fromEntries(Object.entries(SHARED_BODY_POLICIES).map(([key,policySHA256])=>[key,{policyURL:sharedBodyPolicyURL(key),policySHA256}]))},candidates};
}
test('full batch requires all ninety source choices and all own body policies',()=>{
 const p=profile();assert.equal(Object.keys(p.candidates).length,90);assert.equal(validateCreationStagesDelivery(p,{profileURL:CREATION_STAGES_PROFILE_V4}),p);
 for(const key of Object.keys(p.candidates)){const broken=structuredClone(p);delete broken.candidates[key];assert.throws(()=>validateCreationStagesDelivery(broken),/incomplete/);}
 for(const key of Object.keys(p.sharedGeometry.bodies)){
  const broken=structuredClone(p);delete broken.sharedGeometry.bodies[key];assert.throws(()=>validateCreationStagesDelivery(broken),/policy/);
 }
});
test('body policies cannot be swapped, redirected, or enabled through an old profile',()=>{
 for(const [key,row]of Object.entries(profile().sharedGeometry.bodies)){
  for(const patch of [{policyURL:'https://external.invalid/policy.json'},{policyURL:sharedBodyPolicyURL('0:1')},{policySHA256:'0'.repeat(64)}]){
   if(patch.policyURL===row.policyURL)continue;
   const broken=profile();Object.assign(broken.sharedGeometry.bodies[key],patch);assert.throws(()=>validateCreationStagesDelivery(broken),/policy/);
  }
 }
 assert.throws(()=>validateCreationStagesDelivery(profile(),{profileURL:CREATION_STAGES_PROFILE_V3}),/policy/);
});
test('preview expansion cannot silently change legacy provider, Part scope, or played-world admission',()=>{
 for(const key of Object.keys(profile().candidates)){
  const broken=profile();broken.candidates[key].provider=legacy.has(key)?'shared-source-geometry-v2':undefined;
  assert.throws(()=>validateCreationStagesDelivery(broken),/provider|incomplete/);
 }
 for(const patch of [{createsPlayableRole:true},{wholeCreationRestored:true}])assert.throws(()=>validateCreationStagesDelivery({...profile(),...patch}),/scope/);
 for(const patch of [{fullClassQueueRestored:true},{initialSourceIdleOnly:false}]){
  const broken=profile();Object.assign(broken.sharedGeometry,patch);assert.throws(()=>validateCreationStagesDelivery(broken),/policy/);
 }
 const broken=profile();broken.candidates['1:4:1:0']=broken.candidates['1:4:0:0'];assert.throws(()=>validateCreationStagesDelivery(broken));
});
test('new profile remains opt-in and demands source contract closure',()=>{
 assert.equal(selectCreationProfile({[CREATION_STAGES_PROFILE_V3]:{},'/assets/source-creation-stages/contract.json':{}}),CREATION_STAGES_PROFILE_V3);
 assert.equal(selectCreationProfile({[CREATION_STAGES_PROFILE_V3]:{},[CREATION_STAGES_PROFILE_V4]:{},'/assets/source-creation-stages/contract.json':{}}),CREATION_STAGES_PROFILE_V4);
 assert.throws(()=>selectCreationProfile({[CREATION_STAGES_PROFILE_V4]:{}}),/incomplete/);
});
