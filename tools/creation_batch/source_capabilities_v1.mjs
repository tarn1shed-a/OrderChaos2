// Typed source-data abilities. Not a ready callback, actor factory, deployment
// permission, or an unqualified expansion of the frozen geometry core.
import {finite,same} from './contracts.mjs';
export const REGISTRY_SHA256='337c79ea6501456014771e94222648257f676464e261e33cb367853a5fdabc60';
async function digest(bytes,crypto){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');}
function identityOf(input){
 if(input?.request&&input?.sourceModel)return {screen:input.screen,panel:input.panel,race:input.race,gender:input.gender,professionIndex:input.professionIndex,
  profession:input.profession,displayId:input.request.displayId,sourceModelId:input.sourceModel.ID};
 return input;
}
export async function createCreationCapabilityRegistry({registryBytes,crypto}){
 if(!(registryBytes instanceof Uint8Array)||!crypto?.subtle||await digest(registryBytes,crypto)!==REGISTRY_SHA256)throw Error('Exact original capability batch projection required');
 const registry=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(registryBytes));
 if(registry.format!=='oc2-creation-typed-capability-registry-v1'||registry.mirrorMaterials?.length!==10||registry.rigidRootArmor?.length!==2||
  registry.selectedSkinnedArmor?.length!==1||registry.unselectedRigidAlternatives?.length!==1||registry.wholeModelsOrGPUOrRolesReadyClaimed!==false)
  throw Error('Original source capability membership differs');
 let live=true;
 const ensure=()=>{if(!live)throw Error('Source capability registry disposed');};
 return Object.freeze({
  inspect(){ensure();return {mirrorMaterials:10,mirrorAxes:[0,1],rigidRootArmor:2,selectedSkinInsteadOfOldRigid:1,sourceOnly:true,originalGPUOrRoleReady:false};},
  resolveMirror({sourceModelSHA256,material,sampler,sourceTextureSHA256,sourceRequest,axis,observedCapability,previousSourceEnum}){
   ensure();const rows=registry.mirrorMaterials.filter(r=>r.sourceModelSHA256===sourceModelSHA256&&r.material===material&&r.sampler===sampler&&r.axis===axis);
   if(rows.length!==1)throw Error('Mirror source property is not in the proved batch');
   const row=rows[0];
   if(row.sourceTextureSHA256!==sourceTextureSHA256||!same(row.sourceRequest,sourceRequest)||row.sourceEnum!==4||
    observedCapability?.contextType!=='webgl2'||typeof observedCapability.mirrorRepeat!=='boolean'||![0,1].includes(previousSourceEnum))
    throw Error('Exact Mirror property, observed current capability and current previous enum required');
   return Object.freeze({action:observedCapability.mirrorRepeat?'applyMirror':'preservePrevious',axis,
    sourceEnum:observedCapability.mirrorRepeat?4:previousSourceEnum,
    GLValue:observedCapability.mirrorRepeat?33648:null,
    sourceCPUFragment:row.sourceConsumer,originalGPUObserved:false,sourceOnly:true});
  },
  checkRigidArmorRoot({identity,sourceRequest,source}){
   ensure();const own=identityOf(identity);
   const selectedSkin=registry.selectedSkinnedArmor.find(row=>same(row.identity,own));
   if(selectedSkin&&sourceRequest?.path===selectedSkin.sourcePath)throw Error('Original alias selects a real skin controller here; old rigid variant is not admitted');
   const rows=registry.rigidRootArmor.filter(row=>same(row.identity,own));
   if(rows.length!==1)throw Error('Original identity has no proved rigid armor root capability');
   const row=rows[0],request={slot:sourceRequest?.slot,itemKey:sourceRequest?.itemKey,path:sourceRequest?.path,positionAnchor:sourceRequest?.positionAnchor};
   if(!same(row.sourceRequest,request)||source?.source!==row.sourcePath||source.sourceBDAESHA256!==row.sourceBDAESHA256||
    source.sourceControllerCount!==0||source.rig||source.meshes?.length!==1||source.meshes[0].name!==row.sourceMeshName||
    source.meshes[0].vertexCount!==row.sourceVertexCount||!same(source.sourceNodes,row.sourceNodes))throw Error('Own original rigid source/slot/controller differs');
   const proof=source.sourceRigidMeshTransform,expected=row.sourceRigidMeshTransform;
   if(!proof||proof.nativeCPUExecuted!==true||proof.originalGPUObserved!==false||proof.sourceLiteralMeshAttachmentVerified!==true||
    proof.originalModelLoaderExecuted!==false||proof.format!==expected.format||proof.sourceMeshName!==expected.sourceMeshName||proof.sourceNodeIndex!==expected.sourceNodeIndex||
    !same(proof.sourceAncestorIndices,expected.sourceAncestorIndices)||!same(proof.sourceAncestors,expected.sourceAncestors)||
    !same(proof.sourceNode,expected.sourceNode)||!finite(proof.nativeMatrix,16)||proof.nativeMatrix.some((v,i)=>Math.abs(v-expected.nativeMatrix[i])>2e-6))
    throw Error('Own original complete rigid ancestor proof differs');
   return Object.freeze({attachmentTarget:'actorRoot',slot:14,sourceBDAESHA256:row.sourceBDAESHA256,
    sourceCPUConsumer:row.originalConsumer,hostOwnBodyAndMaterialConstructionRequired:true,
    skinWeightsInvented:false,originalModelOrGPUReady:false});
  },
  inspectSelectedSkin({identity,sourcePath,sourceSHA256}){
   ensure();const rows=registry.selectedSkinnedArmor.filter(row=>same(row.identity,identityOf(identity))&&row.sourcePath===sourcePath&&row.sourceBDAESHA256===sourceSHA256);
   if(rows.length!==1)throw Error('Own original selected skin source differs');
   return Object.freeze({sourceControllerCount:rows[0].sourceControllerCount,sourceVertices:rows[0].sourceVertices,
    sourceBoneNames:rows[0].sourceBoneNames.slice(),mustUseSkinProvider:true,rigidRootCapabilityGranted:false,originalGPUOrWholeModelReady:false});
  },
  dispose(){live=false;}
 });
}
