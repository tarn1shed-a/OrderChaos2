// Conditional original scene effect; no default-world insertion or timer.
import {createParticleRenderer} from './particle-renderer.js';
export const SCENE_EFFECT_FORMAT='oc2-source-tutorial-scene-effects-v1';
const source='effects/scene/scene_fire_smoke.beff';
const hash='3f5c397bcad07580513ddb50adcb5abcd95fb6c6b55919d886470857e233510a';
const textures=['texture/fire01_6x6.tga','texture/fire03_xulie4x4.tga','texture/fire_cir02.tga'];
const finite=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);

export function validateSourceSceneEffect(definition,instance){
 const p=definition?.sourceSceneEffect,r=instance?.originalRequest;
 if(p?.format!==SCENE_EFFECT_FORMAT||p.source!==source||p.sourceSHA256!==hash||p.sourceType!==8||
  definition.sourceSHA256!==hash||p.originalRequestParametersExecuted!==true||p.insertIntoDefaultScene!==false||
  p.automaticRestart!==false||p.nativeRandomSequenceRestored!==false||p.originalResourceCompletionExecuted!==false||
  p.shaderFogContributionZero!==true||p.lightsAdded!==false||definition.fogRate!==0||definition.durationMs!==null||
  definition.verification?.completePayload!==true||definition.verification.opaquePayloadBytes!==0||
  JSON.stringify(definition.textures)!==JSON.stringify(textures)||definition.emitters?.length!==3||definition.modelNodes?.length!==0||
  JSON.stringify(definition.emitters.map(e=>e.particle?.materialId))!=='[6,6,0]')throw Error('原场景火焰资料不匹配');
 if(instance?.sourceType!==8||instance.model!==source||instance.nativeRequestParametersExecuted!==true||
  instance.sourcePhaseWord60!==0xffffffff||!finite(instance.position,3)||!finite(instance.quaternion,4)||!finite(instance.scale,3)||
  r?.kind!=='original-async-scene-effect-request'||r.source!==source||r.originalResourceTaskExecuted!==false||
  ['position','quaternion','scale'].some(k=>JSON.stringify(r[k])!==JSON.stringify(instance[k])))throw Error('原场景特效摆放输入未核对');
 for(const e of definition.emitters){
  const m=e.particle.material;
  if(e.shape!==0||e.durationFrames!==-1||e.startFrame!==0||e.children.length||e.particle.type!==0||
   !m||m.id!==e.particle.materialId||m.blend!==(m.id===6?'additive':'alpha')||m.twoColor!==false||m.noDepthTest!==false)
   throw Error('原场景特效模式尚未恢复');
 }
 return true;
}

export function createSourceSceneEffect(THREE,{definition,instance,textures:maps,camera}){
 validateSourceSceneEffect(definition,instance);
 for(const path of textures){const key=definition.textureURLs?.[path];if(!key||!maps.has(key))throw Error('原场景特效贴图未就绪');}
 const group=new THREE.Group();group.name='source-scene-effect:'+instance.id;
 const pose={position:new THREE.Vector3(...instance.position),quaternion:new THREE.Quaternion(...instance.quaternion),
  scale:new THREE.Vector3(...instance.scale)};
 const renderer=createParticleRenderer(THREE,{data:{effects:{sceneEffect:definition}},textures:maps,camera});
 const draw=renderer.create('sceneEffect',`inspection:${instance.tile}:${instance.id}`,group);
 group.userData.sourceSceneEffect={format:SCENE_EFFECT_FORMAT,source,instanceId:instance.id,
  insertIntoDefaultScene:false,automaticRestart:false,nativeRandomSequenceRestored:false,hostClockOrigin:true};
 return {group,update(milliseconds){
  if(!Number.isFinite(milliseconds)||milliseconds<0||milliseconds>600000)throw Error('原场景特效需要显式有界时钟');
  return draw.update(milliseconds,pose);
 },dispose(){draw.dispose();renderer.dispose();}};
}
