// Stage1/2 source actor geometry/material bridge. This is a WebGL adaptation,
// not a replacement original model-ready reply or a played-role permission.
import {checkedStageCandidate} from './stage_switch.mjs';
const finite=(values,n)=>Array.isArray(values)&&(n===undefined||values.length===n)&&values.every(Number.isFinite);
const same=(a,b)=>{
 if(a===b)return true;
 if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;
 const keys=Object.keys(a).sort(),other=Object.keys(b).sort();
 return keys.length===other.length&&keys.every((k,i)=>k===other[i]&&same(a[k],b[k]));
};
const attributes=[['Vertex','position'],['Normal','normal'],['TexCoord0','uv'],['Tangent','sourceTangent'],['Binormal','sourceBinormal'],['SkinWeights','skinWeight'],['SkinIndices','skinIndex']];
const EFFECT='Effects/skill/mage/electric_arc_aggregated_cast_hand_loop.beff';
const EFFECT_SHA='1e903b18b1e07bca346d3528110a9c50d3048879fc88b001242896c56ab6458e';
const GATE_SHA='922e4b8710f93d10525abc7d022afd011d1d89dc6ded37662a90cf2510fdd242';
export function checkedIndependentBodyEffectGate(manifest,identity){
 const source=identity.sourceModel,gate=manifest.sourceIndependentEffectGate;
 if(identity.screen!=='CharacterChooseClass'||identity.request.displayId!==2116||identity.race!==2||identity.gender!==1||identity.professionIndex!==2||
  identity.profession!==2||source.ID!==62||source.Flags!==4||source.ModelPath!=='model/npc/character/elf/female/oc2_elf_f_body_01.bdae'||
  source.eff_mod_node1!=='Dummy_Left_Hand-node'||source.eff_mod_eff1!==EFFECT||
  [2,3,4,5,6].some(i=>source['eff_mod_node'+i]!==''||source['eff_mod_eff'+i]!=='')||
  manifest.appearanceComplete!==false||manifest.mainBodyAppearanceComplete!==true)
  throw Error('Original independent effect gate is not this exact Model62/display2116');
 const expectedGate={format:'oc2-source-mainbody-independent-effect-gate-v1',sourceContractSHA256:GATE_SHA,
  displayId:2116,sourceModelId:62,sourceBodyPath:source.ModelPath,
  sourceOrder:['mainbody virtual58 returnbit0','initial idle','Display.Effect1 request','parts/weapons','body-visible'],
  effectResultRequiredByFinalVisibleFragment:false,wholeNativeModelOrEffectSuccessSupplied:false,
  requiresActualHostBodyMaterials:true,effectConstructed:false,appearanceComplete:false};
 const expectedEffects=[{sourceField:'creaturedisplayinfo.Effect1',sourceValue:'Dummy_Left_Hand-node,'+EFFECT+',100',
  node:'Dummy_Left_Hand-node',path:EFFECT,scale:1,sourceResourceSHA256:EFFECT_SHA,sourceResourceBytes:4704,
  sourceResourceExists:true,sourceRequestConsumer:'9d5104->3360a0',resourceDecoded:false,effectConstructed:false,
  originalGPUObserved:false,status:'source-effect-not-restored'}];
 if(!same(gate,expectedGate)||!same(manifest.modelEffects,expectedEffects))throw Error('Original body/effect visibility proof or unresolved effect differs');
 return gate;
}
export function checkedStageModel(manifest,data,identity){
 checkedStageCandidate(manifest,identity);
 const source=data?.sourceCreation;
 if(data?.format!=='bdae946-character-v1'||data.source!==identity.sourceModel.ModelPath||
  source?.displayId!==identity.request.displayId||source.stage!==identity.panel||source.screen!==identity.screen||
  source.race!==identity.race||source.gender!==identity.gender||source.professionIndex!==identity.professionIndex||source.profession!==identity.profession||
  source.sourceModelId!==identity.sourceModel.ID||source.originalFloatWeightsPreserved!==true||source.createdRole!==false||
  !Array.isArray(data.meshes)||!Array.isArray(data.materials)||!Array.isArray(data.rig?.nodes)||!Array.isArray(data.rig?.skins)||
  JSON.stringify(source.visibleMeshIndices)!==JSON.stringify(manifest.visibleMeshIndices))throw Error('Original stage actor does not match its own display/model');
 if(!Array.isArray(manifest.attachments)||!Array.isArray(manifest.modelEffects))throw Error('Original source effects/attachments absent');
 const requiresEffect=manifest.modelEffects.length||[1,2,3,4,5,6].some(i=>identity.sourceModel['eff_mod_eff'+i]);
 if(requiresEffect)checkedIndependentBodyEffectGate(manifest,identity);
 else if(manifest.sourceIndependentEffectGate!=null)throw Error('Independent effect gate attached to a different source model');
 if(manifest.animationScope?.initialSourceName!=='idle'||manifest.animationScope.finiteInitialClipOnly!==true||manifest.animationScope.noInventedInfiniteIdleLoop!==true)
  throw Error('Unproved source selection animation continuation');
 if(data.clips?.length!==1||data.clips[0].name!=='idle'||data.clips[0].duration!==manifest.idleDuration||!(manifest.idleDuration>0))throw Error('Original finite stage idle differs');
 return manifest;
}
function checkedMaterial(row){
 const profiles=row?.sourceEffectProfiles?.profiles,states=profiles?.map(p=>p.state);
 if(states?.length!==2||JSON.stringify(states[0])!==JSON.stringify(states[1])||states[0].blendEnabled||!states[0].depthTestEnabled||
  !states[0].depthWriteEnabled||states[0].depthFunctionGL!==515||!row.samplers||!row.addressing)throw Error('Uncovered original stage material pass');
 return row;
}
function wrap(THREE,value,capabilities,address,axis){
 if(value===0)return THREE.RepeatWrapping;
 if(value===1||value===2)return THREE.ClampToEdgeWrapping;
 if(value===4){
  const proof=address?.sourceMirrorRequestProof;
  if(axis!==0||proof?.sourceCPUReceiptSHA256!=='f58b5a25cbf3b4cc1cfe8ae8b8d4bcd9edf0b06324d9133d23c1d359d2bb9438'||
   proof.sourceModelSHA256!=='0515d1f5f829ef1ad65b8be3f7cf797e0441aead2a6f329e088ce64856084a2b'||
   proof.sampler!=='texture'||proof.axis!==0||proof.sourceEnum!==4||proof.originalCapabilityField!=='driver+1b2.bit2'||
   proof.supportedGLValue!==33648||proof.unsupportedPreservesPreviousState!==true||
   proof.actualAndroidCapabilitiesObserved!==false||proof.hostCapabilityMustBeObserved!==true||
   address.sourceRequest?.addressU!==4||capabilities?.contextType!=='webgl2'||capabilities.mirrorRepeat!==true)
   throw Error('Exact source Mirror request needs observed current WebGL2 capability');
  return THREE.MirroredRepeatWrapping;
 }
 throw Error('Unknown original texture address');
}
// Attachment references, rather than filename aliases, determine the real
// mesh node. Every ancestor is retained; animated ancestors remain unsupported.
export function checkedRigidTransform(THREE,source,mesh,proof){
 const all=source.sourceNodes;
 if(!Array.isArray(all))throw Error('Original rigid source nodes missing');
 const refs=all.flatMap((node,index)=>(node.attachments||[]).filter(a=>a.kind===3&&a.reference==='#'+mesh.name).map(()=>index));
 if(refs.length!==1)throw Error('Rigid mesh needs one actual original kind3 reference');
 let index=refs[0];const chain=[],seen=new Set();
 while(index!==-1){
  if(!Number.isInteger(index)||index<0||index>=all.length||seen.has(index))throw Error('Invalid original rigid ancestor hierarchy');
  seen.add(index);const node=all[index];
  if(node.controllerRelative!==0||!finite(node.position,3)||!finite(node.quaternion,4)||!finite(node.scale,3))throw Error('Unproved original rigid ancestor TRS/controller');
  chain.unshift(index);index=node.parent;
 }
 const expected=new THREE.Matrix4();
 for(const i of chain){const node=all[i];expected.multiply(new THREE.Matrix4().compose(new THREE.Vector3(...node.position),new THREE.Quaternion(...node.quaternion),new THREE.Vector3(...node.scale)));}
 if(proof){
  if(proof.sourceMeshName!==mesh.name||proof.sourceNodeIndex!==refs[0]||!same(proof.sourceNode,all[refs[0]])||
   proof.nativeCPUExecuted!==true||proof.originalGPUObserved!==false||proof.originalModelLoaderExecuted!==false||
   proof.sourceLiteralMeshAttachmentVerified!==true||!finite(proof.nativeMatrix,16))throw Error('Original rigid source proof differs');
  if(proof.format==='oc2-original-rigid-root-mesh-transform-v1'){
   if(chain.length!==1||all[refs[0]].parent!==-1)throw Error('Root-only proof cannot cover a child mesh');
  }else if(proof.format==='oc2-original-rigid-mesh-ancestor-transform-v2'){
   if(proof.originalEmptyNodeHierarchyConstructed!==true||!same(proof.sourceAncestorIndices,chain)||
    !same(proof.sourceAncestors,chain.map(i=>({index:i,node:all[i]}))))throw Error('Original rigid ancestor proof differs');
  }else throw Error('Unsupported original rigid proof format');
  if(expected.elements.some((v,i)=>Math.abs(v-proof.nativeMatrix[i])>2e-6))throw Error('Original complete rigid ancestor matrix differs');
  return new THREE.Matrix4().fromArray(proof.nativeMatrix);
 }
 // Exact compatibility only: a genuinely attached identity *root* may use the
 // legacy representation. An identity alias with a child mesh is rejected.
 if(chain.length!==1||expected.elements.some((v,i)=>v!==(i%5===0?1:0)))throw Error('Legacy rigid source is not an actual identity mesh root');
 return expected;
}
export function buildCreationStageActor({THREE,manifest,data,identity,textures,attachmentData,createMaterial,textureCapabilities}){
 checkedStageModel(manifest,data,identity);
 if(!(textures instanceof Map)||!(attachmentData instanceof Map)||typeof createMaterial!=='function')throw Error('Actual texture/model/material constructors required');
 const root=new THREE.Group(),geometries=[],materials=[],clones=[],skeletons=[],meshes=[],weapons=[];
 let mixer=null,disposed=false;
 const release=()=>{if(disposed)return;disposed=true;root.removeFromParent();if(mixer){mixer.stopAllAction();mixer.uncacheRoot(root);}for(const value of geometries)value.dispose();for(const value of materials)value.dispose();for(const value of clones)value.dispose();for(const value of skeletons)value.dispose();};
 try{
  const nodes=data.rig.nodes.map((n,i)=>{
   if(!finite(n.position,3)||!finite(n.quaternion,4)||!finite(n.scale,3)||!Number.isInteger(n.parent)||n.parent< -1||n.parent>=i)throw Error('Original source hierarchy differs');
   const bone=new THREE.Bone();bone.name='creation_stage_node_'+i;bone.position.fromArray(n.position);bone.quaternion.fromArray(n.quaternion);bone.scale.fromArray(n.scale);return bone;
  });
  data.rig.nodes.forEach((n,i)=>(n.parent<0?root:nodes[n.parent]).add(nodes[i]));
  const geometryFor=m=>{
   const g=new THREE.BufferGeometry();geometries.push(g);
   for(const [name,key,width]of [['position','positions',3],['normal','normals',3],['uv','uvs',2],['sourceTangent','sourceTangents',3],['sourceBinormal','sourceBinormals',3]]){
    if(!finite(m[key])||m[key].length%width)throw Error('Original stage geometry attribute absent');
    g.setAttribute(name,new THREE.Float32BufferAttribute(m[key],width));
   }
   if(!Array.isArray(m.indices)||!Array.isArray(m.groups))throw Error('Original stage source indices absent');
   g.setIndex(m.indices);for(const group of m.groups)g.addGroup(group.start,group.count,group.material);return g;
  };
  const materialsFor=(object,sourceRows,groups)=>{
   const result=[];
   for(const index of new Set(groups.map(g=>g.material))){
    const row=checkedMaterial(sourceRows.find(m=>m.index===index));if(!row)throw Error('Original visible material missing');
    const samplers=new Map();
    for(const [slot,path]of Object.entries(row.samplers)){
     const original=textures.get(path),address=row.addressing[slot];
     if(!original?.isTexture||original.flipY!==false||original.colorSpace!==THREE.NoColorSpace||!address)throw Error('Original stage sampler was not constructed');
     const texture=original.clone();clones.push(texture);texture.wrapS=wrap(THREE,address.addressU,textureCapabilities,address,0);texture.wrapT=wrap(THREE,address.addressV,textureCapabilities,address,1);texture.needsUpdate=true;samplers.set(path,texture);
    }
    const material=createMaterial(THREE,row,samplers,manifest.colors,object);
    if(!material?.isMaterial)throw Error('Actual source material constructor did not return a Three material');materials.push(material);result[index]=material;
   }
   for(const [to,from]of attributes){const attribute=object.geometry.getAttribute(from);if(attribute)object.geometry.setAttribute(to,attribute);}
   return result;
  };
  const visible=new Set(manifest.visibleMeshIndices),skinMap=new Map(data.rig.skins.map(s=>[s.mesh,s]));
  data.meshes.forEach((m,index)=>{
   const geometry=geometryFor(m),skin=skinMap.get(index);
   if(!skin||!Array.isArray(skin.boneNodes)||!Array.isArray(skin.inverseBindMatrices)||skin.boneNodes.some(i=>!nodes[i]))throw Error('Original stage skin absent');
   geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skin.skinIndices,4));geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(skin.skinWeights,4));
   const object=new THREE.SkinnedMesh(geometry,[]),skeleton=new THREE.Skeleton(skin.boneNodes.map(i=>nodes[i]),skin.inverseBindMatrices.map(m=>new THREE.Matrix4().fromArray(m)));skeletons.push(skeleton);
   object.bind(skeleton,new THREE.Matrix4());object.visible=visible.has(index);object.name=m.name;object.frustumCulled=false;root.add(object);meshes.push(object);
   if(object.visible)object.material=materialsFor(object,manifest.materials,m.groups);
  });
  const seen=new Set();
  for(const row of manifest.attachments){
   const source=attachmentData.get(row.model),mount=row.mount;
   if(seen.has(row.slot)||!source||source.source!==row.source||row.sourceRequest?.slot!==row.slot||row.sourceRequest.itemKey!==row.itemKey||
    !mount?.sourceNodePresent||mount.rootFallback||!nodes[mount.sourceNodeIndex]||mount.slot!==row.slot||!finite(mount.rootLocalTranslation,3)||
    mount.rotationOrScaleRewritten!==false||mount.sourceRootGeometryTransformPreserved!==true||source.meshes?.length!==1)
    throw Error('Original weapon source mount/model differs');
   seen.add(row.slot);const attachment=new THREE.Group();attachment.position.fromArray(mount.rootLocalTranslation);nodes[mount.sourceNodeIndex].add(attachment);
   for(const m of source.meshes){
    const object=new THREE.Mesh(geometryFor(m),[]),transform=source.sourceRigidMeshTransform;
    const matrix=checkedRigidTransform(THREE,source,m,transform);
    object.matrix.copy(matrix);object.matrixAutoUpdate=false;
    object.name=m.name;object.frustumCulled=false;object.material=materialsFor(object,row.materials,m.groups);attachment.add(object);weapons.push(object);
   }
  }
  const clip=data.clips[0],tracks=clip.tracks.map(t=>{
   if(!nodes[t.node]||!['position','quaternion','scale'].includes(t.type))throw Error('Original stage idle target absent');
   const name=`creation_stage_node_${t.node}.${t.type}`;
   return t.type==='quaternion'?new THREE.QuaternionKeyframeTrack(name,t.times,t.values):new THREE.VectorKeyframeTrack(name,t.times,t.values);
  });
  mixer=new THREE.AnimationMixer(root);const action=mixer.clipAction(new THREE.AnimationClip('idle',clip.duration,tracks));
  action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();mixer.update(0);root.updateMatrixWorld(true);
  return {root,manifest,nodes,meshes,weapons,mixer,action,scope:{stageGeometryConstructed:true,sourceMaterialObjectsConstructed:true,
    originalGPUObserved:false,selectionAnimationContinuationRestored:false,createsPlayableRole:false,unresolvedSourceEffects:manifest.modelEffects.length,sourceEffectSuccessSupplied:false},
   update(delta){if(!disposed)mixer.update(Math.min(Math.max(delta,0),.1));},dispose:release};
 }catch(error){release();throw error;}
}
