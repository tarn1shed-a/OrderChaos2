// One geometry/material/mount traversal for the source Class and Part recipes.
// No per-profession renderer, timers, queue production, ready reply or role grant.
import {checkedStageModel} from '../creation_class_stage/actor_v6.mjs';
import {checkedRigidTransform} from '../creation_class_stage/actor_v3.mjs';
import {finite,same,ARMOR_ROOT,checkArmorRoot,checkedPass,sourceWrap} from './contracts.mjs';
const ATTRIBUTES=[['position','positions',3],['normal','normals',3],['uv','uvs',2],['sourceTangent','sourceTangents',3],['sourceBinormal','sourceBinormals',3]];
const SEMANTICS=[['Vertex','position'],['Normal','normal'],['TexCoord0','uv'],['Tangent','sourceTangent'],['Binormal','sourceBinormal'],['SkinWeights','skinWeight'],['SkinIndices','skinIndex']];
export function recipeFromFrozenStage({manifest,data,identity,validateStageModel=checkedStageModel}){
 validateStageModel(manifest,data,identity); // Includes exact independent Model62/BEFF contract, not effect success.
 const bindings=new Map();
 for(const skin of data.rig.skins){
  if(!Number.isInteger(skin.mesh)||bindings.has(skin.mesh)||!data.meshes[skin.mesh])throw Error('Source mesh has duplicate or absent skin binding');
  bindings.set(skin.mesh,skin);
 }
 if(bindings.size!==data.meshes.length)throw Error('Every source body/garment mesh needs its own proved skin');
 if(new Set(manifest.visibleMeshIndices).size!==manifest.visibleMeshIndices.length||manifest.visibleMeshIndices.some(i=>!Number.isInteger(i)||!data.meshes[i]))throw Error('Original visible mesh selection differs');
 return Object.freeze({format:'oc2-creation-shared-geometry-recipe-v1',manifest,data,identity,bindings,validateStageModel});
}
export function createCreationGeometry({THREE,recipe,textures,attachmentData,createMaterial,textureCapabilities,samplerAddressResolver=sourceWrap,armorRootValidator=checkArmorRoot}){
 if(recipe?.format!=='oc2-creation-shared-geometry-recipe-v1'||!(textures instanceof Map)||!(attachmentData instanceof Map)||typeof createMaterial!=='function')
  throw Error('Explicit source recipe and actual constructors are required');
 const {manifest,data,identity}=recipe;
 const verified=recipeFromFrozenStage({manifest,data,identity,validateStageModel:recipe.validateStageModel}); // Revalidate after caller loading; no trusted ready or mutable binding map.
 const root=new THREE.Group(),nodes=[],meshes=[],weapons=[],rigidParts=[],geometries=[],materials=[],clones=[],skeletons=[];
 let disposed=false;
 const dispose=()=>{if(disposed)return;disposed=true;root.removeFromParent();for(const x of geometries)x.dispose();for(const x of materials)x.dispose();for(const x of clones)x.dispose();for(const x of skeletons)x.dispose();};
 try{
  for(const [index,node]of data.rig.nodes.entries()){
   if(!finite(node.position,3)||!finite(node.quaternion,4)||!finite(node.scale,3)||!Number.isInteger(node.parent)||node.parent< -1||node.parent>=index)throw Error('Original source hierarchy differs');
   const bone=new THREE.Bone();bone.name='creation_stage_node_'+index;bone.position.fromArray(node.position);bone.quaternion.fromArray(node.quaternion);bone.scale.fromArray(node.scale);nodes.push(bone);
   (node.parent<0?root:nodes[node.parent]).add(bone);
  }
  const geometryFor=mesh=>{
   if(!Number.isInteger(mesh.vertexCount)||mesh.vertexCount<1)throw Error('Source geometry count absent');
   const geometry=new THREE.BufferGeometry();geometries.push(geometry);
   for(const [name,key,width]of ATTRIBUTES){if(!finite(mesh[key],mesh.vertexCount*width))throw Error('Original source geometry attribute absent or mismatched');geometry.setAttribute(name,new THREE.Float32BufferAttribute(mesh[key],width));}
   if(!Array.isArray(mesh.indices)||mesh.indices.some(i=>!Number.isInteger(i)||i<0||i>=mesh.vertexCount)||!Array.isArray(mesh.groups))throw Error('Original source indices absent or invalid');
   geometry.setIndex(mesh.indices);
   for(const group of mesh.groups){if(![group.start,group.count,group.material].every(Number.isInteger)||group.start<0||group.count<0||group.start+group.count>mesh.indices.length||group.material<0)throw Error('Original source material range differs');geometry.addGroup(group.start,group.count,group.material);}
   return geometry;
  };
  const materialFor=(object,rows,groups)=>{
   const result=[];
   for(const index of new Set(groups.map(group=>group.material))){
    const matches=rows.filter(row=>row.index===index);if(matches.length!==1)throw Error('Original visible material must be unique');
    const row=checkedPass(matches[0]),maps=new Map();
    for(const [sampler,url]of Object.entries(row.samplers)){
     const input=textures.get(url),address=row.addressing[sampler];
     if(!input?.isTexture||input.flipY!==false||input.colorSpace!==THREE.NoColorSpace||!address)throw Error('Source sampler input was not constructed');
     const texture=input.clone();clones.push(texture);texture.wrapS=samplerAddressResolver(THREE,address.addressU,textureCapabilities,address,0,{texture,input});texture.wrapT=samplerAddressResolver(THREE,address.addressV,textureCapabilities,address,1,{texture,input});texture.needsUpdate=true;maps.set(url,texture);
    }
    const material=createMaterial(THREE,row,maps,manifest.colors,object);
    if(!material?.isMaterial)throw Error('Actual source material constructor failed');materials.push(material);result[index]=material;
   }
   for(const [semantic,name]of SEMANTICS){const attribute=object.geometry.getAttribute(name);if(attribute)object.geometry.setAttribute(semantic,attribute);}
   return result;
  };
  const visible=new Set(manifest.visibleMeshIndices);
  for(const [index,mesh]of data.meshes.entries()){
   const skin=verified.bindings.get(index),geometry=geometryFor(mesh);
   if(!skin||!Array.isArray(skin.boneNodes)||!Array.isArray(skin.inverseBindMatrices)||skin.boneNodes.length!==skin.inverseBindMatrices.length||
    skin.boneNodes.some(i=>!Number.isInteger(i)||!nodes[i])||skin.inverseBindMatrices.some(m=>!finite(m,16))||
    !finite(skin.skinWeights,mesh.vertexCount*4)||!Array.isArray(skin.skinIndices)||skin.skinIndices.length!==mesh.vertexCount*4||
    skin.skinIndices.some(i=>!Number.isInteger(i)||i<0||i>=skin.boneNodes.length))throw Error('Original source skin/bone stream differs');
   geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skin.skinIndices,4));geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(skin.skinWeights,4));
   const object=new THREE.SkinnedMesh(geometry,[]),skeleton=new THREE.Skeleton(skin.boneNodes.map(i=>nodes[i]),skin.inverseBindMatrices.map(m=>new THREE.Matrix4().fromArray(m)));skeletons.push(skeleton);
   object.bind(skeleton,new THREE.Matrix4());object.visible=visible.has(index);object.name=mesh.name;object.frustumCulled=false;root.add(object);meshes.push(object);
   if(object.visible)object.material=materialFor(object,manifest.materials,mesh.groups);
  }
  const slots=new Set();
  for(const row of manifest.attachments){
   if(slots.has(row.slot))throw Error('Duplicate original attachment slot');slots.add(row.slot);
   const source=attachmentData.get(row.model),mount=row.mount;
   let target,container;
   if(row.kind===ARMOR_ROOT){armorRootValidator(row,source,identity);target=root;container=rigidParts;}
   else{
    if(row.kind!==undefined||!source||source.source!==row.source||row.sourceRequest?.slot!==row.slot||row.sourceRequest.itemKey!==row.itemKey||
     !mount?.sourceNodePresent||mount.rootFallback||!nodes[mount.sourceNodeIndex]||mount.slot!==row.slot||!finite(mount.rootLocalTranslation,3)||
     mount.rotationOrScaleRewritten!==false||mount.sourceRootGeometryTransformPreserved!==true||source.meshes?.length!==1)throw Error('Original source weapon mount differs');
    target=new THREE.Group();target.position.fromArray(mount.rootLocalTranslation);nodes[mount.sourceNodeIndex].add(target);container=weapons;
   }
   for(const mesh of source.meshes){
    const object=new THREE.Mesh(geometryFor(mesh),[]);object.name=mesh.name;object.frustumCulled=false;
    object.matrix.copy(checkedRigidTransform(THREE,source,mesh,source.sourceRigidMeshTransform));object.matrixAutoUpdate=false;
    object.material=materialFor(object,row.materials,mesh.groups);target.add(object);container.push(object);
   }
  }
  root.updateMatrixWorld(true);
  const applySourcePose=pose=>{
   if(disposed)throw Error('Shared source geometry disposed');
   const expected={uiRace:identity.race,gender:identity.gender,uiProfessionIndex:identity.professionIndex,profession:identity.profession,stage:identity.panel,displayId:identity.request.displayId,sourceModelId:identity.sourceModel.ID};
   if(pose?.format!=='oc2-creation-pure-source-pose-v1'||Object.entries(expected).some(([key,value])=>pose.identity?.[key]!==value)||!Array.isArray(pose.nodeTRS))throw Error('Own source pose identity required');
   const seen=new Set();
   for(const row of pose.nodeTRS){
    const index=row.sourceNodeIndex,source=data.rig.nodes[index];
    if(!Number.isInteger(index)||seen.has(index)||!source||!finite(row.position,3)||!finite(row.quaternion,4)||!finite(row.scale,3)||
     row.name!==source.name||!same(row.aliases,source.aliases))throw Error('Actual source pose target differs');
    seen.add(index);
   }
   for(const row of pose.nodeTRS){const node=nodes[row.sourceNodeIndex];node.position.fromArray(row.position);node.quaternion.fromArray(row.quaternion);node.scale.fromArray(row.scale);}
   root.updateMatrixWorld(true);
  };
  return {root,nodes,meshes,weapons,rigidParts,manifest,applySourcePose,dispose,
   scope:{sharedSourceGeometryConstructed:true,sourceMaterialObjectsConstructed:true,unresolvedSourceEffects:manifest.modelEffects.length,
    sourceEffectSuccessSupplied:false,originalGPUObserved:false,originalReadySupplied:false,createsPlayableRole:false,sourceClockOrQueueCreated:false}};
 }catch(error){dispose();throw error;}
}
// Compatibility replay only: finite original idle is separate from geometry.
// Full source queue/sampler is injected through applySourcePose, never inferred
// from Three.finished or a new infinite loop.
export function attachFrozenFiniteIdle(THREE,geometry,data){
 const clip=data.clips[0],tracks=clip.tracks.map(track=>{
  if(!geometry.nodes[track.node]||!['position','quaternion','scale'].includes(track.type))throw Error('Source finite idle target absent');
  const name=`creation_stage_node_${track.node}.${track.type}`;
  return track.type==='quaternion'?new THREE.QuaternionKeyframeTrack(name,track.times,track.values):new THREE.VectorKeyframeTrack(name,track.times,track.values);
 });
 const mixer=new THREE.AnimationMixer(geometry.root),action=mixer.clipAction(new THREE.AnimationClip('idle',clip.duration,tracks));
 action.setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;action.play();mixer.update(0);geometry.root.updateMatrixWorld(true);
 let stopped=false;
 return {mixer,action,update(delta){if(!stopped)mixer.update(Math.min(Math.max(delta,0),.1));},dispose(){if(stopped)return;stopped=true;mixer.stopAllAction();mixer.uncacheRoot(geometry.root);}};
}
