// Six original type2 map7 stones. Preserve both UV streams and RGBA product.
import {BAKED_VERTEX,BAKED_FRAGMENT,BAKED_FORMAT} from './scene-baked-lighting.js?source-selection=1';
import {sceneDiffuseTexture} from './scene-sampling.js';
import {guardSceneOrientation} from './scene-culling.js';

export const SELECTION_STONES_FORMAT='oc2-selection-scene-stones-append-v1';
const EFFECT='u2t_lightmap_solid.bdae';
const SOURCE_FX='75bad7fe12152d853ae44206a5d2a2f6bfadc5c01414bae71815277604fffd03';
const SOURCE_BRES='172b30438e12a0fe18610fe66e145e9f87372987c2699034a5490dd5b1f3d547';
const MODELS={
 'model/scene/region_whitepike/wp_stone/wp_big_stone003.bdae':{sha:'ef9a6cb2c311c6aca52bee8b79762d0980cba6f20748bd16bd69deaeffcc8d4a',
  ids:[990891040,990891328,990891472],vertices:419,triangles:282,parts:2},
 'model/scene/region_whitepike/wp_stone/wp_small_stone001.bdae':{sha:'1dd4a485fc24945cf523deeb2c586e6a0aec0a8b0adba45aec67f5c5a0bc7f24',
  ids:[990891616,990891904,990892624],vertices:77,triangles:62,parts:1},
};
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const replaceOnce=(text,from,to)=>{if(text.split(from).length!==2)throw Error('既核双贴图程序接口已变化');return text.replace(from,to);};

export function validateSelectionStones(p){
 if(p?.format!==SELECTION_STONES_FORMAT||p.world!=='selection'||p.mapId!==7||p.sourceType!==2||p.models?.length!==2||
  p.bindings?.length!==6||p.lightsChanged!==false||p.savesChanged!==false||p.geometryChanged!==false)throw Error('选角石头来源不匹配');
 for(const e of p.models){
  const s=MODELS[e.model];
  if(!s||e.sourceSHA256!==s.sha||!same(e.instances?.map(i=>i.id),s.ids)||
   e.instances.some(i=>i.model!==e.model||i.sourceType!==2||!same(i.tile,[-41,-3])||!finite(i.position,3)||!finite(i.quaternion,4)||!finite(i.scale,3)))
   throw Error('原石头ITM摆放不匹配');
  for(const inst of e.instances){
   const b=p.bindings.filter(b=>b.model===e.model&&b.objectId===inst.id);
   if(b.length!==1||b[0].recordPath!=='world/selection/lightmap/-41_-3.dat'||b[0].bindings?.length!==1||
    b[0].bindings[0].ordinal!==0||!finite(b[0].bindings[0].uvTransform,4)||
    b[0].bindings[0].atlas!=='texture/lightmap/selection/lightmap/-41_-3.tga'||!p.textures[b[0].bindings[0].atlas])throw Error('原选角石头图集缺失');
  }
 }
 return p;
}

export function validateSelectionStoneModel(e,data,p){
 const expected=MODELS[e.model],profile=data.selectionStones,mesh=data.meshes?.[0];
 if(!expected||data.source!==e.model||data.sourceSHA256!==expected.sha||profile?.format!==SELECTION_STONES_FORMAT||
  profile.effect!==EFFECT||profile.effectSHA256!==SOURCE_FX||profile.effectBRESSHA256!==SOURCE_BRES||profile.sourceType!==2||
  profile.materials?.length!==expected.parts||data.materials?.length!==expected.parts||data.meshes?.length!==1||
  mesh.vertexCount!==expected.vertices||mesh.triangleCount!==expected.triangles||mesh.indices.length!==expected.triangles*3||
  !same(mesh.groups.map(g=>g.material),e.partToMaterial)||mesh.groups.length!==expected.parts||
  mesh.selectionStoneUV?.sourceSemantic!==6||mesh.selectionStoneUV.runtimeSemantic!==3||mesh.selectionStoneUV.type!==6||mesh.selectionStoneUV.components!==2||
  !finite(mesh.sourceUV1,expected.vertices*2)||!finite(mesh.sourceUV2,expected.vertices*2)||!finite(mesh.sourceNodeTransform?.matrix,16)||
  data.sceneBakedLighting?.format!==BAKED_FORMAT)throw Error('原双纹理模型数据不匹配');
 for(const [i,r]of profile.materials.entries()){
  const a=data.sceneAlpha?.materials?.[i],c=data.sceneCulling?.materials?.[i],m=data.materials[i],lm=data.sceneBakedLighting.materials?.[i];
  if(r.index!==i||r.name!==m.name||r.effect!==EFFECT||r.operation!=='component-wise-RGBA-multiply-before-lightMap'||r.secondSourceUV!==2||
   !same(Object.keys(r.samplers).sort(),['lightMap','texture','texture2'])||r.samplers.texture.texture!==m.diffuse||r.samplers.lightMap.texture!=='texture/lightmap.tga'||
   a?.index!==i||a.effectPath!==EFFECT||a.name!==m.name||a.rule!=='none'||a.reference!==null||a.sourceTechnique?.name!=='tech0'||
   c?.index!==i||c.effectPath!==EFFECT||c.cullEnabled!==false||c.cullFace!=='BACK'||c.frontFaceBeforeTarget!=='CCW'||c.technique!=='tech0'||
   lm?.name!==m.name||lm.texture!==m.diffuse||lm.sourceLightMap!=='texture/lightmap.tga')throw Error('原石头材质和绘制状态不匹配');
  for(const [key,s]of Object.entries(r.samplers)){
   if(Object.values(s.request).some(v=>v!==null)||key!=='lightMap'&&!p.textures[s.texture])throw Error('原双纹理sampler缺失');
  }
 }
 return data;
}

function stoneMaterial(THREE,data,index,maps,atlas,binding,lighting){
 const r=data.selectionStones.materials[index],map=maps.get(r.samplers.texture.texture),second=maps.get(r.samplers.texture2.texture);
 for(const[key,t]of [['texture',map],['texture2',second]]){
  const d=r.textureDimensions[key];
  if(!t||t.colorSpace!==THREE.NoColorSpace||t.flipY!==false||t.image?.width!==d.width||t.image?.height!==d.height)throw Error('原双纹理尺寸/色彩接口不匹配');
 }
 const vertex='attribute vec2 sourceUV2;varying vec2 selectionSecondUV;\n'+replaceOnce(BAKED_VERTEX,'diffuseUV=uv;','selectionSecondUV=sourceUV2;diffuseUV=uv;');
 const fragment='uniform sampler2D selectionSecond;varying vec2 selectionSecondUV;\n'+replaceOnce(BAKED_FRAGMENT,
  'vec4 color=texture2D(sourceDiffuse,diffuseUV);','vec4 color=texture2D(sourceDiffuse,diffuseUV);\ncolor*=texture2D(selectionSecond,selectionSecondUV);');
 const material=new THREE.ShaderMaterial({vertexShader:vertex,fragmentShader:fragment,
  uniforms:{...lighting.uniforms,sourceDiffuse:{value:map},selectionSecond:{value:second},sourceAtlas:{value:atlas},sourceUVTransform:{value:new THREE.Vector4(...binding.uvTransform)}},
  defines:{},side:THREE.DoubleSide,depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,transparent:false,toneMapped:false,lights:false});
 material.map=map;material.alphaTest=0;material.userData.sceneCulling={format:'oc2-scene-culling-v1',cullEnabled:false};
 material.userData.selectionStone={format:SELECTION_STONES_FORMAT,index,effect:EFFECT};return material;
}

export async function createSelectionStonesAppend(THREE,p,{origin,lighting,json,texture}){
 validateSelectionStones(p);
 if(lighting?.sourceSelectionRegion!==211||!lighting.uniforms?.sourceModelLight||!origin||
  ![origin.x,origin.y,origin.z].every(Number.isFinite))throw Error('原选角环境未接线');
 const root=new THREE.Group(),maps=new Map(),ownedMaps=new Set(),materials=[],geometries=[];
 function dispose(){root.removeFromParent();for(const g of geometries)g.dispose();for(const m of materials)m.dispose();for(const t of ownedMaps)t.dispose();}
 try{
  for(const[name,row]of Object.entries(p.textures)){
   const raw=await texture(row.url,THREE.NoColorSpace),t=raw.clone();ownedMaps.add(t);
   if(t.image?.width!==row.width||t.image?.height!==row.height)throw Error('原选角石头纹理尺寸不匹配');
   t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.needsUpdate=true;maps.set(name,t);
  }
  for(const e of p.models){
   const data=validateSelectionStoneModel(e,await json(e.url),p),source=data.meshes[0],geometry=new THREE.BufferGeometry();geometries.push(geometry);
   for(const[name,values,n]of [['position',source.positions,3],['normal',source.normals,3],['uv',source.uvs,2],['sourceUV1',source.sourceUV1,2],['sourceUV2',source.sourceUV2,2]])geometry.setAttribute(name,new THREE.Float32BufferAttribute(values,n));
   geometry.setIndex(source.indices);for(const g of source.groups)geometry.addGroup(g.start,g.count,g.material);geometry.computeBoundingSphere();
   for(const[i,m]of data.materials.entries()){
    const t=sceneDiffuseTexture(THREE,maps.get(m.diffuse),m,i,data.sceneSampling);ownedMaps.add(t);t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.needsUpdate=true;maps.set(m.diffuse,t);
   }
   for(const inst of e.instances){
    const b=p.bindings.find(b=>b.objectId===inst.id&&b.model===e.model).bindings[0],atlas=maps.get(b.atlas);
    const list=data.materials.map((_,i)=>stoneMaterial(THREE,data,i,maps,atlas,b,lighting));materials.push(...list);
    const group=new THREE.Group(),mesh=new THREE.Mesh(geometry,list);
    group.position.set(inst.position[0]-origin.x,inst.position[1]-origin.y,inst.position[2]-origin.z);
    group.quaternion.fromArray(inst.quaternion);group.scale.fromArray(inst.scale);
    mesh.matrix.fromArray(source.sourceNodeTransform.matrix);mesh.matrixAutoUpdate=false;mesh.matrixWorldNeedsUpdate=true;
    group.userData.selectionStone={format:SELECTION_STONES_FORMAT,id:inst.id,sourceType:2};group.add(mesh);root.add(group);
   }
  }
  root.updateMatrixWorld(true);guardSceneOrientation(root);
  return {root,materials,instances:6,parts:9,originalGPUObserved:false,dispose};
 }catch(error){dispose();throw error;}
}
