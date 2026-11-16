// Small source-policy adapters for one shared geometry core. They do not build
// another actor/renderer or turn CPU evidence into native GPU/role success.
import {checkedStageCandidate} from '../creation_class_stage/stage_switch.mjs';
import {checkedStageModel as oldStageModel} from '../creation_class_stage/actor_v6.mjs';
import {finite,same,sourceWrap} from './contracts.mjs';
import {createCreationCapabilityRegistry,REGISTRY_SHA256} from './source_capabilities_v1.mjs';
async function digest(bytes,crypto){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');}
const identityOf=i=>({screen:i.screen,panel:i.panel,race:i.race,gender:i.gender,professionIndex:i.professionIndex,profession:i.profession,displayId:i.request.displayId,sourceModelId:i.sourceModel.ID});
export async function createPinnedCreationStageAdapters({policyBytes,registryBytes,crypto,policySHA256}){
 if(!(policyBytes instanceof Uint8Array)||!crypto?.subtle||await digest(policyBytes,crypto)!==policySHA256)throw Error('Exact own source Class policy required');
 const policy=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(policyBytes)),registry=await createCreationCapabilityRegistry({registryBytes,crypto});
 if(policy.format!=='oc2-source-class-stage-policy-v1'||policy.choices?.length!==5||policy.wholeOriginalModelOrGPUOrRoleReadyClaimed!==false)throw Error('Own five-Class policy membership differs');
 let live=true;const ensure=()=>{if(!live)throw Error('Source stage adapters disposed');};
 const postPolicy=policy.postTextureOverride;
 function checkedPostAddress(address){
  const proof=address?.sourcePostTextureOverrideProof,mirror=address?.sourceTypedMirrorProof;
  if(!proof||!mirror||proof.format!=='oc2-source-post-texture-override-v1'||proof.sourceContractSHA256!==policy.sourcePostTextureOverrideReceiptSHA256||
   proof.originalRequestAppliesToOldTexture!==true||proof.samplingStateCopiedByOriginalSetter!==false||
   !same(proof.freshReplacementSourceUV,postPolicy.freshReplacementUV)||proof.requiresFreshHostMaterialTextureClone!==true||
   proof.actualAndroidCacheOrGPUFinalStateKnown!==false||!same(proof.originalMaterialRequest,address.sourceRequest)||
   address.source!==postPolicy.sourceReplacementTexture.path||address.sourceSHA256!==postPolicy.sourceReplacementTexture.sha256||
   proof.replacementTexturePath!==address.source||proof.replacementTextureSHA256!==address.sourceSHA256||
   proof.originalTextureSHA256!==postPolicy.sourceOriginalTexture.sha256||
   mirror.sourceRegistrySHA256!==REGISTRY_SHA256||mirror.sourceTextureSHA256!==postPolicy.sourceOriginalTexture.sha256||mirror.sourceModelSHA256!==proof.sourceModelSHA256||
   !same(address.sourceRequest,mirror.sourceRequest)||address.addressU!==0||address.addressV!==0)
   throw Error('Original post-texture replacement state proof differs');
  const context=postPolicy.sourceContexts.find(row=>same(row.identity,proof.identity)&&row.sourceModelSHA256===proof.sourceModelSHA256&&
   row.sourceSlot===proof.sourceSlot&&row.sourceItemKey===proof.sourceItemKey&&row.material===mirror.material&&row.sampler===mirror.sampler);
  if(!context)throw Error('Original own post-texture replacement context absent');
  return proof;
 }
 function validateStageModel(manifest,data,identity){
  ensure();if(identity.race!==policy.race||identity.gender!==policy.gender)return oldStageModel(manifest,data,identity);
  checkedStageCandidate(manifest,identity);
  const own=identityOf(identity),row=policy.choices.find(r=>same(r.identity,own)),source=data?.sourceCreation;
  if(!row||!same(manifest.sourceModel,row.sourceModel)||data?.format!=='bdae946-character-v1'||data.source!==row.sourceBodyPath||
   data.sourceSHA256!==row.sourceDataBodySHA256||!same(data.rig?.nodes,policy.bodyLiteralRigNodes)||
   !Array.isArray(data.rig?.skins)||!Array.isArray(data.meshes)||!Array.isArray(data.materials)||
   !same(source?.visibleMeshIndices,manifest.visibleMeshIndices)||source.displayId!==own.displayId||source.stage!==own.panel||source.screen!==own.screen||
   source.race!==own.race||source.gender!==own.gender||source.professionIndex!==own.professionIndex||source.profession!==own.profession||
   source.sourceModelId!==own.sourceModelId||source.originalFloatWeightsPreserved!==true||source.createdRole!==false||
   !same(manifest.modelEffects,row.modelEffects)||!same(manifest.sourceIndependentEffectGate,row.sourceIndependentEffectGate)||
   manifest.appearanceComplete!==row.appearanceComplete||manifest.mainBodyAppearanceComplete!==row.mainBodyAppearanceComplete||
   !Array.isArray(manifest.attachments))throw Error('Own original Class identity/body/effect gate differs');
  if(manifest.animationScope?.initialSourceName!=='idle'||manifest.animationScope.finiteInitialClipOnly!==true||
   manifest.animationScope.noInventedInfiniteIdleLoop!==true||data.clips?.length!==1||data.clips[0].name!=='idle'||
   data.clips[0].duration!==manifest.idleDuration||!(manifest.idleDuration>0))throw Error('Own finite source initial idle differs');
  const actualContracts=[];
  for(const material of manifest.materials)for(const [sampler,address]of Object.entries(material.addressing)){
   if(address.sourcePostTextureOverrideProof)checkedPostAddress(address);
   if(address.sourcePostTextureOverrideProof||address.sourceTypedMirrorProof)actualContracts.push({materialIndex:material.index,sampler,
    source:address.source,sourceSHA256:address.sourceSHA256,sourceRequest:address.sourceRequest,addressU:address.addressU,addressV:address.addressV,
    sourceTypedMirrorProof:address.sourceTypedMirrorProof??null,sourcePostTextureOverrideProof:address.sourcePostTextureOverrideProof??null});
  }
  if(!same(actualContracts,row.requiredSamplingContracts))throw Error('Required original sampling contracts were removed or altered');
  return manifest;
 }
 function samplerAddressResolver(THREE,value,capabilities,address,axis,context){
  ensure();
  if(address?.sourcePostTextureOverrideProof){
   checkedPostAddress(address);
   if(!context?.texture?.isTexture||!context.input?.isTexture||context.texture===context.input||value!==0||axis<0||axis>1)
    throw Error('Original fresh replacement state requires an actual fresh host material texture clone');
   return THREE.RepeatWrapping;
  }
  const proof=address?.sourceTypedMirrorProof;
  if(proof&&proof.axis===axis){
   if(proof.format!=='oc2-source-mirror-batch-request-v1'||proof.hostCapabilityAndPreviousWrapMustBeObserved!==true||
    proof.originalTextureOrModelOrGPUReadyProved!==false||address.sourceSHA256!==proof.sourceTextureSHA256||
    !same(address.sourceRequest,proof.sourceRequest)||value!==4||!context?.texture?.isTexture||context.texture===context.input)
    throw Error('Own exact typed Mirror property and fresh texture context required');
   const previous=axis===0?context.texture.wrapS:context.texture.wrapT;
   if(previous!==THREE.RepeatWrapping&&previous!==THREE.ClampToEdgeWrapping)throw Error('Current host previous wrap is outside the proved previous enum pair');
   const resolved=registry.resolveMirror({sourceModelSHA256:proof.sourceModelSHA256,material:proof.material,sampler:proof.sampler,
    sourceTextureSHA256:proof.sourceTextureSHA256,sourceRequest:proof.sourceRequest,axis,observedCapability:capabilities,
    previousSourceEnum:previous===THREE.RepeatWrapping?0:1});
   return resolved.sourceEnum===4?THREE.MirroredRepeatWrapping:previous;
  }
  return sourceWrap(THREE,value,capabilities,address,axis);
 }
 return Object.freeze({validateStageModel,samplerAddressResolver,
  inspect(){ensure();return {ownClassChoices:5,ownRigNodes:policy.bodyLiteralRigNodes.length,postTextureSourceContexts:postPolicy.sourceContexts.length,
   sourceOnly:true,originalGPUOrRoleReady:false};},dispose(){if(live){live=false;registry.dispose();}}});
}
