// Public inventory fixtures only: no PNG/GLSL/native actor or GPU is mocked as
// recovered evidence. Real bytes/rendering are checked in private Linux QA.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {prepareNPCMarkerDelivery,NPC_MARKER_PROFILE} from '../deploy/npc_marker_delivery.mjs';
const prefix='/assets/source-ordinary-npc-head/';
const pixels={
  6:['a361292574e8f7c07b4798338c231e94e583ff9df50f13f13032dbca77b1213d','531b68b58d749de22e65c4f61ebf7dc83aefd505d256e72aabc749b80656fd36'],
  4:['6365e38da2771d45551e9101407a689c36fc6c7f297c360daf6e2d4ecebf3914','4b8eaf95b0379e5e9c7415fff8c81c0824e045b4accc20525db93a92c0c5e491'],
  9:['c2a100b67727486da71300eca6b91ff911d215518640fd416cbf8707f01dba28','995a1f2f7ec7b45d1a36094d8e5843ab82a24dff5c4d9710dea65c776cddcc34'],
};
async function fixture(run){
  const root=await mkdtemp(join(tmpdir(),'oc2-marker-delivery-')),path=join(root,'profile.json'),files={},added=[];
  const p={format:'oc2-ordinary-npc-quest-marker-assets-v1',questId:461,npcEntry:2079,originalActivityOrTaskApproved:false,
    presentation:{format:'oc2-compatible-461-source-head-presentation-v1',compatibleLedgerOnly461:true,
      originalActorQualificationRestored:false,originalCacheScheduleRestored:false,originalGPUCompletionProvided:false},assets:{}};
  for(const [state,[png,rgba]]of Object.entries(pixels)){
    const pngURL=prefix+'assets/'+png+'.png',rgbaURL=prefix+'assets/'+png+'.rgba';
    p.assets[state]={pngURL,rgbaURL,sha256:png,rgbaSHA256:rgba,size:[96,96]};files[pngURL]={sha256:png};files[rgbaURL]={sha256:rgba};
  }
  for(const[key,name,sha]of [['vertexURL','UnlitOneTextureAndVertexColorVP.glsl','377148e4ab5b16e33cca09a0a82ae74e75d72837801b2ea6b278318d713f3f58'],
    ['fragmentURL','UnlitTexturedBlendTextureAlphaFP.glsl','a61201783340bd10e928fee191388fddac1999af9db26b90200613b92a5d67a5']]){p[key]=prefix+name;files[p[key]]={sha256:sha};}
  files['/ordinary-npc-name-basis.mjs']={sha256:'3cb848013e533abfa8ebbc83b31c21963840327fcf3fbe0bdbc108dd2699fa52'};
  files['/ordinary-npc-head-material.mjs']={sha256:'7fa6fe16c4b0e727953517366372e6dd2e3ed1fe500f01c763b4421172c6ccd6'};
  files[NPC_MARKER_PROFILE]={path};const save=()=>writeFile(path,JSON.stringify(p)),add=async(...v)=>added.push(v);
  try{await save();await run({root,files,p,save,add,added});}finally{await rm(root,{recursive:true,force:true});}
}
test('old private bundles do not opt in or require marker modules',async()=>{
  let adds=0;assert.equal(await prepareNPCMarkerDelivery('/no-runtime',{},()=>adds++),false);assert.equal(adds,0);
});
test('complete reviewed inventory registers only two browser presentation modules',async()=>fixture(async({root,files,add,added})=>{
  assert.equal(await prepareNPCMarkerDelivery(root,files,add),true);
  assert.deepEqual(added.map(v=>[v[0],v[2]]),[['/__delivery/ordinary_npc_marker.mjs','text/javascript; charset=utf-8'],['/__delivery/ordinary_npc_projection.mjs','text/javascript; charset=utf-8']]);
}));
test('missing/corrupt images, shader, helper and a foreign URL cannot opt in',async()=>{
  for(const bad of ['missing','pixel','shader','helper','external'])await fixture(async({root,files,p,save,add,added})=>{
    if(bad==='missing')delete files[p.assets[6].rgbaURL];
    if(bad==='pixel')files[p.assets[6].pngURL].sha256='0'.repeat(64);
    if(bad==='shader')files[p.fragmentURL].sha256='0'.repeat(64);
    if(bad==='helper')delete files['/ordinary-npc-name-basis.mjs'];
    if(bad==='external')p.assets[6].pngURL='https://external.invalid/marker.png';
    await save();await assert.rejects(prepareNPCMarkerDelivery(root,files,add));assert.deepEqual(added,[]);
  });
});
test('other quests/NPCs or invented native admission never enter this compatible presentation',async()=>{
  for(const bad of ['quest','npc','approved','qualification','cache','GPU','state'])await fixture(async({root,files,p,save,add,added})=>{
    if(bad==='quest')p.questId=208;if(bad==='npc')p.npcEntry=800;if(bad==='approved')p.originalActivityOrTaskApproved=true;
    if(bad==='qualification')p.presentation.originalActorQualificationRestored=true;
    if(bad==='cache')p.presentation.originalCacheScheduleRestored=true;
    if(bad==='GPU')p.presentation.originalGPUCompletionProvided=true;
    if(bad==='state')delete p.assets[4];
    await save();await assert.rejects(prepareNPCMarkerDelivery(root,files,add));assert.deepEqual(added,[]);
  });
});
