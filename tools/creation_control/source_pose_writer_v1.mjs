// Web ownership guard only; no source clock, sampler, renderer or ready reply.
export function createSourcePoseWriter({applySourcePose,current,stopFinite,updateFinite,isDisposed}){
 if([applySourcePose,current,stopFinite,updateFinite,isDisposed].some(f=>typeof f!=='function'))throw Error('Explicit source pose/finite-owner callbacks required');
 let mode='finite',disposed=false;
 const live=()=>{if(disposed||isDisposed())throw Error('Source pose writer disposed');if(current()!==true)throw Error('Retired source pose owner');};
 return Object.freeze({
  claim(){live();if(mode!=='finite')throw Error('Source pose ownership already claimed');stopFinite();mode='source';return true;},
  apply(pose){live();if(mode!=='source')throw Error('Stop finite writer before applying source pose');return applySourcePose(pose);},
  update(delta){live();if(mode==='source')return false;updateFinite(delta);return true;},
  inspect(){return {mode,disposed:disposed||isDisposed(),originalGPUOrModelReadyProduced:false,automaticShowStarted:false};},
  dispose(){disposed=true;},
 });
}
