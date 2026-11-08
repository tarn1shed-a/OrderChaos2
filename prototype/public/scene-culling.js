// Native target Y reflection and front-face XOR cancel for this source branch.
// Three keeps its own unreflected projection; do not copy the native target bit.
const FORMAT='oc2-scene-culling-v1';
const EFFECT_CULL={
 'ut_cull_lightmap_solid.bdae':true,
 'ut_lightmap_solid.bdae':false,
 'ut_lightmap_trans.bdae':false,
};
export function applySceneCulling(THREE,material,source,index,profile){
 const entry=profile?.materials?.[index];
 if(profile?.format!==FORMAT||profile.projectionRule!=='target-y-inversion-compensated-by-front-face-xor'||
  profile.transformScope!=='positive-affine-source-nodes-and-world-instances'||entry?.index!==index||
  entry.name!==source.name||entry.texture!==source.diffuse||!Object.hasOwn(EFFECT_CULL,entry.effectPath)||
  entry.cullEnabled!==EFFECT_CULL[entry.effectPath]||entry.cullFace!=='BACK'||entry.frontFaceBeforeTarget!=='CCW'||entry.technique!=='tech0')
  throw new Error('原场景剔除资源不匹配，请更新本地素材包');
 material.side=entry.cullEnabled?THREE.FrontSide:THREE.DoubleSide;
 // Retain existing web shadow behavior; this is not an original shadow pass.
 material.shadowSide=THREE.DoubleSide;
 material.userData.sceneCulling={format:FORMAT,cullEnabled:entry.cullEnabled};
 return material;
}
export function assertSceneOrientation(object){
 const determinant=object.matrixWorld.determinantAffine();
 if(!Number.isFinite(determinant)||determinant<=1e-8)
  throw new Error('原场景镜像或退化变换的剔除尚未恢复');
}
export function guardSceneOrientation(root,onChecked){
 // Object3D.clone does not copy render callbacks. Bind each final instance.
 root.traverse(object=>{
  const materials=Array.isArray(object.material)?object.material:[object.material];
  if(!object.isMesh||!materials.some(m=>m?.userData.sceneCulling?.format===FORMAT))return;
  object.onBeforeRender=function(){assertSceneOrientation(this);onChecked?.();};
 });
 return root;
}
