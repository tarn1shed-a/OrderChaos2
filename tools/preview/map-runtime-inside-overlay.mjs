// Deployment-only integration. The reviewed 127-file runtime stays byte exact.
// This is the already inspected four-primary-model candidate, not a full map.
export const INSIDE_MANIFEST='/assets/source-tutorial-inside/manifest.json';
export const PREVIOUS_MANIFEST='/assets/source-temple-sampling/manifest.json';
const IMPORT="import {prepareInsideSource,createInsideSceneMaterial,prepareInsideGeometry,prepareInsideRoot,bindInsideInstance} from '/source-inside-models.js';\n";

export function stageInsideEntry(source){
 if(source.includes(IMPORT))throw Error('Inside deployment overlay already applied');
 const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Inside deployment anchor differs: '+from.slice(0,72));source=source.replace(from,to);};
 replace(PREVIOUS_MANIFEST,INSIDE_MANIFEST);
 replace("  if (data.sourceUV2?.length) g.setAttribute('TexCoord2',new THREE.Float32BufferAttribute(data.sourceUV2,2));",
  "  if (data.sourceUV2?.length) g.setAttribute('TexCoord2',new THREE.Float32BufferAttribute(data.sourceUV2,2));\n  prepareInsideGeometry(THREE,g,data);");
 replace("  await prepareDynamicWind(data,async url=>{const r=await fetch(url);if(!r.ok)throw Error('原摇动程序缺失');return r.text();});",
  "  await prepareDynamicWind(data,async url=>{const r=await fetch(url);if(!r.ok)throw Error('原摇动程序缺失');return r.text();});\n  await prepareInsideSource(THREE,data,assets.textures,texture);");
 replace('      if(data.sourceMixedWall)return createMixedWallMaterial',
  '      if(data.sourceInsideMaterials)return createInsideSceneMaterial(THREE,tex,mat,index,data,bakedLighting);\n      if(data.sourceMixedWall)return createMixedWallMaterial');
 replace('  partLightmaps.prepare(root,entry,data);','  prepareInsideRoot(root,data);\n  partLightmaps.prepare(root,entry,data);');
 replace('        bindDynamicWind(THREE,model,origin,windClock,canvas);',
  '        bindInsideInstance(THREE,model,windClock);\n        bindDynamicWind(THREE,model,origin,windClock,canvas);');
 return IMPORT+source;
}

// Reuse the reviewed scheduler, widening only its manifest and second-sampler
// dependency set. Existing terrain/windows/background scheduling stays intact.
export async function stageInsidePlan(basePlan,texts,closure){
 if(!texts.has(INSIDE_MANIFEST))throw Error('Inside deployment manifest missing');
 const full=JSON.parse(texts.get(INSIDE_MANIFEST));
 if(full.sourceInsideRecovery?.format!=='oc2-source-tutorial-inside-models-v1')throw Error('Inside manifest profile differs');
 const aliased=new Map(texts);aliased.set(PREVIOUS_MANIFEST,texts.get(INSIDE_MANIFEST));
 const resolve=(entry,documents)=>{
  if(documents!==aliased){
   documents=new Map(documents);
   const curated=JSON.parse(documents.get(PREVIOUS_MANIFEST));
   for(const row of curated.scenery){
    const data=JSON.parse(texts.get(row.url));
    for(const mat of data.sourceInsideMaterials?.materials||[]){
     if(mat.missingSamplers.length)continue;
     for(const sampler of Object.values(mat.samplers))if(full.textures[sampler.texture])curated.textures[sampler.texture]=full.textures[sampler.texture];
    }
   }
   documents.set(INSIDE_MANIFEST,JSON.stringify(curated));
  }
  return closure(entry,documents);
 };
 const plan=await basePlan(aliased,resolve);
 return {...plan,scope:{...plan.scope,insidePrimaryModels:4,insideDynamicLiftRestored:false,wholeMapAccepted:false}};
}
