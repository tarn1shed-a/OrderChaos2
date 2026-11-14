// Private development acceptance only. No identity API, save or game UI.
import * as THREE from '/human-male/three.module.js';
import * as world from '/world-runtime/source-locomotion-blending.js';
import {createNPCMaterial} from '/human-male/source-npc-material.js';
import * as human from './character_world_motion_avatar.mjs';
import * as elf from './character_elf_male_world_avatar.mjs';
import {createSpeciesMotionBinding} from './species_world_motion.mjs';

const json=url=>fetch(url).then(r=>{if(!r.ok)throw Error('Private reviewed input unavailable');return r.json();});
const [profiles,report]=await Promise.all(['/profiles-v1.json','/native-roundtrip-v1.json'].map(json));
const canvas=document.querySelector('canvas'),renderer=new THREE.WebGLRenderer({canvas,antialias:true});
renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;renderer.setPixelRatio(1);
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(38,1,.01,1000),loader=new THREE.TextureLoader(),actors=[];
for(const[key,profile]of Object.entries(profiles)){
 const base='/'+key+'/',manifest=await json(base+'manifest.json'),data=await json(base+manifest.model.replace(/^\//,'')),textures=new Map();
 await Promise.all([...new Set(manifest.materials.flatMap(m=>Object.values(m.samplers)))].map(async url=>{
  const t=await loader.loadAsync(base+url.replace(/^\//,''));t.flipY=false;t.colorSpace=THREE.NoColorSpace;textures.set(url,t);
 }));
 const materials=Array(data.materials.length),owned=[];
 for(const entry of manifest.materials){
  const maps=new Map();for(const[slot,url]of Object.entries(entry.samplers)){
   const t=textures.get(url).clone(),a=entry.addressing[slot];
   t.wrapS=human.sourceHumanMotionWrap(THREE,a.addressU);t.wrapT=human.sourceHumanMotionWrap(THREE,a.addressV);t.needsUpdate=true;maps.set(url,t);owned.push(t);
  }
  materials[entry.index]=createNPCMaterial(THREE,entry,maps,manifest.colors);
 }
 const make=key==='elf-male'?elf.createElfMaleWorldFactory:human.createSourceHumanMotionFactory;
 const sample=key==='elf-male'?elf.sampleElfMaleWorldPose:human.sampleSourceHumanMotion;
 const root=make({THREE,manifest,data,materials,createCharacterFactory:world.createCharacterFactory})();
 root.position.x=(actors.length-1)*2;scene.add(root);
 const binding=createSpeciesMotionBinding({profile,clips:data.clips,sample,root});
 actors.push({key,root,binding,materials,textures,owned,sourceModelId:profile.sourceModelId});
}
const bounds=new THREE.Box3().setFromObject(scene),center=bounds.getCenter(new THREE.Vector3());
camera.position.set(center.x,center.y+.5,9);camera.lookAt(center);
function resize(){renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();}addEventListener('resize',resize);resize();
let elapsed=0,previous=performance.now(),playing=true,mode='play',frames=0;
const controls={play:document.querySelector('#play'),stop:document.querySelector('#stop'),resume:document.querySelector('#resume')};
controls.play.onclick=()=>{playing=!playing;mode=playing?'play':'pause';controls.play.textContent=playing?'暂停重放':'继续重放';};
controls.stop.onclick=()=>{elapsed=24*50+750;playing=false;mode='stop-difference';controls.play.textContent='继续重放';};
controls.resume.onclick=()=>{elapsed=63*50;playing=false;mode='resume';controls.play.textContent='继续重放';};
for(const button of Object.values(controls))button.disabled=false;
const proof=document.createElement('script');proof.type='application/json';proof.id='species-motion-review';document.body.append(proof);
function render(now){
 if(playing)elapsed=(elapsed+Math.max(0,Math.min(now-previous,100)))%(report.framesPerActor*50);previous=now;
 const index=Math.min(report.framesPerActor-1,Math.floor(elapsed/50)),offset=elapsed-index*50;
 for(const a of actors){const packet=report.frames[a.key][index];
  // A recording loop is a new host replay, so monotonic transport time remains
  // independent from the recorded native age. No action time is stretched.
  a.binding.sync(packet,now);world.updateCharacterAnimation(a.root,0,{moving:false},now);a.binding.update(now+offset);
 }
 renderer.render(scene,camera);frames++;
 document.querySelector('#status').textContent=actors.map(a=>a.key+'：'+a.binding.state.lastPose.map(p=>p.clip+' '+p.timeSeconds.toFixed(3)+'s').join(' + ')).join('\n');
 proof.textContent=JSON.stringify({frames,index,mode,calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,
  actors:actors.map(a=>({key:a.key,sourceModelId:a.sourceModelId,state:a.binding.state})),originalRecordedCPU:true,gameEntryChanged:false});
 requestAnimationFrame(render);
}requestAnimationFrame(render);
