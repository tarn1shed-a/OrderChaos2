// Capability adapters for the shared geometry traversal. Old artifacts remain
// byte-identical. These checks carry source evidence, never GPU/role success.
export const finite=(v,n)=>Array.isArray(v)&&(n===undefined||v.length===n)&&v.every(Number.isFinite);
export const same=(a,b)=>a===b||Boolean(a&&b&&typeof a==='object'&&typeof b==='object'&&Array.isArray(a)===Array.isArray(b)&&
 Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(k=>Object.hasOwn(b,k)&&same(a[k],b[k])));
export const ARMOR_ROOT='original-rigid-armor-root-v1';
export function checkArmorRoot(row,source,identity){
 if(identity.screen!=='CharacterChooseClass'||identity.request.displayId!==2701||identity.race!==2||identity.gender!==1||identity.professionIndex!==0||
  row.kind!==ARMOR_ROOT||row.slot!==14||row.itemKey!==2481179||row.source!=='model/item/armor/6_feet/oc2_elf_f_upd13_sea_pvp_heavy_feet_l.bdae'||
  row.sourceRequest?.slot!==14||row.sourceRequest.itemKey!==row.itemKey||row.sourceRequest.path!==row.source||
  row.mount?.format!=='oc2-original-armor14-rigid-root-mount-v1'||row.mount.slot!==14||row.mount.attachmentTarget!=='actorRoot'||
  row.mount.sourceCPUContractSHA256!=='346895ecb4bcacbc5f0dadc06d7c34ab8b812130ac7c547d6b176304f60c2be2'||
  row.mount.rootAttachmentBranchProved!==true||row.mount.skinWeightsInvented!==false||
  source?.source!==row.source||source.sourceBDAESHA256!=='6718de7f0c40f1163edcafdcfeb420849679420ba1a83fe8f17d745df89dff8f'||
  source.sourceControllerCount!==0||source.meshes?.length!==1||source.meshes[0].vertexCount!==316||source.rig)
  throw Error('Original rigid armor root evidence does not cover this source');
 return row.mount;
}
export function checkedPass(row){
 const states=row?.sourceEffectProfiles?.profiles?.map(p=>p.state);
 if(states?.length!==2||!same(states[0],states[1])||states[0].blendEnabled||!states[0].depthTestEnabled||
  !states[0].depthWriteEnabled||states[0].depthFunctionGL!==515||!row.samplers||!row.addressing)
  throw Error('Original material pass has no proved shared bridge');
 return row;
}
export function sourceWrap(THREE,value,capabilities,address,axis){
 if(value===0)return THREE.RepeatWrapping;
 if(value===1||value===2)return THREE.ClampToEdgeWrapping;
 if(value!==4)throw Error('Unproved original sampler address');
 const proof=address?.sourceMirrorRequestProof;
 if(axis!==0||proof?.sourceCPUReceiptSHA256!=='f58b5a25cbf3b4cc1cfe8ae8b8d4bcd9edf0b06324d9133d23c1d359d2bb9438'||
  proof.sourceModelSHA256!=='0515d1f5f829ef1ad65b8be3f7cf797e0441aead2a6f329e088ce64856084a2b'||
  proof.sampler!=='texture'||proof.axis!==0||proof.sourceEnum!==4||proof.originalCapabilityField!=='driver+1b2.bit2'||
  proof.supportedGLValue!==33648||proof.unsupportedPreservesPreviousState!==true||
  proof.actualAndroidCapabilitiesObserved!==false||proof.hostCapabilityMustBeObserved!==true||
  address.sourceRequest?.addressU!==4||capabilities?.contextType!=='webgl2'||capabilities.mirrorRepeat!==true)
  throw Error('Original Mirror branch needs its exact source proof and observed current capability');
 return THREE.MirroredRepeatWrapping;
}
