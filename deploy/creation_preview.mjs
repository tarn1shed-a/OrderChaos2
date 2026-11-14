// Original race-selection scene, attached to the existing recovered UI only.
// Account/character creation and played-world appearance are separate systems.
import {createSelectionScene} from '/source-selection-scene.js';
import {createSelectionInsideAppend} from '/selection_scene_inside_material.js';
import {createSelectionStonesAppend} from '/selection_scene_stones_material.js';
import {buildCreationRacePreview,creationPreviewKey} from '/character_creation_preview_proposal.mjs';
import {applyCreationStageTransform,createCreationStageCamera,createCreationCameraTrack} from '/source-creation-stage.mjs';
import {loadSourceCharacterPrograms,createSourceCharacterMaterial} from './attribute_preview.mjs';

export const CREATION_DELIVERY_FORMAT='oc2-source-creation-preview-delivery-v1';
export const CREATION_EXTENDED_FORMAT='oc2-source-creation-preview-delivery-v2';
export const CREATION_GROUP_FORMAT='oc2-source-creation-preview-delivery-v3';
const extensions={
 dry:['/assets/source-selection-water/overlay.json','/selection_scene_water_material.js','createSelectionWaterDryAppend'],
 flowers:['/assets/source-selection-flowers/overlay.json','/selection_scene_flowers_material.js','createSelectionFlowersAppend'],
 grass:['/assets/source-selection-grass/overlay.json','/selection_scene_grass_material.js','createSelectionGrassAppend'],
 waterfalls:['/assets/source-selection-waterfalls/overlay.json','/selection_scene_waterfalls_material.js','createSelectionWaterfallsAppend'],
 waterSurface:['/assets/source-selection-water-surface/overlay.json','/selection_scene_water_surface.js','createSelectionWaterSurfaceAppend'],
 wetFloor:['/assets/source-selection-water-floor/overlay.json','/selection_scene_water_floor.js','createSelectionWaterFloorAppend'],
};
const correctedExtensions={...extensions,wetFloor:['/assets/source-selection-water-floor-groups/overlay.json',...extensions.wetFloor.slice(1)]};
const safe=url=>typeof url==='string'&&url.startsWith('/assets/source-')&&!url.includes('..')&&!url.includes('//');
export function validateCreationDelivery(p){
 if(![CREATION_DELIVERY_FORMAT,CREATION_EXTENDED_FORMAT,CREATION_GROUP_FORMAT].includes(p?.format)||p.mapId!==7||p.sourceSelectionRegion!==211||p.freshStartOnly!==true||
  p.wholeCreationRestored!==false||p.createsPlayableRole!==false||p.stages?.length!==1||p.stages[0]!=='CharacterChooseRace'||
  !['stage','environment','scene','inside','stones'].every(k=>safe(p[k]))||
  Object.keys(p.previews||{}).sort().join(',')!=='0:0,0:1'||!Object.values(p.previews).every(v=>safe(v.baseURL)&&v.baseURL.endsWith('/')))
  throw Error('Original race-preview delivery scope differs');
 const routes=p.format===CREATION_GROUP_FORMAT?correctedExtensions:extensions;
 if(p.format!==CREATION_DELIVERY_FORMAT&&(!Array.isArray(p.extensions)||
  p.extensions.map(e=>e.kind).join(',')!==Object.keys(extensions).join(',')||
  p.extensions.some(e=>e.url!==routes[e.kind]?.[0])||
  p.originalStaticInstances!==151||p.originalDryChunks!==192||p.originalWaterSurfaceChunks!==152||p.originalWetFloorRestored!==true))
  throw Error('Original selection scene extensions differ');
 if(p.format===CREATION_GROUP_FORMAT&&p.originalGroupRepresentativeMaterialCopies!==true)throw Error('Original material group copies missing');
 if(p.format===CREATION_DELIVERY_FORMAT&&p.extensions!==undefined)throw Error('Original v1 preview cannot activate new extensions');
 return p;
}
const attributes=[['Vertex','position'],['Normal','normal'],['TexCoord0','uv'],['Tangent','sourceTangent'],['Binormal','sourceBinormal'],['SkinWeights','skinWeight'],['SkinIndices','skinIndex']];

export function createSourceCreationPreview(root,{profileURL}){
 if(!root?.prepend||!safe(profileURL))throw Error('Existing recovered entry and explicit private profile required');
 let engine=null,pending=null,serial=0,active=false,closed=false,raf=0,actor=null,lastTime=0;
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
   const p=validateCreationDelivery(await json(profileURL));
   const THREE=await import('/vendor/three.module.js');
   const [profile,fresh,sceneProfile,insideProfile,stonesProfile]=await Promise.all([p.stage,p.environment,p.scene,p.inside,p.stones].map(json));
   const extra=await Promise.all((p.extensions||[]).map(async row=>({kind:row.kind,profile:await json(row.url)})));
   if(fresh.format!=='oc2-selection-environment-fresh-inputs-v1'||!fresh.freshStartOnly||!fresh.fieldInputsReady||fresh.sourceSelectionRegion!==211||fresh.reentrySupported)
    throw Error('Original fresh selection environment missing');
   const uniforms=Object.fromEntries(Object.entries(fresh.uniformInputs).map(([key,v])=>[key,{value:Array.isArray(v)?(v.length===2?new THREE.Vector2(...v):new THREE.Vector3(...v)):v}]));
   const lighting={sourceSelectionRegion:211,uniforms},origin=new THREE.Vector3(),loader=new THREE.TextureLoader();
   const texture=url=>{
    if(!loaderCache.has(url))loaderCache.set(url,loader.loadAsync(url).then(t=>{t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.needsUpdate=true;return t;}));
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
     const[,module,name]=(p.format===CREATION_GROUP_FORMAT?correctedExtensions:extensions)[row.kind],api=await import(module);
     const part=await api[name](THREE,row.profile,{origin,lighting,json,text,texture,clock});parts.push(part);extraParts.set(row.kind,part);
    }
    const assembly={staticInstances:parts.reduce((n,p)=>n+(p.instances||0),0),dryChunks:extraParts.get('dry')?.chunks||0,waterSurfaceChunks:extraParts.get('waterSurface')?.chunks||0,wetFloorChunks:extraParts.get('wetFloor')?.chunks||0,waterBorderChunks:extraParts.get('wetFloor')?.borderChunks||0};
    if(p.format!==CREATION_DELIVERY_FORMAT&&(assembly.staticInstances!==p.originalStaticInstances||assembly.dryChunks!==p.originalDryChunks||assembly.waterSurfaceChunks!==p.originalWaterSurfaceChunks||assembly.wetFloorChunks!==152||assembly.waterBorderChunks!==152))throw Error('Original selection assembly is incomplete');
    for(const part of parts)scene.add(part.root);
    const track=createCreationCameraTrack(profile,{pose:profile.configuredInitialPose,group:-1});
    // Original CharacterChooseRace ENTER_RACE=0 -> panel table[0]=3.
    track.select(3,0);
    const built={p,THREE,profile,fresh,lighting,scene,camera,track,renderer,texture,parts,assembly};
    if(closed){for(const part of parts)part.dispose();renderer.dispose();throw Error('Preview disposed');}
    engine=built;return built;
   }catch(e){for(const part of parts)part.dispose();renderer.dispose();throw e;}
  })().catch(e=>{pending=null;throw e;});
  return pending;
 }
 function dropActor(){if(actor){actor.dispose();actor=null;}}
 async function loadActor(e,race,gender){
  const base=e.p.previews[creationPreviewKey(race,gender)]?.baseURL;if(!base)return null;
  const manifest=await json(base+'manifest.json'),data=await json(base+manifest.model.replace(/^\//,'')),textures=new Map();
  await Promise.all([...new Set(manifest.materials.flatMap(row=>Object.values(row.samplers)))].map(async name=>textures.set(name,await e.texture(base+name.replace(/^\//,'')))));
  const preview=buildCreationRacePreview({THREE:e.THREE,createMaterial:()=>new e.THREE.MeshBasicMaterial(),manifest,data,textures,race,gender});
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
      t.wrapS=a.addressU===0?e.THREE.RepeatWrapping:e.THREE.ClampToEdgeWrapping;t.wrapT=a.addressV===0?e.THREE.RepeatWrapping:e.THREE.ClampToEdgeWrapping;t.needsUpdate=true;samplers.set(path,t);
     }
     const m=createSourceCharacterMaterial(e.THREE,row,samplers,programs,object,colors,e.fresh.sourceCharacterLight,e.lighting,e.profile.sourceControllerLight.direction);
     list[index]=m;materials.push(m);
    }
    object.material=list;object.castShadow=object.receiveShadow=false;
   }
   applyCreationStageTransform(preview.root,e.profile);
   return {...preview,dispose:release};
  }catch(error){release();throw error;}
 }
 function frame(time){
  if(!active||closed||!engine)return;
  actor?.update((time-lastTime)/1000);lastTime=time;
  engine.camera.setPose(engine.track.update());engine.renderer.render(engine.scene,engine.camera.camera);
  root.dataset.sourceCreationDrawCalls=String(engine.renderer.info.render.calls);
  raf=requestAnimationFrame(frame);
 }
 function hide(){serial++;active=false;canvas.hidden=true;cancelAnimationFrame(raf);dropActor();root.dataset.sourceCreationPreview='hidden';delete root.dataset.sourceCreationDisplay;delete root.dataset.sourceCreationDrawCalls;delete root.dataset.sourceCreationAssembly;}
 return {
  async show({screen,race,gender}){
   hide();if(closed||screen!=='CharacterChooseRace'||!creationPreviewKey(race,gender))return;
   const token=serial;root.dataset.sourceCreationPreview='loading';
   try{
    const e=await initialise();if(token!==serial||closed)return;
    const next=await loadActor(e,race,gender);
    if(token!==serial||closed){next?.dispose();return;}
    if(!next)return;actor=next;e.scene.add(actor.root);
    root.prepend(canvas);canvas.hidden=false;active=true;lastTime=performance.now();raf=requestAnimationFrame(frame);
    root.dataset.sourceCreationPreview='ready';root.dataset.sourceCreationDisplay=String(next.manifest.originalDisplayId);
    root.dataset.sourceCreationAssembly=JSON.stringify(e.assembly);
   }catch(error){if(token===serial&&!closed){canvas.hidden=true;root.dataset.sourceCreationPreview='unavailable';root.dataset.sourceCreationError=error.message;}}
  },
  hide,
  dispose(){hide();closed=true;canvas.remove();if(engine){for(const p of engine.parts)p.dispose();engine.renderer.dispose();}for(const t of loaderCache.values())t.then(v=>v.dispose()).catch(()=>{});loaderCache.clear();},
 };
}
