// One world lease and authenticated snapshots. Frozen adapters retain the
// original formats, numerical samplers and material/geometry pools.
import {loadWorldCharacterInputs} from '/world-character-common-v1/inputs.mjs';
import {loadWorldOwnAirInputs} from '/world-own-air-actors-v3/inputs.mjs';
import {createWorldCharacterMaterialHost} from '/world-character-peer-v1/material_host.mjs';
import {createWorldNormalActorFactory} from '/world-own-air-actors-v3/entry.mjs';
import {createPlayerChoiceScene} from '/__delivery/player_choice_scene.mjs';
import {createSourceResourceScope} from '/__delivery/source_actor_lifecycle.mjs';

export async function createQuestSourcePlayers({THREE,renderer,scene,camera,sourceMap,origin,registry,catalog,
  readScope,loadBytes,decodeTexture,createCharacterFactory,characterAnimationState,disposeCharacterAnimation,
  install,update,remove,onError,enabledBodyKeys=Object.keys(catalog?.definitions??{}),crypto=globalThis.crypto}){
  if(typeof readScope!=='function'||registry?.count!==45||typeof registry.check!=='function'||!catalog?.definitions)throw Error('Current world and trusted content directory required');
  for(const fn of [install,update,remove,onError])if(typeof fn!=='function')throw Error('Explicit existing world ports required');
  if(!Array.isArray(enabledBodyKeys)||!enabledBodyKeys.length||new Set(enabledBodyKeys).size!==enabledBodyKeys.length||enabledBodyKeys.some(k=>!catalog.definitions[k]))throw Error('Explicit reviewed source bodies required');
  const enabled=new Set(enabledBodyKeys),ownAirBodyKeys=enabledBodyKeys.filter(k=>catalog.definitions[k].normal.mode==='own-air');
  const initial=readScope(),owner=initial?.owner,mapGeneration=initial?.mapGeneration,contextGeneration=initial?.contextGeneration;
  let disposed=false,failed=false,host=null,actors=null,factory=null,hostPromise=null,actorEpoch=0,released=false;
  const baseInputs=new Map(),airInputs=new Map(),reported=new WeakSet(),resourceRetries=new Map();
  const current=()=>{const s=readScope();return !disposed&&!failed&&s?.active===true&&s.owner===owner&&s.mapGeneration===mapGeneration&&s.contextGeneration===contextGeneration&&s.scene===scene&&s.renderer===renderer&&s.sourceMap===sourceMap;};
  const resources=createSourceResourceScope({current});
  const retryable=error=>error?.retryable===true||(error instanceof AggregateError&&error.errors.length>0&&error.errors.every(retryable));
  function loadResource(key,prepare,options){
    const previous=resourceRetries.get(key);
    if(previous&&Date.now()<previous.until)return Promise.reject(previous.error);
    return resources.load(key,prepare,options).then(value=>{resourceRetries.delete(key);return value;},error=>{
      if(retryable(error))resourceRetries.set(key,{error,until:Date.now()+1000});throw error;
    });
  }
  function definition(record){const body=registry.check(record.sourceAvatar,record.profession),row=catalog.definitions[body.key];if(!enabled.has(body.key)||!row||row.sourceModelId!==body.sourceModelId)throw Error('Unadmitted source body');return row;}
  function accepts(record){try{definition(record);return true;}catch{return false;}}
  function loadBase({bodyKey,mode}){
    return loadResource('base:'+bodyKey+':'+mode,async({current,signal})=>{
      const input=await loadWorldCharacterInputs({THREE,bodyKey,mode,loadBytes:url=>loadBytes(url,{signal}),decodeTexture,crypto,current});
      baseInputs.set(bodyKey+':'+mode,input);return input;
    },{dispose:input=>input.dispose(),priority:0});
  }
  function loadInputs(options){
    if(!enabled.has(options.bodyKey))throw Error('Unadmitted source input body');
    if(options.mode!=='own-air')return loadBase(options);
    return loadResource('own-air:'+options.bodyKey,async({current,signal})=>{
      const input=await loadWorldOwnAirInputs({...options,loadGroundInputs:loadBase,loadBytes:url=>loadBytes(url,{signal}),crypto,current});
      airInputs.set(options.bodyKey,input);return input;
    },{dispose:input=>input.dispose(),priority:1});
  }
  function prepareFactory(input){
    if(!hostPromise){
      hostPromise=(async()=>{
        const made=await createWorldCharacterMaterialHost({THREE,renderer,scene,camera,sourceMap,origin,inputs:[input.materialInputs??input],readScope,crypto});
        if(!current()){made.dispose();throw Error('World owner expired during source host loading');}
        host=made;
        factory=createWorldNormalActorFactory({THREE,registry,loadInputs,ownAirBodyKeys,bodyKeys:enabledBodyKeys,materialHost:host,createCharacterFactory,characterAnimationState,disposeCharacterAnimation,currentWorld:current,crypto});
        return factory;
      })().catch(error=>{try{host?.dispose();}finally{host=null;factory=null;hostPromise=null;}throw error;});
    }
    return hostPromise;
  }
  function release(){
    if(released)return;released=true;const errors=[];
    for(const run of [()=>actors?.dispose(),()=>factory?.dispose(),()=>host?.dispose(),()=>resources.dispose()])try{run();}catch(error){errors.push(error);}
    if(errors.length)throw new AggregateError(errors,'Source world cleanup failed');
  }
  function fault(error){
    if(disposed||failed||reported.has(error))return;reported.add(error);
    if(retryable(error)){onError(error,{retryable:true});return;}
    failed=true;try{release();}catch(cleanup){error=new AggregateError([error,cleanup],'Source world failed');}onError(error,{retryable:false});
  }
  function dispose(){if(disposed)return;disposed=true;release();}
  if(!current())throw Error('World owner expired before source loading');
  actors=createPlayerChoiceScene({actors:{async create(record,{current:actorCurrent,definition:row}){
    const input=await loadInputs({bodyKey:row.bodyKey,mode:row.normal.mode});
    if(!current()||!actorCurrent())return null;
    const create=await prepareFactory(input);
    if(!current()||!actorCurrent())return null;
    return create(record,{current:()=>current()&&actorCurrent(),actorEpoch:++actorEpoch});
  }},resolve:definition,install,update,remove,readReady:a=>a.view.inspect().clientReady===true,onError:fault});
  return Object.freeze({
    accepts,
    readNormalPoseContract(record){
      if(!current()||!accepts(record))return null;
      const input=airInputs.get(record.sourceAvatar.key),row=input?.sourcePoseContract;
      if(!row||input.inspect().disposed)return null;
      const idleClips=Object.keys(input.sourceMotionProfile.ranges).filter(name=>/^idle(?:_\d+)?$/.test(name));
      return Object.freeze({...row,idleClips:Object.freeze(idleClips)});
    },
    async sync(records,at,{current:connectionCurrent,connection}={}){
      if(!current())return;
      if(typeof connectionCurrent!=='function')throw Error('Current authenticated connection required');
      try{await actors.sync(records,at,{current:()=>current()&&connectionCurrent(),connection});}catch(error){fault(error);}
    },
    clear(){actors.clear();},
    isPlayable:actors.isPlayable,
    beforeRender(token){if(!current()||!host)return false;try{host.prepareBeforeWorldRender(token);return true;}catch(error){fault(error);return false;}},
    afterRender(token){if(!current()||!host)return;try{host.afterWorldRender(token);actors.refreshReadiness();}catch(error){fault(error);}},
    dispose,
    async drain(){await actors.drain();await resources.drain();await hostPromise?.catch(()=>{});},
    inspect:()=>({disposed,failed,current:current(),actors:actors.inspect(),lifecycle:actors.inspectLifecycle(),resources:resources.inspect(),
      factory:factory?.inspect()??null,inputs:[...baseInputs.values(),...airInputs.values()].map(i=>i.inspect()),serverAdmission:false}),
  });
}
