// Original broken-wall pass; browser frame submission/sorting remain adapters.
import {BAKED_FORMAT,BAKED_VERTEX,BAKED_FRAGMENT} from './scene-baked-lighting.js?source-selection=1';
export const MIXED_WALL_FORMAT='oc2-source-mixed-wall-v1';
export function validateMixedWall(source,index,data){
 const p=data?.sourceMixedWall,b=data?.sceneBakedLighting?.materials?.[index];
 if(p?.format!==MIXED_WALL_FORMAT||data.source!=='model/scene/main_human/hum_village_wall_broken01.bdae'||
  p.modelBRESSHA256!=='785bcd221c47ed65a01e3fe4c34e73c8bd9dbfdd9934a387fce67ea0ff622d7e'||
  p.effect!=='ut_lightmap_blend.bdae'||p.effectBRESSHA256!=='d7eeed62283e2cf49a6096ba89ec540d084a6d4b57fb7694a27c5b47a275c244'||
  index!==0||source.name!=='Material__689'||p.material!==source.name||p.texture!==source.diffuse||
  source.diffuse!=='texture/hum_village_wall_broken01.tga'||p.technique?.name!=='tech0'||
  p.alpha?.mode!=='split-red'||p.alpha.width!==128||p.alpha.height!==128||
  p.blend?.equation!==32774||p.blend.src!==770||p.blend.dst!==771||p.blend.separateAlpha!==false||
  p.depthTest!==true||p.depthWrite!==false||p.depthFunction!==515||p.cull!==false||p.sourcePasses!==1||p.alphaTest!==false||
  p.nativeStateProof?.nativeCPU!==true||p.originalGPUObserved!==false||p.hostSubmissionAndSorting!==true||
  data.sceneBakedLighting?.format!==BAKED_FORMAT||b?.index!==0||b.name!==source.name||b.texture!==source.diffuse||b.sourceLightMap!=='texture/lightmap.tga')
  throw Error('原破损墙混合材质资料不匹配');
 return p;
}
export function createMixedWallMaterial(THREE,map,source,index,data,lighting){
 validateMixedWall(source,index,data);
 if(map?.colorSpace!==THREE.NoColorSpace||map.flipY!==false||map.image?.width!==128||map.image?.height!==128)throw Error('原破损墙贴图资料不匹配');
 const m=new THREE.ShaderMaterial({vertexShader:BAKED_VERTEX,fragmentShader:BAKED_FRAGMENT,
  uniforms:{...lighting.uniforms,sourceDiffuse:{value:map},sourceAtlas:{value:null},sourceUVTransform:{value:new THREE.Vector4(0,0,1,1)}},
  defines:{},transparent:true,blending:THREE.CustomBlending,blendEquation:THREE.AddEquation,
  blendSrc:THREE.SrcAlphaFactor,blendDst:THREE.OneMinusSrcAlphaFactor,
  blendEquationAlpha:THREE.AddEquation,blendSrcAlpha:THREE.SrcAlphaFactor,blendDstAlpha:THREE.OneMinusSrcAlphaFactor,
  premultipliedAlpha:false,side:THREE.DoubleSide,forceSinglePass:true,
  depthTest:true,depthWrite:false,depthFunc:THREE.LessEqualDepth,toneMapped:false,lights:false});
 m.map=map;m.alphaTest=0;
 m.userData.sceneBakedLighting={format:BAKED_FORMAT,index};
 m.userData.sceneCulling={format:'oc2-scene-culling-v1',cullEnabled:false};
 m.userData.sourceMixedWall={format:MIXED_WALL_FORMAT,hostSubmissionAndSorting:true,originalGPUObserved:false};
 return m;
}
export function bindMixedWallInstance(root,instance,canvas){
 root.traverse(object=>{
  if(!object.isMesh)return;
  const materials=Array.isArray(object.material)?object.material:[object.material];
  if(!materials.some(m=>m.userData.sourceMixedWall))return;
  const expected=instance.id===1047555168?[-39,-2]:instance.id===410878536?[-38,-1]:null;
  if(!expected||expected.some((v,i)=>v!==instance.tile[i]))throw Error('原破损墙摆放资料不匹配');
  // No unverified original shadow pass. Retain the source color pass only.
  object.castShadow=false;object.receiveShadow=false;
  const before=object.onBeforeRender;
  object.onBeforeRender=function(...args){
   before?.apply(this,args);
   const seen=JSON.parse(canvas.dataset.sourceMixedWalls??'{}');
   seen[instance.id]={tile:instance.tile,draws:(seen[instance.id]?.draws??0)+1,triangles:2,
    blend:'SRC_ALPHA,ONE_MINUS_SRC_ALPHA',depthWrite:false,singlePass:true,hostSorting:true};
   canvas.dataset.sourceMixedWalls=JSON.stringify(seen);
  };
 });return root;
}
