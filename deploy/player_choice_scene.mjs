// Compatibility entry for the shared browser lifecycle. Original adapters still
// own poses/validation. An old caller must clear between connection generations.
import {createSourceActorLifecycle} from './source_actor_lifecycle.mjs';
class ClearSeparatedSceneScope {}
const legacyDefinition=record=>({definitionKey:JSON.stringify([record.id,record.profession,record.sourceAvatar??null])});

export function createPlayerChoiceScene({actors,install,update,remove,onError=()=>{},resolve=legacyDefinition,readReady=()=>false}={}){
  const core=createSourceActorLifecycle({actors,resolve,install,update,remove,onError,readReady});
  let legacyScope=new ClearSeparatedSceneScope(),explicit=false;
  return Object.freeze({
    sync(records,at,options={}){
      explicit=Object.hasOwn(options,'connection');
      return core.sync(records,at,{current:options.current===undefined?()=>true:options.current,connection:explicit?options.connection:legacyScope});
    },
    clear(){legacyScope=new ClearSeparatedSceneScope();explicit=false;return core.clear();},
    inspect:core.inspect,
    inspectLifecycle:()=>({...core.inspectLifecycle(),connectionBound:explicit}),
    isPlayable:core.isPlayable,refreshReadiness:core.refreshReadiness,
    dispose:core.dispose,drain:core.drain,
  });
}
