// Losslessly copy completed original CPU values. No action/queue decisions.
import {checkedHumanCompositionBinding} from './character_human_queue_composition_avatar.mjs';
const owners=new WeakMap();

export async function createFastHumanPoseConsumer({root,bones,data,binding,actorKey,crypto=globalThis.crypto}={}){
 checkedHumanCompositionBinding(binding,data);
 if(typeof actorKey!=='string'||!actorKey.length||actorKey.length>128||!crypto?.subtle||!root?.updateMatrixWorld||owners.has(root)||!Array.isArray(bones)||bones.length!==data.rig.nodes.length||new Set(bones).size!==bones.length||bones.some((b,i)=>!b?.isBone||b.name!==`node_${i}`||data.rig.nodes[i].parent>=0&&b.parent!==bones[data.rig.nodes[i].parent]))throw Error('Explicit actor, independent source bones and SHA implementation required');
 const order=binding.propertyOrder.map(row=>({...row}));
 const description=[binding.nativeSHA256,binding.sourceBodyDataSHA256,binding.sourceMaskSHA256,binding.sourceMotion.sha256,...order.map((r,i)=>`${i}|${r.node}|${r.sourceNode}|${r.sourceType}|${r.originalPropertyWeight===0?'00000000':r.originalPropertyWeight===.5?'0000003f':'0000803f'}`)].join('\n');
 const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(description)),bindingId=Array.from(new Uint8Array(digest),n=>n.toString(16).padStart(2,'0')).join('');
 if(owners.has(root))throw Error('Source pose root already attached');
 const owner={bindingId,actorKey,bones:[...bones],last:null};owners.set(root,owner);
 return {
  apply(pose){
   if(owners.get(root)!==owner||pose?.format!=='oc2-human-original-fast-pose-v1'||pose.actorKey!==actorKey||pose.bindingId!==bindingId||pose.valueEncoding!=='float32-le-base64'||pose.valueBytes!==1992||typeof pose.values!=='string'||!/^[A-Za-z0-9+/]{2656}$/.test(pose.values))throw Error('Own complete original pose transport required');
   const bytes=Uint8Array.from(atob(pose.values),c=>c.charCodeAt(0));if(bytes.length!==1992)throw Error('Original pose value span differs');
   const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),pending=[];let offset=0;
   for(const row of order){const values=[];for(let i=0;i<(row.sourceType===5?4:3);i++){const v=view.getFloat32(offset,true);offset+=4;if(!Number.isFinite(v))throw Error('Nonfinite source property rejected');values.push(v);}pending.push({bone:owner.bones[row.node],type:row.sourceType,values});}
   if(offset!==1992)throw Error('Original source property widths differ');
   for(const row of pending)(row.type===5?row.bone.quaternion:row.bone.position).fromArray(row.values);
   root.updateMatrixWorld(true);owner.last={actorKey,bindingId,sourceProperties:135,valueBytes:1992};return true;
  },
  state(){return owners.get(root)===owner&&owner.last?{...owner.last}:null;},
  dispose(){if(owners.get(root)===owner)owners.delete(root);},
  bindingId,
 };
}
