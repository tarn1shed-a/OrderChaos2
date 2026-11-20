// Passive observer of an existing own bridge. No tick, native actor or clock
// is manufactured; each selected body/mode remains its own trusted producer.
import{selectWorldContract,preparedWorldContract,matchesSourceMotion,LEGACY_WORLD_CONTRACT_SET,assertTrustedWorldContractSet,bindWorldContractSetReceipt}from'./contracts.mjs';
const stamp=p=>JSON.stringify([p.id,p.profession,p.sourceAvatar]);
export function observeSourceWorldFirstPose({registry,contractSet=LEGACY_WORLD_CONTRACT_SET,resolveContract=null,inputFactory,readOwner,readPreparedBody}){
 if(registry?.count!==45||typeof registry.check!=='function'||typeof inputFactory!=='function'||typeof readOwner!=='function'||typeof readPreparedBody!=='function'||resolveContract!==null&&typeof resolveContract!=='function')throw Error('Existing own motion and trusted owner/body-policy ports required');
 assertTrustedWorldContractSet(contractSet);
 const actors=new WeakMap();
 function owner(p,id,contract=null){
  const c=selectWorldContract(registry,p,resolveContract,contractSet),o=readOwner(p,id);
  if(!c||contract&&c!==contract||!o?.connected||o.player!==p||o.characterId!==p.id||typeof o.socket!=='object'||!o.socket||!Number.isSafeInteger(o.generation)||o.generation<0||o.identity!==id||o.mapId!==c.policy.mapId||typeof o.roomKey!=='string'||!o.roomKey||!['pending','active'].includes(o.phase)||!preparedWorldContract(c,readPreparedBody(c.bodyKey,c.mode,p)))throw Error('Actual same-session own model preparation required');
  return{contract:c,owner:o};
 }
 function current(p,r){const{owner:o}=owner(p,r.identity,r.contract);if(r.stamp!==stamp(p)||o.socket!==r.socket||o.generation!==r.generation||o.roomKey!==r.roomKey)throw Error('Original source actor owner changed');return o;}
 function wrap(context,airOnly){
  const bridges=new Map(),factoryOwner={};
  function record(p,id){const r=actors.get(p);if(!r||r.identity!==id||r.failed||r.factoryOwner!==factoryOwner)throw Error('Existing same native actor/context required');return r;}
  return{
   reset(p,id,position){
    if(actors.has(p))throw Error('One actual native fork per player');const{contract:c,owner:o}=owner(p,id);
    if(airOnly&&!c.capabilities.jump)throw Error('Ground-only body has no admitted air input route');
    if(!bridges.has(c)){const bridge=inputFactory(context,c);if([bridge?.reset,bridge?.tick,bridge?.forget].some(f=>typeof f!=='function')||c.capabilities.jump&&typeof bridge.press!=='function')throw Error('Actual own bridge interfaces required');bridges.set(c,bridge);}
    const bridge=bridges.get(c),out=bridge.reset(p,id,position);
    actors.set(p,{identity:id,stamp:stamp(p),socket:o.socket,generation:o.generation,roomKey:o.roomKey,contract:c,bridge,factoryOwner,pose:null,failed:false,forgotten:null});return out;
   },
   press(p,id,pressed){
    const r=record(p,id),o=current(p,r);if(typeof pressed!=='boolean'||o.phase==='pending'&&pressed)throw Error('Pending join has no world press');
    if(pressed&&!r.contract.capabilities.jump||typeof r.bridge.press!=='function')throw Error('No verified own press/release route');return r.bridge.press(p,id,pressed);
   },
   tick(p,id,input){
    const r=record(p,id);
    try{
     const o=current(p,r);if(o.phase==='pending'&&(input.forward!==false||!Array.isArray(input.velocity)||input.velocity.some(v=>v!==0)))throw Error('Pending join must retain its actual initial stopped input');
     const out=r.bridge.tick(p,id,input),c=r.contract,v=out?.sourceFields?.[c.poseField],m=out?.sourceFields?.sourceAnimation?.sourceMotion;
     if(v?.actorKey!==p.id||v.bindingId!==c.policy.bindingId||v.valueBytes!==c.policy.valueBytes||!matchesSourceMotion(c,m)||Object.keys(out?.sourceFields??{}).some(k=>/^source[A-Z][A-Za-z]*Pose$/.test(k)&&k!==c.poseField))throw Error('Actual own mode/binding native packet required');
     current(p,r);r.pose=structuredClone(v);return out;
    }catch(error){r.failed=true;r.pose=null;try{r.forgotten=r.bridge.forget(p,id);}catch(cleanup){throw new AggregateError([error,cleanup],'Actual source tick and release failed');}throw error;}
   },
   forget(p,id){const r=actors.get(p);if(!r||r.identity!==id||r.factoryOwner!==factoryOwner)throw Error('Existing captured native actor required');const out=r.forgotten??r.bridge.forget(p,id);actors.delete(p);return out;},
   inspect(p,id){const r=record(p,id);return r.bridge.inspect?.(p,id);},
  };
 }
 return Object.freeze({
  motionInputFactory:context=>wrap(context,false),airInputFactory:context=>wrap(context,true),
  readReady(p){
   const r=actors.get(p);if(!r||r.failed||!r.pose)return null;current(p,r);const c=r.contract,v=p[c.poseField];
   if(v?.actorKey!==p.id||v.bindingId!==c.policy.bindingId||v.valueBytes!==c.policy.valueBytes||v.values!==r.pose.values||!matchesSourceMotion(c,p.sourceAnimation?.sourceMotion))return null;
   return bindWorldContractSetReceipt(Object.freeze({actorKey:p.id,identity:r.identity,generation:r.generation,roomKey:r.roomKey,mapId:c.policy.mapId,sourceModelId:c.policy.modelId,bindingId:c.policy.bindingId,valueBytes:c.policy.valueBytes,sourceMotion:c.policy.motionSHA256,
    actualNativeActorAndConsumedPose:true,clientGLObserved:false,serverApprovalOrSkillsGranted:false,bodyKey:c.bodyKey,mode:c.mode,poseField:c.poseField}),contractSet);
  },
 });
}
