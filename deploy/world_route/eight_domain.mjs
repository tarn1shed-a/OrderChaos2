// Eight data rows, one existing Python/native transport and original carrier.
// This contains host ownership/preparation only; source algorithms stay frozen.
export function createEightDomain({registry,descriptors,contracts,preparedWorldContract,createNativePort,createInputBridge,entry,pending,airInputFactory}){
 const keys=Object.keys(descriptors),cache=new Map();let native=null,motion=null,cold=null,closed=false,creating=false;
 if(!keys.length||keys.some(k=>!Object.hasOwn(contracts,k)||contracts[k].mode!=='own-air')||typeof createNativePort!=='function')throw Error('Explicit fixed own-eight domain required');
 function checkedCold(value,key){if(value?.format!=='oc2-own-eight-cold-runtime-v1'||value.domain!=='own-eight-controller'||value.sourceValuesFromOriginalProducer!==true||value.qaConfiguredRandomWordsAdmittedAsInitialState!==false||value.HumanFAndLegacyIncluded!==false||value.originalNativeSHA256!==native.info.nativeSHA256||value.coldInitialized!==true||value.bodyKey!==key||value.originalSetting34Word!==0xc47a0000||value.originalFilterCold!==0||value.unknownFilterOrSettingUpdateAdmitted!==false)throw Error('Actual original cold runtime required');return value;}
 function transport(){
  if(closed||creating)throw Error('Unavailable own-eight domain');if(native)return native;
  creating=true;let port;
  try{
   port=createNativePort();if(typeof port?.rpc?.request!=='function'||typeof port?.rpc?.close!=='function'||typeof port?.bindQuestMotion!=='function'||!Array.isArray(port?.info?.sourceSpeciesKeys)||keys.some(k=>!port.info.sourceSpeciesKeys.includes(k)))throw Error('Actual fixed eight-body native transport required');
   for(const key of keys){const c=contracts[key],d=descriptors[key];if(d.binding?.bindingId!==c.policy.bindingId||d.binding?.valueBytes!==c.policy.valueBytes||Object.entries(c.sourceMotion).some(([k,v])=>d.profile?.[k]!==v))throw Error('Own eight profile/binding differs from canonical contract');}
   native=port;motion=port.bindQuestMotion(port.rpc,port.info,entry,undefined,null,airInputFactory);return native;
  }catch(error){port?.rpc?.close();native=null;motion=null;throw error;}finally{creating=false;}
 }
 const request=(operation,data)=>transport().rpc.request('withOwnSourceTimeval',{timeval:pending.readNativeTimeval(operation,data),operation,data});
 function prepare(key){
  if(!keys.includes(key)||closed)throw Error('Unconfigured own body');if(cache.has(key))return cache.get(key);
  try{const port=transport(),c=contracts[key],actual=request('prepareOwnBody',{species:key});if(!preparedWorldContract(c,actual))throw Error('Actual own body preparation differs');
  if(!cold){const timevals=[pending.readNativeTimeval('cold-rng'),pending.readNativeTimeval('cold-origin')];const value=port.rpc.request('initializeOwnRuntime',{species:key,timevals});if(value?.sourceValuesFromOriginalProducer!==true||JSON.stringify(value.actualTimevals)!==JSON.stringify(timevals))throw Error('Original bootstrap did not consume the authoritative host clock');cold=value;}
  const runtime=checkedCold(port.rpc.request('readOwnRuntimeInitialization',{species:key}),key);if(runtime.originalOriginMs!==cold.originalOriginMs||runtime.initialRNGSHA256!==cold.initialRNGSHA256)throw Error('Own body is outside the one actual source carrier');
  const value=Object.freeze({...actual,key,pose:Object.freeze({...actual.pose}),sourceRuntimeInitialized:true,sourceRuntime:Object.freeze({...runtime})});cache.set(key,value);return value;
  }catch(error){if(!cache.size){native?.rpc.close();native=null;motion=null;cold=null;}throw error;}
 }
 function inputFactory(context,c){
  const port=transport();if(context.rpc!==port.rpc||context.info!==port.info||!keys.includes(c.bodyKey)||contracts[c.bodyKey]!==c)throw Error('Different eight native context/contract');
  let call=null;
  const run=(p,id,fn,closing=false)=>{if(call)throw Error('Nested native owner operation');const owner=closing?null:pending.readOwner(p,id);if(!closing&&(!owner||owner.player!==p||owner.identity!==id))throw Error('Actual current native actor owner required');call={p,id};try{return fn();}finally{call=null;}};
  const rpc={request(operation,data){if(!call)throw Error('Own native request escaped its owner');if(operation==='prepareOwnBody'){const key=registry.check(call.p.sourceAvatar,call.p.profession).key,ready=cache.get(key);if(data.species!==key||!preparedWorldContract(contracts[key],ready))throw Error('Actual passive prepared receipt required');return ready;}return request(operation,data);}};
  const bridge=createInputBridge({rpc,info:port.info,registry,descriptors,sourceTimeval:pending.sourceTimeval,eventOwner:pending.eventOwner});
  return{reset:(p,id,pos)=>run(p,id,()=>bridge.reset(p,id,pos)),press:(p,id,v)=>run(p,id,()=>bridge.press(p,id,v)),tick:(p,id,value)=>run(p,id,()=>bridge.tick(p,id,value)),forget:(p,id)=>run(p,id,()=>bridge.forget(p,id),true),inspect:(p,id)=>bridge.inspect(p,id)};
 }
 return Object.freeze({prepare,readPreparedBody:key=>cache.get(key)??null,inputFactory,getMotion:()=>{if(!motion)throw Error('Actual selected own domain was not prepared');return motion;},
  inspect:()=>({keys,loaded:!!native,preparedKeys:[...cache.keys()],coldInitialized:!!cold,ownGlobalCarrier:true,HumanFIncluded:false}),
  close(){if(closed)return;closed=true;cache.clear();return native?.rpc.close();}});
}
