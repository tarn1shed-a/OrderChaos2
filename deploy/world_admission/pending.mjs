import{selectWorldContract,preparedWorldContract,readyWorldContract,LEGACY_WORLD_CONTRACT_SET,assertTrustedWorldContractSet,bindWorldContractSetReceipt}from'./contracts.mjs';
// Source-only web join transaction on the existing server tick. No new timer,
// native frame, clock, original game rule, pose or client approval is produced.
export function createSourceWorldPendingJoins({registry,contractSet=LEGACY_WORLD_CONTRACT_SET,readPreparedBody,readNativeReady,resolveContract=null,prepareJoin=null,clock=Date.now,onFault=()=>{}}){
 if(registry?.count!==45||typeof registry.check!=='function'||typeof readPreparedBody!=='function'||typeof readNativeReady!=='function'||typeof clock!=='function'||resolveContract!==null&&typeof resolveContract!=='function'||prepareJoin!==null&&typeof prepareJoin!=='function')throw Error('Explicit same-body native ports required');
 assertTrustedWorldContractSet(contractSet);
 const pending=new Map(),byCharacter=new Map(),byPlayer=new WeakMap();let runtime=null,generation=0,context=null,disposed=false;
 function staticBody(record){
  const c=selectWorldContract(registry,record,resolveContract,contractSet);
  return !!c&&preparedWorldContract(c,readPreparedBody(c.bodyKey,c.mode,record))&&
   record.sourceInventoryPolicy==='empty-compatible-container-v1'&&record.hotbar===null&&record.inventory&&Object.keys(record.inventory).length===0&&record.equipment&&Object.values(record.equipment).every(v=>v===null);
 }
 function current(r){return!disposed&&r.ws.readyState===1&&r.ws.character===r.record&&r.ws.player===r.player&&runtime.store.records.get(r.record.id)===r.record&&byCharacter.get(r.record.id)===r&&
  (r.phase==='pending'||runtime.active.get(r.record.id)===r.ws);}
 function remove(r){pending.delete(r.ws);if(byCharacter.get(r.record.id)===r)byCharacter.delete(r.record.id);byPlayer.delete(r.player);}
 function forget(r){let error;try{r.ws.motion?.forget?.(r.player);}catch(e){error=e;}remove(r);
  if(runtime.active.get(r.record.id)===r.ws)runtime.active.delete(r.record.id);
  if(r.room.get(r.record.id)===r.ws)r.room.delete(r.record.id);
  if(!r.room.size&&!api.room(r.roomKey)){if(runtime.rooms.get(r.roomKey)===r.room)runtime.rooms.delete(r.roomKey);runtime.combatRooms.delete(r.roomKey);}
  if(error)throw error;
 }
 function transportFault(e){if(runtime.isPhysicsTransportFailure?.(e))return e;for(const sub of e?.errors||[]){const found=transportFault(sub);if(found)return found;}return null;}
 const api=Object.freeze({
  attach(value){if(runtime||!value?.store||!value.active||typeof value.clock!=='function'||typeof value.reject!=='function')throw Error('Attach the one reviewed server once');runtime=value;},
  preflight(ws,record,msg){try{return!!runtime&&!disposed&&runtime.store.records.get(record.id)===record&&!byCharacter.has(record.id)&&staticBody(record)&&msg.scene==='resources'&&msg.mapWindow==='heaven-landing'&&!Object.hasOwn(msg,'lab')&&!Object.hasOwn(msg,'sourceAvatar')&&msg.profession===record.profession;}catch{return false;}},
  canCreate(){return false;},
  count(roomKey){return[...pending.values()].filter(r=>r.roomKey===roomKey).length;},
  entryActiveView(active){return Object.freeze({has:id=>active.has(id)||byCharacter.has(id),get:id=>active.get(id)||byCharacter.get(id)?.ws});},
  totalNewRooms(){return new Set([...pending.values()].filter(r=>!runtime.rooms.has(r.roomKey)).map(r=>r.roomKey)).size;},
  room(roomKey){return[...pending.values()].find(r=>r.roomKey===roomKey)?.room;},
  slots(roomKey){return[...pending.values()].filter(r=>r.roomKey===roomKey).map(r=>r.ws.spawnSlot);},
  stage(ws,{room,roomKey,message,commit}){
   if(!api.preflight(ws,ws.character,message)||typeof commit!=='function')throw Error('Source join preparation is unavailable');
   const contract=selectWorldContract(registry,ws.character,resolveContract,contractSet);if(!contract)throw Error('Pinned own body contract required');
   const r={ws,player:ws.player,record:ws.character,contract,room,roomKey,message:structuredClone(message),commit,phase:'pending',generation:++generation,identity:null,capability:null,preparation:null};
   pending.set(ws,r);byCharacter.set(r.record.id,r);byPlayer.set(r.player,r);
   if(prepareJoin){
    // Keep the existing slot/character reservation while actual resources load.
    // Resource readiness alone never creates a native pose or join capability.
    const preparation={state:'loading',error:null};r.preparation=preparation;
    Promise.resolve().then(()=>{
     if(!current(r)||r.phase!=='pending')return;
     return prepareJoin({record:r.record,contract:r.contract});
    }).then(value=>{
     if(!current(r)||r.phase!=='pending')return;
     if(value!==true)throw Error('Actual source admission resources were not prepared');
     preparation.state='ready';
    }).catch(error=>{
     if(!current(r)||r.phase!=='pending')return;
     preparation.error=error instanceof Error?error:new Error('Source admission resource preparation failed',{cause:error});preparation.state='failed';
    });
   }
  },
  readOwner(player,id){const r=byPlayer.get(player);if(!r||!current(r))return null;if(r.identity===null)r.identity=id;else if(r.identity!==id)throw Error('Same player cannot change native fork');
   return{player,characterId:r.record.id,socket:r.ws,generation:r.generation,identity:id,connected:true,mapId:r.contract.policy.mapId,roomKey:r.roomKey,phase:r.phase};},
  withMotion(ws,tick,run){
   if(!ws.player?.sourceAvatar)return run();const r=byPlayer.get(ws.player);
   // ws enters CLOSING before its close listener removes the room member.
   // That final room tick has no live input owner and must not advance native
   // motion or turn an ordinary disconnect into a server storage failure.
   if(r?.ws===ws&&(ws.readyState===2||ws.readyState===3))return;
   if(!r||!current(r)||context)throw Error('Actual current source motion owner required');
   const epoch=runtime.clock();if(!Number.isSafeInteger(tick)||tick<0||!Number.isSafeInteger(epoch)||epoch<0||epoch>2147483647999)throw Error('Actual authoritative tick/epoch required');
   context={r,tick,timeval:[Math.floor(epoch/1000),epoch%1000*1000]};
   try{return run();}catch(error){if(r.phase!=='active')throw error;try{forget(r);}catch(cleanup){onFault(cleanup);}runtime.gate?.forget(ws);runtime.reject(ws,'角色动作暂时不可用，请重新进入');const fault=transportFault(error);if(fault)runtime.storageFailure(fault);else onFault(error);}
   finally{context=null;}
  },
  sourceTimeval(player,id){if(!context||context.r.player!==player||context.r.identity!==id)throw Error('Source clock requested outside this actual motion tick');return[...context.timeval];},
  readNativeTimeval(operation,data={}){
   // Reset/press belong to the same authoritative frame already captured by
   // withMotion. Startup/preparation and release after disconnect use the
   // same server clock, without advancing a native frame or accepting a TV
   // from a browser command.
   if(context&&context.r.identity===data.identity)return[...context.timeval];
   if(['reset','press','release','tick'].includes(operation))throw Error('Native motion clock requested outside its current frame');
   if(!['cold-rng','cold-origin','prepareOwnBody','forget','input-state','water'].includes(operation))throw Error('Unknown native clock operation');
   const epoch=(runtime?.clock||clock)();
   if(!Number.isSafeInteger(epoch)||epoch<0||epoch>2147483647999)throw Error('Actual authoritative epoch required');
   return[Math.floor(epoch/1000),epoch%1000*1000];
  },
  eventOwner(player,id){if(!context||context.r.player!==player||context.r.identity!==id||!current(context.r))throw Error('Source event requested outside current authenticated motion');return'world';},
  capability(record){
   const r=byCharacter.get(record.id);if(!r||r.record!==record||!current(r)||!r.capability)return null;
   const ready=readNativeReady(r.player);return readyWorldContract(r.contract,r,ready,contractSet)?r.capability:null;
  },
  step(tick){
   for(const r of [...pending.values()]){
    try{
     if(!current(r))throw Error('角色连接已变更，请重新进入');
     if(r.preparation?.state==='loading')continue;
     if(r.preparation?.state==='failed')throw r.preparation.error;
     api.withMotion(r.ws,tick,()=>r.ws.motion.move(r.player,r.ws.input,.05,r.ws.world));
     const ready=readNativeReady(r.player);if(!readyWorldContract(r.contract,r,ready,contractSet))throw Error('原角色首姿势尚未就绪');
     r.capability=bindWorldContractSetReceipt(Object.freeze({...r.contract.policy,actorKey:r.record.id,identity:r.identity,generation:r.generation}),contractSet);
     if(!runtime.gate.join(r.ws,r.record,r.message))throw Error('此角色的当前地图接线尚未就绪');
     // Existing active rooms already ticked. Newly committed source players
     // join their normal room movement only on the NEXT existing server tick.
     r.commit();r.phase='active';pending.delete(r.ws);
    }catch(error){
     const commitFailure=runtime.active.get(r.record.id)===r.ws;
     try{forget(r);}catch(cleanup){onFault(cleanup);}
     runtime.gate?.forget(r.ws);runtime.reject(r.ws,'角色暂时无法进入地图，请重新进入');
     const fault=transportFault(error);if(commitFailure||fault)runtime.storageFailure(fault||error);else onFault(error);
    }
   }
  },
  close(ws){
   const r=byPlayer.get(ws.player);if(!r)return;
   if(r.phase==='pending')forget(r);
   // Active room membership must remain visible to the server's original
   // close handler so it can save the final position before removing it.
   else try{r.ws.motion?.forget?.(r.player);}catch(error){onFault(error);}finally{remove(r);}
  },
  failUncommitted(ws,error){
   if(!ws.character?.sourceAvatar||runtime.active.get(ws.character.id)===ws)return false;
   const r=byPlayer.get(ws.player);if(r)try{forget(r);}catch(cleanup){onFault(cleanup);}
   else {const key=ws.roomId||ws.sourcePendingRoomKey;if(key&&!runtime.rooms.has(key)&&!api.room(key))runtime.combatRooms.delete(key);}
   runtime.gate?.forget(ws);runtime.reject(ws,'角色暂时无法进入地图，请重新进入');const fault=transportFault(error);if(fault)runtime.storageFailure(fault);else onFault(error);return true;
  },
  dispose(){if(disposed)return;for(const r of [...byCharacter.values()]){try{forget(r);}catch(e){onFault(e);}}disposed=true;},
  inspect:()=>({pending:pending.size,trackedCharacters:byCharacter.size,newTickCreated:false,newClockCreated:false,disposed}),
 });return api;
}
