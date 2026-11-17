// One server/store/ticker consumes this route. Original body-specific producers
// retain their own native actors, bindings and clock/global-state domains.
import{createEightDomain}from'./eight_domain.mjs';
import{createNineBodyMotionSelector,assertSameWorldFrame}from'./selector.mjs';
const empty=v=>!!v&&typeof v==='object'&&!Array.isArray(v)&&Object.values(v).every(x=>x===null);
export function createNineBodyWorldRoute({registry,admission,contractSet,legacyMotion,entry,clock,
 humanProfile,createHumanFemaleMotion,createFemaleInputFactory,eightDescriptors,createEightNativePort,createSharedOwnAirInputBridge,
 enabledBodyKeys=[],startupPrepareKeys=[],creationKeys=[],canGather=()=>false,onFault=()=>{}}){
 const{selectWorldContract,preparedWorldContract,assertTrustedWorldContractSet,createSourceWorldPendingJoins,observeSourceWorldFirstPose,createCommonSourceWorldCommandGate}=admission??{};
 if(registry?.count!==45||typeof clock!=='function'||typeof createHumanFemaleMotion!=='function'||typeof createFemaleInputFactory!=='function'||typeof canGather!=='function'||typeof assertTrustedWorldContractSet!=='function')throw Error('Explicit current identity, canonical admission and native providers required');
 assertTrustedWorldContractSet(contractSet);if(contractSet!==admission.SOURCE_WORLD_CONTRACT_SET)throw Error('The compiled shared nine-source contract set is required');const contracts=contractSet.contracts;
 function plan(keys,allow){if(!Array.isArray(keys)||new Set(keys).size!==keys.length||keys.some(k=>typeof k!=='string'||!Object.hasOwn(contracts,k)||allow&&!allow.includes(k)))throw Error('Explicit unique configured body plan required');return[...keys];}
 const enabled=plan(enabledBodyKeys),startup=plan(startupPrepareKeys,enabled),creatable=plan(creationKeys,enabled);
 if(enabled.some(key=>key==='human-female'?contracts[key].mode!=='normal15':contracts[key].mode!=='own-air'||!Object.hasOwn(eightDescriptors,key)))throw Error('Enabled source plan has no fixed own descriptor');
 const prepared=new Map(),disabled=new Set();let observer,pending,human=null,eight=null,attached=null,closed=false,ownerCount=0;
 const resolveContract=(record,avatar)=>enabled.includes(avatar.key)?contracts[avatar.key]:null;
 function checked(record){if(!record||typeof record.id!=='string'||!record.id||!empty(record.equipment)||record.hotbar!==null||record.sourceInventoryPolicy!=='empty-compatible-container-v1'||!record.inventory||typeof record.inventory!=='object'||Array.isArray(record.inventory)||Object.keys(record.inventory).length)throw Error('Current source record with known empty container required');const c=selectWorldContract(registry,record,resolveContract,contractSet);if(!c)throw Error('Body not configured for this server');return c;}
 const readPreparedBody=(key,mode)=>contracts[key]?.mode===mode?prepared.get(key)??null:null;
 pending=createSourceWorldPendingJoins({registry,contractSet,resolveContract,clock,readPreparedBody,readNativeReady:p=>observer.readReady(p),onFault});
 const inputFactory=(context,c)=>{
  if(c===contracts['human-female'])return createFemaleInputFactory({registry,profile:humanProfile,sourceTimeval:pending.sourceTimeval,eventOwner:pending.eventOwner})(context);
  return eight.inputFactory(context,c);
 };
 observer=observeSourceWorldFirstPose({registry,contractSet,resolveContract,inputFactory,readOwner:pending.readOwner,readPreparedBody});
 eight=createEightDomain({registry,descriptors:eightDescriptors,contracts,preparedWorldContract,createNativePort:createEightNativePort,createInputBridge:createSharedOwnAirInputBridge,entry,pending,airInputFactory:observer.airInputFactory});
 function prepareKey(key){
  if(closed||!enabled.includes(key)||disabled.has(key))throw Error('Body is not available on this server');if(prepared.has(key))return prepared.get(key);const c=contracts[key];let result;
  try{
   if(key==='human-female'){
    const value=createHumanFemaleMotion({prepareBodies:['human-female'],airInputFactory:observer.airInputFactory,readNativeTimeval:pending.readNativeTimeval,readGatherOwner:(p,id)=>pending.readOwner(p,id)});
    try{result=value?.preparedPlayerBodies?.find(r=>r.key===key);if(!preparedWorldContract(c,result))throw Error('Actual HumanF normal15 preparation differs');assertSameWorldFrame(legacyMotion,value);human=value;}catch(error){value?.close();throw error;}
   }else{result=eight.prepare(key);assertSameWorldFrame(legacyMotion,eight.getMotion());}
   if(!preparedWorldContract(c,result))throw Error('Actual body preparation does not match its own contract');prepared.set(key,result);return result;
  }catch(error){disabled.add(key);onFault(error);throw error;}
 }
 const getSourceMotion=p=>{const c=selectWorldContract(registry,p,resolveContract,contractSet);if(!c||!empty(p.equipment)||!preparedWorldContract(c,readPreparedBody(c.bodyKey,c.mode)))throw Error('Actual own body preparation required; no legacy fallback');return c.bodyKey==='human-female'?human:eight.getMotion();};
 const motionBase=createNineBodyMotionSelector({legacy:legacyMotion,registry,readSourceMotion:getSourceMotion,isClosed:()=>closed,onOwnerCount:n=>{ownerCount+=n;}});
 const gate=createCommonSourceWorldCommandGate({registry,contractSet,resolveContract,resolveCapability:pending.capability,canGather:(ws,c)=>c.bodyKey==='human-female'&&canGather(ws,c)===true});
 function authenticatedPreflight(ws,record,msg){
  try{
   if(closed||!attached||ws?.readyState!==1||attached.store.records.get(record.id)!==record||pending.entryActiveView(attached.active).has(record.id)||!msg||msg.scene!=='resources'||msg.mapWindow!=='heaven-landing'||Object.hasOwn(msg,'lab')||Object.hasOwn(msg,'sourceAvatar')||msg.profession!==record.profession)return false;
   const c=checked(record);prepareKey(c.bodyKey);return pending.preflight(ws,record,msg);
  }catch{return false;}
 }
 const pendingHost=Object.freeze({...pending,
  attach(runtime){if(runtime?.clock!==clock)throw Error('One authoritative game clock required');pending.attach(runtime);attached=runtime;},
  preflight:authenticatedPreflight,
 });
 const close=()=>{if(closed)return;pending.dispose();closed=true;prepared.clear();return Promise.all([human?.close(),eight.close(),legacyMotion.close()]);};
 const motion=Object.freeze({...motionBase,close});
 try{for(const key of startup)prepareKey(key);}catch(error){close();throw error;}
 return Object.freeze({motion,pending:pendingHost,observer,gate,contractSet,
  prepareCurrent(record){return prepareKey(checked(record).bodyKey);},readPreparedBody,
  canCreate(selection,avatar){try{const verified=registry.check(avatar,selection.profession);if(closed||!creatable.includes(verified.key)||JSON.stringify(registry.draft(selection))!==JSON.stringify(verified))return false;return preparedWorldContract(contracts[verified.key],prepareKey(verified.key));}catch{return false;}},
  inspect:()=>({enabledKeys:enabled,startupPrepareKeys:startup,creationKeys:creatable,preparedKeys:[...prepared.keys()],disabledKeys:[...disabled],ownerCount,onePending:true,oneObserver:true,oneGate:true,newTicker:false,newClock:false,HumanFPrepared:!!human,eight:eight.inspect(),closed}),
  close});
}
