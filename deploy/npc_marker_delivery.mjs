// Optional461 source presentation. A complete additive private closure is
// required before the HTML can opt in; old bundles retain their old path.
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
export const NPC_MARKER_PROFILE='/assets/source-ordinary-npc-head/profile.json';
const PREFIX='/assets/source-ordinary-npc-head/';
const pins={
  6:['a361292574e8f7c07b4798338c231e94e583ff9df50f13f13032dbca77b1213d','531b68b58d749de22e65c4f61ebf7dc83aefd505d256e72aabc749b80656fd36'],
  4:['6365e38da2771d45551e9101407a689c36fc6c7f297c360daf6e2d4ecebf3914','4b8eaf95b0379e5e9c7415fff8c81c0824e045b4accc20525db93a92c0c5e491'],
  9:['c2a100b67727486da71300eca6b91ff911d215518640fd416cbf8707f01dba28','995a1f2f7ec7b45d1a36094d8e5843ab82a24dff5c4d9710dea65c776cddcc34'],
};
const sourceShaders={
  vertexURL:['UnlitOneTextureAndVertexColorVP.glsl','377148e4ab5b16e33cca09a0a82ae74e75d72837801b2ea6b278318d713f3f58'],
  fragmentURL:['UnlitTexturedBlendTextureAlphaFP.glsl','a61201783340bd10e928fee191388fddac1999af9db26b90200613b92a5d67a5'],
};
export async function prepareNPCMarkerDelivery(root,files,add){
  if(!files[NPC_MARKER_PROFILE])return false;
  const p=JSON.parse(await readFile(files[NPC_MARKER_PROFILE].path,'utf8')),scope=p.presentation;
  if(p.format!=='oc2-ordinary-npc-quest-marker-assets-v1'||p.questId!==461||p.npcEntry!==2079||
    p.originalActivityOrTaskApproved!==false||scope?.format!=='oc2-compatible-461-source-head-presentation-v1'||
    scope.compatibleLedgerOnly461!==true||scope.originalActorQualificationRestored!==false||
    scope.originalCacheScheduleRestored!==false||scope.originalGPUCompletionProvided!==false)
    throw Error('Original461 marker scope differs');
  const pin=(url,sha)=>{if(!files[url]||files[url].sha256!==sha)throw Error('Original461 marker payload unavailable: '+url);};
  if(!p.assets||Object.keys(p.assets).sort().join(',')!=='4,6,9')throw Error('Original461 marker states differ');
  for(const[status,[png,rgba]]of Object.entries(pins)){
    const row=p.assets[status],pngURL=PREFIX+'assets/'+png+'.png',rgbaURL=PREFIX+'assets/'+png+'.rgba';
    if(row?.pngURL!==pngURL||row.rgbaURL!==rgbaURL||row.sha256!==png||row.rgbaSHA256!==rgba||
      JSON.stringify(row.size)!=='[96,96]')throw Error('Original461 marker image differs');
    pin(pngURL,png);pin(rgbaURL,rgba);
  }
  for(const[key,[file,sha]]of Object.entries(sourceShaders)){
    if(p[key]!==PREFIX+file)throw Error('Original461 marker shader route differs');pin(p[key],sha);
  }
  pin('/ordinary-npc-name-basis.mjs','3cb848013e533abfa8ebbc83b31c21963840327fcf3fbe0bdbc108dd2699fa52');
  pin('/ordinary-npc-head-material.mjs','7fa6fe16c4b0e727953517366372e6dd2e3ed1fe500f01c763b4421172c6ccd6');
  for(const name of ['ordinary_npc_marker.mjs','ordinary_npc_projection.mjs'])
    await add('/__delivery/'+name,resolve(root,'deploy',name),'text/javascript; charset=utf-8');
  return true;
}
