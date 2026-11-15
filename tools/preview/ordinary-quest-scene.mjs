// Original dawnwatch/map1 geometry for the explicitly labelled ordinary-quest
// compatibility world. No new terrain, lamps, saved positions or quest rules.
import {tileGeometry} from './terrain-materials-expanded.js?expansion=1';
import {createLitTerrainMaterial} from './terrain-lighting-window.js?geometry=2';
import {sceneDiffuseTexture} from './scene-sampling.js';
import {createBakedSceneMaterial} from './source-wind-identity.js?sourceWind=1';
import {applySceneCulling,guardSceneOrientation} from './scene-culling.js';

export const ORDINARY_MAP_FORMAT='oc2-ordinary-quest-map1-v1';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

export function validateOrdinaryMap(p){
 if(p?.format!==ORDINARY_MAP_FORMAT||p.world!=='dawnwatch'||p.mapId!==1||p.profile!=='APK_Default'||
  p.sourceMapInfo?.file!=='world/dawnwatch.wld'||p.geometryChanged!==false||p.savesChanged!==false||
  !same(p.sourceWorld?.configurationWords,[3,3,1])||!Array.isArray(p.scenery)||!Array.isArray(p.bindings))
  throw Error('原港口地图资料不匹配');
 const coordinates=new Set(['-1,-5','0,-5','-1,-4','0,-4']),ids=new Set();
 for(const m of p.scenery){
  if(!m.model?.startsWith('model/')||!m.url?.startsWith('/assets/source-ordinary-quest-map1/')||!/^[a-f0-9]{64}$/.test(m.sourceSHA256))throw Error('原港口模型来源不完整');
  for(const i of m.instances){
   const key=[...i.tile,i.id].join(':');
   if(ids.has(key)||!coordinates.has(i.tile.join(','))||i.sourceType!==2||i.model!==m.model||
    i.admission!=='admittedBeforeTypeFactory'||!finite(i.position,3)||!finite(i.quaternion,4)||!finite(i.scale,3))throw Error('原港口摆放记录不匹配');
   ids.add(key);
   const binding=p.bindings.filter(b=>b.model===i.model&&b.objectId===i.id&&same(b.tile,i.tile));
   if(binding.length!==1||!binding[0].recordPath.startsWith('world/dawnwatch/lightmap/')||
    !binding[0].bindings.length||binding[0].bindings.some((b,k)=>b.ordinal!==k||!finite(b.uvTransform,4)||
    !b.atlas.startsWith('texture/lightmap/dawnwatch/')||!p.textures[b.atlas]))throw Error('原港口图集绑定不完整');
  }
 }
 return p;
}

export function createOrdinaryLighting(THREE,p){
 const t=p?.targets,r=p?.nativeRGB?.submitted,fog=p?.fog;
 if(p?.format!=='oc2-ordinary-map1-source-environment-v1'||p.world!=='dawnwatch'||p.mapId!==1||p.sourceRegionId!==3||p.sourceOverlayId!==9||
  p.environmentHistoryObserved!==false||!finite(r?.light_model_lightMap,3)||!finite(r?.light_lightMap,3)||
  !finite(t?.tone?.distanceUniform,2)||!finite(t.tone.gainNear,3)||!finite(t.tone.gainFar,3)||!finite(fog?.color,3)||
  !Number.isFinite(fog.near)||!Number.isFinite(fog.halfSpan)||fog.halfSpan<=0)throw Error('港口原区域光照输入不完整');
 return {profile:p,sourceOrdinaryMap:1,uniforms:{
  sourceModelLight:{value:new THREE.Vector3(...r.light_model_lightMap)},sourceTerrainLight:{value:new THREE.Vector3(...r.light_lightMap)},
  sourceToneDistance:{value:new THREE.Vector2(...t.tone.distanceUniform)},sourceToneNear:{value:new THREE.Vector3(...t.tone.gainNear)},
  sourceToneFar:{value:new THREE.Vector3(...t.tone.gainFar)},sourceToneOffsetNear:{value:new THREE.Vector3(...t.tone.offsetTargets)},
  sourceToneOffsetFar:{value:new THREE.Vector3(...t.tone.offsetTargets)},sourceFogNear:{value:fog.near},sourceFogSpan:{value:fog.halfSpan},sourceFogColor:{value:new THREE.Vector3(...fog.color)}},
  state:()=>({sourceRegionId:3,sourceOverlayId:9,settledTargetCompatibility:true,originalFullFrame:false})};
}

export async function createOrdinaryScene(THREE,{scene,renderer,json,texture,origin,manifest='/assets/source-ordinary-quest-map1/manifest.json',lighting=null}={}){
 if(typeof json!=='function'||typeof texture!=='function'||!origin||![origin.x,origin.y,origin.z].every(Number.isFinite))throw Error('港口地图加载接口不完整');
 const p=validateOrdinaryMap(typeof manifest==='string'?await json(manifest):manifest);
 const [terrain,materials,ground,environment]=await Promise.all([p.terrain,p.terrainMaterials,p.terrainLighting,p.environment].map(json));
 if([terrain,materials,ground,environment].some(r=>r.world!=='dawnwatch')||terrain.sourceTiles?.length!==4||materials.tiles?.length!==4||ground.tiles?.length!==4)throw Error('港口不能混用其他地图资料');
 lighting ||= createOrdinaryLighting(THREE,environment);
 if(lighting.sourceOrdinaryMap!==1)throw Error('港口不能借用新手神殿或选角光照');
 const root=new THREE.Group();root.name='original-dawnwatch-ordinary-quest-context';
 const geometries=new Set(),mats=new Set(),maps=new Set(),cache=new Map();
 function dispose(){root.removeFromParent();for(const g of geometries)g.dispose();for(const m of mats)m.dispose();for(const t of maps)t.dispose();}
 async function load(url,repeat=true){
  if(!url)throw Error('缺原贴图，未作替代');
  const key=Number(repeat)+':'+url;
  if(!cache.has(key))cache.set(key,Promise.resolve(texture(url,THREE.NoColorSpace)).then(raw=>{
   const map=raw.clone();map.colorSpace=THREE.NoColorSpace;map.flipY=false;map.wrapS=map.wrapT=repeat?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;map.needsUpdate=true;maps.add(map);return map;
  }));return cache.get(key);
 }
 try{
  const empty=new THREE.DataTexture(new Uint8Array(4),1,1);empty.flipY=false;empty.needsUpdate=true;maps.add(empty);
  for(const tile of materials.tiles){
   const light=ground.tiles.find(r=>same(r.tile,tile.tile));
   if(!light||tile.chunks.length!==64||light.runtimeFlags?.length!==64||tile.chunks.some((c,i)=>Boolean(light.runtimeFlags[i]&0x10000)!==c.sourceWaterPending))throw Error('港口原水面标志不一致');
   // Rendering omission is separate from native water/physics flags. The clone
   // only lets the existing geometry constructor skip an unavailable draw.
   const available={...tile,chunks:tile.chunks.map(c=>({...c,sourceWaterPending:c.sourceWaterPending||Boolean(c.sourceResourcePending)}))};
   const {geometry,layers}=tileGeometry(THREE,terrain,available,origin),lightmap=await load(light.lightmap.url),mask=tile.mask?await load(tile.mask.url,false):empty;
   if(lightmap.image.width!==light.lightmap.width||lightmap.image.height!==light.lightmap.height)throw Error('港口原地形光照图尺寸不匹配');
   const layerMaterials=[];
   for(const indices of layers){
    const ts=await Promise.all(indices.map(i=>load(i>=0?tile.textures[i].url:materials.fallback)));
    const material=createLitTerrainMaterial(THREE,indices,ts,mask,lightmap,lighting);mats.add(material);layerMaterials.push(material);
   }
   const mesh=new THREE.Mesh(geometry,layerMaterials);mesh.userData.sourceTile=tile.tile;root.add(mesh);geometries.add(geometry);guardSceneOrientation(mesh);
  }
  let instances=0,parts=0;
  for(const entry of p.scenery){
   const data=await json(entry.url),source=data.meshes?.[0];
   if(data.source!==entry.model||data.sourceSHA256!==entry.sourceSHA256||data.meshes?.length!==1||!same(source.groups.map(g=>g.material),entry.partToMaterial))throw Error('港口原模型/部件不同');
   const geometry=new THREE.BufferGeometry();
   for(const[key,value,width]of [['position',source.positions,3],['normal',source.normals,3],['uv',source.uvs,2],['sourceUV1',source.sourceUV1,2]]){
    if(!finite(value,source.vertexCount*width))throw Error('港口原顶点流缺失');geometry.setAttribute(key,new THREE.Float32BufferAttribute(value,width));
   }
   if(data.sourceWindIdentity){if(!finite(source.sourceUV2,source.vertexCount*2))throw Error('原零摇动附加顶点流缺失');geometry.setAttribute('sourceUV2',new THREE.Float32BufferAttribute(source.sourceUV2,2));}
   geometry.setIndex(source.indices);for(const g of source.groups)geometry.addGroup(g.start,g.count,g.material);geometry.computeBoundingSphere();geometries.add(geometry);
   const diffuse=await Promise.all(data.materials.map(async(m,i)=>{
    const map=sceneDiffuseTexture(THREE,await load(p.textures[m.diffuse]?.url),m,i,data.sceneSampling);map.colorSpace=THREE.NoColorSpace;map.flipY=false;map.needsUpdate=true;maps.add(map);return map;
   }));
   for(const instance of entry.instances){
    const b=p.bindings.find(r=>r.model===instance.model&&r.objectId===instance.id&&same(r.tile,instance.tile)).bindings;
    const materials=[];
    for(const[part,index]of entry.partToMaterial.entries()){
     const binding=b[part]||b[0],sourceMaterial=data.materials[index];
     const material=applySceneCulling(THREE,createBakedSceneMaterial(THREE,diffuse[index],sourceMaterial,index,data,lighting),sourceMaterial,index,data.sceneCulling);
     material.uniforms.sourceAtlas={value:await load(p.textures[binding.atlas].url)};material.uniforms.sourceUVTransform={value:new THREE.Vector4(...binding.uvTransform)};
     materials[index]=material;mats.add(material);parts++;
    }
    if(!finite(source.sourceNodeTransform?.matrix,16))throw Error('港口原节点矩阵缺失');
    const mesh=new THREE.Mesh(geometry,materials),container=new THREE.Group();mesh.matrix.fromArray(source.sourceNodeTransform.matrix);mesh.matrixAutoUpdate=false;mesh.matrixWorldNeedsUpdate=true;
    container.position.set(instance.position[0]-origin.x,instance.position[1]-origin.y,instance.position[2]-origin.z);container.quaternion.fromArray(instance.quaternion);container.scale.fromArray(instance.scale);
    container.add(mesh);container.userData.originalMapInstance={id:instance.id,tile:instance.tile,model:instance.model};root.add(container);guardSceneOrientation(container);instances++;
   }
  }
  root.updateMatrixWorld(true);if(scene){scene.add(root);scene.background=new THREE.Color().setRGB(...environment.fog.color,THREE.LinearSRGBColorSpace);scene.fog=null;scene.userData.characterLighting={ambient:environment.targets.colors.light_ambient,diffuse:environment.targets.colors.light_diffuse};}
  return {root,lighting,origin,manifest:p,instances,parts,tiles:4,dispose,
   update(){return {sourceMapId:1,sourceRegionId:3,sourceOverlayId:9,settledEnvironmentOnly:true};},
   pending:{models:p.gaps,effects:p.pendingEffects,water:p.pendingWaterChunks,terrain:p.missingTerrainChunks,sky:true},originalFinalFrameRestored:false};
 }catch(error){dispose();throw error;}
}
