// Original map7 static scene candidate. No camera, UI, light or new geometry.
// Lighting/viewport state must be supplied by the separately verified caller.
import {createSourceTerrain} from './terrain-materials-expanded.js?expansion=1';
import {sceneDiffuseTexture} from './scene-sampling.js';
import {createBakedSceneMaterial} from './source-wind-identity.js?sourceWind=1';
import {applySceneCulling,guardSceneOrientation} from './scene-culling.js';

export const SELECTION_SCENE_FORMAT='oc2-source-selection-scene-candidate-v1';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);

export function validateSelectionScene(p){
 if(p?.format!==SELECTION_SCENE_FORMAT||p.world!=='selection'||p.mapId!==7||p.profile!=='APK_Default'||
  p.inventedLights!==false||p.inventedGeometry!==false||p.savesChanged!==false||
  p.environment?.region?.ID!==211||p.environment.activeOriginalStateObserved!==false||
  p.conditionalWindow?.originalLiveCenterProven!==false||
  !Array.isArray(p.models)||!Array.isArray(p.bindings)||!p.textures)throw Error('原选角背景资料不匹配');
 const keys=new Set();
 for(const m of p.models){
  if(!/^model\/.+\.bdae$/.test(m.model)||!/^[a-f0-9]{64}$/.test(m.sourceSHA256)||
   !m.url?.startsWith('/assets/source-selection-scene/')||!m.instances?.length||!m.partToMaterial?.length)
   throw Error('原选角模型来源不完整');
  for(const i of m.instances){
   const key=[...i.tile,i.id].join(':');
   if(keys.has(key)||i.sourceType!==2||i.model!==m.model||!Number.isSafeInteger(i.id)||
    !finite(i.position,3)||!finite(i.quaternion,4)||!finite(i.scale,3)||i.scale.some(v=>v<=0))
    throw Error('原选角摆放记录不匹配');
   const rows=p.bindings.filter(r=>r.objectId===i.id&&r.model===i.model&&r.tile.join(',')===i.tile.join(','));
   if(rows.length!==1||!rows[0].recordPath.startsWith('world/selection/lightmap/')||!rows[0].bindings.length||
    rows[0].bindings.some((b,k)=>b.ordinal!==k||!b.atlas.startsWith('texture/lightmap/selection/')||!finite(b.uvTransform,4)||!p.textures[b.atlas]))
    throw Error('原选角图集绑定不完整');
   keys.add(key);
  }
 }
 return p;
}

export async function createSelectionScene(THREE,p,{origin,lighting,json,texture}){
 validateSelectionScene(p);
 if(!origin||![origin.x,origin.y,origin.z].every(Number.isFinite)||
  lighting?.sourceSelectionRegion!==211||!lighting.uniforms?.sourceModelLight||
  !lighting.uniforms.sourceTerrainLight||!lighting.uniforms.sourceFogColor||
  typeof json!=='function'||typeof texture!=='function')throw Error('原选角环境尚未核对接线');
 const root=new THREE.Group();root.name='source-selection-map7';
 const ownedGeometries=new Set(),ownedMaterials=new Set(),ownedTextures=new Set(),cache=new Map();
 async function load(url){
  if(!cache.has(url))cache.set(url,Promise.resolve(texture(url,THREE.NoColorSpace)).then(raw=>{
   const map=raw.clone();map.colorSpace=THREE.NoColorSpace;map.flipY=false;
   map.wrapS=map.wrapT=THREE.RepeatWrapping;map.needsUpdate=true;ownedTextures.add(map);return map;
  }));return cache.get(url);
 }
 function release(){
  root.removeFromParent();
  for(const g of ownedGeometries)g.dispose();for(const m of ownedMaterials)m.dispose();for(const t of ownedTextures)t.dispose();
 }
 try{
  const [terrain,materials,ground]=await Promise.all([p.terrain,p.terrainMaterials,p.terrainLighting].map(json));
  if(terrain.world!=='selection'||materials.world!=='selection'||ground.world!=='selection')throw Error('选角地形不能混用新手地图');
  const terrainMeshes=await createSourceTerrain(THREE,terrain,materials,origin,load,{profile:ground,context:lighting});
  for(const mesh of terrainMeshes){
   root.add(mesh);ownedGeometries.add(mesh.geometry);
   for(const m of mesh.material){
    ownedMaterials.add(m);
    for(const [name,u]of Object.entries(m.uniforms))if(/^terrain(?:Layer\d|Mask|LightMap)$/.test(name)&&u.value?.isTexture)ownedTextures.add(u.value);
   }
  }
  let instances=0,parts=0;
  for(const entry of p.models){
   const data=await json(entry.url);
   if(data.source!==entry.model||data.sourceSHA256!==entry.sourceSHA256||data.meshes?.length!==1||
    JSON.stringify(data.meshes[0].groups.map(g=>g.material))!==JSON.stringify(entry.partToMaterial))throw Error('选角原模型和部件不匹配');
   const source=data.meshes[0],geometry=new THREE.BufferGeometry();
   for(const [key,values,width]of [['position',source.positions,3],['normal',source.normals,3],['uv',source.uvs,2],['sourceUV1',source.sourceUV1,2]]){
    if(!finite(values,key==='uv'||key==='sourceUV1'?source.positions.length/3*2:source.positions.length))throw Error('原选角顶点流不完整');
    geometry.setAttribute(key,new THREE.Float32BufferAttribute(values,width));
   }
   geometry.setIndex(source.indices);for(const g of source.groups)geometry.addGroup(g.start,g.count,g.material);
   geometry.computeBoundingSphere();ownedGeometries.add(geometry);
   const diffuse=await Promise.all(data.materials.map(async(m,k)=>{
    const map=sceneDiffuseTexture(THREE,await load(p.textures[m.diffuse]?.url),m,k,data.sceneSampling);
    map.colorSpace=THREE.NoColorSpace;map.flipY=false;map.needsUpdate=true;ownedTextures.add(map);return map;
   }));
   for(const instance of entry.instances){
    const bindings=p.bindings.find(r=>r.objectId===instance.id&&r.model===instance.model&&r.tile.join(',')===instance.tile.join(',')).bindings;
    const mats=[];
    for(const [part,index]of entry.partToMaterial.entries()){
     const b=bindings[part]||bindings[0],sourceMaterial=data.materials[index];
     const material=applySceneCulling(THREE,createBakedSceneMaterial(THREE,diffuse[index],sourceMaterial,index,data,lighting),sourceMaterial,index,data.sceneCulling);
     material.uniforms.sourceAtlas={value:await load(p.textures[b.atlas].url)};
     material.uniforms.sourceUVTransform={value:new THREE.Vector4(...b.uvTransform)};
     ownedMaterials.add(material);mats[index]=material;parts++;
    }
    const mesh=new THREE.Mesh(geometry,mats),container=new THREE.Group();
    if(!finite(source.sourceNodeTransform?.matrix,16))throw Error('选角原节点矩阵缺失');
    mesh.matrix.fromArray(source.sourceNodeTransform.matrix);mesh.matrixAutoUpdate=false;mesh.matrixWorldNeedsUpdate=true;
    container.position.set(instance.position[0]-origin.x,instance.position[1]-origin.y,instance.position[2]-origin.z);
    container.quaternion.fromArray(instance.quaternion);container.scale.fromArray(instance.scale);
    container.add(mesh);container.userData.sourceSelectionInstance={id:instance.id,tile:instance.tile,model:instance.model};
    root.add(container);guardSceneOrientation(container);instances++;
   }
  }
  root.updateMatrixWorld(true);
  return {root,instances,parts,tiles:terrainMeshes.length,dispose:release,
   pending:{models:p.gaps,effects:p.pendingEffects,water:p.pendingWaterChunks,sky:p.environment.skyNotRestored},
   originalFinalFrameRestored:false};
 }catch(error){release();throw error;}
}
