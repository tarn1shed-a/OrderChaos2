// Only the ten originally admitted level2 scene_fire records.
export const FIRE10_FORMAT='oc2-source-tutorial-scene-fire10-v1';
const source='effects/scene/scene_fire.beff',hash='fafd102871041292cc12f8c836fa5e2ed2fe07e8b9c131308ab3c7c61105e5cf';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
export function validateFire10(definition,instance){
 const p=definition?.sourceSceneEffect,r=instance?.originalRequest;
 if(p?.format!==FIRE10_FORMAT||p.source!==source||p.sourceSHA256!==hash||definition.sourceSHA256!==hash||
  p.sourceType!==8||p.originalRequestParametersExecuted!==true||p.nativeClockAndFirstSpawnExecuted!==true||
  p.originalResourceCompletionExecuted!==false||p.automaticRestart!==false||p.lightsAdded!==false||
  definition.fogRate!==0||definition.durationMs!==null||definition.emitters?.length!==2||definition.modelNodes?.length!==0||
  definition.verification?.completePayload!==true||definition.verification.opaquePayloadBytes!==0)
  throw Error('原纯火焰资源不匹配');
 if(instance?.model!==source||instance.sourceType!==8||instance.sourcePhaseWord60!==0xffffffff||
  instance.originalAdmission!=='admittedBeforeTypeFactory'||instance.originalLookupLevel!==2||
  instance.nativeRequestParametersExecuted!==true||!finite(instance.position,3)||!finite(instance.quaternion,4)||!finite(instance.scale,3)||
  r?.kind!=='original-async-scene-effect-request'||r.source!==source||r.originalResourceTaskExecuted!==false||
  ['position','quaternion','scale'].some(k=>JSON.stringify(r[k])!==JSON.stringify(instance[k])))
  throw Error('原纯火焰摆放/准入不匹配');
 for(const e of definition.emitters)if(e.shape!==0||e.startFrame!==0||e.durationFrames!==-1||e.children.length||e.affectors.length||
  e.particle?.type!==0||e.particle.materialId!==6||e.particle.material?.id!==6||e.particle.material.blend!=='additive'||
  e.particle.material.twoColor!==false||e.particle.material.noDepthTest!==false)throw Error('原纯火焰材质/发射器模式尚未恢复');
 return true;
}
