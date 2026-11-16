// Exact shared source-pose validation/assignment body, parameterized lifetime.
import {finite,same} from '../creation_batch/contracts.mjs';
export function createSourcePoseApplier({identity,data,nodes,root,isDisposed}){
 if(!Array.isArray(data?.rig?.nodes)||!Array.isArray(nodes)||nodes.length!==data.rig.nodes.length||!root?.isObject3D||typeof isDisposed!=='function')throw Error('Actual source rig/nodes/root and lifetime required');
  const applySourcePose=pose=>{
   if(isDisposed())throw Error('Shared source geometry disposed');
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
 return applySourcePose;
}
