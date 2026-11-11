// Only original zero-speed vegetation is admitted. No substitute wind or clock.
import {createBakedSceneMaterial as grayCreate,bindInstanceLightmap as grayBind} from './source-gray-materials.js?sourceGray=1';
import {createBakedSceneMaterial as baseCreate} from './scene-baked-lighting.js?source-selection=1';
export const WIND_FORMAT='oc2-source-wind-identity-v1';
const EFFECT='ut_lightmap_shake_gray_trans.bdae';
export function validateWindIdentity(data,source,index){
 const effect=data.sceneAlpha?.materials?.[index]?.effectPath,profile=data.sourceWindIdentity;
 if(!profile){if(effect===EFFECT)throw Error('原摇动参数未核对');return false;}
 const row=profile.materials?.[index],gray=data.sourceGray?.materials?.[index];
 if(profile.format!==WIND_FORMAT||profile.zeroDisplacementVerified!==true||profile.dynamicRendererInputsRestored!==false||
  profile.semantic?.sourceSemantic!==6||profile.semantic.runtimeSemantic!==3||profile.semantic.runtimeName!=='texcoord2'||profile.semantic.nativeCPU!==true||
  row?.index!==index||row.name!==source.name||typeof row.enabled!=='boolean'||row.enabled!==(effect===EFFECT))throw Error('原摇动材质资料不匹配');
 if(!row.enabled)return false;
 if(row.speed!==0||row.nativePropertyCopy?.value!==0||row.nativePropertyCopy.nativeCPU!==true||row.nativePropertyCopy.resourceOrGPUCreated!==false||
  data.sourceGray?.format!=='oc2-source-scene-gray-v1'||gray?.index!==index||gray.name!==source.name||gray.enabled!==true||
  !Array.isArray(gray.color)||gray.color.length!==3||![...gray.color,gray.rate].every(v=>Number.isFinite(v)&&v>=0&&v<=1)||
  gray.nativePropertyCopy?.nativeCPU!==true||gray.nativePropertyCopy.resourceOrGPUCreated!==false||gray.nativePropertyCopy.rate!==gray.rate||!gray.color.every((v,i)=>v===gray.nativePropertyCopy.color?.[i])||
  !Array.isArray(data.meshes)||!data.meshes.length||data.meshes.some(m=>m.sourceWindAttributes?.sourceSemantic!==6||m.sourceWindAttributes.runtimeSemantic!==3||m.sourceWindAttributes.type!==6||m.sourceWindAttributes.components!==2||
   !Array.isArray(m.sourceUV2)||m.sourceUV2.length!==m.positions.length/3*2||!m.sourceUV2.every(Number.isFinite)))throw Error('原零摇动分支输入不完整');
 return true;
}
function uniforms(THREE,material,gray){material.uniforms.sourceGrayColor={value:new THREE.Vector3(...gray.color)};material.uniforms.sourceGrayRate={value:gray.rate};}
export function createBakedSceneMaterial(THREE,map,source,index,data,lighting){
 const wind=validateWindIdentity(data,source,index);
 if(!wind){
  // Solid trunk within a verified wind model has no gray branch.
  if(data.sourceWindIdentity)return baseCreate(THREE,map,source,index,data,lighting);
  return grayCreate(THREE,map,source,index,data,lighting);
 }
 const material=baseCreate(THREE,map,source,index,data,lighting),gray=data.sourceGray.materials[index],before='color.rgb*=texture2D(sourceAtlas,atlasUV).rgb;';
 if(material.fragmentShader.split(before).length!==2)throw Error('原图集着色器接口已变化');
 material.fragmentShader='uniform vec3 sourceGrayColor;\nuniform float sourceGrayRate;\n'+material.fragmentShader.replace(before,'color.rgb*=mix(texture2D(sourceAtlas,atlasUV).rgb,sourceGrayColor,sourceGrayRate);');
 uniforms(THREE,material,gray);material.userData.sourceWindIdentity={format:WIND_FORMAT,speed:0,color:[...gray.color],rate:gray.rate};return material;
}
export function bindInstanceLightmap(THREE,root,instance,lighting,atlases){
 grayBind(THREE,root,instance,lighting,atlases);
 root.traverse(object=>{if(!object.isMesh)return;for(const m of Array.isArray(object.material)?object.material:[object.material]){const g=m.userData.sourceWindIdentity;if(g?.format===WIND_FORMAT)uniforms(THREE,m,g);}});return root;
}
