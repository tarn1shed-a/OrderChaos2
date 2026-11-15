// Original872 asset composition. Caller owns scene/camera/material adaptation.
// This never creates a world identity, activity record or task qualification.
const FORMAT='oc2-original-npc872-default-assets-v1';
const need=(value,message)=>{if(!value)throw Error(message);};

export async function loadNPC872Assets(THREE,{
  profileURL='/assets/source-ordinary-npc872/profile.json',
  json=async url=>{const r=await fetch(url);if(!r.ok)throw Error('Missing original872 asset '+url);return r.json();},
  texture=async url=>new THREE.TextureLoader().loadAsync(url),
}={}){
  const profile=await json(profileURL);
  need(profile?.format===FORMAT&&profile.entry===872&&profile.defaultDisplay===852&&profile.sourceModelId===32&&
    profile.sourceExtraId===720&&profile.sourceAssetOnly===true&&profile.actorGUID===null&&profile.questState===null&&profile.worldPlacement===null,
    'Unsupported original872 asset descriptor');
  const data=await json(profile.model);
  need(data?.format==='bdae946-character-v1'&&data.sourceNPC872?.entry===872&&data.sourceNPC872.actualGUID===null&&
    data.source==='model/npc/character/human/female/oc2_human_f_body_01.bdae'&&data.rig?.nodes?.length===116&&
    data.rig.skins.length===data.meshes.length&&data.materials.length===profile.materialSlotCount,
    'Original872 composition/rig missing');
  const sourceTextures=new Map(),rows=new Map(),instances=new Set(),usedMaterials=new WeakSet();let released=false;
  for(const row of Object.values(profile.textures)){
    if(rows.has(row.url))need(JSON.stringify(rows.get(row.url).size)===JSON.stringify(row.size),'Conflicting872 texture dimensions');
    else rows.set(row.url,row);
  }
  const loaded=await Promise.allSettled([...rows.values()].map(async row=>{
    const t=await texture(row.url);
    if(!t?.isTexture||t.image?.width!==row.size[0]||t.image?.height!==row.size[1]){
      t?.dispose?.();throw Error('Original872 texture dimensions differ');
    }
    t.flipY=false;t.colorSpace=THREE.NoColorSpace;t.needsUpdate=true;sourceTextures.set(row.url,t);
  }));
  const failed=loaded.find(r=>r.status==='rejected');
  if(failed){for(const t of new Set(sourceTextures.values()))t.dispose();throw failed.reason;}
  function geometry(source){
    const g=new THREE.BufferGeometry();
    for(const[name,key,width]of[['position','positions',3],['normal','normals',3],['uv','uvs',2],
      ['sourceTangent','sourceTangents',3],['sourceBinormal','sourceBinormals',3]]){
      need(Array.isArray(source[key])&&source[key].length===source.vertexCount*width,'Original872 vertex stream missing '+key);
      g.setAttribute(name,new THREE.Float32BufferAttribute(source[key],width));
    }
    g.setIndex(source.indices);for(const group of source.groups)g.addGroup(group.start,group.count,group.material);
    g.computeBoundingBox();g.computeBoundingSphere();return g;
  }
  function createNPC872({materialFactory}={}){
    need(!released,'Original872 asset factory released');need(typeof materialFactory==='function','Inject the existing NPC material builder');
    const root=new THREE.Group();root.name='original-npc872-default-asset';
    const materials=new Array(profile.materialSlotCount).fill(null),geometries=[],meshes=[],bones=[];let mixer,action,disposed=false,time=0;
    function dispose(){
      if(disposed)return;disposed=true;root.removeFromParent();mixer?.stopAllAction();mixer?.uncacheRoot(root);
      for(const g of geometries)g.dispose();for(const m of materials)if(m)m.dispose();instances.delete(instance);
    }
    const instance={root,materials,geometries,meshes,bones,dispose,
      sampleIdle(seconds){
        need(!disposed&&!released,'Original872 instance released');
        need(Number.isFinite(seconds)&&seconds>=0&&seconds<=profile.idleDuration,'Explicit bounded original idle time required');
        action.reset().play();action.time=seconds;action.paused=true;mixer.update(0);root.updateMatrixWorld(true);
        for(const m of meshes)m.skeleton.update();time=seconds;return true;
      },
      inspect(){return{entry:872,defaultDisplay:852,sourceAssetOnly:true,boneCount:bones.length,meshCount:meshes.length,
        visibleMeshIndices:meshes.flatMap((m,i)=>m.visible?[i]:[]),idleDuration:profile.idleDuration,idleSampleSeconds:time,
        actorGUID:null,questState:null,worldPlacement:null,disposed};},
    };
    try{
      for(const record of profile.materials){
        const m=materialFactory({THREE,record,textures:sourceTextures,colors:profile.colors});
        need(m?.isMaterial&&!usedMaterials.has(m),'NPC872 material must be independently owned');usedMaterials.add(m);materials[record.index]=m;
      }
      data.rig.nodes.forEach((n,i)=>{
        const b=new THREE.Bone();b.name='npc872_node_'+i;b.position.fromArray(n.position);b.quaternion.fromArray(n.quaternion);b.scale.fromArray(n.scale);bones.push(b);
      });
      data.rig.nodes.forEach((n,i)=>(n.parent<0?root:bones[n.parent]).add(bones[i]));
      const skins=new Map(data.rig.skins.map(s=>[s.mesh,s]));
      data.meshes.forEach((source,index)=>{
        const g=geometry(source);geometries.push(g);const s=skins.get(index);need(s,'Original872 skin missing');
        g.setAttribute('skinIndex',new THREE.Uint16BufferAttribute(s.skinIndices,4));g.setAttribute('skinWeight',new THREE.Float32BufferAttribute(s.skinWeights,4));
        const m=new THREE.SkinnedMesh(g,materials);m.name=source.name;
        m.bind(new THREE.Skeleton(s.boneNodes.map(i=>bones[i]),s.inverseBindMatrices.map(v=>new THREE.Matrix4().fromArray(v))),new THREE.Matrix4());
        // Three's normal static bounds are unsuitable for the sampled source
        // skin; this is the existing NPC host adapter's culling boundary.
        m.frustumCulled=false;m.visible=profile.visibleMeshIndices.includes(index);
        need(!m.visible||source.groups.every(g=>materials[g.material]),'Visible872 source material missing');root.add(m);meshes.push(m);
      });
      need(data.clips.length===1&&data.clips[0].name==='idle'&&data.clips[0].duration===profile.idleDuration,'Original872 idle differs');
      const source=data.clips[0],clip=new THREE.AnimationClip(source.name,source.duration,source.tracks.map(t=>new(
        t.type==='quaternion'?THREE.QuaternionKeyframeTrack:THREE.VectorKeyframeTrack)(`npc872_node_${t.node}.${t.type}`,t.times,t.values)));
      mixer=new THREE.AnimationMixer(root);action=mixer.clipAction(clip).setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;
      instances.add(instance);instance.sampleIdle(0);return instance;
    }catch(error){dispose();throw error;}
  }
  return{profile,data,createNPC872,inspect:()=>({format:FORMAT,instances:instances.size,released,sourceAssetOnly:true}),
    dispose(){if(released)return;for(const instance of [...instances])instance.dispose();released=true;for(const t of new Set(sourceTextures.values()))t.dispose();sourceTextures.clear();},
  };
}
