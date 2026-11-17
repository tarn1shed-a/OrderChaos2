// One existing world and authenticated native snapshots. This adapter owns no
// action clock, game rules, fallback body, camera or renderer.
import {loadWorldCharacterInputs} from '/world-character-common-v1/inputs.mjs';
import {loadWorldOwnAirInputs} from '/world-own-air-actors-v3/inputs.mjs';
import {createWorldCharacterMaterialHost} from '/world-character-peer-v1/material_host.mjs';
import {createWorldNormalActorFactory} from '/world-own-air-actors-v3/entry.mjs';
import {createPlayerChoiceScene} from '/__delivery/player_choice_scene.mjs';
import {SOURCE_WORLD_BODY_KEYS as bodyKeys} from '/__delivery/source_world_bodies.mjs';

export async function createQuestSourcePlayers({THREE,renderer,scene,camera,sourceMap,origin,registry,
  readScope,loadBytes,decodeTexture,createCharacterFactory,characterAnimationState,disposeCharacterAnimation,
  install,update,remove,onError,enabledBodyKeys=['human-female'],crypto=globalThis.crypto}){
  if(typeof readScope!=='function'||registry?.count!==45||typeof registry.check!=='function')throw Error('Current world and trusted choices required');
  for(const fn of [install,update,remove,onError])if(typeof fn!=='function')throw Error('Explicit existing world ports required');
  if(!Array.isArray(enabledBodyKeys)||!enabledBodyKeys.length||new Set(enabledBodyKeys).size!==enabledBodyKeys.length||enabledBodyKeys.some(k=>!bodyKeys.includes(k)))throw Error('Explicit reviewed source bodies required');
  const enabled=new Set(enabledBodyKeys),ownAirBodyKeys=enabledBodyKeys.filter(k=>k!=='human-female');
  const initial=readScope(),owner=initial?.owner,mapGeneration=initial?.mapGeneration,contextGeneration=initial?.contextGeneration;
  let disposed=false,failed=false,host=null,actors=null,factory=null,actorEpoch=0,released=false;
  const baseLoads=new Map(),airLoads=new Map(),baseInputs=new Map(),airInputs=new Map();
  const current=()=>{const s=readScope();return !disposed&&!failed&&s?.active===true&&s.owner===owner&&s.mapGeneration===mapGeneration&&s.contextGeneration===contextGeneration&&s.scene===scene&&s.renderer===renderer&&s.sourceMap===sourceMap;};
  function accepts(record){try{return enabled.has(registry.check(record.sourceAvatar,record.profession).key);}catch{return false;}}
  function loadBase({bodyKey,mode}){
    const key=bodyKey+':'+mode;
    if(!baseLoads.has(key))baseLoads.set(key,(async()=>{
      const input=await loadWorldCharacterInputs({THREE,bodyKey,mode,loadBytes,decodeTexture,crypto,current});
      if(!current()){input.dispose();throw Error('World owner expired during source loading');}
      baseInputs.set(key,input);return input;
    })());return baseLoads.get(key);
  }
  function loadInputs(options){
    if(!enabled.has(options.bodyKey))throw Error('Unadmitted source input body');
    if(options.mode!=='own-air')return loadBase(options);
    if(!airLoads.has(options.bodyKey))airLoads.set(options.bodyKey,(async()=>{
      const input=await loadWorldOwnAirInputs({...options,loadGroundInputs:loadBase,loadBytes,crypto,current});
      if(!current()){input.dispose();throw Error('World owner expired during own source loading');}
      airInputs.set(options.bodyKey,input);return input;
    })());return airLoads.get(options.bodyKey);
  }
  function release(){if(released)return;released=true;const errors=[];for(const run of [()=>actors?.clear(),()=>factory?.dispose(),()=>host?.dispose(),...Array.from(airInputs.values(),i=>()=>i.dispose()),...Array.from(baseInputs.values(),i=>()=>i.dispose())])try{run();}catch(error){errors.push(error);}if(errors.length)throw new AggregateError(errors,'Source world cleanup failed');}
  function fault(error){if(disposed||failed)return;failed=true;try{release();}catch(cleanup){error=new AggregateError([error,cleanup],'Source world failed');}onError(error);}
  function dispose(){if(disposed)return;disposed=true;release();}
  try{
    if(!current())throw Error('World owner expired before source loading');
    const first=enabled.has('human-female')?'human-female':enabledBodyKeys[0];
    const inputs=await loadInputs({bodyKey:first,mode:first==='human-female'?'normal15':'own-air'});
    if(!current())throw Error('World owner expired during source loading');
    host=await createWorldCharacterMaterialHost({THREE,renderer,scene,camera,sourceMap,origin,inputs:[inputs.materialInputs??inputs],readScope,crypto});
    if(!current())throw Error('World owner expired during source host loading');
    factory=createWorldNormalActorFactory({THREE,registry,loadInputs,ownAirBodyKeys,materialHost:host,createCharacterFactory,characterAnimationState,disposeCharacterAnimation,currentWorld:current,crypto});
    actors=createPlayerChoiceScene({actors:{create(record,{current:actorCurrent}){
      if(!accepts(record))throw Error('Unadmitted source body');
      return factory(record,{current:()=>current()&&actorCurrent(),actorEpoch:++actorEpoch});
    }},install,update,remove,onError:fault});
    return Object.freeze({
      accepts,
      readNormalPoseContract(record){
        if(!current()||!accepts(record))return null;
        const input=airInputs.get(record.sourceAvatar.key),row=input?.sourcePoseContract;
        if(!row||input.inspect().disposed)return null;
        // These names come from the byte-checked own animation bank. This is
        // client input ordering only; native collection admission stays server-side.
        const idleClips=Object.keys(input.sourceMotionProfile.ranges).filter(name=>/^idle(?:_\d+)?$/.test(name));
        return Object.freeze({...row,idleClips:Object.freeze(idleClips)});
      },
      async sync(records,at,{current:connectionCurrent}={}){
        if(!current())return;
        if(typeof connectionCurrent!=='function')throw Error('Current authenticated connection required');
        try{await actors.sync(records,at,{current:()=>current()&&connectionCurrent()});}
        catch(error){fault(error);}
      },
      clear(){actors.clear();},
      beforeRender(token){if(!current())return false;try{host.prepareBeforeWorldRender(token);return true;}catch(error){fault(error);return false;}},
      afterRender(token){if(!current())return;try{host.afterWorldRender(token);}catch(error){fault(error);}},
      dispose,
      inspect:()=>({disposed,failed,current:current(),actors:actors.inspect(),inputs:[...baseInputs.values(),...airInputs.values()].map(i=>i.inspect()),serverAdmission:false}),
    });
  }catch(error){dispose();throw error;}
}
