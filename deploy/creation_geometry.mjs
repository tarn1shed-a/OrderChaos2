// One shared source geometry traversal. No character creation, played-world
// admission, native model-ready reply or missing BEFF is produced here.
import {createSharedStageGuard} from './creation_batch/stage_guard.mjs';
import {recipeFromFrozenStage,createCreationGeometry,attachFrozenFiniteIdle} from './creation_batch/geometry_core.mjs';
import {sourceWrap} from './creation_batch/contracts.mjs';

export async function createSharedStageFactory({profile,loadBytes,crypto}){
 if(!profile||typeof loadBytes!=='function'||!crypto?.subtle)throw Error('Checked shared stage delivery required');
 const [policyBytes,registryBytes]=await Promise.all([profile.policyURL,profile.registryURL].map(loadBytes));
 const guard=await createSharedStageGuard({policyBytes,registryBytes,crypto});
 let live=true;
 const validate=guard.checkedStageModel;
 return Object.freeze({
  checkedStageModel:validate,
  build({THREE,renderer,manifest,data,identity,textures,attachmentData,createMaterial}){
   if(!live)throw Error('Shared stage factory disposed');
   const gl=renderer?.getContext();
   if(!gl||typeof WebGL2RenderingContext==='undefined'||!(gl instanceof WebGL2RenderingContext)||gl.isContextLost())
    throw Error('Observed live WebGL2 context required for original sampler capabilities');
   const textureCapabilities={contextType:'webgl2',mirrorRepeat:gl.MIRRORED_REPEAT===33648};
   const recipe=recipeFromFrozenStage({manifest,data,identity,validateStageModel:validate});
   const actor=createCreationGeometry({THREE,recipe,textures,attachmentData,createMaterial,textureCapabilities,
    samplerAddressResolver:identity.panel===2?sourceWrap:guard.samplerAddressResolver});
   let initial;
   try{initial=attachFrozenFiniteIdle(THREE,actor,data);}catch(error){actor.dispose();throw error;}
   let disposed=false;
   return {...actor,update:delta=>{if(!disposed)initial.update(delta);},
    sharedSource:{sourceDisplay:identity.request.displayId,sourceModel:identity.sourceModel.ID,
     bodyOnly:manifest.appearanceComplete!==true,unresolvedEffects:manifest.modelEffects.length,
     originalGPUReadyProduced:false,createsPlayableRole:false,fullClassQueueRestored:false},
    dispose(){if(disposed)return;disposed=true;initial.dispose();actor.dispose();}};
  },
  dispose(){if(!live)return;live=false;guard.dispose();},
 });
}
