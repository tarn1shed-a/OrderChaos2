// Original 43 type8 placements, integrated through the existing display window.
import {validateSourceSceneEffect} from './source-scene-effect-preview.js';
import {createSourceSceneEffectClock} from './source-scene-effect-clock.mjs';
import {createParticleRenderer} from './particle-renderer.js';
const BASE='/assets/source-scene-effects/';
const HASH='3f5c397bcad07580513ddb50adcb5abcd95fb6c6b55919d886470857e233510a';
const NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4';

export function validateSceneEffectPlayback(profile){
 if(profile?.format!=='oc2-source-scene-effect-playback-v1'||profile.sourceSHA256!==HASH||profile.nativeSHA256!==NATIVE||
  profile.nativeCompletionGateExecuted!==true||profile.nativeClockAndFirstSpawnExecuted!==true||
  profile.defaultEmitterCount!==3||profile.defaultPause294!==0||profile.defaultSpawn4c0!==1||
  profile.defaultFirst38a!==1||profile.defaultClock200!==0||profile.defaultRootTimeScale23c!==1||
  profile.durationFrames!==-1||profile.automaticRestart!==false||profile.lightsAdded!==false||
  profile.callbackField250IsClock!==false||profile.wholeMapAccepted!==false)
  throw Error('原场景特效播放证据不匹配');
 return true;
}

export function createSourceSceneEffectRuntime(THREE,{definition,instances,profile,textures,camera,origin,scene,archiveObjects}){
 validateSceneEffectPlayback(profile);
 if(instances.length!==43||new Set(instances.map(r=>r.tile+':'+r.id)).size!==43)throw Error('原场景特效摆放清单不完整');
 for(const row of instances)validateSourceSceneEffect(definition,row);
 const renderer=createParticleRenderer(THREE,{data:{effects:{sceneEffect:definition}},textures,camera});
 let disposed=false,previous=null,residencyText=null,resident=new Set(),archiveReady=false;
 const rows=instances.map(instance=>{
  const group=new THREE.Group();group.name='source-scene-effect:'+instance.id;
  // Keep the source pose exact. Only the existing browser origin is subtracted.
  group.position.copy(origin).multiplyScalar(-1);group.visible=false;
  const pose={position:new THREE.Vector3(...instance.position),quaternion:new THREE.Quaternion(...instance.quaternion),scale:new THREE.Vector3(...instance.scale)};
  const draw=renderer.create('sceneEffect',`inspection:${instance.tile}:${instance.id}`,group),clock=createSourceSceneEffectClock();
  const archiveEntry={root:group,tile:instance.tile};archiveObjects.push(archiveEntry);scene.add(group);
  return {instance,group,pose,draw,clock,archiveEntry,particles:0};
 });
 return {update(now,sourceArchiveWindow){
  if(disposed)throw Error('场景特效已卸载');
  if(!Number.isFinite(now)||(previous!==null&&now<previous))throw Error('场景特效需要单调帧时钟');
  if(sourceArchiveWindow!==residencyText){
   const state=JSON.parse(sourceArchiveWindow||'null');
   if(!Array.isArray(state?.resident)){previous=now;archiveReady=false;for(const row of rows)row.group.visible=false;return this.inspect();}
   resident=new Set(state.resident);residencyText=sourceArchiveWindow;
  }
  archiveReady=true;
  const delta=previous===null?0:now-previous;previous=now;
  for(const row of rows){row.group.visible=resident.has(row.instance.tile.join(','));
   const ms=row.clock.advance(delta,{visible:row.group.visible});
   if(row.group.visible)row.particles=row.draw.update(ms,row.pose);
  }
  return this.inspect();
 },inspect({detailed=false}={}){return{format:'oc2-source-scene-effects-runtime-v1',placements:rows.length,archiveReady,
  visible:rows.filter(r=>r.group.visible).length,particles:rows.filter(r=>r.group.visible).reduce((n,r)=>n+r.particles,0),
  loadedResourceClock:true,automaticRestart:false,lightsAdded:false,
  ...(detailed?{entries:rows.map(r=>({id:r.instance.id,tile:r.instance.tile,visible:r.group.visible,clock:r.clock.inspect().milliseconds}))}:{})};
 },dispose(){if(disposed)return;disposed=true;for(const row of rows){scene.remove(row.group);row.draw.dispose();
   const index=archiveObjects.indexOf(row.archiveEntry);if(index>=0)archiveObjects.splice(index,1);
  }renderer.dispose();}};
}

export async function loadSourceSceneEffectRuntime(THREE,{json,texture,...context}){
 const manifest=await json(BASE+'manifest.json');
 if(manifest.source!=='effects/scene/scene_fire_smoke.beff'||manifest.placementCount!==43||manifest.wholeMapAccepted!==false)
  throw Error('原场景特效资源组不匹配');
 const[definition,instances,profile]=await Promise.all([json(BASE+manifest.effect),json(BASE+manifest.placements),json(BASE+'playback.json')]);
 const textures=new Map();await Promise.all(Object.values(manifest.textures).map(async r=>textures.set(r.file,await texture(BASE+r.file))));
 return createSourceSceneEffectRuntime(THREE,{definition,instances,profile,textures,...context});
}
