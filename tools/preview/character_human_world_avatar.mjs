// Original human inputs only. Caller owns game state, collision, selection and
// clocks. This module never grants equipment or invents an animation transition.
const FORMAT='oc2-human-male-world-source-v1';
const controllers=new WeakMap();

export function checkedHumanWorldSource(manifest,data){
  const source=data?.sourceHumanWorld;
  if(manifest?.format!==FORMAT||manifest.race!==0||manifest.gender!==0||manifest.createdRole!==false||manifest.initialServerAttributes!==null||
     data?.format!=='bdae946-character-v1'||data.source!=='model/npc/character/human/male/oc2_human_m_body_01.bdae'||
     source?.sourceModelId!==1||source.race!==0||source.gender!==0||source.face!==0||source.hair!==1||source.beard!==0||
     Object.values(source.equipment||{}).some(Boolean)||!data.rig?.nodes?.length||!data.rig?.skins?.length||data.appearance||
     !Array.isArray(manifest.actions)||manifest.actions.some(name=>!data.clips.some(c=>c.name===name))||
     !Array.isArray(manifest.visibleMeshIndices)||manifest.visibleMeshIndices.some(i=>!Number.isInteger(i)||!data.meshes[i]))
    throw Error('Unverified human world-source descriptor');
  return {race:0,gender:0,sourceModelId:1,emptyEquipmentOnly:true,createsRole:false,writesCharacter:false,grantsEquipment:false};
}

export function humanWorldAppearanceGate({race,gender,face,hair,beard,look,equipment}={}){
  const unresolvedEquipment=Object.entries(equipment||{}).filter(([,item])=>item).map(([slot,item])=>({slot,item}));
  const supported=race===0&&gender===0&&face===0&&hair===1&&beard===0&&look?.hair==='hair1'&&
    look.hairColor==='color1'&&look.skinColor==='color1'&&unresolvedEquipment.length===0;
  return {supported,unresolvedEquipment,reason:supported?null:'Explicit human face0/hair1/beard0/color1 and empty equipment only'};
}

export function humanWorldSourceWrap(THREE,value){
  if(value===0)return THREE.RepeatWrapping;
  if(value===1||value===2)return THREE.ClampToEdgeWrapping;
  throw Error('Unverified original human texture address');
}

export function createHumanWorldFactory({THREE,manifest,data,materials,createCharacterFactory}){
  const scope=checkedHumanWorldSource(manifest,data);
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
    root.userData.sourceHumanWorld={...scope,actions:[...actions.keys()]};
    sampleHumanWorldPose(root,[{clip:'idle',timeSeconds:0,weight:1}]);
    return root;
  };
}

export function sampleHumanWorldPose(root,pose){
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

export function humanWorldPoseState(root){
  const c=controllers.get(root);return c?{...c.scope,pose:c.lastPose.map(p=>({...p})),height:root.userData.height}:null;
}

export function disposeHumanWorldPose(root){
  const c=controllers.get(root);if(!c)return;
  c.mixer.stopAllAction();c.mixer.uncacheRoot(root);controllers.delete(root);
  // The caller retains responsibility for the injected world's base mixer,
  // shared geometry/material ownership, and removal from its own scene.
}
