// 111b8c4/113235c store materials in part order; 33faa0 indexes DAT by that order.
import {bindInstanceLightmap as previousBind} from './source-dynamic-wind.js?dynamicWind=1';
export const PART_LIGHTMAP_FORMAT='oc2-source-part-lightmaps-v1';
export function validatePartLightmaps(policy){
 if(policy?.format!==PART_LIGHTMAP_FORMAT||policy.slot!==0||policy.profile!=='APK_Default'||policy.originalDeviceObserved!==false||!Array.isArray(policy.models))throw Error('原部件光照资料未核对');
 const seen=new Set();
 for(const row of policy.models){
  const order=row.partToMaterial;
  if(typeof row.model!=='string'||seen.has(row.model)||!/^[a-f0-9]{64}$/.test(row.sourceSHA256)||!Array.isArray(order)||!order.length||order.length>32||order.some((v,i)=>!Number.isSafeInteger(v)||v<0||v>=order.length)||new Set(order).size!==order.length)throw Error('原部件顺序不匹配');
  seen.add(row.model);
 }
 return policy;
}
export function createPartLightmapContext(policy,canvas){
 validatePartLightmaps(policy);const models=new Map(policy.models.map(r=>[r.model,r]));
 return {
  prepare(root,entry,data){
   const row=models.get(entry.model);if(!row)return;
   if(data.sourceSHA256!==row.sourceSHA256||data.meshes?.length!==1||data.materials.length!==row.partToMaterial.length||JSON.stringify(data.meshes[0].groups?.map(g=>g.material))!==JSON.stringify(row.partToMaterial))throw Error('原模型部件与光照顺序不符');
   root.userData.sourcePartLightmaps={format:PART_LIGHTMAP_FORMAT,model:entry.model,partToMaterial:[...row.partToMaterial]};
  },
  bind(THREE,root,instance,lighting,atlases){
   const meta=root.userData.sourcePartLightmaps,row=models.get(instance.model);
   if(!row)return previousBind(THREE,root,instance,lighting,atlases);
   if(meta?.format!==PART_LIGHTMAP_FORMAT||meta.model!==instance.model||JSON.stringify(meta.partToMaterial)!==JSON.stringify(row.partToMaterial))throw Error('原实例部件资料缺失');
   // Leave material-table order and draw groups intact. Only the existing
   // binder's ordinal input changes, on per-instance copies of the templates.
   root.traverse(object=>{
    if(!object.isMesh)return;
    if(!Array.isArray(object.material)||JSON.stringify(object.geometry.groups.map(g=>g.materialIndex))!==JSON.stringify(row.partToMaterial))throw Error('原实例绘制部件不匹配');
    object.material=object.material.map((template,index)=>{
     if(template.userData.sceneBakedLighting?.index!==index)throw Error('原材质编号不匹配');
     const material=template.clone();material.uniforms=template.uniforms;material.userData.sceneBakedLighting={...template.userData.sceneBakedLighting,index:row.partToMaterial.indexOf(index),sourceMaterialIndex:index};return material;
    });
   });
   previousBind(THREE,root,instance,lighting,atlases);
   root.traverse(object=>{if(!object.isMesh)return;for(const material of object.material){const m=material.userData.sceneBakedLighting;material.userData.sceneBakedLighting={...m,index:m.sourceMaterialIndex,sourcePartOrdinal:m.index};}});
   root.userData.sceneLightmap.partOrderVerified=true;
   if(canvas)canvas.dataset.sourcePartLightmapInstances=String(Number(canvas.dataset.sourcePartLightmapInstances||0)+1);
   return root;
  }
 };
}
