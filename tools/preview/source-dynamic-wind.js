// Original nonzero formula, explicit APK defaults. Host clock/draw adapters remain.
import {createBakedSceneMaterial as oldCreate,bindInstanceLightmap} from './source-wind-identity.js?sourceWind=1';
import {createBakedSceneMaterial as baseCreate} from './scene-baked-lighting.js?source-selection=1';
export {bindInstanceLightmap};
export const DYNAMIC_WIND_FORMAT='oc2-source-dynamic-wind-v1';
const EFFECT='ut_lightmap_shake_trans.bdae',f=Math.fround;
export function createWindClock(originUs){
 if(!Number.isSafeInteger(originUs)||originUs<0)throw Error('Invalid host monotonic clock');
 let seconds=0;
 return {update(nowUs){if(!Number.isSafeInteger(nowUs)||nowUs<originUs)throw Error('Invalid host monotonic frame');const delta=Math.floor(nowUs/1000)-Math.floor(originUs/1000);if(delta>0xffffffff)throw Error('Clock interval exceeds checked source bound');const ticks=Math.min(0xffffffff,Math.max(0,Math.trunc(f(f(delta)*1))));seconds=f(f(ticks)*f(.001));return seconds;},value:()=>seconds};
}
export async function prepareDynamicWind(data,load){
 const p=data.sourceDynamicWind;if(!p)return;
 if(p.vertexBlockURL!=='/assets/source-map-dynamic-wind/wind-block.glsl'||!/^[a-f0-9]{64}$/.test(p.vertexBlockSHA256??''))throw Error('原摇动程序引用不匹配');
 const text=await load(p.vertexBlockURL),digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
 if([...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('')!==p.vertexBlockSHA256)throw Error('原摇动程序校验失败');
 p.vertexBlock=text;
}
export function validateDynamicWind(data,source,index){
 const p=data.sourceDynamicWind,effect=data.sceneAlpha?.materials?.[index]?.effectPath;
 if(!p){if(effect===EFFECT)throw Error('原动态摇动参数缺失');return false;}
 const r=p.materials?.[index],q=p.quality,c=p.clock;
 if(p.format!==DYNAMIC_WIND_FORMAT||p.effect!==EFFECT||p.fullOriginalFrameRestored!==false||
  data.source!=='model/scene/region_whitepike/wp_plant_pinetree001.bdae'||r?.index!==index||r.name!==source.name||typeof r.enabled!=='boolean'||r.enabled!==(effect===EFFECT)||
  q?.profile!=='APK_Default'||q.ShadersLevel!==2||q.qualityMask!==0||q.DCC_MAX!==false||q.actualDeviceObserved!==false||
  c?.initialBase!==0||c.initialPauseCount!==0||c.scale!==1||c.secondsScale!==f(.001)||c.hostOrigin!==true||
  p.matrix?.semantic!==87||p.matrix.operation!=='transpose-full-world-matrix'||p.matrix.nativeCPU!==true||p.matrix.hostMatrixSubmission!==true)throw Error('原动态摇动资料不匹配');
 if(!r.enabled)return false;
 if(!Number.isFinite(r.speed)||r.speed<=0||r.nativePropertyCopy?.value!==r.speed||r.nativePropertyCopy.nativeCPU!==true||r.nativePropertyCopy.resourceOrGPUCreated!==false||
  typeof p.vertexBlock!=='string'||!p.vertexBlock.includes('vert.xyz += t1 * t1 * wind_off;')||
  !Array.isArray(data.meshes)||!data.meshes.length||data.meshes.some(m=>m.sourceWindAttributes?.sourceSemantic!==6||m.sourceWindAttributes.runtimeSemantic!==3||m.sourceWindAttributes.type!==6||m.sourceWindAttributes.components!==2||!Array.isArray(m.sourceUV2)||m.sourceUV2.length!==m.positions.length/3*2||!m.sourceUV2.every(Number.isFinite)))throw Error('原动态摇动输入不完整');
 return true;
}
export function createBakedSceneMaterial(THREE,map,source,index,data,lighting){
 const active=validateDynamicWind(data,source,index);if(!data.sourceDynamicWind)return oldCreate(THREE,map,source,index,data,lighting);
 const m=baseCreate(THREE,map,source,index,data,lighting);if(!active)return m;
 const marker='vec4 view=modelViewMatrix*vec4(position,1.0);';if(m.vertexShader.split(marker).length!==2)throw Error('原顶点程序接口已变化');
 m.vertexShader='attribute mediump vec2 TexCoord2;\nuniform highp mat4 WorldT;\nuniform highp float time,shakeSpeed;\n'+m.vertexShader.replace(marker,'vec4 vert=vec4(position,1.0);\n'+data.sourceDynamicWind.vertexBlock+'vec4 view=modelViewMatrix*vert;');
 m.defines.VERTEX_ANIM=1;m.uniforms.WorldT={value:new THREE.Matrix4()};m.uniforms.time={value:0};m.uniforms.shakeSpeed={value:data.sourceDynamicWind.materials[index].speed};
 m.userData.sourceDynamicWind={format:DYNAMIC_WIND_FORMAT,speed:data.sourceDynamicWind.materials[index].speed,hostOrigin:true};return m;
}
export function bindDynamicWind(THREE,root,origin,clock,canvas){
 root.traverse(object=>{if(!object.isMesh)return;const list=Array.isArray(object.material)?object.material:[object.material];if(!list.some(m=>m.userData.sourceDynamicWind))return;
  // Source lightmap binding clones shader materials and rebuilds uniforms.
  for(const m of list)if(m.userData.sourceDynamicWind){m.uniforms.WorldT={value:new THREE.Matrix4()};m.uniforms.time={value:0};m.uniforms.shakeSpeed={value:m.userData.sourceDynamicWind.speed};}
  const before=object.onBeforeRender;object.onBeforeRender=function(renderer,scene,camera,geometry,material,group){
   before?.call(this,renderer,scene,camera,geometry,material,group);if(!material.userData.sourceDynamicWind)return;
   const matrix=material.uniforms.WorldT.value;matrix.copy(this.matrixWorld);matrix.elements[12]+=origin.x;matrix.elements[13]+=origin.y;matrix.elements[14]+=origin.z;matrix.transpose();
   material.uniforms.time.value=clock.value();material.uniformsNeedUpdate=true;
   const uv=geometry.getAttribute('TexCoord2');let max=0;for(let i=0;i<uv.count;i++)max=Math.max(max,uv.getY(i)**2);
   canvas.dataset.sourceDynamicWind=JSON.stringify({format:DYNAMIC_WIND_FORMAT,seconds:clock.value(),speed:material.uniforms.shakeSpeed.value,direction:matrix.elements.slice(0,3),maxUVSquared:max,phase:Math.sin(clock.value()*material.uniforms.shakeSpeed.value),hostClockOrigin:true,fullOriginalFrameRestored:false});
  };
 });return root;
}
