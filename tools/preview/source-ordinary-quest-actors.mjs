// Original asset factories only. The compatibility server owns actor IDs,
// admission, transforms, collection events and quest/reward state.
import {finalPairMaterial} from './source-npc-final-pair-material.js';
import {createBakedSceneMaterial} from './scene-baked-lighting.js';
import {sceneDiffuseTexture} from './scene-sampling.js';
import {applySceneCulling,guardSceneOrientation} from './scene-culling.js';

const FORMAT='oc2-ordinary-quest-actors-v1';
const required=(test,message)=>{if(!test)throw Error(message);};

export async function loadOrdinaryQuestActorAssets(THREE,{
  profileURL='/assets/source-ordinary-quest-actors/profile.json',
  json=async url=>{const r=await fetch(url);if(!r.ok)throw Error('Missing source actor JSON: '+url);return r.json();},
  texture=async url=>new THREE.TextureLoader().loadAsync(url),
}={}){
  const profile=await json(profileURL);
  required(profile.format===FORMAT&&profile.questId===461&&profile.npc?.entry===2079&&profile.object?.entry===467,
    'Unsupported original quest actor assets');
  const [data,objectData]=await Promise.all([json(profile.npc.model),json(profile.object.model)]);
  const textures=new Map(),instances=new Set();let released=false;
  await Promise.all(Object.values(profile.textures).map(async row=>{
    const t=await texture(row.url);required(t.image?.width===row.size[0]&&t.image?.height===row.size[1],'Source actor texture dimensions differ');
    t.flipY=false;t.colorSpace=THREE.NoColorSpace;t.needsUpdate=true;textures.set(row.url,t);
  }));
  function meshGeometry(mesh){
    const geometry=new THREE.BufferGeometry();
    for(const[name,key,size]of [['position','positions',3],['normal','normals',3],['uv','uvs',2],
      ['sourceTangent','sourceTangents',3],['sourceBinormal','sourceBinormals',3],['sourceUV1','sourceUV1',2]]){
      if(mesh[key])geometry.setAttribute(name,new THREE.Float32BufferAttribute(mesh[key],size));
    }
    required(geometry.getAttribute('position')&&geometry.getAttribute('normal')&&geometry.getAttribute('uv'),'Source actor vertex stream missing');
    geometry.setIndex(mesh.indices);for(const group of mesh.groups)geometry.addGroup(group.start,group.count,group.material);
    return geometry;
  }
  function own(root,geometries,materials,extras={}){
    const instance={root,...extras,disposed:false,dispose(){
      if(instance.disposed)return;instance.disposed=true;root.removeFromParent();instance.mixer?.stopAllAction();
      instance.mixer?.uncacheRoot(root);for(const g of geometries)g.dispose();for(const m of materials)if(m)m.dispose();
      instances.delete(instance);
    }};instances.add(instance);return instance;
  }
  function createNPC2079({materialFactory}={}){
    required(!released,'Actor asset factory released');
    required(materialFactory===undefined||typeof materialFactory==='function','Explicit host NPC material factory required');
    const entry=profile.npc,root=new THREE.Group();root.name='source-npc2079-asset';
    const bones=data.rig.nodes.map((n,i)=>{
      const bone=new THREE.Bone();bone.name='ordinary_npc2079_node_'+i;
      bone.position.fromArray(n.position);bone.quaternion.fromArray(n.quaternion);bone.scale.fromArray(n.scale);return bone;
    });
    data.rig.nodes.forEach((n,i)=>{if(n.parent<0)root.add(bones[i]);else bones[n.parent].add(bones[i]);});
    const materials=new Array(entry.materialSlotCount).fill(null);
    for(const source of entry.materials){
      const material=materialFactory?materialFactory({THREE,record:source,textures,colors:entry.colors}):finalPairMaterial(THREE,source,textures,entry.colors,'source');
      required(material?.isMaterial,'NPC material factory must return a Three material');materials[source.index]=material;
    }
    const skins=new Map(data.rig.skins.map(s=>[s.mesh,s])),geometries=[],meshes=[];
    data.meshes.forEach((source,index)=>{
      const geometry=meshGeometry(source),skin=skins.get(index);required(skin,'Original actor skin missing');
      geometry.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(skin.skinIndices,4));
      geometry.setAttribute('skinWeight',new THREE.Float32BufferAttribute(skin.skinWeights,4));
      const mesh=new THREE.SkinnedMesh(geometry,materials);mesh.name=source.name;
      mesh.bind(new THREE.Skeleton(skin.boneNodes.map(i=>bones[i]),skin.inverseBindMatrices.map(m=>new THREE.Matrix4().fromArray(m))),new THREE.Matrix4());
      mesh.frustumCulled=false;mesh.visible=entry.visibleMeshIndices.includes(index);
      required(!mesh.visible||source.groups.every(g=>materials[g.material]),'Visible source actor material missing');
      root.add(mesh);geometries.push(geometry);meshes.push(mesh);
    });
    const clips=data.clips.map(clip=>new THREE.AnimationClip(clip.name,clip.duration,clip.tracks.map(track=>{
      const name='ordinary_npc2079_node_'+track.node+'.'+track.type;
      return track.type==='quaternion'?new THREE.QuaternionKeyframeTrack(name,track.times,track.values):new THREE.VectorKeyframeTrack(name,track.times,track.values);
    })));
    required(clips.length===1&&clips[0].name==='idle'&&clips[0].duration===entry.idleDuration,'Source NPC2079 idle differs');
    const mixer=new THREE.AnimationMixer(root),action=mixer.clipAction(clips[0]);action.play();mixer.update(0);root.updateMatrixWorld(true);
    return own(root,geometries,materials,{mixer,action,bones,meshes,
      update(deltaSeconds){required(Number.isFinite(deltaSeconds)&&deltaSeconds>=0,'Explicit host animation delta required');mixer.update(deltaSeconds);root.updateMatrixWorld(true);},
      inspect(){return {entry:2079,sourceAssetOnly:true,animationTime:action.time,idleDuration:entry.idleDuration,
        visibleMeshIndices:meshes.flatMap((m,i)=>m.visible?[i]:[]),boneCount:bones.length,actorGUID:null,questState:null};}});
  }
  function createObject467({lighting}={}){
    required(!released&&lighting?.uniforms?.sourceModelLight,'Object467 requires explicit host scene lighting uniforms');
    const root=new THREE.Group();root.name='source-static467-asset';const materials=[],geometries=[],ownedMaps=[];
    for(const[index,source]of objectData.materials.entries()){
      const diffuse=sceneDiffuseTexture(THREE,textures.get(source.diffuseAsset),source,index,objectData.sceneSampling);
      diffuse.flipY=false;diffuse.colorSpace=THREE.NoColorSpace;ownedMaps.push(diffuse);
      const material=createBakedSceneMaterial(THREE,diffuse,source,index,objectData,lighting);
      required(textures.has(source.lightmapAsset),'Original default lightMap texture missing');
      const atlas=textures.get(source.lightmapAsset).clone();atlas.flipY=false;atlas.colorSpace=THREE.NoColorSpace;
      atlas.wrapS=atlas.wrapT=THREE.RepeatWrapping;atlas.needsUpdate=true;ownedMaps.push(atlas);
      material.uniforms.sourceAtlas.value=atlas;
      applySceneCulling(THREE,material,source,index,objectData.sceneCulling);materials.push(material);
    }
    for(const source of objectData.meshes){const geometry=meshGeometry(source);required(geometry.getAttribute('sourceUV1'),'Original static UV1 missing');
      const mesh=new THREE.Mesh(geometry,materials);mesh.name=source.name;root.add(mesh);geometries.push(geometry);}
    const result=own(root,geometries,materials,{meshes:root.children,inspect(){return {entry:467,sourceAssetOnly:true,
      defaultLightMapUsed:true,sceneDATAtlasSupplied:false,actorGUID:null,collectionState:null};}});
    const release=result.dispose;result.dispose=()=>{if(!result.disposed)for(const t of ownedMaps)t.dispose();release();};
    root.updateMatrixWorld(true);guardSceneOrientation(root);return result;
  }
  return {profile,createNPC2079,createObject467,inspect:()=>({format:FORMAT,instances:instances.size,released}),
    dispose(){if(released)return;for(const instance of [...instances])instance.dispose();for(const t of new Set(textures.values()))t.dispose();released=true;}};
}
