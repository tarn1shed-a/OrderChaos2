// A source capability validator for the shared core; no actor or renderer.
import {same} from './contracts.mjs';
import {createCreationCapabilityRegistry,REGISTRY_SHA256} from './source_capabilities_v1.mjs';
export async function createTypedArmorRootValidator({registryBytes,crypto}){
 const registry=await createCreationCapabilityRegistry({registryBytes,crypto});let live=true;
 const ensure=()=>{if(!live)throw Error('Typed armor validator disposed');};
 function validate(row,source,identity){
  ensure();const proof=registry.checkRigidArmorRoot({identity,sourceRequest:row.sourceRequest,source});
  const expected={format:'oc2-source-typed-rigid-armor-root-v1',sourceRegistrySHA256:REGISTRY_SHA256,
   sourceCPUConsumer:proof.sourceCPUConsumer,slot:14,attachmentTarget:'actorRoot',sourceBDAESHA256:proof.sourceBDAESHA256,
   originalRootBranchProved:true,skinWeightsInvented:false,originalModelOrGPUReadyClaimed:false};
  if(row.kind!=='original-rigid-armor-root-v1'||row.slot!==14||row.itemKey!==row.sourceRequest?.itemKey||row.source!==source.source||!same(row.mount,expected))
   throw Error('Exact typed armor root mount required');
  return proof;
 }
 return Object.freeze({validate,dispose(){if(live){live=false;registry.dispose();}}});
}
