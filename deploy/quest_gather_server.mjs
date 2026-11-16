// Current compatible461 presentation only. These explicitly supplied ABI/RNG
// inputs are a web presentation context, not recovered original actor state.
import {readFile} from 'node:fs/promises';
import {randomBytes,randomUUID,webcrypto} from 'node:crypto';
import {resolve} from 'node:path';
import {createGatherBrowserLibrary} from '../tools/preview/ordinary-quest461-gather-browser.mjs';
import {createCompatible461GatherEvents} from '../tools/preview/ordinary-quest461-gather-events.mjs';
export const GATHER_BINDING='c03c5f0cd41117b7f88b32f41d6a9a299f5bf0e802a6ea307de22e92ad37a473';
const context={movementState:5,postureState:8,actionState:0x800,actorFlag4c:0,actorPointer638:null,
 kindAttribute0:0x120a,rawActorByte114:1,cachedWeaponEvent:0,sourceClassWeaponRow:null,
 explicitNoWeaponRecord:true,loadedEngineFlags:3,sourceFilterByte:0};
export async function createQuestGatherServer({runtime,collection,readGame,onFault=console.error}){
 const base=resolve(runtime,'game-data/converted/source-quest461-gather-v1');
 const[sourceBytes,bindingBytes]=await Promise.all(['source.json','binding.json'].map(async n=>new Uint8Array(await readFile(resolve(base,n)))));
 const library=await createGatherBrowserLibrary({sourceBytes,bindingBytes,crypto:webcrypto});
 const covered=ws=>{
  const role=ws?.character,p=ws?.player,a=role?.appearance;
  return !!role&&!!p&&!role.sourceAvatar&&!p.sourceAvatar&&(!a||a.race===2&&a.gender===1)&&
   !role.equipment?.mainHand&&p.hp>0&&p.grounded===true&&!p.jump&&!p.cast&&Math.hypot(ws.input?.x||0,ws.input?.y||0)===0;
 };
 const owned=ws=>{
  const game=readGame(),role=ws?.character,p=ws?.player;
  if(!role||!p||game?.entryActive?.get(role.id)!==ws||game.entryStore.records.get(role.id)!==role||
   ws.ordinaryQuestMap!==1||p.id!==role.id||!ws.roomId||![1,2,3,4,5].includes(role.profession)||!covered(ws))return null;
  return {characterId:role.id,actorKey:p.id,roomKey:ws.roomId,profession:role.profession,mapId:1};
 };
 const tape=createCompatible461GatherEvents({collection,historyLimit:8192,nextSessionKey:randomUUID,readOwner:owned,
  makeSourceSession(input){
   // The exact legacy body has a checked browser target. Equipped, airborne,
   // moving or unsupported source actors retain task execution without this
   // restricted presentation; they are not guessed into the covered context.
   if(!covered(input.owner))return null;
   const seed=randomBytes(32),inputs={randomWords:[0,8,16,24].map(at=>seed.readBigUInt64LE(at).toString()),
    initialIdleVariant:0,sourceContext:structuredClone(context)};
   return {session:library.createSession({...input,...inputs}),inputs,bindingId:GATHER_BINDING};
  },onFault});
 return Object.freeze({collection:tape,tape,dispose(){tape.dispose();library.dispose();}});
}
