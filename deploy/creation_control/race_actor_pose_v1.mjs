// Thin adapter for the existing nine stage0 factories. No model/renderer/math.
import {checkedCreationModel,CREATION_RACE_IDENTITIES,completeElfConditionalPreview} from '/character_creation_race_preview_v2.mjs';
import {createSourcePoseApplier} from './source_pose_applier_v1.mjs';
import {createSourcePoseWriter} from './source_pose_writer_v1.mjs';
const HUMAN={'0:0':{key:'human-male',display:2038,model:1},'0:1':{key:'human-female',display:2045,model:32}},BOUND=new WeakSet();
export function attachRaceSourcePose({THREE,actor,data,race,gender,current}){
 const scope=checkedCreationModel(actor?.manifest,data,{race,gender}),source=CREATION_RACE_IDENTITIES[scope.key]||HUMAN[scope.key];
 if(!source||!actor||BOUND.has(actor)||typeof current!=='function'||current()!==true||!actor.root?.isObject3D||!Array.isArray(actor.nodes)||actor.nodes.length!==data.rig.nodes.length||
  !actor.nodes.every((n,i)=>n?.isBone&&n.name==='creation_node_'+i&&n.parent===(data.rig.nodes[i].parent<0?actor.root:actor.nodes[data.rig.nodes[i].parent]))||
  !Array.isArray(actor.meshes)||actor.meshes.length!==data.meshes.length||!actor.meshes.every(m=>m.isSkinnedMesh)||
  !actor.mixer||typeof actor.mixer.update!=='function'||typeof actor.mixer.stopAllAction!=='function'||typeof actor.mixer.uncacheRoot!=='function'||
  typeof actor.action?.isRunning!=='function'||!actor.action.isRunning()||typeof actor.update!=='function'||typeof actor.dispose!=='function'||actor.applySourcePose||actor.claimSourcePoseWriter)
  throw Error('Actual fresh Race nodes, finite mixer and current lifetime required');
 for(const skin of data.rig.skins){const mesh=actor.meshes[skin.mesh];if(!mesh||mesh.skeleton.bones.length!==skin.boneNodes.length||skin.boneNodes.some((n,i)=>mesh.skeleton.bones[i]!==actor.nodes[n]))throw Error('Actual own Race skin/node pointers differ');}
 const checkConditional=()=>{
  if(!source.conditional)return null;
  if(actor.conditionalReady?.hostSourceMaterialReady!==true||actor.conditionalReady.display!==2046||actor.conditionalReady.appearanceComplete!==false)throw Error('Existing ElfM conditional material gate required');
  return completeElfConditionalPreview(THREE,{manifest:actor.manifest,data,preview:actor});
 };
 checkConditional();
 // Race identity has no Class profession. Keep it absent, rather than adding
 // synthetic Class/stage fields to the frozen sourceCreation record.
 const identity={race,gender,panel:0,request:{displayId:source.display},sourceModel:{ID:source.model}};
 let disposed=false;const finiteUpdate=actor.update.bind(actor),release=actor.dispose.bind(actor),mixerUpdate=actor.mixer.update.bind(actor.mixer);
 const applySourcePose=createSourcePoseApplier({identity,data,nodes:actor.nodes,root:actor.root,isDisposed:()=>disposed});
 const writer=createSourcePoseWriter({applySourcePose,current,isDisposed:()=>disposed,updateFinite:finiteUpdate,
  stopFinite(){checkConditional();actor.mixer.stopAllAction();actor.mixer.uncacheRoot(actor.root);if(actor.action.isRunning())throw Error('Race finite writer did not stop');}});
 actor.mixer.update=function(delta){if(disposed)throw Error('Race source actor disposed');if(writer.inspect().mode==='source')throw Error('Finite Race mixer cannot write while source queue owns pose');return mixerUpdate(delta);};
 actor.update=writer.update;actor.applySourcePose=writer.apply;actor.claimSourcePoseWriter=writer.claim;actor.sourcePoseWriter=writer.inspect;
 actor.raceSourcePoseBridge=()=>({key:'race-'+source.key,display:source.display,sourceModelId:source.model,stage:0,conditionalMaterialGatePreserved:source.conditional===true,originalGPUOrHistoryProduced:false});
 actor.dispose=()=>{if(disposed)return;disposed=true;writer.dispose();release();};
 BOUND.add(actor);return actor;
}
