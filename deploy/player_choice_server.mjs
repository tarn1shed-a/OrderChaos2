// Web account/storage adapter for original UI choices; not game admission.
import {entryNameError} from './entry_name.mjs';
import {trialRoleManager} from './entry_manage.mjs';
import {createHash} from 'node:crypto';

export function createPlayerChoiceManager(store,active,registry,{admit,...options}={}){
 if(store?.sourceAvatarPersistence!==true||registry?.count!==45||typeof admit!=='function')throw Error('Explicit runtime capability admission required');
 const original=trialRoleManager(store,active,options);
 return {...original,create(data){
  const selected={race:data.race,gender:data.gender,profession:data.profession},avatar=registry.draft(selected);
  if(admit(selected,avatar)!==true)throw Error('该角色的实际地图资源尚未全部接入，未创建角色');
  const error=entryNameError(data.name);if(error)throw Error(error);
  const entries=[...store.records],dirty=store.dirty,savedAt=store.savedAt;
  try{
   const identity=store.resolveCharacter(data.name,undefined,undefined,data.profession,avatar),record=identity.record;
   return {character:{id:record.id,name:record.name,level:record.level,profession:record.profession,sourceAvatar:registry.check(record.sourceAvatar,record.profession)},resumeToken:identity.resumeToken};
  }catch(error){store.records.clear();for(const[k,v]of entries)store.records.set(k,v);store.dirty=dirty;store.savedAt=savedAt;throw error;}
 }};
}

export function stagePlayerChoiceServer(source,registryModuleURL){
 if(typeof registryModuleURL!=='string'||!registryModuleURL.startsWith('file:'))throw Error('Trusted local registry module required');
 const replace=(a,b)=>{if(source.split(a).length!==2)throw Error('Reviewed player-choice server anchor differs');source=source.replace(a,b);};
 const api=new URL('./player_choice_registry.mjs',import.meta.url).href;
 replace("import { CharacterStore, characterView } from './game/character-store.mjs';",
  `import { CharacterStore as ReviewedStore, characterView as reviewedCharacterView } from './game/character-store.mjs';\nimport {registry as originalPlayerChoiceRegistry} from ${JSON.stringify(registryModuleURL)};\nimport {createPlayerChoiceStore,playerChoiceView} from ${JSON.stringify(api)};\nconst CharacterStore=createPlayerChoiceStore(ReviewedStore,originalPlayerChoiceRegistry),characterView=record=>playerChoiceView(record,reviewedCharacterView,originalPlayerChoiceRegistry);`);
 const joined='        if (ws.character.hp <= 0) ws.character.hp = ws.character.maxHp;\n        syncPlayerStats(ws);';
 replace(joined,joined+"\n        if(Object.hasOwn(ws.character,'sourceAvatar'))ws.player.sourceAvatar=originalPlayerChoiceRegistry.check(ws.character.sourceAvatar,ws.character.profession);");
 return source;
}

export function stagePlayerChoiceRead(source,registryModuleURL){
 if(typeof registryModuleURL!=='string'||!registryModuleURL.startsWith('file:'))throw Error('Trusted local registry module required');
 const from="import {sourceAvatar} from './source_avatar_state.mjs';",check='sourceAvatar(c.sourceAvatar)';
 if(source.split(from).length!==2||source.split(check).length!==2)throw Error('Reviewed character-read anchors differ');
 return source.replace(from,`import {registry as originalPlayerChoiceRegistry} from ${JSON.stringify(registryModuleURL)};`)
  .replace(check,'originalPlayerChoiceRegistry.check(c.sourceAvatar,c.profession)');
}

export function stagePlayerChoiceStoreSource(source,registryModuleURL){
 if(typeof registryModuleURL!=='string'||!registryModuleURL.startsWith('file:'))throw Error('Trusted local registry module required');
 if(createHash('sha256').update(source).digest('hex')!=='49a9f84c2ec5d4a0708932d2e77cc1296077e3b988d5614ef7e840e95de16eba')throw Error('Reviewed source store identity differs');
 const replace=(a,b)=>{if(source.split(a).length!==2)throw Error('Reviewed empty-container store anchor differs');source=source.replace(a,b);};
 source=`import {registry as originalPlayerChoiceRegistry} from ${JSON.stringify(registryModuleURL)};\n`+source;
 const header='function validate(record, legacy = false, requireLook = true, requireHotbar = true, version=6) {';
 replace(header,header+"\n  const emptySource=record?.sourceInventoryPolicy==='empty-compatible-container-v1';\n  if(record?.sourceInventoryPolicy!==undefined&&!emptySource)throw Error('Unknown source inventory policy');");
 replace('!record.inventory || !integer(record.inventory.wolfPelt)',
  "!record.inventory || !(emptySource?Object.keys(record.inventory).length===0:integer(record.inventory.wolfPelt))");
 const old='  if (legacy) {\n';
 replace(old,`  if(emptySource){
    originalPlayerChoiceRegistry.check(record.sourceAvatar,record.profession);
    if(version!==6||Array.isArray(record.inventory)||!record.equipment||Array.isArray(record.equipment)||
      Object.keys(record.equipment).sort().join(',')!==Object.keys(EQUIPMENT_SLOTS).sort().join(',')||
      Object.values(record.equipment).some(v=>v!==null))throw Error('Invalid source empty inventory/equipment');
  }
`+old);
 replace('  } else {\n    if (!record.equipment','  } else if(!emptySource) {\n    if (!record.equipment');
 replace('export class CharacterStore {','export class CharacterStore {\n  get sourceChoiceEmptyInventory(){return true;}');
 return source;
}
