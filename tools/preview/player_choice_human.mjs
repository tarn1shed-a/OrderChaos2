// Human1 actor root with exact fresh appearance and server-composed properties.
// The consumer never chooses animation names, priorities or an initial weapon.
import {createFastHumanPoseConsumer} from './character_human_queue_fast_avatar.mjs';
import {checkedHumanCreationDraft,resolveHumanCreationDraft} from './character_human_creation_defaults_avatar.mjs';

export function createPlayerChoiceHumanFactory({THREE,manifest,draftData,bodyData,binding,createCharacterFactory,characterAnimationState,createMaterials}){
 const descriptor=checkedHumanCreationDraft(manifest,draftData);
 const materialOwners=new WeakSet();
 for(const field of ['rig','meshes','materials','clips','characterMaterials','sourceCombatBinding'])
  if(JSON.stringify(bodyData[field])!==JSON.stringify(draftData[field]))throw Error('Frozen human geometry, rig or motion changed');
 if(typeof createMaterials!=='function'||typeof createCharacterFactory!=='function'||typeof characterAnimationState!=='function')throw Error('Actual current actor factory and materials required');
 return async snapshot=>{
  const a=snapshot?.sourceAvatar,p=snapshot?.profession;
  if(typeof snapshot?.id!=='string'||a?.format!=='oc2-web-source-avatar-v1'||a.key!=='human-male'||a.race!==0||a.gender!==0||a.sourceModelId!==1||!a.appearance||
    ![1,3,2,5,4].includes(p)||Object.values(snapshot.equipment||{}).some(Boolean))throw Error('Explicit empty-equipment human actor required');
  const variant=resolveHumanCreationDraft(descriptor,{professionIndex:[1,3,2,5,4].indexOf(p),displayId:a.creationDisplayId,
   face:a.appearance.face,hair:a.appearance.hair,beard:a.appearance.beard,skinColorWord:a.appearance.skinColor,hairColorWord:a.appearance.hairColor});
  if(!variant)throw Error('Own exact original fresh appearance unavailable');
  const materials=createMaterials({skin:[...variant.colors.skin],hair:[...variant.colors.hair]});
  if(!Array.isArray(materials)||materials.length!==bodyData.materials.length||materials.some(m=>!m?.isMaterial||materialOwners.has(m)))throw Error('Own complete independent source material array required');
  new Set(materials).forEach(m=>materialOwners.add(m));
  const body=createCharacterFactory(THREE,bodyData,materials)(),meshes=[];
  body.traverse(n=>{if(Number.isInteger(n.userData?.sourceMeshIndex))meshes[n.userData.sourceMeshIndex]=n;});
  if(meshes.filter(Boolean).length!==14)throw Error('Own original human body mesh binding missing');
  meshes.forEach((m,i)=>m.visible=variant.visibleMeshIndices.includes(i));
  const pose=await createFastHumanPoseConsumer({root:body,bones:characterAnimationState(body).bones,data:bodyData,binding,actorKey:snapshot.id});
  let disposed=false;
  return {body,apply(next){
   if(disposed||next.id!==snapshot.id||JSON.stringify(next.sourceAvatar)!==JSON.stringify(a)||next.profession!==p||Object.values(next.equipment||{}).some(Boolean))throw Error('Actual actor appearance changed without source resources');
   pose.apply(next.sourceHumanPose);return true;
  },inspect(){return {id:snapshot.id,key:a.key,sourceModelId:1,profession:p,creationDisplayId:a.creationDisplayId,appearance:{...a.appearance},pose:pose.state(),sourceEquipment:{},sourceClothingGranted:false};},
  dispose(){if(disposed)return;disposed=true;pose.dispose();new Set(materials).forEach(m=>m.dispose());}};
 };
}
