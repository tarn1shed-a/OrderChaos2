// Original638 full source keys and fresh clock in an independent review frame.
import * as THREE from './three.module.js';
import {weaponReviewMaterial} from './source-npc-weapon-material.js';
import {create638ClipSampler,create638FreshClock} from './ordinary_638_animation_complete.mjs';
const json=async path=>{const r=await fetch(path);if(!r.ok)throw Error('Missing original review input '+path);return r.json();};
const status=document.querySelector('#status'),qa=document.querySelector('#review-state');
try{
 const [profile,data,rig,animation]=await Promise.all(['profile.json','model.json','rig.json','complete-animation.json'].map(json));
 if(profile.format!=='oc2-original-crocodile-animated-material-review-v1')throw Error('Verified complete original638 profile required');
 const canvas=document.querySelector('canvas'),renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
 renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=THREE.LinearSRGBColorSpace;renderer.toneMapping=THREE.NoToneMapping;
 const scene=new THREE.Scene();scene.background=new THREE.Color('#14191d');const root=new THREE.Group();scene.add(root);
 const camera=new THREE.PerspectiveCamera(38,1,.01,1000),loader=new THREE.TextureLoader(),textures=new Map();
 await Promise.all(Object.entries(profile.textures).map(async([url,row])=>{const t=await loader.loadAsync(url);if(t.image.width!==row.size[0]||t.image.height!==row.size[1])throw Error('Original source texture size differs');t.flipY=false;t.colorSpace=THREE.NoColorSpace;t.needsUpdate=true;textures.set(url,t);}));
 const material=weaponReviewMaterial(THREE,profile.material,textures,{skin:[1,1,1],hair:[1,1,1]},'source');
 const nodes=rig.nodes.map((n,i)=>{const b=new THREE.Bone();b.name='source638_'+i;b.position.fromArray(n.position);b.quaternion.fromArray(n.quaternion);b.scale.fromArray(n.scale);return b;});
 const byName=new Map();rig.nodes.forEach((n,i)=>{for(const name of[n.name,...n.aliases])byName.set(name,i);(n.parent<0?root:nodes[n.parent]).add(nodes[i]);});
 const source=data.meshes[0],skin=rig.skins[0],g=new THREE.BufferGeometry();
 for(const[name,key,width]of[['position','positions',3],['normal','normals',3],['uv','uvs',2],['sourceTangent','sourceTangents',3],['sourceBinormal','sourceBinormals',3]]){if(!source[key])throw Error('Original stream absent');g.setAttribute(name,new THREE.Float32BufferAttribute(source[key],width));}
 g.setIndex(source.indices);for(const group of source.groups)g.addGroup(group.start,group.count,group.material);
 g.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skin.skinIndices,4));g.setAttribute('skinWeight',new THREE.Float32BufferAttribute(skin.skinWeights,4));
 const mesh=new THREE.SkinnedMesh(g,[material]);mesh.bind(new THREE.Skeleton(skin.boneNodes.map(i=>nodes[i]),skin.inverseBindMatrices.map(m=>new THREE.Matrix4().fromArray(m))),new THREE.Matrix4());mesh.frustumCulled=false;root.add(mesh);
 let name,sampler,clock,current,start,end,frames=0,loops=0,lastSample=null,view='side';
 const center=new THREE.Vector3();let distance=7,height=1;
 function pose(ms){lastSample=sampler.sampleAbsolute(ms);for(const sample of lastSample.samples){const node=nodes[byName.get(sample.node)];if(!node)throw Error('Original target absent');if(sample.type==='position')node.position.fromArray(sample.value);else if(sample.type==='quaternion')node.quaternion.fromArray(sample.value);else throw Error('Unexpected source property');}root.updateMatrixWorld(true);mesh.skeleton.update();}
 function aim(){if(view==='side')camera.position.set(center.x+distance,center.y+height*.55,center.z+distance*.15);else camera.position.set(center.x,center.y+height*.5,center.z+distance);camera.lookAt(center);}
 let last=performance.now();
 function select(key){const clip=animation.clips.find(c=>c.name===key);if(!clip)throw Error('Original action missing');name=key;sampler=create638ClipSampler(animation,key);clock=create638FreshClock(clip);start=clip.startMs;end=clip.endMs;current=start;loops=0;pose(start);
  const bounds=new THREE.Box3().setFromObject(mesh,true);bounds.getCenter(center);height=bounds.max.y-bounds.min.y;distance=Math.max(bounds.max.x-bounds.min.x,bounds.max.z-bounds.min.z,height)*1.65;aim();last=performance.now();
  status.textContent=`原鳄鱼638 · ${key==='idle'?'原待机':'原行走'} ${start}～${end} ms\n44原轨道 / 27骨 / 6原贴图\n保留原重复关键时间及缓存；没有活动身份或战斗状态。`;
 }
 for(const[label,key]of[['播放原待机','idle'],['播放原行走','walk_forward']]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>select(key);document.querySelector('#poses').append(b);}
 for(const[label,key]of[['侧面','side'],['正面','front']]){const b=document.createElement('button');b.textContent=label;b.onclick=()=>{view=key;aim();};document.querySelector('#views').append(b);}
 const resize=()=>{renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();aim();};addEventListener('resize',resize);select('idle');resize();
 const frame=now=>{try{const delta=Math.max(0,now-last);last=now;const tick=clock.tick(delta);current=tick.absoluteMs;if(tick.crossedEnd)loops++;pose(current);renderer.render(scene,camera);frames++;
  if(frames%10===0)qa.textContent=JSON.stringify({ready:true,frames,clip:name,sourceMs:current,sourceRange:[start,end],loops,tracks:lastSample.samples.length,rootPosition:lastSample.samples.find(s=>s.node==='Bip01-node'&&s.type==='position')?.value,calls:renderer.info.render.calls,triangles:renderer.info.render.triangles,bones:27,vertices:1266,worldActorCreated:false,clockAndCacheAdapter:'original638-verified',ordinaryThreeKeyframeUsed:false});requestAnimationFrame(frame);
 }catch(error){status.textContent='原动画审阅失败：'+error.message;qa.textContent=JSON.stringify({ready:false,error:error.message});console.error(error);}};requestAnimationFrame(frame);
}catch(error){status.textContent='原资源审阅失败：'+error.message;qa.textContent=JSON.stringify({ready:false,error:error.message});console.error(error);}
