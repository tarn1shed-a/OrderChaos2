import * as THREE from './three.module.js';
import {createNPCMaterial} from './source-npc-material.js';

const canvas=document.querySelector('canvas'),status=document.querySelector('#status');
const manifest=await fetch('/manifest.json').then(r=>r.json());
if(manifest.format!=='oc2-tutorial-npc750-source-candidate-v1'||manifest.liveActor!==false)throw Error('Unverified NPC candidate');
const data=await fetch(manifest.model).then(r=>r.json());
const loader=new THREE.TextureLoader(),textures=new Map();
await Promise.all([...new Set(manifest.materials.flatMap(m=>Object.values(m.samplers)))].map(async url=>{
  const texture=await loader.loadAsync(url);texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;texture.needsUpdate=true;textures.set(url,texture);
}));
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
const scene=new THREE.Scene();scene.background=new THREE.Color('#14191d');
const root=new THREE.Group();scene.add(root);
const materials=manifest.materials.map(m=>createNPCMaterial(THREE,m,textures,manifest.colors));
const nodes=data.rig.nodes.map((node,index)=>{
  const bone=new THREE.Bone();bone.name='node_'+index;bone.position.fromArray(node.position);bone.quaternion.fromArray(node.quaternion);bone.scale.fromArray(node.scale);return bone;
});
data.rig.nodes.forEach((node,index)=>{if(node.parent<0)root.add(nodes[index]);else nodes[node.parent].add(nodes[index]);});
const skinByMesh=new Map(data.rig.skins.map(s=>[s.mesh,s]));
const meshes=data.meshes.map((mesh,index)=>{
  if(!mesh.sourceTangents||!mesh.sourceBinormals)throw Error('Source NPC tangent basis missing');
  const geometry=new THREE.BufferGeometry();
  for(const [name,values,width]of [['position',mesh.positions,3],['normal',mesh.normals,3],['uv',mesh.uvs,2],
    ['sourceTangent',mesh.sourceTangents,3],['sourceBinormal',mesh.sourceBinormals,3]])geometry.setAttribute(name,new THREE.Float32BufferAttribute(values,width));
  geometry.setIndex(mesh.indices);for(const group of mesh.groups)geometry.addGroup(group.start,group.count,group.material);
  const skin=skinByMesh.get(index);let object;
  if(skin){
    geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skin.skinIndices,4));geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(skin.skinWeights,4));
    object=new THREE.SkinnedMesh(geometry,materials);const skeleton=new THREE.Skeleton(skin.boneNodes.map(i=>nodes[i]),skin.inverseBindMatrices.map(m=>new THREE.Matrix4().fromArray(m)));
    object.bind(skeleton,new THREE.Matrix4());object.frustumCulled=false;
  }else object=new THREE.Mesh(geometry,materials);
  object.name=mesh.name;object.visible=manifest.visibleMeshIndices.includes(index);root.add(object);return object;
});
root.updateMatrixWorld(true);
const clips=data.clips.map(clip=>new THREE.AnimationClip(clip.name,clip.duration,clip.tracks.map(track=>{
  const name=`node_${track.node}.${track.type}`;return track.type==='quaternion'?new THREE.QuaternionKeyframeTrack(name,track.times,track.values):new THREE.VectorKeyframeTrack(name,track.times,track.values);
})));
if(clips.length!==1||clips[0].name!=='idle'||clips[0].duration!==4)throw Error('Original idle range differs');
const mixer=new THREE.AnimationMixer(root),idle=mixer.clipAction(clips[0]);idle.play();mixer.update(0);
const bounds=new THREE.Box3();for(const mesh of meshes)if(mesh.visible)bounds.union(new THREE.Box3().setFromObject(mesh,true));
const center=bounds.getCenter(new THREE.Vector3()),height=bounds.max.y-bounds.min.y;
const target=center.clone(),camera=new THREE.PerspectiveCamera(38,1,.01,1000);let yaw=.45,pitch=.08,distance=height*2.05;
const cameraUpdate=()=>{camera.position.set(target.x+distance*Math.sin(yaw)*Math.cos(pitch),target.y+distance*Math.sin(pitch),target.z+distance*Math.cos(yaw)*Math.cos(pitch));camera.lookAt(target);};
const resize=()=>{renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();cameraUpdate();};
addEventListener('resize',resize);resize();let dragging=false,lastX=0,lastY=0;
canvas.addEventListener('pointerdown',e=>{dragging=true;lastX=e.clientX;lastY=e.clientY;canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointerup',()=>{dragging=false;});
canvas.addEventListener('pointermove',e=>{if(!dragging)return;yaw-=(e.clientX-lastX)*.008;pitch=Math.max(-.8,Math.min(.8,pitch+(e.clientY-lastY)*.006));lastX=e.clientX;lastY=e.clientY;cameraUpdate();});
canvas.addEventListener('wheel',e=>{e.preventDefault();distance=Math.max(height*.7,Math.min(height*5,distance*Math.exp(e.deltaY*.001)));cameraUpdate();},{passive:false});
document.querySelector('h1').textContent=manifest.name+' · 750';
status.textContent='原模型、部件、骨骼与 4 秒 idle\n原部位计数规则决定显示集合\n\n仅核查默认外观分支；实际活动消息、任务状态及武器姿态仍未闭合。';
let frames=0,last=performance.now();
const qa=document.createElement('script');qa.id='npc-review-state';qa.type='application/json';document.body.append(qa);
const reviewState=()=>({format:manifest.format,entry:750,frames,animationTime:idle.time,idleDuration:clips[0].duration,
  visibleMeshIndices:meshes.flatMap((m,i)=>m.visible?[i]:[]),meshCount:meshes.length,nodeCount:nodes.length,height,
  worldPlacement:null,runtimeGUID:null,liveActor:false,questAvailability:null,
  canvas:[canvas.width,canvas.height],boneSample:nodes.slice(0,24).map((b,i)=>({i,p:b.position.toArray(),q:b.quaternion.toArray()})),
  renderer:{calls:renderer.info.render.calls,triangles:renderer.info.render.triangles}});
const frame=now=>{mixer.update(Math.min((now-last)/1000,.1));last=now;root.updateMatrixWorld(true);renderer.render(scene,camera);frames++;if(frames%10===0)qa.textContent=JSON.stringify(reviewState());requestAnimationFrame(frame);};
requestAnimationFrame(frame);
