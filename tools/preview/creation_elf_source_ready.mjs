// Exact source Elf-male st222 only. No generic missing-image fallback.
// Texture readiness is attached to real host Texture objects in a private map.
export const ELF_CONDITIONAL_FORMAT='oc2-elf-male-conditional-creation-candidate-v1';
export const ELF_CONTRACT_SHA='51a825509778cec34f72369b3a57cb2cbcec2d5102954f2b5eb2b0ebc2c3dc3e';
export const ELF_FAILURE_SHA='3d8aa34c783f622c45139c7a868773880b0a5589767e0297608b640842aed5db';
export const ELF_SOURCE_PACKET_SHA='6c3c300912f2cc7021a3784c601a7229b327916ee89c9a34ac72390b82f680a8';
export const ELF_MISSING_PATH='texture/oc2_human_m_light_sunken_chest_brown_d.tga';
export const ELF_PART='model/item/armor/3_chest/oc2_elf_m_light_sunken_chest.bdae';
export const ELF_PART_SHA='2c525bb80bb5aea758326a33380dd1bbb78e9739b981b9363a5a7cb772aba1d9';
export const ELF_SAMPLERS=Object.freeze({"texture":{"sourcePath":"texture/oc2_human_m_light_sunken_chest_d.tga","sourceSHA256":"d5685df350aa04da0e588b42b1588ba2134098f379ebdeb2150869086c490aee","url":"/assets/d5685df350aa04da0e588b42b1588ba2134098f379ebdeb2150869086c490aee.png","pngSHA256":"038d6d21d920773ffe2293c39207984fb0fbb75053fe8de65e9fb09d4beb09aa","width":256,"height":256},"normalMap":{"sourcePath":"texture/oc2_human_m_light_sunken_chest_n.tga","sourceSHA256":"5f8ef764db6cc7eca331bda0dde7bd7ece0051620acf96af74c09fc571f401da","url":"/assets/5f8ef764db6cc7eca331bda0dde7bd7ece0051620acf96af74c09fc571f401da.png","pngSHA256":"322c5155ad60d58b48e3d7e61198ace253f8c1541f476edbb5af050079c5db5b","width":256,"height":256},"maskMap":{"sourcePath":"texture/oc2_human_m_light_sunken_chest_s.tga","sourceSHA256":"150973aa380c71fbc9047e895d2464b7752c8507555416061ac4abbd2ed7f091","url":"/assets/150973aa380c71fbc9047e895d2464b7752c8507555416061ac4abbd2ed7f091.png","pngSHA256":"79ef72c27c40da595011c33c13b7910711d4b7d89db6b525f6728389943793c6","width":256,"height":256},"diffusePal":{"sourcePath":"texture/Fx_BARLA_00_basic.tga","sourceSHA256":"2d2db39a5c7a8969bbac82a138bfd9ff3d64a1f42b9f8cdd815268698af88d59","url":"/assets/2d2db39a5c7a8969bbac82a138bfd9ff3d64a1f42b9f8cdd815268698af88d59.png","pngSHA256":"c38fee893a3471acef2bbeaf1ff12048eb37756d3f9833c1dc48091621ae927c","width":256,"height":8},"specularPal":{"sourcePath":"texture/Fx_SPEC_00_asset.tga","sourceSHA256":"ba65cd1c84a7445882879209ba3cfa30a38d8607bf0f3e99d73c3a89db2509b9","url":"/assets/ba65cd1c84a7445882879209ba3cfa30a38d8607bf0f3e99d73c3a89db2509b9.png","pngSHA256":"6b36ab0f5bb6598d6c838d17f3703912ad4f26d692be3514394e6756632543d8","width":256,"height":8},"specularPalBack":{"sourcePath":"texture/Fx_SPEC_00_basic_01.tga","sourceSHA256":"074d7afacaec8cd3730f15fad0de93209f900b7b95350a102ac61e509b79bcb5","url":"/assets/074d7afacaec8cd3730f15fad0de93209f900b7b95350a102ac61e509b79bcb5.png","pngSHA256":"d91f9f4a28e1fe86b0a11f8e1005836ac71c8c3bb4211c96bce757af83abb4fe","width":256,"height":8}});
const receipts=new WeakMap();
for(const definition of Object.values(ELF_SAMPLERS))Object.freeze(definition);
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const keys=o=>Object.keys(o||{}).sort().join(',');
export function checkedElfConditionalPolicy(manifest){
 const p=manifest?.retainedSourceMaterial,missing=manifest?.missingSourceOverrides;
 if(manifest?.format!==ELF_CONDITIONAL_FORMAT||manifest.key!=='elf-male'||manifest.race!==2||manifest.gender!==0||
  manifest.originalDisplayId!==2046||manifest.sourceModelId!==33||manifest.sourceTraceSHA256!==ELF_SOURCE_PACKET_SHA||manifest.creationPreviewAdmitted!==false||
  manifest.appearanceComplete!==false||manifest.hostConditionalDisplay!==true||manifest.originalAndroidFinalAppearanceKnown!==false||manifest.originalGPUObserved!==false||
  p?.format!=='oc2-exact-elf-st222-missing-stream-policy-v1'||p.contractSHA256!==ELF_CONTRACT_SHA||
  p.originalFailureEvidenceSHA256!==ELF_FAILURE_SHA||p.sourceMaterialName!=='st222'||p.sourcePartPath!==ELF_PART||
  p.sourcePartSHA256!==ELF_PART_SHA||p.materialIndex!==2||p.hostSourceMaterialReadyRequired!==true||p.originalAndroidFinalAppearanceKnown!==false||
  keys(p.samplers)!==keys(ELF_SAMPLERS)||Object.entries(ELF_SAMPLERS).some(([name,wanted])=>!same(p.samplers[name],wanted))||
  !same(p.requestedOverride,{channel:0,path:ELF_MISSING_PATH,availableOriginalPayloads:0,overrideApplied:false,overrideCacheWritten:false})||
  !Array.isArray(missing)||missing.length!==1||missing[0].slot!==11||missing[0].material!=='st222'||missing[0].requestedPath!==ELF_MISSING_PATH||
  missing[0].availableOriginalPayloads!==0||missing[0].overrideApplied!==false||missing[0].overrideCacheWritten!==false||
  missing[0].originalMissingStreamEvidenceSHA256!==ELF_FAILURE_SHA||missing[0].permittedOnlyAfterRealHostSourceMaterialReady!==true)
  throw Error('Only the exact source missing-stream policy is covered');
 const row=manifest.materials?.find(row=>row.index===p.materialIndex);
 if(row?.sourceMaterialName!=='st222'||row.sourceModel!==ELF_PART||row.effectPath!=='lt_pal_normal_trans.bdae'||
  keys(row.samplers)!==keys(ELF_SAMPLERS)||Object.entries(ELF_SAMPLERS).some(([name,wanted])=>row.samplers[name]!==wanted.url||
   row.addressing?.[name]?.source!==wanted.sourcePath||row.addressing[name].sourceSHA256!==wanted.sourceSHA256))
  throw Error('All exact BDAE-declared material inputs are required');
 return p;
}
function decodedTexture(THREE,texture,definition){
 const image=texture?.image,bitmap=typeof globalThis.ImageBitmap==='function'&&image instanceof globalThis.ImageBitmap;
 if(!(texture instanceof THREE.Texture)||texture.flipY!==false||texture.colorSpace!==THREE.NoColorSpace||
  !image||image.width!==definition.width||image.height!==definition.height||
  ('complete' in image&&image.complete!==true)||
  (texture instanceof THREE.DataTexture?(!ArrayBuffer.isView(image.data)||image.data.byteLength!==definition.width*definition.height*4):
   (!bitmap&&(image.complete!==true||image.naturalWidth!==definition.width||image.naturalHeight!==definition.height))))
  throw Error('Retained source texture has not actually decoded');
}
async function browserDecode(THREE,bytes){
 if(typeof globalThis.createImageBitmap!=='function')throw Error('Verified source ImageBitmap decoding is unavailable');
 // Verified bytes are decoded in memory, without an image-src/blob URL fetch.
 // These frozen PNGs have no orientation/color-profile chunks. Do not flip,
 // premultiply alpha, resize, or perform decoder color-space conversion.
 const bitmap=await globalThis.createImageBitmap(new Blob([bytes],{type:'image/png'}),
  {imageOrientation:'from-image',premultiplyAlpha:'none',colorSpaceConversion:'none'});
 try{
  const texture=new THREE.Texture(bitmap);let closed=false;
  texture.addEventListener('dispose',()=>{if(!closed){closed=true;bitmap.close();}});
  return texture;
 }catch(error){bitmap.close();throw error;}
}
export async function loadElfConditionalTexture(THREE,url,sampler,{fetcher=globalThis.fetch,decodeForHost,documentURL=globalThis.location?.href}={}){
 const definition=ELF_SAMPLERS[sampler];if(!definition)throw Error('Unknown conditional sampler');
 const resource=new URL(url,documentURL),document=new URL(documentURL);
 if(resource.origin!==document.origin||resource.search||resource.hash||!/^\/[A-Za-z0-9_./-]+$/.test(resource.pathname)||
  resource.pathname.includes('..')||resource.pathname.includes('//')||!resource.pathname.endsWith(definition.url))
  throw Error('Conditional sampler escaped its exact source resource');
 const response=await fetcher(resource.href);
 if(!response.ok)throw Error('Retained source sampler unavailable');
 const bytes=await response.arrayBuffer(),digest=await crypto.subtle.digest('SHA-256',bytes);
 const actual=[...new Uint8Array(digest)].map(v=>v.toString(16).padStart(2,'0')).join('');
 if(actual!==definition.pngSHA256)throw Error('Retained source image bytes differ');
 let texture;
 try{
  texture=await(decodeForHost?decodeForHost(THREE,bytes,sampler):browserDecode(THREE,bytes));
  texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;texture.needsUpdate=true;
  decodedTexture(THREE,texture,definition);
  receipts.set(texture,Object.freeze({sampler,pngSHA256:actual,width:definition.width,height:definition.height,
   verifiedBytes:bytes.byteLength,decoder:decodeForHost?'explicit-host-decoder':'browser-image-bitmap',originalGPUObserved:false}));
  return texture;
 }catch(error){texture?.dispose();throw error;}
}
export function inheritElfTextureReceipt(original,clone){
 const proof=receipts.get(original);if(!proof)return false;
 if(!clone?.isTexture||clone.image!==original.image||clone.source!==original.source)throw Error('Source texture clone does not retain its verified image');
 receipts.set(clone,proof);return true;
}
export function completeElfConditionalPreview(THREE,{manifest,data,preview}){
 const p=checkedElfConditionalPolicy(manifest),source=data.materials[p.materialIndex];
 if(data.sourceCreation?.displayId!==2046||data.sourceCreation.sourceModelId!==33||source?.name!=='st222'||source.sourceModel!==ELF_PART||
  !(preview?.root instanceof THREE.Group)||!Array.isArray(preview.meshes)||preview.manifest!==manifest)
  throw Error('Conditional source model/material has not been constructed');
 const hosts=preview.meshes.filter((object,index)=>object.visible&&data.meshes[index]?.groups.some(g=>g.material===p.materialIndex));
 if(hosts.length!==1||!(hosts[0] instanceof THREE.SkinnedMesh)||!(hosts[0].skeleton instanceof THREE.Skeleton)||!hosts[0].skeleton.bones.length)throw Error('Actual original st222 host mesh required');
 const object=hosts[0],material=object.material[p.materialIndex],row=manifest.materials.find(m=>m.index===p.materialIndex);
 if(!(material instanceof THREE.RawShaderMaterial)||material.userData.sourceAttributePreview!==true||material.depthTest!==true||material.depthWrite!==true||
  material.blending!==THREE.NoBlending||material.depthFunc!==THREE.LessEqualDepth||material.side!==THREE.DoubleSide||
  material.defines?.HARDWARE_SKINNING_CUSTOM_BONE_COUNT!==object.skeleton.bones.length||row.defines.some(d=>material.defines[d]!==1))
  throw Error('Actual original source material is not ready');
 const bindings=[],verified=[];
 for(const[sampler,wanted]of Object.entries(ELF_SAMPLERS)){
  const texture=material.uniforms[sampler==='texture'?'sourceTexture':sampler]?.value,proof=receipts.get(texture),a=row.addressing[sampler];
  decodedTexture(THREE,texture,wanted);
  if(proof?.sampler!==sampler||proof.pngSHA256!==wanted.pngSHA256||
   texture.wrapS!==(a.addressU===0?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping)||
   texture.wrapT!==(a.addressV===0?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping))
   throw Error('Source sampler lacks its actual checked load/decoded image');
  bindings.push(texture);verified.push({...proof,sourceSHA256:wanted.sourceSHA256});
 }
 // This branch deliberately performs no uniform setter and writes no override
 // cache. All six already-created original bindings remain the same objects.
 const unchanged=Object.keys(ELF_SAMPLERS).every((sampler,index)=>material.uniforms[sampler==='texture'?'sourceTexture':sampler].value===bindings[index]);
 if(!unchanged)throw Error('Original source binding was replaced');
 return Object.freeze({format:'oc2-elf-st222-host-source-ready-v1',display:2046,hostSourceMaterialReady:true,
  verifiedSamplers:verified,existingBindingsUnchanged:6,omittedOverride:ELF_MISSING_PATH,overrideApplied:false,overrideCacheWritten:false,
  appearanceComplete:false,originalAndroidFinalAppearanceKnown:false,originalGPUObserved:false});
}
