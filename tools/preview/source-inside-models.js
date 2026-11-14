// Original type15 primary-model inputs. This does not fabricate missing inside
// companions or reproduce the original camera/PHY/global inside-state machine.
import {BAKED_VERTEX,BAKED_FRAGMENT,BAKED_FORMAT} from './scene-baked-lighting.js?source-selection=1';
export const INSIDE_FORMAT='oc2-source-tutorial-inside-models-v1';
const UV='ut_lightmap_trans_uv.bdae',LUMIN='u2t_lightmap_trans_uv_lumin.bdae';
const effects=new Set(['ut_lightmap_solid.bdae','ut_cull_lightmap_solid.bdae','ut_lightmap_trans.bdae',UV,LUMIN]);
const prepared=new WeakMap();
const models=new Map();
const finite=(v,n)=>Array.isArray(v)&&v.length===n&&v.every(Number.isFinite);

export function validateInsideModel(data){
 const p=data?.sourceInsideMaterials,m=data?.sourceInsideModel;
 if(p?.format!==INSIDE_FORMAT||p.fullOriginalFrameRestored!==false||p.lightsChanged!==false||
  m?.format!==INSIDE_FORMAT||m.sourceType!==15||m.primaryOnlyCandidate!==true||m.liveInsideVisibilityRestored!==false||
  data.source!==m.originalPrimary||m.originalCompanion!==data.source.slice(0,-5)+'_inside.bdae'||
  p.materials?.length!==data.materials?.length||!data.meshes?.length)throw Error('原室内主模型资料不匹配');
 for(const [i,r]of p.materials.entries()){
  if(r.index!==i||r.name!==data.materials[i].name||!effects.has(r.effect)||!Array.isArray(r.missingSamplers)||
   JSON.stringify(Object.keys(r.values).sort())!==JSON.stringify((r.effect===UV?['uvSpeed']:r.effect===LUMIN?['tex2_color','tex2_intensity','uvSpeed2']:[]).sort()))throw Error('原室内材质资料不匹配');
  for(const [name,values]of Object.entries(r.values)){
   const n=name==='tex2_intensity'?1:name==='tex2_color'?3:2;
   if(!finite(values,n)||r.nativePropertyCopy?.[name]?.nativeCPU!==true||
    JSON.stringify(values)!==JSON.stringify(r.nativePropertyCopy[name].value))throw Error('原室内材质参数未核对');
  }
  if(r.missingSamplers.length&&(r.effect!==LUMIN||r.missingSamplers.some(s=>s.sampler!=='texture2Mask'||s.path!=='texture/hum_portal005.tga'||s.candidateCount!==0)))throw Error('未核对的室内贴图缺口');
 }
 return p;
}

export async function prepareInsideSource(THREE,data,textures,load){
 if(!data.sourceInsideMaterials)return;
 const p=validateInsideModel(data),maps=new Map();
 for(const r of p.materials){
  if(r.missingSamplers.length)continue;
  for(const name of ['texture2','texture2Mask']){
   const path=r.samplers[name]?.texture;if(!path||maps.has(path))continue;
   if(!textures[path])throw Error('原室内第二贴图缺失');
   const raw=await load(textures[path],THREE.NoColorSpace),map=raw.clone();
   map.colorSpace=THREE.NoColorSpace;map.wrapS=map.wrapT=THREE.RepeatWrapping;map.flipY=false;map.needsUpdate=true;
   maps.set(path,map);
  }
 }
 prepared.set(data,maps);models.set(data.source,data);
}

function inputs(THREE,material,row,maps,clock){
 material.uniforms.sourceInsideTime={value:clock?.value()??0};
 if(row.effect===UV)material.uniforms.sourceInsideUVSpeed={value:new THREE.Vector2(...row.values.uvSpeed)};
 if(row.effect===LUMIN&&!row.missingSamplers.length){
  material.uniforms.sourceInsideUV2Speed={value:new THREE.Vector2(...row.values.uvSpeed2)};
  material.uniforms.sourceInsideTint={value:new THREE.Vector3(...row.values.tex2_color)};
  material.uniforms.sourceInsideIntensity={value:row.values.tex2_intensity[0]};
  for(const [key,name]of [['sourceInsideSecond','texture2'],['sourceInsideMask','texture2Mask']]){
   const tex=maps.get(row.samplers[name].texture);if(!tex)throw Error('原室内特效贴图未就绪');
   material.uniforms[key]={value:tex};
  }
 }
}

export function createInsideSceneMaterial(THREE,map,source,index,data,lighting){
 const p=validateInsideModel(data),r=p.materials[index],a=data.sceneAlpha?.materials?.[index],c=data.sceneCulling?.materials?.[index];
 const baked=data.sceneBakedLighting?.materials?.[index],alpha=a?.sourceAlpha;
 const cut=r.effect!=='ut_lightmap_solid.bdae'&&r.effect!=='ut_cull_lightmap_solid.bdae';
 if(!prepared.has(data)||data.sceneBakedLighting?.format!==BAKED_FORMAT||baked?.name!==source.name||baked.texture!==source.diffuse||
  baked.sourceLightMap!=='texture/lightmap.tga'||a?.effectPath!==r.effect||a.index!==index||a.name!==source.name||a.texture!==source.diffuse||
  a.rule!==(cut?'discard-less-equal':'none')||a.reference!==(cut?.5:null)||a.resolvedTechniqueIndex!==0||a.sourceTechnique?.name!=='tech0'||
  !['split-red','opaque-ETC1'].includes(alpha?.mode)||map.image?.width!==alpha.width||map.image?.height!==alpha.height||
  map.colorSpace!==THREE.NoColorSpace||map.flipY!==false||c?.index!==index||c.effectPath!==r.effect||c.name!==source.name||
  c.cullEnabled!==(r.effect==='ut_cull_lightmap_solid.bdae')||c.cullFace!=='BACK'||c.frontFaceBeforeTarget!=='CCW'||c.technique!=='tech0')throw Error('原室内绘制状态不匹配');
 let vertex=BAKED_VERTEX,fragment=BAKED_FRAGMENT;
 if(r.effect===UV){
  vertex='uniform highp float sourceInsideTime;uniform highp vec2 sourceInsideUVSpeed;\n'+vertex;
  vertex=vertex.replace('diffuseUV=uv;','diffuseUV=uv+fract(sourceInsideUVSpeed*sourceInsideTime);');
 }
 if(r.effect===LUMIN){
  vertex='attribute vec2 sourceUV2,sourceUV3;uniform highp float sourceInsideTime;uniform highp vec2 sourceInsideUV2Speed;varying vec2 insideSecondUV,insideMaskUV;\n'+vertex;
  vertex=vertex.replace('diffuseUV=uv;','insideSecondUV=sourceUV2+fract(sourceInsideUV2Speed*sourceInsideTime);insideMaskUV=sourceUV3;diffuseUV=uv;');
  fragment='uniform sampler2D sourceInsideSecond,sourceInsideMask;uniform vec3 sourceInsideTint;uniform float sourceInsideIntensity;varying vec2 insideSecondUV,insideMaskUV;\n'+fragment;
  fragment=fragment.replace('color.rgb*=vertexLight;','color.rgb*=vertexLight;\nvec4 second=texture2D(sourceInsideSecond,insideSecondUV);\nfloat maskAlpha=texture2D(sourceInsideMask,insideMaskUV).a;\ncolor.rgb+=second.rgb*sourceInsideTint*sourceInsideIntensity*(second.a*maskAlpha);');
 }
 const material=new THREE.ShaderMaterial({vertexShader:vertex,fragmentShader:fragment,
  uniforms:{...lighting.uniforms,sourceDiffuse:{value:map},sourceAtlas:{value:null},sourceUVTransform:{value:new THREE.Vector4(0,0,1,1)}},
  defines:cut?{SOURCE_CUTOUT:1}:{},side:c.cullEnabled?THREE.FrontSide:THREE.DoubleSide,
  depthTest:true,depthWrite:true,depthFunc:THREE.LessEqualDepth,transparent:false,toneMapped:false,lights:false});
 material.map=map;material.alphaTest=cut?.5:0;material.shadowSide=THREE.DoubleSide;
 material.userData.sceneBakedLighting={format:BAKED_FORMAT,index};
 material.userData.sceneAlpha={format:data.sceneAlpha.format,rule:a.rule,reference:a.reference};
 material.userData.sceneCulling={format:data.sceneCulling.format,cullEnabled:c.cullEnabled};
 material.userData.sourceInsideMaterial={format:INSIDE_FORMAT,index,pending:r.missingSamplers.length>0};
 // Original referenced mask is absent. Omit this original part, preserving its
 // geometry/material/part ordinal; do not substitute a similarly named texture.
 if(r.missingSamplers.length)material.visible=false;
 else inputs(THREE,material,r,prepared.get(data));
 return material;
}

export function prepareInsideGeometry(THREE,geometry,mesh){
 if(!mesh.sourceInsideAttributes)return;
 for(const [name,sourceSemantic,runtimeSemantic]of [['sourceUV2',6,3],['sourceUV3',7,4]]){
  const info=mesh.sourceInsideAttributes?.['UV'+(sourceSemantic-4)],values=mesh[name];
  if(info?.sourceSemantic!==sourceSemantic||info.runtimeSemantic!==runtimeSemantic||!finite(values,mesh.positions.length/3*2))throw Error('原室内 UV 流缺失');
  geometry.setAttribute(name,new THREE.Float32BufferAttribute(values,2));
 }
}

export function prepareInsideRoot(root,data){
 if(data.sourceInsideMaterials){validateInsideModel(data);root.userData.sourceInsideModelSource=data.source;}
 return root;
}

// Call after the existing original part-ordered lightmap binder, which clones
// materials and rebuilds uniforms. Object3D.clone also loses render callbacks.
export function bindInsideInstance(THREE,root,clock){
 const name=root.userData.sourceInsideModelSource;if(!name)return root;
 const data=models.get(name);if(!data)throw Error('原室内模型来源缺失');
 const p=validateInsideModel(data),maps=prepared.get(data);if(!maps)throw Error('原室内材质还未准备');
 root.traverse(object=>{
  if(!object.isMesh)return;
  const materials=Array.isArray(object.material)?object.material:[object.material];
  for(const material of materials){
   const meta=material.userData.sourceInsideMaterial;if(meta?.format!==INSIDE_FORMAT)throw Error('原室内部件丢失');
   const row=p.materials[meta.index];if(row.missingSamplers.length)material.visible=false;else inputs(THREE,material,row,maps,clock);
  }
  const before=object.onBeforeRender;
  object.onBeforeRender=function(renderer,scene,camera,geometry,material,group){
   before?.call(this,renderer,scene,camera,geometry,material,group);
   if(material.visible&&material.uniforms.sourceInsideTime){material.uniforms.sourceInsideTime.value=clock.value();material.uniformsNeedUpdate=true;}
  };
 });return root;
}
