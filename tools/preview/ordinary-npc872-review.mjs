// Developer-only source asset review; no activity, identity or task state.
import * as THREE from './three.module.js';
import {loadNPC872Assets} from './source-ordinary-npc872.mjs';
import {finalPairMaterial} from './source-npc-final-pair-material.js';
const status=document.querySelector('#status'),qa=document.querySelector('#review-state');
try{
 const factory=await loadNPC872Assets(THREE),profile=factory.profile;
 const actor=factory.createNPC872({materialFactory:({THREE,record,textures,colors})=>finalPairMaterial(THREE,record,textures,colors,'source')});
 const canvas=document.querySelector('canvas'),renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const scene=new THREE.Scene();scene.background=new THREE.Color('#14191d');scene.add(actor.root);
 const camera=new THREE.PerspectiveCamera(38,1,.01,1000),center=new THREE.Vector3();let distance=3,height=1,yaw=0,frames=0,selected=0;
 function aim(){camera.position.set(center.x+Math.sin(yaw)*distance,center.y+height*.1,center.z+Math.cos(yaw)*distance);camera.lookAt(center);}
 function select(seconds){actor.sampleIdle(seconds);selected=seconds;
  const bounds=new THREE.Box3();for(const m of actor.meshes)if(m.visible)bounds.union(new THREE.Box3().setFromObject(m,true));bounds.getCenter(center);height=bounds.max.y-bounds.min.y;distance=height*1.75;aim();
  const d=actor.inspect();if(typeof profile.name!=='string')throw Error('Original localized name missing');status.textContent=`原NPC872 · ${profile.name}\n原默认部位 · ${d.visibleMeshIndices.length}可见网格 / 23原贴图\n原待机取样 ${seconds} 秒；没有活动身份或任务资格。`;
 }
 for(const t of[0,1.25,profile.idleDuration]){const b=document.createElement('button');b.textContent=`原待机 ${t} s`;b.onclick=()=>select(t);document.querySelector('#poses').append(b);}
 for(const[label,value]of[['正面',0],['侧面',Math.PI/2],['背面',Math.PI]]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{yaw=value;aim();};document.querySelector('#views').append(b);}
 const resize=()=>{renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();aim();};addEventListener('resize',resize);select(0);resize();
 const frame=()=>{renderer.render(scene,camera);frames++;if(frames%10===0)qa.textContent=JSON.stringify({ready:true,frames,selectedSeconds:selected,...actor.inspect(),sourceTextures:Object.keys(profile.textures).length,materialCount:actor.materials.filter(Boolean).length,calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,originalAndroidGPUObserved:false});requestAnimationFrame(frame);};requestAnimationFrame(frame);
}catch(error){status.textContent='原资源审阅失败：'+error.message;qa.textContent=JSON.stringify({ready:false,error:error.message});console.error(error);}
