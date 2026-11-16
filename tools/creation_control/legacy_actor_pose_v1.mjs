// Thin fresh-instance adapter for the four published legacy Class actors.
import {checkedStageModel} from '../creation_class_stage/actor_v6.mjs';
import {createSourcePoseApplier} from './source_pose_applier_v1.mjs';
import {createSourcePoseWriter} from './source_pose_writer_v1.mjs';
const KEYS=new Set(['0:0:0:2024:1','0:0:1:2695:1','2:1:1:2112:2','2:1:4:2111:2']),BOUND=new WeakSet();
export function attachLegacyClassSourcePose({actor,data,identity,current}){
 if(identity?.panel!==1||identity.screen!=='CharacterChooseClass'||!KEYS.has([identity.race,identity.gender,identity.professionIndex,identity.request?.displayId,identity.sourceModel?.ID].join(':')))
  throw Error('Only the exact four legacy Class identities are covered');
 checkedStageModel(actor?.manifest,data,identity);
 if(!actor||BOUND.has(actor)||typeof current!=='function'||current()!==true||!actor.root?.isObject3D||!Array.isArray(actor.nodes)||actor.nodes.length!==data.rig.nodes.length||
  !actor.nodes.every(n=>n?.isBone)||!actor.mixer||typeof actor.mixer.update!=='function'||typeof actor.mixer.stopAllAction!=='function'||typeof actor.mixer.uncacheRoot!=='function'||
  typeof actor.action?.isRunning!=='function'||typeof actor.update!=='function'||typeof actor.dispose!=='function')
  throw Error('Actual fresh legacy nodes, finite mixer and lifetime required');
 let disposed=false;const finiteUpdate=actor.update.bind(actor),release=actor.dispose.bind(actor),mixerUpdate=actor.mixer.update.bind(actor.mixer);
 const applySourcePose=createSourcePoseApplier({identity,data,nodes:actor.nodes,root:actor.root,isDisposed:()=>disposed});
 const writer=createSourcePoseWriter({applySourcePose,current,isDisposed:()=>disposed,updateFinite:finiteUpdate,
  stopFinite(){actor.mixer.stopAllAction();actor.mixer.uncacheRoot(actor.root);if(actor.action.isRunning())throw Error('Legacy finite writer did not stop');}});
 actor.mixer.update=function(delta){if(disposed)throw Error('Legacy source actor disposed');if(writer.inspect().mode==='source')throw Error('Finite mixer cannot write while source queue owns pose');return mixerUpdate(delta);};
 actor.update=writer.update;actor.applySourcePose=writer.apply;actor.claimSourcePoseWriter=writer.claim;
 actor.sourcePoseWriter=writer.inspect;
 actor.dispose=()=>{if(disposed)return;disposed=true;writer.dispose();release();};
 BOUND.add(actor);return actor;
}
