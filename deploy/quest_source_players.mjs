// One existing world and authenticated native snapshots. This adapter owns no
// action clock, game rules, fallback body, camera or renderer.
import {loadHumanFemaleWorldInputs} from '/human-female-world-common-v1/inputs.mjs';
import {createHumanFemaleWorldMaterialHost} from '/world-character-peer-v1/human_female_material_host.mjs';
import {createHumanFemaleWorldActorFactory} from '/human-female-world-v1/actor_factory.mjs';
import {createPlayerChoiceScene} from '/__delivery/player_choice_scene.mjs';

export async function createQuestSourcePlayers({THREE,renderer,scene,camera,sourceMap,origin,registry,
  readScope,loadBytes,decodeTexture,createCharacterFactory,characterAnimationState,disposeCharacterAnimation,
  install,update,remove,onError,crypto=globalThis.crypto}){
  if(typeof readScope!=='function'||registry?.count!==45||typeof registry.check!=='function')throw Error('Current world and trusted choices required');
  for(const fn of [install,update,remove,onError])if(typeof fn!=='function')throw Error('Explicit existing world ports required');
  const initial=readScope(),owner=initial?.owner,mapGeneration=initial?.mapGeneration,contextGeneration=initial?.contextGeneration;
  let disposed=false,failed=false,inputs=null,host=null,actors=null,actorEpoch=0;
  const current=()=>{const s=readScope();return !disposed&&!failed&&s?.active===true&&s.owner===owner&&s.mapGeneration===mapGeneration&&s.contextGeneration===contextGeneration&&s.scene===scene&&s.renderer===renderer&&s.sourceMap===sourceMap;};
  function accepts(record){try{return registry.check(record.sourceAvatar,record.profession).key==='human-female';}catch{return false;}}
  function fault(error){if(disposed||failed)return;failed=true;actors?.clear();host?.dispose();inputs?.dispose();onError(error);}
  function dispose(){if(disposed)return;disposed=true;actors?.clear();host?.dispose();inputs?.dispose();}
  try{
    if(!current())throw Error('World owner expired before source loading');
    inputs=await loadHumanFemaleWorldInputs({THREE,loadBytes,decodeTexture,crypto,current});
    if(!current())throw Error('World owner expired during source loading');
    host=await createHumanFemaleWorldMaterialHost({THREE,renderer,scene,camera,sourceMap,origin,inputs,readScope,crypto});
    if(!current())throw Error('World owner expired during source host loading');
    const create=createHumanFemaleWorldActorFactory({THREE,registry,inputs,materialHost:host,createCharacterFactory,characterAnimationState,disposeCharacterAnimation,crypto});
    actors=createPlayerChoiceScene({actors:{create(record,{current:actorCurrent}){
      if(!accepts(record))throw Error('Unadmitted source body');
      return create(record,{current:()=>current()&&actorCurrent(),actorEpoch:++actorEpoch});
    }},install,update,remove,onError:fault});
    return Object.freeze({
      accepts,
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
      inspect:()=>({disposed,failed,current:current(),actors:actors.inspect(),inputs:inputs.inspect(),serverAdmission:false}),
    });
  }catch(error){dispose();throw error;}
}
