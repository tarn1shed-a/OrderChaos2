// Only transport already composed original CPU properties onto the same rig.
// No queue policy, guessed priorities, quaternion/Three mixing or fallback pose.
const owners=new WeakMap();
const NATIVE='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4';
const BODY='e6d6e16b6bed829922ebc06fbd7ff458a0ea1c4622d0fbd46a81c5493b71d783';
const MASK='0d18cc2976795cbb2535f3ca73bc9e8810f18a84d6f653f075c6de370c1f25b1';
const MOTION='14adc20cc5f602ab97c9f10414522a38e7590199efc90cb57dfe0868af21cada';

export function checkedHumanCompositionBinding(binding,data){
 if(binding?.format!=='oc2-human-original-composition-binding-v1'||binding.nativeSHA256!==NATIVE||binding.sourceBodyDataSHA256!==BODY||binding.sourceMaskSHA256!==MASK||binding.sourceMotion?.sha256!==MOTION||binding.sourceMotion.race!==0||binding.sourceMotion.gender!==0||binding.sourceMotion.sourceModelId!==1||binding.properties!==135||binding.propertyOrder?.length!==135||binding.originalComposerEntry!=='0x372318'||binding.originalOrdinaryPropertyMixEntry!=='0x11894f8'||binding.completeFrameContextFactoryExecuted!==false||binding.serverDefaultsSupplied!==false||binding.savesReadOrWritten!==false||binding.originalGPUExecuted!==false||binding.originalConstructor?.originalComposerConstructionExecuted!==true||data?.format!=='bdae946-character-v1'||data.sourceHumanWorld?.sourceModelId!==1||JSON.stringify(binding.rigNodes)!==JSON.stringify(data.rig?.nodes))throw Error('Verified own human original composition binding required');
 const keys=new Set();
 for(const [i,row]of binding.propertyOrder.entries()){
  const source=data.rig.nodes[row.node],key=row.node+':'+row.sourceType;
  if(row.sourcePropertyIndex!==i||!source||source.name!==row.sourceNode&&!(source.aliases||[]).includes(row.sourceNode)||![1,5].includes(row.sourceType)||![0,.5,1].includes(row.originalPropertyWeight)||keys.has(key))throw Error('Original property ordering/target differs');
  keys.add(key);
 }
 return binding;
}

export function attachHumanComposition({root,bones,data,binding}){
 checkedHumanCompositionBinding(binding,data);
 if(!root?.updateMatrixWorld||owners.has(root)||!Array.isArray(bones)||bones.length!==data.rig.nodes.length||new Set(bones).size!==bones.length||bones.some((b,i)=>!b?.isBone||b.name!==`node_${i}`||data.rig.nodes[i].parent>=0&&b.parent!==bones[data.rig.nodes[i].parent]))throw Error('Independent current-factory human bone targets required');
 owners.set(root,{bones:[...bones],binding:structuredClone(binding),last:null});return root;
}

export function applyHumanComposition(root,pose){
 const entry=owners.get(root);if(!entry)throw Error('Own human composition instance required');
 const binding=entry.binding;
 if(pose?.format!=='oc2-human-original-composed-properties-v1'||pose.nativeSHA256!==NATIVE||pose.sourceBodyDataSHA256!==BODY||pose.sourceMaskSHA256!==MASK||JSON.stringify(pose.sourceMotion)!==JSON.stringify(binding.sourceMotion)||pose.originalFullCompositionEntryExecuted!==true||pose.intraLayerPropertyMixCPU!==true||pose.completeFrameContextFactoryExecuted!==false||pose.originalGPUExecuted!==false||pose.ordinaryMixModeFromOriginalConstructor!==0||pose.properties?.length!==135||pose.originalSetterCalls?.length!==135||new Set(pose.originalSetterCalls.map(c=>c.property)).size!==135||pose.originalSetterCalls.some(c=>c.entry!=='0x11891f4'||c.source!=='original-composition'||!Number.isInteger(c.property)||c.property<0||c.property>=135))throw Error('Complete original CPU composition packet required');
 // Validate the whole payload before changing any live bone. The source
 // quaternion is copied as produced; no normalisation or host interpolation.
 const pending=pose.properties.map((row,i)=>{
  const target=binding.propertyOrder[i];
  if(row.node!==target.sourceNode||row.type!==target.sourceType||!Array.isArray(row.value)||row.value.length!==(row.type===5?4:3)||row.value.some(v=>!Number.isFinite(v)))throw Error('Original composed property payload differs');
  return{bone:entry.bones[target.node],type:row.type,values:[...row.value]};
 });
 for(const row of pending)(row.type===5?row.bone.quaternion:row.bone.position).fromArray(row.values);
 root.updateMatrixWorld(true);entry.last={sourceMotion:{...pose.sourceMotion},properties:135,originalComposerEntry:binding.originalComposerEntry,sourceQueuePacket:structuredClone(pose.sourceQueuePacket)};return true;
}

export function humanCompositionState(root){const entry=owners.get(root);return entry?structuredClone(entry.last):null;}
export function detachHumanComposition(root){owners.delete(root);}
