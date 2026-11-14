// A generated server copy adds only chosen-draft persistence and snapshot DTOs.
// The SHA-checked private server/store source files are not rewritten.
import {createHash} from 'node:crypto';
export function stageSourceAvatarServer(source){
  const replace=(from,to)=>{if(source.split(from).length!==2)throw Error('Source avatar server anchor differs');source=source.replace(from,to);};
  const state=new URL('./source_avatar_state.mjs',import.meta.url).href;
  replace("import { CharacterStore, characterView } from './game/character-store.mjs';",
    `import { CharacterStore as ReviewedStore, characterView as reviewedCharacterView } from './game/character-store.mjs';\nimport {createSourceAvatarStore,sourceCharacterView,sourceAvatar} from ${JSON.stringify(state)};\nconst CharacterStore=createSourceAvatarStore(ReviewedStore),characterView=record=>sourceCharacterView(record,reviewedCharacterView);`);
  const joined='        if (ws.character.hp <= 0) ws.character.hp = ws.character.maxHp;\n        syncPlayerStats(ws);';
  replace(joined,joined+"\n        if(Object.hasOwn(ws.character,'sourceAvatar'))ws.player.sourceAvatar=sourceAvatar(ws.character.sourceAvatar);");
  return source;
}

export function stageSourceSpeciesCollision(source){
  if(createHash('sha256').update(source).digest('hex')!=='63ef96740c801b6c4e5887bbdff585c31404582c07a59e523fd8769721bbfb1e')throw Error('Reviewed collision adapter identity differs');
  const before="rpc.request('reset',{identity:identity(entity),position:[p.x,entity.worldY,p.z]});";
  if(source.split(before).length!==2)throw Error('Source model reset anchor differs');
  const after="if(entity.sourceAvatar&&!info.sourceSpeciesKeys?.includes(sourceAvatar(entity.sourceAvatar).key))throw Error('Original model queue is unavailable');"+
    "rpc.request('reset',{identity:identity(entity),position:[p.x,entity.worldY,p.z],...(entity.sourceAvatar?{species:sourceAvatar(entity.sourceAvatar).key}:{})});";
  return `import {sourceAvatar} from ${JSON.stringify(new URL('./source_avatar_state.mjs',import.meta.url).href)};\n`+source.replace(before,after);
}
