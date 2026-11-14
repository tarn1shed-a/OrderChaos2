// Original no-record path retains the original fresh-mounted default lightMap.
import {BAKED_VERTEX,BAKED_FRAGMENT} from './scene-baked-lighting.js?source-selection=1';
import {sceneDiffuseTexture} from './scene-sampling.js';
import {guardSceneOrientation} from './scene-culling.js';
export const SELECTION_GRASS_FORMAT='oc2-selection-scene-grass-append-v1';
const MODEL='model/scene/region_whisper_island/whi_plant_unknowgrass006.bdae';
const SHA='af7e764074b378199e115d8b1d20743d8c7a7717d5ea6193c0b98547877a0fc5';
const LIGHTMAP='texture/lightmap.tga',LM_SHA='822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite),same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);

export function validateSelectionGrass(p,data){
 const e=p?.entry,m=data?.materials?.[0],mesh=data?.meshes?.[0],a=data?.sceneAlpha?.materials?.[0],c=data?.sceneCulling?.materials?.[0],inst=e?.instances?.[0];
 if(p?.format!==SELECTION_GRASS_FORMAT||p.world!=='selection'||p.mapId!==7||p.sourceRegion!==211||p.sourceType!==2||
  p.lightsChanged!==false||p.savesChanged!==false||p.geometryChanged!==false||p.freshStartOnly!==true||e?.model!==MODEL||e.sourceSHA256!==SHA||
  e.instances?.length!==1||inst.id!==1014080736||inst.model!==MODEL||inst.sourceType!==2||!finite(inst.position,3)||!finite(inst.quaternion,4)||!finite(inst.scale,3)||
  data.source!==MODEL||data.sourceSHA256!==SHA||data.meshes?.length!==1||data.materials?.length!==1||
  m.name!=='_4_-_Default'||m.samplers.lightMap!==LIGHTMAP||mesh.vertexCount!==227||mesh.triangleCount!==165||mesh.indices.length!==495||
  mesh.groups.length!==1||mesh.groups[0].material!==0||!finite(mesh.sourceUV1,454)||!finite(mesh.sourceNodeTransform?.matrix,16)||
  a?.name!==m.name||a.effectPath!=='ut_lightmap_trans.bdae'||a.rule!=='discard-less-equal'||a.reference!==.5||
  a.sourceTechnique?.name!=='tech0'||a.resolvedTechniqueIndex!==0||c?.effectPath!=='ut_lightmap_trans.bdae'||c.cullEnabled!==false||
  c.cullFace!=='BACK'||c.frontFaceBeforeTarget!=='CCW'||c.technique!=='tech0'||p.recordPath!=='world/selection/lightmap/-42_-1.dat'||p.recordCount!==0||
  p.nativeEmptyRecords?.objectId!==inst.id||p.nativeEmptyRecords.recordCount!==0||p.nativeEmptyRecords.noAtlasReplacement!==true||p.nativeEmptyRecords.freshVectorsUnchanged!==true||
  p.nativeTextureMount?.nativeCPU!==true||p.nativeTextureMount.coldCache!==true||p.nativeTextureMount.selected!=='res_t_upd10.bin'||
  p.sourceDefaultLightMap!==LIGHTMAP||!same(p.sourceConstantRGBA,[130,130,130,255])||p.selectionAtlasApplied!==false||p.selectionDATTransformApplied!==false||
  p.textures?.[LIGHTMAP]?.sourceSHA256!==LM_SHA||p.textures[LIGHTMAP].sourcePack!=='res_t_upd10.bin'||p.textures[LIGHTMAP].width!==8||p.textures[LIGHTMAP].height!==8||!p.textures[m.diffuse])throw Error('原选角缺记录草木来源不匹配');
 return p;
}

export async function createSelectionGrassAppend(THREE,p,{origin,lighting,json,texture}){
 if(lighting?.sourceSelectionRegion!==211||!lighting.uniforms?.sourceModelLight||!origin||![origin.x,origin.y,origin.z].every(Number.isFinite))throw Error('原选角草木环境未接线');
 const data=await json(p.entry.url);validateSelectionGrass(p,data);
 const root=new THREE.Group(),ownedMaps=new Set(),materials=[];let geometry;
 const dispose=()=>{root.removeFromParent();geometry?.dispose();for(const m of materials)m.dispose();for(const t of ownedMaps)t.dispose();};
 try{
  const maps=new Map();
  for(const[name,row]of Object.entries(p.textures)){
   const raw=await texture(row.url,THREE.NoColorSpace),t=raw.clone();ownedMaps.add(t);
   if(t.image?.width!==row.width||t.image?.height!==row.height)throw Error('原草木贴图尺寸不匹配');
   t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.needsUpdate=true;maps.set(name,t);
  }
  const source=data.meshes[0],decl=data.materials[0],map=sceneDiffuseTexture(THREE,maps.get(decl.diffuse),decl,0,data.sceneSampling);
  ownedMaps.add(map);map.colorSpace=THREE.NoColorSpace;map.flipY=false;map.needsUpdate=true;
  geometry=new THREE.BufferGeometry();
  for(const[name,value,n]of [['position',source.positions,3],['normal',source.normals,3],['uv',source.uvs,2],['sourceUV1',source.sourceUV1,2]])geometry.setAttribute(name,new THREE.Float32BufferAttribute(value,n));
  geometry.setIndex(source.indices);for(const g of source.groups)geometry.addGroup(g.start,g.count,g.material);geometry.computeBoundingSphere();
  // No original DAT records means no atlas replacement. The actual selected
  //8x8 default image is constant; direct source UV is pixel-equivalent.
  const marker='atlasUV=sourceUVTransform.xy+sourceUV1*sourceUVTransform.zw;';
  if(BAKED_VERTEX.split(marker).length!==2)throw Error('已核光照贴图接口已变化');
  const material=new THREE.ShaderMaterial({vertexShader:BAKED_VERTEX.replace(marker,'atlasUV=sourceUV1;'),fragmentShader:BAKED_FRAGMENT,
   uniforms:{...lighting.uniforms,sourceDiffuse:{value:map},sourceAtlas:{value:maps.get(LIGHTMAP)}},
   defines:{SOURCE_CUTOUT:1},side:THREE.DoubleSide,depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,transparent:false,lights:false,toneMapped:false});
  material.map=map;material.alphaTest=.5;material.userData.sceneCulling={format:'oc2-scene-culling-v1',cullEnabled:false};materials.push(material);
  const inst=p.entry.instances[0],group=new THREE.Group(),mesh=new THREE.Mesh(geometry,material);
  group.position.set(inst.position[0]-origin.x,inst.position[1]-origin.y,inst.position[2]-origin.z);group.quaternion.fromArray(inst.quaternion);group.scale.fromArray(inst.scale);
  mesh.matrix.fromArray(source.sourceNodeTransform.matrix);mesh.matrixAutoUpdate=false;mesh.matrixWorldNeedsUpdate=true;
  group.userData.selectionGrass={format:SELECTION_GRASS_FORMAT,id:inst.id,sourceType:2,sourceLightMap:LIGHTMAP,selectionAtlasApplied:false};group.add(mesh);root.add(group);
  root.updateMatrixWorld(true);guardSceneOrientation(root);
  return {root,materials,instances:1,parts:1,originalGPUObserved:false,selectionAtlasApplied:false,dispose};
 }catch(error){dispose();throw error;}
}
