import{validateFlag,paletteAt,deform,createFlagClock,FLAG_FORMAT}from'./flag-motion-math.js';
// CPU deformation is the browser graphics interface. Literal weights/inverses
// and source-model coordinates are preserved; ITM is applied once by the scene.
export function prepareFlagModel(root,data){
 if(!data.sourceFlagMotion)return;
 const p=validateFlag(data.sourceFlagMotion),meshes=[];root.traverse(o=>{if(o.isMesh)meshes.push(o);});
 if(meshes.length!==1||data.meshes.length!==1||meshes[0].geometry.getAttribute('position').count!==p.weights.length)throw Error('原旗面顶点绑定不匹配');
 root.userData.sourceFlagMotion={format:FLAG_FORMAT};root.userData.flagMotionData=p;
}
export function bindFlagInstance(root,instance,canvas,registry,now){
 if(!root.userData.sourceFlagMotion)return;
 const p=validateFlag(root.userData.flagMotionData),list=[];
 root.traverse(o=>{if(o.isMesh){o.geometry=o.geometry.clone();o.castShadow=false;list.push({mesh:o,positions:o.geometry.getAttribute('position').array.slice()});}});
 const c={clock:createFlagClock(),previous:now,list,p,instance};registry.push(c);
 const prior=list[0].mesh.onBeforeRender;
 list[0].mesh.onBeforeRender=function(...args){prior?.apply(this,args);canvas.dataset.sourceFlagDraw=JSON.stringify({id:instance.id,tile:instance.tile,timeMs:c.clock.value(),bones:p.bones.length,hostCPUDeformation:true,originalGPUObserved:false});};
}
export function updateFlags(registry,now,canvas){
 for(const c of registry){const dt=Math.max(0,Math.floor(now)-Math.floor(c.previous));c.previous=now;const t=c.clock.tick(dt),matrices=paletteAt(c.p,t);
  for(const r of c.list){const a=r.mesh.geometry.getAttribute('position');deform(c.p,r.positions,matrices,a.array);a.needsUpdate=true;r.mesh.geometry.computeBoundingSphere();}
 }
 if(registry.length)canvas.dataset.sourceFlagMotion=JSON.stringify({instances:registry.length,timeMs:registry[0].clock.value(),loop:true,hostClockOrigin:true,originalGPUObserved:false});
}
