// Mechanical connection of original static LIGHTMAP_GRAY properties.
import {createBakedSceneMaterial as baseCreate,bindInstanceLightmap as baseBind} from './scene-baked-lighting.js?source-selection=1';
export const GRAY_FORMAT='oc2-source-scene-gray-v1';
export function grayLight(atlas,color,rate){return atlas.map((v,i)=>v*(1-rate)+color[i]*rate);}
function checked(data,source,index){
 const profile=data.sourceGray;if(!profile)return null;
 const row=profile.materials?.[index];
 if(profile.format!==GRAY_FORMAT||row?.index!==index||row.name!==source.name||typeof row.enabled!=='boolean'||
  row.enabled!==(data.sceneAlpha?.materials?.[index]?.effectPath==='ut_lightmap_gray_trans.bdae'))throw Error('原灰度材质资料不匹配');
 if(!row.enabled)return null;
 if(!Array.isArray(row.color)||row.color.length!==3||![...row.color,row.rate].every(v=>Number.isFinite(v)&&v>=0&&v<=1)||
  row.nativePropertyCopy?.nativeCPU!==true||row.nativePropertyCopy.resourceOrGPUCreated!==false||
  row.nativePropertyCopy.rate!==row.rate||!row.color.every((v,i)=>v===row.nativePropertyCopy.color?.[i]))throw Error('原灰度材质参数未核对');
 return {format:GRAY_FORMAT,color:[...row.color],rate:row.rate};
}
function uniforms(THREE,material,gray){
 material.uniforms.sourceGrayColor={value:new THREE.Vector3(...gray.color)};
 material.uniforms.sourceGrayRate={value:gray.rate};
}
export function createBakedSceneMaterial(THREE,map,source,index,data,lighting){
 const gray=checked(data,source,index),material=baseCreate(THREE,map,source,index,data,lighting);
 if(!gray)return material;
 const before='color.rgb*=texture2D(sourceAtlas,atlasUV).rgb;';
 if(material.fragmentShader.split(before).length!==2)throw Error('原图集着色器接口已变化');
 material.fragmentShader='uniform vec3 sourceGrayColor;\nuniform float sourceGrayRate;\n'+material.fragmentShader.replace(before,
  'color.rgb*=mix(texture2D(sourceAtlas,atlasUV).rgb,sourceGrayColor,sourceGrayRate);');
 uniforms(THREE,material,gray);material.userData.sourceGray=gray;return material;
}
export function bindInstanceLightmap(THREE,root,instance,lighting,atlases){
 baseBind(THREE,root,instance,lighting,atlases);
 root.traverse(object=>{
  if(!object.isMesh)return;
  for(const material of Array.isArray(object.material)?object.material:[object.material]){
   const gray=material.userData.sourceGray;if(gray?.format===GRAY_FORMAT)uniforms(THREE,material,gray);
  }
 });return root;
}
