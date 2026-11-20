import{createNineBodyWorldRoute}from'./route.mjs';
// Adapt the parent's already verified payload/loaders to its existing createRoute
// callback. No data is taken from a browser here and no second server is made.
export function createNineBodyRouteAssembly({registry,admission,contractSet,humanProfile,eightDescriptors,
 loadHumanFemaleMotion,loadEightNativePort,createFemaleInputFactory,createSharedOwnAirInputBridge,
 enabledBodyKeys=[],startupPrepareKeys=[],creationKeys=[],canGather=()=>false}){
 if(typeof loadHumanFemaleMotion!=='function'||typeof loadEightNativePort!=='function')throw Error('Trusted pinned native delivery loaders required');
 let route=null,used=false;
 return Object.freeze({
  createRoute({legacyMotion,entryPosition,clock,onFault}){
   if(used)throw Error('One source route per existing game server');used=true;
   route=createNineBodyWorldRoute({registry,admission,contractSet,legacyMotion,entry:entryPosition,clock,onFault,humanProfile,eightDescriptors,
    createHumanFemaleMotion:options=>loadHumanFemaleMotion({entryPosition,options}),
    createEightNativePort:()=>loadEightNativePort({entryPosition}),createFemaleInputFactory,createSharedOwnAirInputBridge,
    enabledBodyKeys,startupPrepareKeys,creationKeys,canGather});
   return route;
  },
  get current(){return route;},
  close:()=>route?.close(),
 });
}
