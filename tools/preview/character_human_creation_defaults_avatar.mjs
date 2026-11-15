// Exact source fresh draft tuples. Does not grant demonstration clothing.
import {sourceHumanTrackSample,sourceHumanMotionWrap} from './character_world_motion_avatar.mjs';
export {sourceHumanMotionWrap as humanCreationDraftSourceWrap};
const FORMAT='oc2-human-male-original-creation-draft-v1',owners=new WeakMap(),ownedMaterials=new WeakSet();
const fields=['professionIndex','displayId','face','hair','beard','skinColorWord','hairColorWord'];

export function humanCreationDefaultInput(descriptor,professionIndex){
 if(descriptor?.format!==FORMAT||!Number.isInteger(professionIndex))return null;
 const row=descriptor.variants.find(v=>v.professionIndex===professionIndex);return row?{professionIndex,...row.draft}:null;
}
export function resolveHumanCreationDraft(descriptor,input){
 if(descriptor?.format!==FORMAT||!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).length!==fields.length||fields.some(k=>!Number.isSafeInteger(input[k])||input[k]<0))return null;
 return descriptor.variants.find(v=>v.professionIndex===input.professionIndex&&Object.entries(v.draft).every(([k,n])=>input[k]===n))||null;
}
export function checkedHumanCreationDraft(manifest,data){
 const d=manifest?.sourceHumanCreationDraft;
 if(manifest?.format!==FORMAT||d?.format!==FORMAT||d.race!==0||d.gender!==0||d.sourceBodyModelId!==1||d.creationPreviewAdmitted!==false||d.createdRole!==false||d.requiresExplicitDraftSelection!==true||
  d.originalServerDefaultAppearanceKnown!==false||d.originalServerInitialEquipmentKnown!==false||data.sourceHumanWorld||JSON.stringify(d)!==JSON.stringify(data.sourceHumanCreationDraft)||
  data.source!=='model/npc/character/human/male/oc2_human_m_body_01.bdae'||data.rig?.nodes?.length!==130||data.rig?.skins?.length!==14||data.meshes?.length!==14||data.clips?.length!==115||
  d.motionClock.constantBits!=='0x42055555'||d.motionClock.framesPerMsBits!=='0x3cf5c290'||d.motionClock.quaternionEpsilonBits!=='0x3d4ccccd'||d.motionClock.tolerance!==.002||d.motionClock.nativeKeySelection!==true||d.motionClock.sourceValuesChanged!==false||
  d.variants.length!==5||d.variants.some(v=>v.sourceClothingGranted!==false||Object.keys(v.sourceEquipment).length||v.originalServerDefaultAppearanceKnown!==false||v.sourceBodyModelId!==1||v.visibleMeshIndices.some(i=>!Number.isInteger(i)||!data.meshes[i]))||
  data.clips.some(c=>!manifest.actions.includes(c.name)||['attack','hurt','death'].includes(c.name)||c.tracks.some(t=>!t.nativeClock?.frames.length)))throw Error('Unverified original human creation body draft');
 return d;
}
export function createHumanCreationDraftFactory({THREE,manifest,data,createMaterials,createCharacterFactory}){
 const descriptor=checkedHumanCreationDraft(manifest,data);if(typeof createMaterials!=='function'||typeof createCharacterFactory!=='function')throw Error('Own materials/current factory required');
 const clips=data.clips.map(c=>new THREE.AnimationClip(c.name,c.duration,c.tracks.map(t=>{
  const track=new(t.type==='quaternion'?THREE.QuaternionKeyframeTrack:THREE.VectorKeyframeTrack)(`node_${t.node}.${t.type}`,t.times,t.values);
  track.createInterpolant=result=>new(class extends THREE.Interpolant{constructor(){super(track.times,track.values,t.nativeClock.components,result);}evaluate(time){const v=sourceHumanTrackSample(t,c.sourceRangeMs[0],time);for(let i=0;i<v.length;i++)this.resultBuffer[i]=v[i];return this.resultBuffer;}})();return track;
 })));
 return input=>{
  const variant=resolveHumanCreationDraft(descriptor,input);if(!variant)throw Error('Exact explicit source draft required');
  const colors={skin:[...variant.colors.skin],hair:[...variant.colors.hair]},materials=createMaterials(colors);
  if(!Array.isArray(materials)||materials.length!==data.materials.length||materials.some(m=>!m?.isMaterial||ownedMaterials.has(m)))throw Error('Independent own-body materials required');
  materials.forEach(m=>ownedMaterials.add(m));const create=createCharacterFactory(THREE,data,materials),root=create(),meshes=[];
  root.traverse(n=>{if(Number.isInteger(n.userData?.sourceMeshIndex))meshes[n.userData.sourceMeshIndex]=n;});if(meshes.filter(Boolean).length!==14)throw Error('Own body mesh mapping missing');
  for(let i=0;i<meshes.length;i++)meshes[i].visible=variant.visibleMeshIndices.includes(i);
  const mixer=new THREE.AnimationMixer(root),actions=new Map();for(const c of clips){const action=mixer.clipAction(c).setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;actions.set(c.name,action);}
  owners.set(root,{variant,materials,mixer,actions,pose:[]});sampleHumanCreationDraftPose(root,[{clip:'idle',timeSeconds:0,weight:1}]);return root;
 };
}
export function sampleHumanCreationDraftPose(root,pose){
 const e=owners.get(root);if(!e)throw Error('Own human creation draft required');
 if(!Array.isArray(pose)||!pose.length||pose.length>2||Math.abs(pose.reduce((s,p)=>s+p.weight,0)-1)>1e-6||pose.some(p=>!e.actions.has(p.clip)||!Number.isFinite(p.timeSeconds)||p.timeSeconds<0||p.timeSeconds>e.actions.get(p.clip).getClip().duration||!Number.isFinite(p.weight)||p.weight<0||p.weight>1)||new Set(pose.map(p=>p.clip)).size!==pose.length)throw Error('Unsupported original pose/time/weight');
 e.mixer.stopAllAction();for(const p of pose){const a=e.actions.get(p.clip);a.reset().play();a.time=p.timeSeconds;a.paused=true;a.setEffectiveWeight(p.weight);}e.mixer.update(0);root.updateMatrixWorld(true);e.pose=pose.map(p=>({...p}));return true;
}
export function humanCreationDraftState(root){const e=owners.get(root);return e?{input:{professionIndex:e.variant.professionIndex,...e.variant.draft},colors:{skin:[...e.variant.colors.skin],hair:[...e.variant.colors.hair]},visibleMeshIndices:[...e.variant.visibleMeshIndices],pose:e.pose.map(p=>({...p})),creationPreviewAdmitted:false,sourceEquipment:{},createdRole:false}:null;}
export function disposeHumanCreationDraft(root){const e=owners.get(root);if(!e)return;e.mixer.stopAllAction();e.mixer.uncacheRoot(root);e.materials.forEach(m=>m.dispose());owners.delete(root);}
