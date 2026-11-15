// Original human inputs only. Caller owns game state, collision, selection and
// clocks. This module never grants equipment or invents an animation transition.
const FORMAT='oc2-human-female-world-source-v1';
const controllers=new WeakMap();

export function checkedHumanFemaleWorldSource(manifest,data){
  const source=data?.sourceHumanWorld;
  const actions=manifest?.actions,clips=data?.clips?.map(c=>c.name);
  if(manifest?.format!==FORMAT||manifest.race!==0||manifest.gender!==1||manifest.createdRole!==false||manifest.initialServerAttributes!==null||
     data?.format!=='bdae946-character-v1'||data.source!=='model/npc/character/human/female/oc2_human_f_body_01.bdae'||
     source?.sourceModelId!==32||source.race!==0||source.gender!==1||source.face!==0||source.hair!==1||source.beard!==0||
     !source.equipment||Array.isArray(source.equipment)||Object.values(source.equipment).some(Boolean)||!data.rig?.nodes?.length||!data.rig?.skins?.length||data.appearance||
     !Array.isArray(actions)||!Array.isArray(clips)||new Set(actions).size!==actions.length||new Set(clips).size!==clips.length||
     actions.length!==clips.length||actions.some(name=>!clips.includes(name))||
     [...(manifest.unadmittedActions||[]),...(manifest.absentActions||[])].some(name=>actions.includes(name))||
     !Array.isArray(manifest.visibleMeshIndices)||manifest.visibleMeshIndices.some(i=>!Number.isInteger(i)||!data.meshes[i]))
    throw Error('Unverified human world-source descriptor');
  return {race:0,gender:1,sourceModelId:32,emptyEquipmentOnly:true,createsRole:false,writesCharacter:false,grantsEquipment:false};
}

export function humanFemaleWorldAppearanceGate({race,gender,face,hair,beard,look,equipment}={}){
  const unresolvedEquipment=Object.entries(equipment||{}).filter(([,item])=>item).map(([slot,item])=>({slot,item}));
  const supported=race===0&&gender===1&&face===0&&hair===1&&beard===0&&look?.hair==='hair1'&&
    look.hairColor==='color1'&&look.skinColor==='color1'&&equipment!==null&&typeof equipment==='object'&&!Array.isArray(equipment)&&unresolvedEquipment.length===0;
  return {supported,unresolvedEquipment,reason:supported?null:'Explicit human face0/hair1/beard0/color1 and empty equipment only'};
}

export function humanFemaleWorldSourceWrap(THREE,value){
  if(value===0)return THREE.RepeatWrapping;
  if(value===1||value===2)return THREE.ClampToEdgeWrapping;
  throw Error('Unverified original human texture address');
}

export function createHumanFemaleWorldFactory({THREE,manifest,data,materials,createCharacterFactory}){
  const scope=checkedHumanFemaleWorldSource(manifest,data);
  if(typeof createCharacterFactory!=='function')throw Error('Existing world character factory must be supplied');
  const originalFactory=createCharacterFactory(THREE,data,materials);
  const clips=data.clips.map(c=>new THREE.AnimationClip(c.name,c.duration,c.tracks.map(t=>new(
    t.type==='quaternion'?THREE.QuaternionKeyframeTrack:THREE.VectorKeyframeTrack)(`node_${t.node}.${t.type}`,t.times,t.values))));
  return()=>{
    const root=originalFactory(),meshes=[];
    root.traverse(node=>{if(Number.isInteger(node.userData?.sourceMeshIndex)){
      const index=node.userData.sourceMeshIndex;node.visible=manifest.visibleMeshIndices.includes(index);meshes[index]=node;
    }});
    if(meshes.length!==data.meshes.length||meshes.filter(Boolean).length!==data.meshes.length)throw Error('Existing world factory did not expose original source mesh indices');
    const mixer=new THREE.AnimationMixer(root),actions=new Map();
    for(const clip of clips){const action=mixer.clipAction(clip).setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;actions.set(clip.name,action);}
    controllers.set(root,{THREE,manifest,data,mixer,actions,lastPose:[],scope});
    root.userData.sourceHumanFemaleWorld={...scope,actions:[...actions.keys()]};
    sampleHumanFemaleWorldPose(root,[{clip:'idle',timeSeconds:0,weight:1}]);
    return root;
  };
}

export function sampleHumanFemaleWorldPose(root,pose){
  const c=controllers.get(root);
  if(!c)throw Error('Root is not an independent human-world instance');
  if(!Array.isArray(pose)||!pose.length||pose.length>2||Math.abs(pose.reduce((s,p)=>s+p.weight,0)-1)>1e-6||
     pose.some(p=>!c.actions.has(p.clip)||!Number.isFinite(p.timeSeconds)||p.timeSeconds<0||
       p.timeSeconds>c.actions.get(p.clip).getClip().duration||!Number.isFinite(p.weight)||p.weight<0||p.weight>1)||
     new Set(pose.map(p=>p.clip)).size!==pose.length)throw Error('Unsupported original human pose/clock/weights');
  // Source time is explicitly supplied. No new loop, jump, fall, land, blend or
  // stop-queue policy is inferred here. Call after existing host updates.
  c.mixer.stopAllAction();
  for(const p of pose){const a=c.actions.get(p.clip);a.reset().play();a.time=p.timeSeconds;a.paused=true;a.setEffectiveWeight(p.weight);}
  c.mixer.update(0);root.updateMatrixWorld(true);c.lastPose=pose.map(p=>({...p}));
  return true;
}

export function humanFemaleWorldPoseState(root){
  const c=controllers.get(root);return c?{...c.scope,pose:c.lastPose.map(p=>({...p})),height:root.userData.height}:null;
}

export function disposeHumanFemaleWorldPose(root){
  const c=controllers.get(root);if(!c)return;
  c.mixer.stopAllAction();c.mixer.uncacheRoot(root);controllers.delete(root);
  // The caller retains responsibility for the injected world's base mixer,
  // shared geometry/material ownership, and removal from its own scene.
}
