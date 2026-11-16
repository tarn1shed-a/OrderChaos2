// Shared browser/server admission of source recipes. No renderer or role gate.
import {createCreationStageAdapters} from './stage_adapters_v1.mjs';
import {checkedStageModel} from '../creation_class_stage/actor_v6.mjs';
import {same} from './contracts.mjs';

export async function createSharedStageGuard({policyBytes,registryBytes,crypto}){
 const adapters=await createCreationStageAdapters({policyBytes,registryBytes,crypto});
 const own=JSON.parse(new TextDecoder().decode(policyBytes));let live=true;
 const validate=(manifest,data,identity)=>{
  if(!live)throw Error('Shared stage guard disposed');
  if(identity.race!==own.race||identity.gender!==own.gender)throw Error('Own shared body identity required');
  if(identity.panel!==2)return adapters.validateStageModel(manifest,data,identity);
  checkedStageModel(manifest,data,identity);
  // Plain Part recipes use their original generic guard, never Class clothes
  // or its independent-effect exception. Typed special Part paths stay closed.
  if(!same(data.rig.nodes,own.bodyLiteralRigNodes)||manifest.modelEffects.length||manifest.appearanceComplete!==true||
   manifest.sourceIndependentEffectGate!=null||manifest.attachments.some(r=>r.kind!==undefined)||
   [...manifest.materials,...manifest.attachments.flatMap(r=>r.materials)].some(r=>Object.values(r.addressing).some(a=>
    a.addressU===4||a.addressV===4||a.sourceTypedMirrorProof||a.sourcePostTextureOverrideProof)))
   throw Error('Unproved special source Part recipe');
  return manifest;
 };
 return Object.freeze({checkedStageModel:validate,samplerAddressResolver:adapters.samplerAddressResolver,
  dispose(){if(!live)return;live=false;adapters.dispose();}});
}
