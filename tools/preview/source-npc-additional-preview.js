import * as THREE from './three.module.js';
import {createNPCMaterial} from './source-npc-material.js';

const manifest=await fetch('/manifest.json').then(r=>r.json());
if(manifest.format!=='oc2-tutorial-npc-additional-candidate-v1'||manifest.liveActor!==false)throw Error('Unverified additional NPC candidate');
const canvas=document.querySelector('canvas'),status=document.querySelector('#status');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
const scene=new THREE.Scene();scene.background=new THREE.Color('#14191d');
const camera=new THREE.PerspectiveCamera(38,1,.01,1000),loader=new THREE.TextureLoader(),textures=new Map();
await Promise.all([...new Set(manifest.entries.flatMap(e=>e.materials.flatMap(m=>Object.values(m.samplers))))].map(async url=>{
  const texture=await loader.loadAsync(url);texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;texture.needsUpdate=true;textures.set(url,texture);
}));
const candidates=[];
for(const entry of manifest.entries){
  const data=await fetch(entry.model).then(r=>r.json());
  const root=new THREE.Group();scene.add(root);root.visible=false;
  const nodes=data.rig.nodes.map((node,index)=>{
    const bone=new THREE.Bone();bone.name='node_'+index;bone.position.fromArray(node.position);bone.quaternion.fromArray(node.quaternion);bone.scale.fromArray(node.scale);return bone;
  });
  data.rig.nodes.forEach((n,i)=>{if(n.parent<0)root.add(nodes[i]);else nodes[n.parent].add(nodes[i]);});
  const materials=entry.materials.map(m=>createNPCMaterial(THREE,m,textures,manifest.colors));
  const skinByMesh=new Map(data.rig.skins.map(s=>[s.mesh,s]));
  const meshes=data.meshes.map((mesh,index)=>{
    const geometry=new THREE.BufferGeometry();
    for(const [name,values,width]of [['position',mesh.positions,3],['normal',mesh.normals,3],['uv',mesh.uvs,2],
      ['sourceTangent',mesh.sourceTangents,3],['sourceBinormal',mesh.sourceBinormals,3]]){
      if(!values)throw Error('Original source stream missing: '+name);
      geometry.setAttribute(name,new THREE.Float32BufferAttribute(values,width));
    }
    geometry.setIndex(mesh.indices);for(const group of mesh.groups)geometry.addGroup(group.start,group.count,group.material);
    const skin=skinByMesh.get(index);if(!skin)throw Error('Original source mesh skin missing');
    geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skin.skinIndices,4));geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(skin.skinWeights,4));
    const object=new THREE.SkinnedMesh(geometry,materials);
    object.bind(new THREE.Skeleton(skin.boneNodes.map(i=>nodes[i]),skin.inverseBindMatrices.map(m=>new THREE.Matrix4().fromArray(m))),new THREE.Matrix4());
    object.frustumCulled=false;object.name=mesh.name;object.visible=entry.visibleMeshIndices.includes(index);root.add(object);return object;
  });
  const clips=data.clips.map(c=>new THREE.AnimationClip(c.name,c.duration,c.tracks.map(t=>{
    const name=`node_${t.node}.${t.type}`;return t.type==='quaternion'?new THREE.QuaternionKeyframeTrack(name,t.times,t.values):new THREE.VectorKeyframeTrack(name,t.times,t.values);
  })));
  if(clips.length!==1||clips[0].name!=='idle'||clips[0].duration!==entry.idleDuration)throw Error('Original idle duration differs');
  const mixer=new THREE.AnimationMixer(root),idle=mixer.clipAction(clips[0]);idle.play();mixer.update(0);root.updateMatrixWorld(true);
  const bounds=new THREE.Box3();for(const mesh of meshes)if(mesh.visible)bounds.union(new THREE.Box3().setFromObject(mesh,true));
  candidates.push({entry,data,root,nodes,meshes,mixer,idle,center:bounds.getCenter(new THREE.Vector3()),height:bounds.max.y-bounds.min.y});
}
let current,yaw=.4,pitch=.06,distance=1,frames=0;
const cameraUpdate=()=>{if(!current)return;const p=current.center;camera.position.set(p.x+distance*Math.sin(yaw)*Math.cos(pitch),p.y+distance*Math.sin(pitch),p.z+distance*Math.cos(yaw)*Math.cos(pitch));camera.lookAt(p);};
function select(entry){
  current=candidates.find(c=>c.entry.entry===entry);if(!current)throw Error('Unknown source candidate');
  for(const c of candidates)c.root.visible=c===current;
  yaw=.4;pitch=.06;distance=current.height*2.05;cameraUpdate();
  document.querySelector('h1').textContent=current.entry.name+' · '+entry;
  status.textContent=`原单体模型与骨骼 · 原 idle ${current.entry.idleDuration} 秒\n`+
    (current.entry.weapon?'原武器资源与请求已核，未补挂接姿态。\n':'原 extra=0；没有补配装备。\n')+
    '\n独立默认外观审阅；原活动出现、GUID、世界变换与任务状态仍未知。';
  for(const b of document.querySelectorAll('#choices button'))b.setAttribute('aria-pressed',String(Number(b.dataset.entry)===entry));
}
for(const c of candidates){const b=document.createElement('button');b.textContent=String(c.entry.entry)+' '+c.entry.name;b.dataset.entry=String(c.entry.entry);b.onclick=()=>select(c.entry.entry);document.querySelector('#choices').append(b);}
select(candidates[0].entry.entry);
const resize=()=>{renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();cameraUpdate();};
addEventListener('resize',resize);resize();let dragging=false,x=0,y=0;
canvas.addEventListener('pointerdown',e=>{dragging=true;x=e.clientX;y=e.clientY;canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointerup',()=>{dragging=false;});
canvas.addEventListener('pointermove',e=>{if(!dragging)return;yaw-=(e.clientX-x)*.008;pitch=Math.max(-.8,Math.min(.8,pitch+(e.clientY-y)*.006));x=e.clientX;y=e.clientY;cameraUpdate();});
canvas.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(current.height*.7,Math.min(current.height*5,distance*Math.exp(e.deltaY*.001)));cameraUpdate();},{passive:false});
const qa=document.createElement('script');qa.type='application/json';qa.id='npc-additional-review-state';document.body.append(qa);
const state=()=>({format:manifest.format,entry:current.entry.entry,frames,idleDuration:current.entry.idleDuration,
  animationTime:current.idle.time,visibleMeshIndices:current.meshes.flatMap((m,i)=>m.visible?[i]:[]),nodeCount:current.nodes.length,
  renderer:{calls:renderer.info.render.calls,triangles:renderer.info.render.triangles},canvas:[canvas.width,canvas.height],
  boneSample:current.nodes.slice(0,24).map((b,i)=>({i,p:b.position.toArray(),q:b.quaternion.toArray()})),
  liveActor:false,runtimeGUID:null,worldPlacement:null,questAvailability:null,weaponMounted:false});
let last=performance.now();
const frame=now=>{const dt=Math.min((now-last)/1000,.1);last=now;for(const c of candidates){c.mixer.update(dt);c.root.updateMatrixWorld(true);}renderer.render(scene,camera);frames++;if(frames%10===0)qa.textContent=JSON.stringify(state());requestAnimationFrame(frame);};
requestAnimationFrame(frame);
