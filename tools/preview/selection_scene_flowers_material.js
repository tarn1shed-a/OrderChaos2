// Original custom lightMap02 is retained by342194, even with valid object DAT.
import {BAKED_VERTEX,BAKED_FRAGMENT} from './scene-baked-lighting.js?source-selection=1';
import {sceneDiffuseTexture} from './scene-sampling.js';
import {guardSceneOrientation} from './scene-culling.js';
export const SELECTION_FLOWERS_FORMAT='oc2-selection-scene-flowers-append-v1';
const MODEL='model/scene/region_whisper_island/whi_plant_flower005.bdae';
const SHA='5d08863bac80a932a54e9738696866d7da351e427e8b3897c1a181c142cd6b8d';
const LIGHTMAP='texture/lightmap02.tga',LM_SHA='822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

export function validateSelectionFlowers(p,data){
 const e=p?.entry,s=data?.selectionFlowers,m=data?.materials?.[0],mesh=data?.meshes?.[0],a=data?.sceneAlpha?.materials?.[0],c=data?.sceneCulling?.materials?.[0];
 if(p?.format!==SELECTION_FLOWERS_FORMAT||p.world!=='selection'||p.mapId!==7||p.sourceType!==2||
  p.lightsChanged!==false||p.savesChanged!==false||p.geometryChanged!==false||e?.model!==MODEL||e.sourceSHA256!==SHA||
  !same(e.instances?.map(i=>i.id),[967639024,967638880])||e.instances.some(i=>i.model!==MODEL||i.sourceType!==2||!finite(i.position,3)||!finite(i.quaternion,4)||!finite(i.scale,3))||
  data.source!==MODEL||data.sourceSHA256!==SHA||s?.format!==SELECTION_FLOWERS_FORMAT||s.sourceType!==2||
  s.sourceLightMap!==LIGHTMAP||s.sourceLightMapSHA256!==LM_SHA||s.selectionAtlasApplied!==false||s.selectionDATTransformApplied!==false||
  !same(s.sourceTextureConstantRGBA,[130,130,130,255])||!same(s,p.sourceLightMap)||data.meshes?.length!==1||data.materials?.length!==1||
  m.name!=='flower_yellow'||m.samplers.lightMap!==LIGHTMAP||mesh.vertexCount!==8||mesh.triangleCount!==4||mesh.indices.length!==12||
  mesh.groups.length!==1||mesh.groups[0].material!==0||!finite(mesh.sourceUV1,16)||!finite(mesh.sourceNodeTransform?.matrix,16)||
  a?.name!==m.name||a.effectPath!=='ut_lightmap_trans.bdae'||a.rule!=='discard-less-equal'||a.reference!==.5||
  a.sourceTechnique?.name!=='tech0'||a.resolvedTechniqueIndex!==0||c?.effectPath!=='ut_lightmap_trans.bdae'||c.cullEnabled!==false||
  c.cullFace!=='BACK'||c.frontFaceBeforeTarget!=='CCW'||c.technique!=='tech0'||
  p.textures?.[LIGHTMAP]?.sourceSHA256!==LM_SHA||p.textures[LIGHTMAP].width!==8||p.textures[LIGHTMAP].height!==8||!p.textures[m.diffuse])throw Error('原选角花草材质/几何不匹配');
 if(p.DATRequests?.length!==2)throw Error('原花草DAT请求证据缺失');
 for(const r of p.DATRequests){
  const policy=r.bindingPolicy;
  if(!e.instances.some(i=>same(i,r.instance))||r.DATBindings?.length!==1||!r.recordPath.startsWith('world/selection/lightmap/')||
   policy?.sourceName!==LIGHTMAP||policy.nativeCPU!==true||policy.replacementAllowed!==false||policy.policyCached!==true||
   policy.atlasReplacedOriginal!==false||policy.originalTextureRetained!==true)throw Error('原花草自有lightMap被错误替换');
 }
 return p;
}

export async function createSelectionFlowersAppend(THREE,p,{origin,lighting,json,texture}){
 if(lighting?.sourceSelectionRegion!==211||!lighting.uniforms?.sourceModelLight||!origin||![origin.x,origin.y,origin.z].every(Number.isFinite))throw Error('原选角花草环境未接线');
 const data=await json(p.entry.url);validateSelectionFlowers(p,data);
 const root=new THREE.Group(),ownedMaps=new Set(),materials=[];let geometry;
 const dispose=()=>{root.removeFromParent();geometry?.dispose();for(const m of materials)m.dispose();for(const t of ownedMaps)t.dispose();};
 try{
  const maps=new Map();
  for(const[name,row]of Object.entries(p.textures)){
   const raw=await texture(row.url,THREE.NoColorSpace),t=raw.clone();ownedMaps.add(t);
   if(t.image?.width!==row.width||t.image?.height!==row.height)throw Error('原花草贴图尺寸不匹配');
   t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.needsUpdate=true;maps.set(name,t);
  }
  const source=data.meshes[0],decl=data.materials[0],map=sceneDiffuseTexture(THREE,maps.get(decl.diffuse),decl,0,data.sceneSampling);
  ownedMaps.add(map);map.colorSpace=THREE.NoColorSpace;map.flipY=false;map.needsUpdate=true;
  geometry=new THREE.BufferGeometry();
  for(const[name,value,n]of [['position',source.positions,3],['normal',source.normals,3],['uv',source.uvs,2],['sourceUV1',source.sourceUV1,2]])geometry.setAttribute(name,new THREE.Float32BufferAttribute(value,n));
  geometry.setIndex(source.indices);for(const g of source.groups)geometry.addGroup(g.start,g.count,g.material);geometry.computeBoundingSphere();
  // Original atlas/DAT policy is rejected. The checked source8x8 image is
  // constant, so direct sourceUV1 is equivalent without guessing live UV state.
  const marker='atlasUV=sourceUVTransform.xy+sourceUV1*sourceUVTransform.zw;';
  if(BAKED_VERTEX.split(marker).length!==2)throw Error('已核光照贴图接口已变化');
  const vertex=BAKED_VERTEX.replace(marker,'atlasUV=sourceUV1;');
  for(const inst of p.entry.instances){
   const material=new THREE.ShaderMaterial({vertexShader:vertex,fragmentShader:BAKED_FRAGMENT,
    uniforms:{...lighting.uniforms,sourceDiffuse:{value:map},sourceAtlas:{value:maps.get(LIGHTMAP)}},
    defines:{SOURCE_CUTOUT:1},side:THREE.DoubleSide,depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,transparent:false,lights:false,toneMapped:false});
   material.map=map;material.alphaTest=.5;material.userData.sceneCulling={format:'oc2-scene-culling-v1',cullEnabled:false};materials.push(material);
   const group=new THREE.Group(),mesh=new THREE.Mesh(geometry,material);
   group.position.set(inst.position[0]-origin.x,inst.position[1]-origin.y,inst.position[2]-origin.z);group.quaternion.fromArray(inst.quaternion);group.scale.fromArray(inst.scale);
   mesh.matrix.fromArray(source.sourceNodeTransform.matrix);mesh.matrixAutoUpdate=false;mesh.matrixWorldNeedsUpdate=true;
   group.userData.selectionFlower={format:SELECTION_FLOWERS_FORMAT,id:inst.id,sourceType:2,sourceLightMap:LIGHTMAP,selectionAtlasApplied:false};group.add(mesh);root.add(group);
  }
  root.updateMatrixWorld(true);guardSceneOrientation(root);
  return {root,materials,instances:2,parts:2,originalGPUObserved:false,selectionAtlasApplied:false,dispose};
 }catch(error){dispose();throw error;}
}
