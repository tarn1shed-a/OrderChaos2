// One source type2 selection placement; no type15/companion visibility policy.
import {BAKED_VERTEX,BAKED_FRAGMENT,BAKED_FORMAT} from './scene-baked-lighting.js?source-selection=1';
import {sceneDiffuseTexture} from './scene-sampling.js';
import {guardSceneOrientation} from './scene-culling.js';

export const SELECTION_INSIDE_FORMAT='oc2-selection-scene-inside-append-v1';
const MODEL='model/scene_generator_temple_000/god_temple01_inside01.bdae';
const MODEL_SHA='a7d5ab9ec74318feaf1c518d8b4b5a94e3e847996c67c9a34e84ee34c3c23192';
const SOLID='ut_lightmap_solid.bdae',UV='ut_lightmap_trans_uv.bdae',LUMIN='u2t_lightmap_trans_uv_lumin.bdae';
const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
const replaceOnce=(text,from,to)=>{if(text.split(from).length!==2)throw Error('既核顶点/像素接口已变化');return text.replace(from,to);};

export function validateSelectionInside(p,data){
 const e=p?.entry,m=data?.selectionInsideMaterials;
 if(p?.format!==SELECTION_INSIDE_FORMAT||p.world!=='selection'||p.mapId!==7||p.sourceType!==2||
  p.type15VisibilityApplied!==false||p.companionModelAdded!==false||p.lightingChanged!==false||p.savesChanged!==false||
  e?.model!==MODEL||e.sourceSHA256!==MODEL_SHA||data.source!==MODEL||data.sourceSHA256!==MODEL_SHA||data.sourceInsideModel||
  e.instances?.length!==1||e.instances[0].id!==684990760||e.instances[0].sourceType!==2||
  m?.format!==SELECTION_INSIDE_FORMAT||m.sourceType!==2||m.type15VisibilityApplied!==false||
  m.materials?.length!==21||data.materials?.length!==21||data.meshes?.length!==1||data.sceneBakedLighting?.format!==BAKED_FORMAT)
  throw Error('原选角神殿材质来源不匹配');
 const mesh=data.meshes[0];
 if(mesh.vertexCount!==11817||mesh.triangleCount!==7900||mesh.indices.length!==23700||mesh.groups?.length!==21||
  JSON.stringify(mesh.groups.map(g=>g.material))!==JSON.stringify(e.partToMaterial))throw Error('原选角神殿几何不匹配');
 for(const key of ['sourceUV1','sourceUV2','sourceUV3'])if(!finite(mesh[key],11817*2))throw Error('原选角神殿UV缺失');
 for(const [key,semantic,runtime]of [['UV2',6,3],['UV3',7,4]]){
  const a=mesh.selectionSecondaryUV?.[key];if(a?.sourceSemantic!==semantic||a.runtimeSemantic!==runtime||a.type!==6||a.components!==2)throw Error('原第二贴图UV语义不匹配');
 }
 const counts=new Map();
 for(const[i,r]of m.materials.entries()){
  const source=data.materials[i],a=data.sceneAlpha?.materials?.[i],c=data.sceneCulling?.materials?.[i],baked=data.sceneBakedLighting.materials?.[i];
  const cut=r.effect!==SOLID,expected=r.effect===LUMIN?['tex2_color','tex2_intensity','uvSpeed2']:r.effect===UV?['uvSpeed']:[];
  if(r.index!==i||r.name!==source.name||![SOLID,UV,LUMIN].includes(r.effect)||r.missingSamplers?.length!==0||
   JSON.stringify(Object.keys(r.values).sort())!==JSON.stringify(expected)||
   a?.name!==r.name||a.effectPath!==r.effect||a.rule!==(cut?'discard-less-equal':'none')||a.reference!==(cut?.5:null)||
   a.resolvedTechniqueIndex!==0||a.sourceTechnique?.name!=='tech0'||c?.effectPath!==r.effect||c.cullEnabled!==false||
   c.cullFace!=='BACK'||c.frontFaceBeforeTarget!=='CCW'||c.technique!=='tech0'||
   baked?.index!==i||baked.name!==source.name||baked.texture!==source.diffuse||baked.sourceLightMap!=='texture/lightmap.tga')throw Error('原选角神殿绘制状态不匹配');
  for(const[name,value]of Object.entries(r.values)){
   const width=name==='tex2_color'?3:name==='tex2_intensity'?1:2;
   if(!finite(value,width)||r.nativePropertyCopy?.[name]?.nativeCPU!==true||
    JSON.stringify(value)!==JSON.stringify(r.nativePropertyCopy[name].value))throw Error('原材质参数未核对');
  }
  for(const[name,s]of Object.entries(r.samplers)){
   if(name==='lightMap'){if(s.texture!=='texture/lightmap.tga')throw Error('原光照占位引用不匹配');continue;}
   if(!p.textures[s.texture]||Object.values(s.request).some(v=>v!==null))throw Error('原多贴图sampler不匹配');
  }
  counts.set(r.effect,(counts.get(r.effect)||0)+1);
 }
 if(counts.get(SOLID)!==18||counts.get(LUMIN)!==2||counts.get(UV)!==1)throw Error('原材质组合改变');
 const b=p.bindings?.[0];
 if(p.bindings.length!==1||b.objectId!==684990760||b.model!==MODEL||b.recordPath!=='world/selection/lightmap/-41_-2.dat'||
  b.bindings?.length!==1||b.bindings[0].ordinal!==0||!finite(b.bindings[0].uvTransform,4)||
  !b.bindings[0].atlas.startsWith('texture/lightmap/selection/')||!p.textures[b.bindings[0].atlas])throw Error('选角原图集不能混用其它地图');
 return p;
}

export function selectionInsideMaterial(THREE,data,index,maps,atlas,binding,lighting,clock){
 const row=data.selectionInsideMaterials.materials[index],source=data.materials[index],alpha=data.sceneAlpha.materials[index];
 const map=maps.get(row.samplers.texture.texture),cut=row.effect!==SOLID;
 if(!map||map.colorSpace!==THREE.NoColorSpace||map.flipY!==false||map.image?.width!==alpha.sourceAlpha.width||map.image?.height!==alpha.sourceAlpha.height)
  throw Error('原神殿贴图尺寸或色彩接口不匹配');
 let vertex=BAKED_VERTEX,fragment=BAKED_FRAGMENT;
 if(row.effect===UV){
  vertex='uniform highp float selectionTime;uniform highp vec2 selectionUVSpeed;\n'+vertex;
  vertex=replaceOnce(vertex,'diffuseUV=uv;','diffuseUV=uv+fract(selectionUVSpeed*selectionTime);');
 }
 if(row.effect===LUMIN){
  vertex='attribute vec2 sourceUV2,sourceUV3;uniform highp float selectionTime;uniform highp vec2 selectionUV2Speed;varying vec2 selectionSecondUV,selectionMaskUV;\n'+vertex;
  vertex=replaceOnce(vertex,'diffuseUV=uv;','selectionSecondUV=sourceUV2+fract(selectionUV2Speed*selectionTime);selectionMaskUV=sourceUV3;diffuseUV=uv;');
  fragment='uniform sampler2D selectionSecond,selectionMask;uniform vec3 selectionTint;uniform float selectionIntensity;varying vec2 selectionSecondUV,selectionMaskUV;\n'+fragment;
  fragment=replaceOnce(fragment,'color.rgb*=vertexLight;','color.rgb*=vertexLight;\nvec4 second=texture2D(selectionSecond,selectionSecondUV);\nfloat maskAlpha=texture2D(selectionMask,selectionMaskUV).a;\ncolor.rgb+=second.rgb*selectionTint*selectionIntensity*(second.a*maskAlpha);');
 }
 const uniforms={...lighting.uniforms,sourceDiffuse:{value:map},sourceAtlas:{value:atlas},
  sourceUVTransform:{value:new THREE.Vector4(...binding.uvTransform)}};
 if(row.effect!==SOLID)uniforms.selectionTime={value:clock.value()};
 if(row.effect===UV)uniforms.selectionUVSpeed={value:new THREE.Vector2(...row.values.uvSpeed)};
 if(row.effect===LUMIN){
  uniforms.selectionUV2Speed={value:new THREE.Vector2(...row.values.uvSpeed2)};
  uniforms.selectionTint={value:new THREE.Vector3(...row.values.tex2_color)};uniforms.selectionIntensity={value:row.values.tex2_intensity[0]};
  uniforms.selectionSecond={value:maps.get(row.samplers.texture2.texture)};uniforms.selectionMask={value:maps.get(row.samplers.texture2Mask.texture)};
  if(!uniforms.selectionSecond.value||!uniforms.selectionMask.value)throw Error('原第二贴图缺失，不能替代');
 }
 const m=new THREE.ShaderMaterial({uniforms,vertexShader:vertex,fragmentShader:fragment,defines:cut?{SOURCE_CUTOUT:1}:{},
  side:THREE.DoubleSide,depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,transparent:false,toneMapped:false,lights:false});
 m.map=map;m.alphaTest=cut?.5:0;m.userData.sceneCulling={format:'oc2-scene-culling-v1',cullEnabled:false};
 m.userData.selectionInside={format:SELECTION_INSIDE_FORMAT,index,effect:row.effect};return m;
}

export async function createSelectionInsideAppend(THREE,p,{origin,lighting,json,texture,clock}){
 if(lighting?.sourceSelectionRegion!==211||!lighting.uniforms?.sourceModelLight||!origin||
  ![origin.x,origin.y,origin.z].every(Number.isFinite)||typeof clock?.value!=='function'||!Number.isFinite(clock.value()))throw Error('原选角环境或显式时钟未接线');
 const data=await json(p.entry.url);validateSelectionInside(p,data);
 const maps=new Map(),ownedMaps=new Set(),materials=[],root=new THREE.Group();let geometry=null;
 function dispose(){root.removeFromParent();geometry?.dispose();for(const m of materials)m.dispose();for(const t of ownedMaps)t.dispose();}
 try{
  for(const[name,row]of Object.entries(p.textures)){
   const raw=await texture(row.url,THREE.NoColorSpace),t=raw.clone();
   if(t.image?.width!==row.width||t.image?.height!==row.height)throw Error('原第二贴图尺寸不匹配');
   t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=THREE.RepeatWrapping;t.needsUpdate=true;maps.set(name,t);ownedMaps.add(t);
  }
  for(const[index,source]of data.materials.entries()){
   const old=maps.get(source.diffuse),owned=sceneDiffuseTexture(THREE,old,source,index,data.sceneSampling);
   owned.colorSpace=THREE.NoColorSpace;owned.flipY=false;owned.needsUpdate=true;
   // Duplicate diffuse names share the same original sampler request here.
   maps.set(source.diffuse,owned);ownedMaps.add(owned);
  }
  const binding=p.bindings[0].bindings[0],atlas=maps.get(binding.atlas);
  for(let i=0;i<21;i++)materials.push(selectionInsideMaterial(THREE,data,i,maps,atlas,binding,lighting,clock));
  const source=data.meshes[0];geometry=new THREE.BufferGeometry();
  for(const[name,values,n]of [['position',source.positions,3],['normal',source.normals,3],['uv',source.uvs,2],
   ['sourceUV1',source.sourceUV1,2],['sourceUV2',source.sourceUV2,2],['sourceUV3',source.sourceUV3,2]])geometry.setAttribute(name,new THREE.Float32BufferAttribute(values,n));
  geometry.setIndex(source.indices);for(const g of source.groups)geometry.addGroup(g.start,g.count,g.material);geometry.computeBoundingSphere();
  const mesh=new THREE.Mesh(geometry,materials),inst=p.entry.instances[0];
  if(!finite(source.sourceNodeTransform?.matrix,16))throw Error('原神殿节点矩阵缺失');
  mesh.matrix.fromArray(source.sourceNodeTransform.matrix);mesh.matrixAutoUpdate=false;mesh.matrixWorldNeedsUpdate=true;
  root.position.set(inst.position[0]-origin.x,inst.position[1]-origin.y,inst.position[2]-origin.z);
  root.quaternion.fromArray(inst.quaternion);root.scale.fromArray(inst.scale);root.add(mesh);root.updateMatrixWorld(true);guardSceneOrientation(root);
  const previous=mesh.onBeforeRender;
  mesh.onBeforeRender=function(...args){
   previous.apply(this,args);const seconds=clock.value();if(!Number.isFinite(seconds)||seconds<0)throw Error('原时钟接口无效');
   for(const m of materials)if(m.uniforms.selectionTime){m.uniforms.selectionTime.value=seconds;m.uniformsNeedUpdate=true;}
  };
  root.userData.selectionInside={format:SELECTION_INSIDE_FORMAT,id:inst.id,sourceType:2};
  return {root,materials,parts:21,instances:1,dispose,originalGPUObserved:false};
 }catch(error){dispose();throw error;}
}
