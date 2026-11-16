import {validateCreationStagesDelivery} from './creation_stages_profile.mjs';
import {creationMotionEventPlan} from './creation_motion.mjs';
// Original source-backed Race/Class/Part scene. Legacy race renderer stays unchanged.
// Account/character creation and played-world appearance are separate systems.
import {createSelectionScene} from '/source-selection-scene.js';
import {createSelectionInsideAppend} from '/selection_scene_inside_material.js';
import {createSelectionStonesAppend} from '/selection_scene_stones_material.js';
import * as legacyCreationPreview from '/character_creation_preview_proposal.mjs';
import {applyCreationStageTransform,createCreationStageCamera,createCreationCameraTrack} from '/source-creation-stage.mjs';
import {loadSourceCharacterPrograms,createSourceCharacterMaterial} from './attribute_preview.mjs';
import {checkedStageContract,checkedStageCandidate,selectStageIdentity,stageResourceURL} from './creation_class_stage/stage_switch.mjs';
import {checkedStageModel,buildCreationStageActor} from './creation_class_stage/actor_v2.mjs';
import {createSourceCreationMaterial} from './creation_class_stage/material_v2.mjs';

export const CREATION_DELIVERY_FORMAT='oc2-source-creation-preview-delivery-v1';
export const CREATION_EXTENDED_FORMAT='oc2-source-creation-preview-delivery-v2';
export const CREATION_GROUP_FORMAT='oc2-source-creation-preview-delivery-v3';
export const CREATION_RACES_FORMAT='oc2-source-creation-preview-delivery-v4';
export const CREATION_CONDITIONAL_FORMAT='oc2-source-creation-preview-delivery-v5';
const raceSources={'1:0':{key:'mendel-male',display:2048,model:34},'1:1':{key:'mendel-female',display:2049,model:31},
 '2:1':{key:'elf-female',display:2047,model:2},'3:0':{key:'orc-male',display:2050,model:28},
 '3:1':{key:'orc-female',display:2051,model:30},'4:0':{key:'kartan',display:2052,model:29}};
const conditionalSource={key:'elf-male',display:2046,model:33};
const conditionalContract='51a825509778cec34f72369b3a57cb2cbcec2d5102954f2b5eb2b0ebc2c3dc3e';
const corrected=format=>[CREATION_GROUP_FORMAT,CREATION_RACES_FORMAT,CREATION_CONDITIONAL_FORMAT].includes(format);
const racePreviewAPI=format=>format===CREATION_CONDITIONAL_FORMAT?import('/character_creation_race_preview_v2.mjs'):import('/character_creation_race_preview_v1.mjs');
const extensions={
 dry:['/assets/source-selection-water/overlay.json','/selection_scene_water_material.js','createSelectionWaterDryAppend'],
 flowers:['/assets/source-selection-flowers/overlay.json','/selection_scene_flowers_material.js','createSelectionFlowersAppend'],
 grass:['/assets/source-selection-grass/overlay.json','/selection_scene_grass_material.js','createSelectionGrassAppend'],
 waterfalls:['/assets/source-selection-waterfalls/overlay.json','/selection_scene_waterfalls_material.js','createSelectionWaterfallsAppend'],
 waterSurface:['/assets/source-selection-water-surface/overlay.json','/selection_scene_water_surface.js','createSelectionWaterSurfaceAppend'],
 wetFloor:['/assets/source-selection-water-floor/overlay.json','/selection_scene_water_floor.js','createSelectionWaterFloorAppend'],
};
const correctedExtensions={...extensions,wetFloor:['/assets/source-selection-water-floor-groups/overlay.json',...extensions.wetFloor.slice(1)]};
const safe=url=>typeof url==='string'&&/^\/assets\/source-[A-Za-z0-9_./-]+$/.test(url)&&!url.includes('..')&&!url.includes('//');
// Legacy profiles must remain usable with their original immutable public
// payload. These two-body guards require no additional private module.
export function legacyCreationResourceURL(baseURL,path,documentURL=globalThis.location?.href){
 const base=new URL(baseURL,documentURL);
 if(!base.pathname.endsWith('/')||base.search||base.hash||typeof path!=='string'||!path||
  !/^\/?[A-Za-z0-9_./-]+$/.test(path)||path.includes('..')||path.includes('//'))throw Error('Unsafe original preview resource path');
 const result=new URL(path.replace(/^\//,''),base);
 if(result.origin!==base.origin||!result.pathname.startsWith(base.pathname))throw Error('Original preview escapes private resource directory');
 return result.href;
}
const legacyBodies={'0:0':{display:2038,model:1,path:'model/npc/character/human/male/oc2_human_m_body_01.bdae'},
 '0:1':{display:2045,model:32,path:'model/npc/character/human/female/oc2_human_f_body_01.bdae'}};
export function checkedLegacyCreationPreview(manifest,{race,gender}){
 legacyCreationPreview.checkedCreationPreview(manifest,{race,gender});
 const body=legacyBodies[`${race}:${gender}`];
 if(!body||manifest.originalDisplayId!==body.display)throw Error('Original legacy preview display differs');
}
export function checkedLegacyCreationModel(manifest,data,{race,gender}){
 checkedLegacyCreationPreview(manifest,{race,gender});
 const body=legacyBodies[`${race}:${gender}`],s=data?.sourceCreation;
 if(data?.source!==body.path||s?.displayId!==body.display||s.race!==race||s.gender!==gender||s.createdRole!==false||s.originalFloatWeightsPreserved!==true||
  (Object.hasOwn(s,'sourceModelId')&&s.sourceModelId!==body.model)||JSON.stringify(s.visibleMeshIndices)!==JSON.stringify(manifest.visibleMeshIndices))
  throw Error('Original legacy preview model does not match its stage costume');
}
const legacySecurity={creationPreviewResourceURL:legacyCreationResourceURL,checkedCreationPreview:checkedLegacyCreationPreview,checkedCreationModel:checkedLegacyCreationModel};
export function validateCreationDelivery(p){
 const keys=Object.keys(p?.previews||{}).sort(),conditional=p?.format===CREATION_CONDITIONAL_FORMAT;
 const races=p?.format===CREATION_RACES_FORMAT||conditional,sources=conditional?{...raceSources,'2:0':conditionalSource}:raceSources;
 if(![CREATION_DELIVERY_FORMAT,CREATION_EXTENDED_FORMAT,CREATION_GROUP_FORMAT,CREATION_RACES_FORMAT,CREATION_CONDITIONAL_FORMAT].includes(p?.format)||p.mapId!==7||p.sourceSelectionRegion!==211||p.freshStartOnly!==true||
  p.wholeCreationRestored!==false||p.createsPlayableRole!==false||p.stages?.length!==1||p.stages[0]!=='CharacterChooseRace'||
  !['stage','environment','scene','inside','stones'].every(k=>safe(p[k]))||
  (!races&&keys.join(',')!=='0:0,0:1')||(races&&(!keys.includes('0:0')||!keys.includes('0:1')||keys.length<3||keys.some(k=>!['0:0','0:1',...Object.keys(sources)].includes(k))))||
  !Object.values(p.previews).every(v=>safe(v.baseURL)&&v.baseURL.endsWith('/')))
  throw Error('Original race-preview delivery scope differs');
 if(races&&(p.sourceRaceTraceSHA256!=='6c3c300912f2cc7021a3784c601a7229b327916ee89c9a34ac72390b82f680a8'||
  !Array.isArray(p.additionalOriginalPreviews)||p.additionalOriginalPreviews.map(v=>v.key).sort().join(',')!==keys.filter(k=>sources[k]).join(',')||
  p.additionalOriginalPreviews.some(v=>v.display!==sources[v.key]?.display||v.model!==sources[v.key]?.model||v.bodyKey!==sources[v.key]?.key)||
  p.allNineRacePreviewsRestored!==false))throw Error('Original additional race-preview evidence differs');
 if(conditional){
  const c=p.conditionalOriginalPreviews;
  if(keys.length!==9||!Array.isArray(c)||c.length!==1||c[0].key!=='2:0'||c[0].contractSHA256!==conditionalContract||
   c[0].appearanceComplete!==false||c[0].sourceRequestSucceeded!==false||c[0].displayOnlyAfterHostReady!==true||
   p.originalAndroidFinalAppearanceKnown!==false)throw Error('Conditional source-material readiness policy differs');
 }else if(p.conditionalOriginalPreviews!==undefined)throw Error('Legacy profile cannot activate a conditional source policy');
 const routes=corrected(p.format)?correctedExtensions:extensions;
 if(p.format!==CREATION_DELIVERY_FORMAT&&(!Array.isArray(p.extensions)||
  p.extensions.map(e=>e.kind).join(',')!==Object.keys(extensions).join(',')||
  p.extensions.some(e=>e.url!==routes[e.kind]?.[0])||
  p.originalStaticInstances!==151||p.originalDryChunks!==192||p.originalWaterSurfaceChunks!==152||p.originalWetFloorRestored!==true))
  throw Error('Original selection scene extensions differ');
 if(corrected(p.format)&&p.originalGroupRepresentativeMaterialCopies!==true)throw Error('Original material group copies missing');
 if(p.format===CREATION_DELIVERY_FORMAT&&p.extensions!==undefined)throw Error('Original v1 preview cannot activate new extensions');
 return p;
}
const attributes=[['Vertex','position'],['Normal','normal'],['TexCoord0','uv'],['Tangent','sourceTangent'],['Binormal','sourceBinormal'],['SkinWeights','skinWeight'],['SkinIndices','skinIndex']];

export function createSourceCreationStages(root,{profileURL,motionHistory=null,initialOwnerSelection=null}){
 if(!root?.prepend||!safe(profileURL))throw Error('Existing recovered entry and explicit private profile required');
 let engine=null,pending=null,serial=0,active=false,closed=false,raf=0,actor=null,lastTime=0,motion=null,resumeClock=true,requested=null,acceptedSelection=initialOwnerSelection?{...initialOwnerSelection}:null;
 const canvas=document.createElement('canvas');canvas.className='source-creation-preview';canvas.hidden=true;canvas.setAttribute('aria-hidden','true');
 const cache=new Map(),loaderCache=new Map(),textCache=new Map();
 const json=async url=>{
  if(!cache.has(url))cache.set(url,fetch(url).then(r=>{if(!r.ok)throw Error('Original preview input unavailable');return r.json();}).catch(e=>{cache.delete(url);throw e;}));
  return cache.get(url);
 };
 const text=async url=>{
  if(!textCache.has(url))textCache.set(url,fetch(url).then(r=>{if(!r.ok)throw Error('Original selection shader unavailable');return r.text();}).catch(e=>{textCache.delete(url);throw e;}));
  return textCache.get(url);
 };
 async function initialise(){
  if(engine)return engine;
  if(!pending)pending=(async()=>{
   const stages=validateCreationStagesDelivery(await json(profileURL),{profileURL});
   const [p,contract]=await Promise.all([json(stages.raceProfileURL).then(validateCreationDelivery),json(stages.contractURL).then(checkedStageContract)]);
   const THREE=await import('/vendor/three.module.js');
   const [profile,fresh,sceneProfile,insideProfile,stonesProfile]=await Promise.all([p.stage,p.environment,p.scene,p.inside,p.stones].map(json));
   const extra=await Promise.all((p.extensions||[]).map(async row=>({kind:row.kind,profile:await json(row.url)})));
   if(fresh.format!=='oc2-selection-environment-fresh-inputs-v1'||!fresh.freshStartOnly||!fresh.fieldInputsReady||fresh.sourceSelectionRegion!==211||fresh.reentrySupported)
    throw Error('Original fresh selection environment missing');
   const uniforms=Object.fromEntries(Object.entries(fresh.uniformInputs).map(([key,v])=>[key,{value:Array.isArray(v)?(v.length===2?new THREE.Vector2(...v):new THREE.Vector3(...v)):v}]));
   const lighting={sourceSelectionRegion:211,uniforms},origin=new THREE.Vector3(),loader=new THREE.TextureLoader();
   const texture=url=>{
    if(closed)return Promise.reject(Error('Preview disposed'));
    if(!loaderCache.has(url)){
     const pendingTexture=loader.loadAsync(url).then(t=>{
      if(closed){t.dispose();throw Error('Preview disposed');}
      t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.needsUpdate=true;return t;
     }).catch(error=>{if(loaderCache.get(url)===pendingTexture)loaderCache.delete(url);throw error;});
     loaderCache.set(url,pendingTexture);
    }
    return loaderCache.get(url);
   };
   const renderer=new THREE.WebGLRenderer({canvas,antialias:true});renderer.outputColorSpace=THREE.LinearSRGBColorSpace;
   renderer.toneMapping=THREE.NoToneMapping;renderer.setPixelRatio(1);renderer.setSize(1136,640,false);
   // Unrestored sky remains the existing empty clear; no replacement sky art.
   renderer.setClearColor(0,1);
   const scene=new THREE.Scene(),camera=createCreationStageCamera(THREE,profile,{width:1136,height:640});
   const clockStart=performance.now(),clock={value:()=>Math.fround((performance.now()-clockStart)/1000)},parts=[],extraParts=new Map();
   try{
    // Parallel byte/image preparation only; source constructors still receive
    // the same complete records and retain their original part order.
    const queued=new Set(),queue=[];
    const discover=value=>{
     if(typeof value==='string'&&safe(value)&&/\.(?:json|png)$/.test(value)&&!queued.has(value)){queued.add(value);queue.push(value);}
     else if(Array.isArray(value))for(const child of value)discover(child);
     else if(value&&typeof value==='object')for(const child of Object.values(value))discover(child);
    };
    [sceneProfile,insideProfile,stonesProfile,...extra.map(e=>e.profile)].forEach(discover);
    async function warm(){while(queue.length){const url=queue.shift();if(url.endsWith('.json'))discover(await json(url));else await texture(url);}}
    await Promise.all(Array.from({length:6},warm));
    parts.push(await createSelectionScene(THREE,sceneProfile,{origin,lighting,json,texture}));
    parts.push(await createSelectionInsideAppend(THREE,insideProfile,{origin,lighting,json,texture,clock}));
    parts.push(await createSelectionStonesAppend(THREE,stonesProfile,{origin,lighting,json,texture}));
    for(const row of extra){
     const[,module,name]=(corrected(p.format)?correctedExtensions:extensions)[row.kind],api=await import(module);
     const part=await api[name](THREE,row.profile,{origin,lighting,json,text,texture,clock});parts.push(part);extraParts.set(row.kind,part);
    }
    const assembly={staticInstances:parts.reduce((n,p)=>n+(p.instances||0),0),dryChunks:extraParts.get('dry')?.chunks||0,waterSurfaceChunks:extraParts.get('waterSurface')?.chunks||0,wetFloorChunks:extraParts.get('wetFloor')?.chunks||0,waterBorderChunks:extraParts.get('wetFloor')?.borderChunks||0};
    if(p.format!==CREATION_DELIVERY_FORMAT&&(assembly.staticInstances!==p.originalStaticInstances||assembly.dryChunks!==p.originalDryChunks||assembly.waterSurfaceChunks!==p.originalWaterSurfaceChunks||assembly.wetFloorChunks!==152||assembly.waterBorderChunks!==152))throw Error('Original selection assembly is incomplete');
    for(const part of parts)scene.add(part.root);
    const track=createCreationCameraTrack(profile,{pose:profile.configuredInitialPose,group:-1});
    // Original CharacterChooseRace ENTER_RACE=0 -> panel table[0]=3.
    track.select(3,0);
    const built={p,stages,contract,THREE,profile,fresh,lighting,scene,camera,track,renderer,texture,parts,assembly};
    if(closed){for(const part of parts)part.dispose();renderer.dispose();throw Error('Preview disposed');}
    engine=built;return built;
   }catch(e){for(const part of parts)part.dispose();renderer.dispose();throw e;}
  })().catch(e=>{pending=null;throw e;});
  return pending;
 }
 function dropActor(){motion?.dispose();motion=null;if(actor){actor.dispose();actor=null;}}
 async function loadActor(e,race,gender,{sourcePoseOwner=null}={}){
  // Existing public proposal bytes are immutable. The versioned additional
  // API validates all incoming resources; v1-v3 retain the old actual factory.
  const extended=e.p.format===CREATION_RACES_FORMAT||e.p.format==='oc2-source-creation-preview-delivery-v5';
  const security=extended?await racePreviewAPI(e.p.format):legacySecurity;
  const api=extended?security:legacyCreationPreview;
  const base=e.p.previews[api.creationPreviewKey(race,gender)]?.baseURL;if(!base)return null;
  const url=path=>security.creationPreviewResourceURL(base,path);
  const manifest=await json(url('manifest.json'));
  // Reject an unexpected identity before following any model/image reference.
  security.checkedCreationPreview(manifest,{race,gender});
  const modelURL=url(manifest.model),paths=[...new Set(manifest.materials.flatMap(row=>Object.values(row.samplers)))];
  const images=paths.map(path=>[path,url(path)]); // Validate the complete closure before requesting it.
  const data=await json(modelURL),textures=new Map();
  security.checkedCreationModel(manifest,data,{race,gender});
  const conditional=manifest.format===security.ELF_CONDITIONAL_FORMAT;
  const policy=conditional?security.checkedElfConditionalPolicy(manifest):null,ownedInputs=[];
  const retained=policy?new Map(Object.entries(policy.samplers).map(([slot,input])=>[input.url,slot])):null;
  const loaded=await Promise.allSettled(images.map(async([path,sourceURL])=>{
   const texture=retained?.has(path)?await security.loadElfConditionalTexture(e.THREE,sourceURL,retained.get(path)):await e.texture(sourceURL);
   if(retained?.has(path))ownedInputs.push(texture);
   textures.set(path,texture);
  }));
  const rejected=loaded.find(result=>result.status==='rejected');
  if(rejected){for(const texture of ownedInputs)texture.dispose();throw rejected.reason;}
  let preview;
  try{preview=api.buildCreationRacePreview({THREE:e.THREE,createMaterial:()=>new e.THREE.MeshBasicMaterial(),manifest,data,textures,race,gender});}
  catch(error){for(const texture of ownedInputs)texture.dispose();throw error;}
  const materials=[],maps=[],rows=new Map(manifest.materials.map(row=>[row.index,row]));
  const release=()=>{preview.dispose();for(const m of materials)m.dispose();for(const t of maps)t.dispose();};
  try{
   const programs=await loadSourceCharacterPrograms(),colors={...manifest.colors,eye:e.profile.transform.freshModelEyeColor};
   for(let i=0;i<preview.meshes.length;i++){
    const object=preview.meshes[i];if(!object.visible)continue;
    for(const[to,from]of attributes){const a=object.geometry.getAttribute(from);if(!a)throw Error('Original character attribute missing');object.geometry.setAttribute(to,a);}
    const list=[];
    for(const index of new Set(data.meshes[i].groups.map(g=>g.material))){
     const row=rows.get(index),states=row?.sourceEffectProfiles?.profiles?.map(p=>p.state);
     if(states?.length!==2||JSON.stringify(states[0])!==JSON.stringify(states[1])||states[0].blendEnabled||!states[0].depthTestEnabled||!states[0].depthWriteEnabled||states[0].depthFunctionGL!==515)
      throw Error('Unverified original character pass');
     const samplers=new Map();
     for(const [slot,path]of Object.entries(row.samplers)){
      const t=textures.get(path).clone(),a=row.addressing[slot];maps.push(t);
      if(conditional)security.inheritElfTextureReceipt(textures.get(path),t);
      t.wrapS=a.addressU===0?e.THREE.RepeatWrapping:e.THREE.ClampToEdgeWrapping;t.wrapT=a.addressV===0?e.THREE.RepeatWrapping:e.THREE.ClampToEdgeWrapping;t.needsUpdate=true;samplers.set(path,t);
     }
     const m=createSourceCharacterMaterial(e.THREE,row,samplers,programs,object,colors,e.fresh.sourceCharacterLight,e.lighting,e.profile.sourceControllerLight.direction);
     list[index]=m;materials.push(m);
    }
    object.material=list;object.castShadow=object.receiveShadow=false;
   }
   applyCreationStageTransform(preview.root,e.profile);
   const conditionalReady=conditional?security.completeElfConditionalPreview(e.THREE,{manifest,data,preview}):null;
   const next={...preview,conditionalReady,dispose:release};
   if(sourcePoseOwner){const {attachRaceSourcePose}=await import('./creation_control/race_actor_pose_v1.mjs');attachRaceSourcePose({THREE:e.THREE,actor:next,data,race,gender,current:sourcePoseOwner});}
   return {actor:next,data};
  }catch(error){release();throw error;}
 }
 async function loadStageActor(e,identity,{sourcePoseOwner=null}={}){
  const route=e.stages.candidates[`${identity.panel}:${identity.race}:${identity.gender}:${identity.professionIndex}`];
  if(!route)return null; // A missing source candidate never reuses a race costume.
  const shared=['shared-source-geometry-v1','shared-source-geometry-v2'].includes(route.provider);
  if(shared&&!e.sharedStageFactory)e.sharedStageFactory=(async()=>{
   const {createSharedStageFactory}=await import('./creation_geometry.mjs');
   return createSharedStageFactory({profile:e.stages.sharedGeometry,crypto:globalThis.crypto,loadBytes:async url=>{
    const r=await fetch(url);if(!r.ok)throw Error('Original shared stage input unavailable');return new Uint8Array(await r.arrayBuffer());
   }});
  })().catch(error=>{e.sharedStageFactory=null;throw error;});
  const actorAPI=shared?await e.sharedStageFactory:e.stages.actorVersion===3?await import('./creation_class_stage/actor_v3.mjs'):{checkedStageModel,buildCreationStageActor};
  const url=path=>stageResourceURL(route.baseURL,path),manifest=await json(url('manifest.json'));
  checkedStageCandidate(manifest,identity);
  const data=await json(url(manifest.model));actorAPI.checkedStageModel(manifest,data,identity);
  const rows=[...manifest.materials,...manifest.attachments.flatMap(row=>row.materials)];
  const paths=[...new Set(rows.flatMap(row=>Object.values(row.samplers)))],textures=new Map(),attachmentData=new Map();
  const requests=paths.map(path=>[path,url(path)]),models=manifest.attachments.map(row=>[row.model,url(row.model)]);
  await Promise.all([...requests.map(async([path,src])=>textures.set(path,await e.texture(src))),
   ...models.map(async([path,src])=>attachmentData.set(path,await json(src)))]);
  const programs=await loadSourceCharacterPrograms();
  const next=(shared?actorAPI.build:actorAPI.buildCreationStageActor)({THREE:e.THREE,renderer:e.renderer,manifest,data,identity,textures,attachmentData,sourcePoseOwner,
   createMaterial:(THREE,row,maps,colors,object)=>createSourceCreationMaterial(THREE,row,maps,programs,object,
    {...colors,eye:e.profile.transform.freshModelEyeColor},e.fresh.sourceCharacterLight,e.lighting,e.profile.sourceControllerLight.direction)});
  if(sourcePoseOwner&&!shared){
   const {attachLegacyClassSourcePose}=await import('./creation_control/legacy_actor_pose_v1.mjs');
   try{attachLegacyClassSourcePose({actor:next,data,identity,current:sourcePoseOwner});}catch(error){next.dispose();throw error;}
  }
  return {actor:next,data};
 }
 function visibilityChanged(){
  // Browser presentation clock only. A hidden tab cannot fabricate intermediate
  // original frames; resume from a fresh observed zero-delta preview frame.
  resumeClock=true;cancelAnimationFrame(raf);
  if(active&&!closed&&!document.hidden){lastTime=performance.now();raf=requestAnimationFrame(frame);}
 }
 document.addEventListener('visibilitychange',visibilityChanged);
 function frame(time){
  if(!active||closed||!engine||document.hidden)return;
  // A browser suspension outside the checked source-delta domain is a clock
  // resumption, not a fabricated sequence of native update calls.
  const resumed=resumeClock||time-lastTime>20000;
  const elapsed=resumed?0:Math.max(0,Math.floor(time)-Math.floor(lastTime));
  const seconds=resumed?0:(time-lastTime)/1000;resumeClock=false;
  try{
   actor?.update(seconds);
   if(motion){const state=motion.update(elapsed,actor);if(motion.kind.startsWith('race-'))motionHistory.raceFrame(state);else motionHistory.classFrame(state);root.dataset.sourceCreationMotion=JSON.stringify({kind:motion.kind,key:motion.key,...state});}
  }catch(error){motion?.dispose();motion=null;motionHistory?.unresolvedClassCarrier();root.dataset.sourceCreationMotionError=error.message;}
  lastTime=time;
  engine.camera.setPose(engine.track.update());engine.renderer.render(engine.scene,engine.camera.camera);
  root.dataset.sourceCreationDrawCalls=String(engine.renderer.info.render.calls);
  raf=requestAnimationFrame(frame);
 }
 function hide(){serial++;active=false;canvas.hidden=true;cancelAnimationFrame(raf);dropActor();root.dataset.sourceCreationPreview='hidden';delete root.dataset.sourceCreationDisplay;delete root.dataset.sourceCreationStage;delete root.dataset.sourceCreationDrawCalls;delete root.dataset.sourceCreationAssembly;delete root.dataset.sourceCreationConditionalReady;delete root.dataset.sourceCreationAppearanceComplete;delete root.dataset.sourceCreationMissingOverride;delete root.dataset.sourceCreationSharedGeometry;delete root.dataset.sourceCreationError;delete root.dataset.sourceCreationMotion;delete root.dataset.sourceCreationMotionError;requested=null;}
 return {
  async show({screen,race,gender,professionIndex,event='page-enter'}){
   const version=profileURL.endsWith('/manifest-stages-v6.json')?2:profileURL.endsWith('/manifest-stages-v5.json')?1:0;
   const plan=creationMotionEventPlan({version,screen,event,target:{race,gender,professionIndex},ownerSelection:acceptedSelection,requested,history:motionHistory});
   if(plan.noop)return;
   const {ownerBefore,initialGlobals}=plan;
   hide();requested={screen,race,gender,professionIndex};if(closed||!['CharacterChooseRace','CharacterChooseClass','CharacterChoosePart'].includes(screen))return;
   const token=serial;root.dataset.sourceCreationPreview='loading';
   try{
    const e=await initialise();if(token!==serial||closed)return;
    const identity=selectStageIdentity(e.contract,{screen,race,gender,professionIndex});
    e.track.select(identity.cameraGroup,identity.race);
    // The original 53d3e8 switches the character wrapper; its selection scene
    // is not destroyed when a race is selected. An unavailable web candidate
    // must not leave a previous race on screen or remove the proven background.
    root.prepend(canvas);canvas.hidden=false;active=true;lastTime=performance.now();raf=requestAnimationFrame(frame);
    root.dataset.sourceCreationAssembly=JSON.stringify(e.assembly);
    const sourcePoseOwner=e.stages.sourceMotion&&(identity.panel===1||e.stages.sourceMotion.version===2&&identity.panel===0)?()=>token===serial&&!closed:null;
    const built=identity.panel===0?await loadActor(e,race,gender,{sourcePoseOwner}):await loadStageActor(e,identity,{sourcePoseOwner});
    const next=built?.actor;
    if(token!==serial||closed){next?.dispose();return;}
    if(!next){root.dataset.sourceCreationPreview='scene-only';return;}actor=next;if(identity.panel!==0)applyCreationStageTransform(actor.root,e.profile);e.scene.add(actor.root);
    if(identity.panel===0&&acceptedSelection){acceptedSelection={...acceptedSelection,race,gender};}
    if(identity.panel===1)acceptedSelection={race,gender,professionIndex};
    if(plan.kind&&e.stages.sourceMotion){
      try{
       if(!motionHistory)throw Error('Explicit session animation history required');
       if(!e.motionLibrary){const {createCreationMotionLibrary}=await import('./creation_motion.mjs');e.motionLibrary=createCreationMotionLibrary({json,crypto:globalThis.crypto,bytes:async url=>{
        const r=await fetch(url);if(!r.ok)throw Error('Original Class motion input unavailable');return new Uint8Array(await r.arrayBuffer());
       },version:e.stages.sourceMotion.version});}
       // Class.Init's synchronous show request is superseded by EnterPanel1's
       // new generic wrapper. Only a later actual Class binding retains show.
       const prepared=await e.motionLibrary.prepare({identity,data:built.data,kind:plan.kind,ownerBefore,initialGlobals,current:sourcePoseOwner});
       if(!sourcePoseOwner()){prepared?.dispose();return;}
       if(prepared){try{actor.claimSourcePoseWriter();motion=prepared;resumeClock=true;root.dataset.sourceCreationMotion=JSON.stringify({kind:motion.kind,key:motion.key,pending:true});}catch(error){prepared.dispose();motion=null;throw error;}}
      }catch(error){if(sourcePoseOwner())root.dataset.sourceCreationMotionError=error.message;}
    }
    if(token!==serial||closed)return;
    lastTime=performance.now();
    root.dataset.sourceCreationPreview='ready';root.dataset.sourceCreationDisplay=String(identity.request.displayId);root.dataset.sourceCreationStage=String(identity.panel);
    if(next.sharedSource){root.dataset.sourceCreationSharedGeometry=JSON.stringify(next.sharedSource);root.dataset.sourceCreationAppearanceComplete=String(!next.sharedSource.bodyOnly);}
    if(next.conditionalReady){root.dataset.sourceCreationConditionalReady=JSON.stringify(next.conditionalReady);root.dataset.sourceCreationAppearanceComplete='false';root.dataset.sourceCreationMissingOverride=next.conditionalReady.omittedOverride;}
    root.dataset.sourceCreationAssembly=JSON.stringify(e.assembly);
   }catch(error){if(token===serial&&!closed){requested=null;if(!active)canvas.hidden=true;root.dataset.sourceCreationPreview=active?'scene-only':'unavailable';root.dataset.sourceCreationError=error.message;}}
  },
  hide,
  dispose(){hide();closed=true;document.removeEventListener('visibilitychange',visibilityChanged);canvas.remove();if(engine){engine.sharedStageFactory?.then(f=>f.dispose()).catch(()=>{});for(const p of engine.parts)p.dispose();engine.renderer.dispose();}for(const t of loaderCache.values())t.then(v=>v.dispose()).catch(()=>{});loaderCache.clear();},
 };
}
