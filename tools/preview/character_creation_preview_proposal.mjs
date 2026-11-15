// A read-only model interface for the existing original creation stage.
// It creates no DOM, layout, role, inventory, attribute, skill or server session.
export function creationSourceWrap(THREE,value){
  if(value===0)return THREE.RepeatWrapping;
  if(value===1||value===2)return THREE.ClampToEdgeWrapping;
  throw Error('Unverified original texture address enum');
}

export const CREATION_RACE_FORMAT='oc2-race-stage-creation-candidate-v1';
export const CREATION_RACE_IDENTITIES=Object.freeze({
  '1:0':Object.freeze({key:'mendel-male',display:2048,model:34}),
  '1:1':Object.freeze({key:'mendel-female',display:2049,model:31}),
  '2:1':Object.freeze({key:'elf-female',display:2047,model:2}),
  '3:0':Object.freeze({key:'orc-male',display:2050,model:28}),
  '3:1':Object.freeze({key:'orc-female',display:2051,model:30}),
  '4:0':Object.freeze({key:'kartan',display:2052,model:29}),
});
export const CREATION_PREVIEW_FORMATS=Object.freeze({
  '0:0':'oc2-human-male-creation-candidate-v1',
  '0:1':'oc2-human-female-creation-candidate-v1',
  ...Object.fromEntries(Object.keys(CREATION_RACE_IDENTITIES).map(key=>[key,CREATION_RACE_FORMAT])),
});

export function creationPreviewKey(race,gender){
  return Number.isInteger(race)&&Number.isInteger(gender)&&Object.hasOwn(CREATION_PREVIEW_FORMATS,`${race}:${gender}`)?`${race}:${gender}`:null;
}

export function creationPreviewResourceURL(baseURL,path,documentURL=globalThis.location?.href){
  const base=new URL(baseURL,documentURL);
  if(!base.pathname.endsWith('/')||base.search||base.hash)throw Error('Original preview base directory must end with slash');
  // Source candidate names are canonical plain relative paths. Encoded path
  // separators/dots are refused before a server can normalize them differently.
  if(typeof path!=='string'||!path||!/^\/?[A-Za-z0-9_./-]+$/.test(path)||path.includes('..')||path.includes('//'))
    throw Error('Unsafe original preview resource path');
  const result=new URL(path.replace(/^\//,''),base);
  if(result.origin!==base.origin||!result.pathname.startsWith(base.pathname))throw Error('Original preview escapes private resource directory');
  return result.href;
}

export function checkedCreationPreview(manifest,{race,gender}){
  const key=creationPreviewKey(race,gender);
  if(!key||manifest?.format!==CREATION_PREVIEW_FORMATS[key]||manifest.race!==race||manifest.gender!==gender||manifest.createdRole!==false||manifest.initialServerAttributes!==null)
    throw Error('Original creation preview identity or scope differs');
  if(manifest.format===CREATION_RACE_FORMAT){
    const source=CREATION_RACE_IDENTITIES[key];
    if(manifest.key!==source.key||manifest.originalDisplayId!==source.display||manifest.sourceModelId!==source.model||
      manifest.creationPreviewAdmitted!==true||manifest.appearanceComplete!==true||manifest.liveActor!==false||
      manifest.sourceTraceSHA256!=='6c3c300912f2cc7021a3784c601a7229b327916ee89c9a34ac72390b82f680a8')
      throw Error('Original race-stage costume evidence is incomplete');
  }
  if(!Array.isArray(manifest.visibleMeshIndices)||!Array.isArray(manifest.materials))throw Error('Original preview indices missing');
  const indices=new Set();
  for(const entry of manifest.materials){
    if(!Number.isInteger(entry.index)||entry.index<0||indices.has(entry.index))throw Error('Ambiguous original material index');
    indices.add(entry.index);
  }
  return Object.freeze({key,createsPlayableRole:false,grantsEquipment:false,writesCharacter:false});
}

export async function loadCreationRacePreview({THREE,createMaterial,baseURL,race,gender,signal}){
  if(!creationPreviewKey(race,gender))return null;
  const url=path=>creationPreviewResourceURL(baseURL,path);
  const read=async path=>{const response=await fetch(url(path),{signal});if(!response.ok)throw Error('Original preview resource unavailable');return response.json();};
  const manifest=await read('manifest.json');
  checkedCreationPreview(manifest,{race,gender});
  const data=await read(manifest.model),textures=new Map(),loader=new THREE.TextureLoader();
  await Promise.all([...new Set(manifest.materials.flatMap(entry=>Object.values(entry.samplers)))].map(async path=>{
    const texture=await loader.loadAsync(url(path));
    if(signal?.aborted){texture.dispose();throw new DOMException('Preview superseded','AbortError');}
    texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;textures.set(path,texture);
  }));
  if(signal?.aborted){for(const t of textures.values())t.dispose();throw new DOMException('Preview superseded','AbortError');}
  return buildCreationRacePreview({THREE,createMaterial,manifest,data,textures,race,gender});
}

export function checkedCreationModel(manifest,data,{race,gender}){
  const scope=checkedCreationPreview(manifest,{race,gender});
  if(data?.format!=='bdae946-character-v1'||!data.rig?.nodes||!data.rig?.skins||!Array.isArray(data.meshes)||!Array.isArray(data.materials))throw Error('Original preview model structure differs');
  const expected=CREATION_RACE_IDENTITIES[scope.key]||({
    '0:0':{display:2038,model:1},'0:1':{display:2045,model:32},
  })[scope.key];
  const modelPaths={1:'human/male/oc2_human_m_body_01.bdae',32:'human/female/oc2_human_f_body_01.bdae',
    34:'mendel/male/oc2_mendel_m_body_01.bdae',31:'mendel/female/oc2_mendel_f_body_01.bdae',
    2:'elf/female/oc2_elf_f_body_01.bdae',28:'orc/male/oc2_orc_m_body_01.bdae',
    30:'orc/female/oc2_orc_f_body_01.bdae',29:'daisauros/male/oc2_daisauros_m_body_01.bdae'};
  const source=data.sourceCreation;
  if(!expected||manifest.originalDisplayId!==expected.display||data.source!=='model/npc/character/'+modelPaths[expected.model]||
    source?.displayId!==expected.display||source.race!==race||source.gender!==gender||source.createdRole!==false||source.originalFloatWeightsPreserved!==true||
    (manifest.format===CREATION_RACE_FORMAT?source.sourceModelId!==expected.model:
      Object.hasOwn(source,'sourceModelId')&&source.sourceModelId!==expected.model)||
    JSON.stringify(source.visibleMeshIndices)!==JSON.stringify(manifest.visibleMeshIndices))
    throw Error('Original preview model does not match its stage costume');
  return scope;
}

export function buildCreationRacePreview({THREE,createMaterial,manifest,data,textures,race,gender}){
  const scope=checkedCreationModel(manifest,data,{race,gender});
  const allTextures=new Set(textures.values()),materials=Array(data.materials.length),geometries=[];
  const wrap=value=>creationSourceWrap(THREE,value);
  for(const entry of manifest.materials){
    if(entry.index>=materials.length)throw Error('Source material index outside model');
    const samplers=new Map(),states=new Map();
    for(const [key,path]of Object.entries(entry.samplers)){
      if(!textures.has(path)||!entry.addressing?.[key])throw Error('Original preview sampler missing');
      const a=entry.addressing[key],state=`${a.addressU}:${a.addressV}`;
      if(states.has(path)&&states.get(path)!==state)throw Error('Shared source texture needs distinct sampler state');
      wrap(a.addressU);wrap(a.addressV);
      states.set(path,state);
      const t=textures.get(path).clone();t.wrapS=wrap(a.addressU);t.wrapT=wrap(a.addressV);t.needsUpdate=true;samplers.set(path,t);allTextures.add(t);
    }
    materials[entry.index]=createMaterial(THREE,entry,samplers,manifest.colors);
  }
  const root=new THREE.Group(),nodes=data.rig.nodes.map((n,i)=>{
    const bone=new THREE.Bone();bone.name='creation_node_'+i;
    bone.position.fromArray(n.position);bone.quaternion.fromArray(n.quaternion);bone.scale.fromArray(n.scale);return bone;
  });
  data.rig.nodes.forEach((n,i)=>{if(!Number.isInteger(n.parent)||n.parent>=i||n.parent< -1)throw Error('Invalid original bone parent');(n.parent<0?root:nodes[n.parent]).add(nodes[i]);});
  const bySkin=new Map(data.rig.skins.map(s=>[s.mesh,s])),visible=new Set(manifest.visibleMeshIndices);
  const meshes=data.meshes.map((m,i)=>{
    const geometry=new THREE.BufferGeometry();geometries.push(geometry);
    for(const [name,values,width]of [['position',m.positions,3],['normal',m.normals,3],['uv',m.uvs,2],['sourceTangent',m.sourceTangents,3],['sourceBinormal',m.sourceBinormals,3]]){
      if(!Array.isArray(values))throw Error('Source preview attribute missing');
      geometry.setAttribute(name,new THREE.Float32BufferAttribute(values,width));
    }
    geometry.setIndex(m.indices);
    for(const group of m.groups){if(visible.has(i)&&!materials[group.material])throw Error('Visible original material not loaded');geometry.addGroup(group.start,group.count,group.material);}
    const skin=bySkin.get(i);if(!skin)throw Error('Original preview skin missing');
    geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skin.skinIndices,4));geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(skin.skinWeights,4));
    const object=new THREE.SkinnedMesh(geometry,materials);
    object.bind(new THREE.Skeleton(skin.boneNodes.map(index=>nodes[index]),skin.inverseBindMatrices.map(matrix=>new THREE.Matrix4().fromArray(matrix))),new THREE.Matrix4());
    object.frustumCulled=false;object.visible=visible.has(i);object.name=m.name;root.add(object);return object;
  });
  const clips=data.clips.map(clip=>new THREE.AnimationClip(clip.name,clip.duration,clip.tracks.map(track=>{
    if(!nodes[track.node]||!['position','quaternion','scale'].includes(track.type))throw Error('Unbound source preview animation track');
    const property=`creation_node_${track.node}.${track.type}`;
    return track.type==='quaternion'?new THREE.QuaternionKeyframeTrack(property,track.times,track.values):new THREE.VectorKeyframeTrack(property,track.times,track.values);
  })));
  if(clips.length!==1||clips[0].name!=='idle'||clips[0].duration!==manifest.idleDuration)throw Error('Original preview idle differs');
  const mixer=new THREE.AnimationMixer(root),action=mixer.clipAction(clips[0]);action.play();mixer.update(0);root.updateMatrixWorld(true);
  let disposed=false;
  return {root,mixer,action,manifest,scope,meshes,nodes,
    update(delta){if(!disposed)mixer.update(Math.min(Math.max(delta,0),.1));},
    dispose(){if(disposed)return;disposed=true;root.removeFromParent();mixer.stopAllAction();mixer.uncacheRoot(root);for(const g of geometries)g.dispose();for(const m of materials)if(m)m.dispose();for(const t of allTextures)t.dispose();for(const m of meshes)m.skeleton.dispose();},
  };
}
