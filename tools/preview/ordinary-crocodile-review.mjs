// Independent original-resource review. Finite source CPU poses only;
// camera/light are the existing review settings, never a game actor or frame.
import * as THREE from './three.module.js';
import {weaponReviewMaterial} from './source-npc-weapon-material.js';
const json=async path=>{const r=await fetch(path);if(!r.ok)throw Error('Missing review input '+path);return r.json();};
const report=document.querySelector('#status'),qa=document.querySelector('#review-state');
try{
 const [profile,data,rig,finite]=await Promise.all(['profile.json','model.json','rig.json','finite-poses.json'].map(json));
 if(profile.format!=='oc2-original-crocodile-finite-material-review-v1'||finite.newContinuousClipOrTimingRule!==false)throw Error('Original finite source profile required');
 const canvas=document.querySelector('canvas'),renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const scene=new THREE.Scene();scene.background=new THREE.Color('#14191d');
 const camera=new THREE.PerspectiveCamera(38,1,.01,1000),root=new THREE.Group();scene.add(root);
 const textureLoader=new THREE.TextureLoader(),textures=new Map();
 await Promise.all(Object.entries(profile.textures).map(async([url,row])=>{
  const t=await textureLoader.loadAsync(url);if(t.image.width!==row.size[0]||t.image.height!==row.size[1])throw Error('Original texture dimensions differ');
  t.flipY=false;t.colorSpace=THREE.NoColorSpace;t.needsUpdate=true;textures.set(url,t);
 }));
 // The source crocodile effect has no SKIN_COLOR define. These required host
 // uniform slots are unused by that source branch, not new cosmetic colors.
 const material=weaponReviewMaterial(THREE,profile.material,textures,{skin:[1,1,1],hair:[1,1,1]},'source');
 const nodes=rig.nodes.map((n,i)=>{const b=new THREE.Bone();b.name='croc_source_'+i;b.position.fromArray(n.position);b.quaternion.fromArray(n.quaternion);b.scale.fromArray(n.scale);return b;});
 rig.nodes.forEach((n,i)=>{if(n.parent<0)root.add(nodes[i]);else nodes[n.parent].add(nodes[i]);});
 const byName=new Map();rig.nodes.forEach((n,i)=>{for(const key of[n.name,...n.aliases])byName.set(key,i);});
 const source=data.meshes[0],skin=rig.skins[0],geometry=new THREE.BufferGeometry();
 for(const[name,key,width]of[['position','positions',3],['normal','normals',3],['uv','uvs',2],['sourceTangent','sourceTangents',3],['sourceBinormal','sourceBinormals',3]]){
  if(!source[key])throw Error('Original stream missing '+key);geometry.setAttribute(name,new THREE.Float32BufferAttribute(source[key],width));
 }
 geometry.setIndex(source.indices);for(const g of source.groups)geometry.addGroup(g.start,g.count,g.material);
 geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skin.skinIndices,4));geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(skin.skinWeights,4));
 const mesh=new THREE.SkinnedMesh(geometry,[material]);mesh.name=source.name;
 mesh.bind(new THREE.Skeleton(skin.boneNodes.map(i=>nodes[i]),skin.inverseBindMatrices.map(m=>new THREE.Matrix4().fromArray(m))),new THREE.Matrix4());mesh.frustumCulled=false;root.add(mesh);
 let selected=0,angle='side',frames=0,maximumVertexError=0,maximumPaletteError=0;
 const center=new THREE.Vector3();let height=1,distance=3;
 function cameraUpdate(){if(angle==='front')camera.position.set(center.x,center.y+height*.5,center.z+distance);else camera.position.set(center.x+distance,center.y+height*.55,center.z+distance*.15);camera.lookAt(center);}
 function choose(index){
  const pose=finite.poses[index];if(!pose)throw Error('Unknown original finite pose');selected=index;
  rig.nodes.forEach((n,i)=>{nodes[i].position.fromArray(n.position);nodes[i].quaternion.fromArray(n.quaternion);nodes[i].scale.fromArray(n.scale);});
  for(const s of pose.originalSamples){const node=nodes[byName.get(s.node)];if(!node)throw Error('Original target node absent');
   if(s.type===1)node.position.fromArray(s.value);else if(s.type===5)node.quaternion.fromArray(s.value);else throw Error('Uncovered original property');
  }
  root.updateMatrixWorld(true);mesh.skeleton.update();
  maximumPaletteError=0;for(let i=0;i<pose.originalPalette.length;i++)for(let j=0;j<16;j++)maximumPaletteError=Math.max(maximumPaletteError,Math.abs(mesh.skeleton.boneMatrices[i*16+j]-pose.originalPalette[i][j]));
  maximumVertexError=0;const v=new THREE.Vector3();for(let i=0;i<source.vertexCount;i++){mesh.getVertexPosition(i,v);for(let k=0;k<3;k++)maximumVertexError=Math.max(maximumVertexError,Math.abs(v.getComponent(k)-pose.originalPositionOnlyVertices[i*3+k]));}
  if(maximumPaletteError>.002||maximumVertexError>.002)throw Error('Three source rig differs from original CPU positions');
  const bounds=new THREE.Box3().setFromObject(mesh,true);bounds.getCenter(center);height=bounds.max.y-bounds.min.y;distance=Math.max(bounds.max.x-bounds.min.x,bounds.max.z-bounds.min.z,height)*1.65;cameraUpdate();
  report.textContent=`原鳄鱼638 · 原时刻 ${pose.absoluteMs} ms\n27骨 / 1266顶点 · 原位置最大差 ${maximumVertexError.toExponential(2)}\n独立资源审阅；不是活动NPC或完整任务。`;
 }
 for(const[at,pose]of finite.poses.entries()){
  const b=document.createElement('button');b.textContent=`原待机 ${pose.absoluteMs} ms`;b.onclick=()=>choose(at);document.querySelector('#poses').append(b);
 }
 for(const key of['side','front']){const b=document.createElement('button');b.textContent=key==='side'?'侧面':'正面';b.onclick=()=>{angle=key;cameraUpdate();};document.querySelector('#views').append(b);}
 const resize=()=>{renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();cameraUpdate();};
 addEventListener('resize',resize);choose(0);resize();
 const frame=()=>{renderer.render(scene,camera);frames++;if(frames%10===0)qa.textContent=JSON.stringify({ready:true,entry:638,frames,selectedPose:finite.poses[selected].absoluteMs,view:angle,nodes:nodes.length,bones:27,vertices:source.vertexCount,maximumPaletteError,maximumVertexError,calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,sourceTextures:Object.keys(profile.textures).length,worldActorCreated:false,continuousAnimationInvented:false});requestAnimationFrame(frame);};requestAnimationFrame(frame);
}catch(error){report.textContent='资源审阅失败：'+error.message;qa.textContent=JSON.stringify({ready:false,error:error.message});console.error(error);}
