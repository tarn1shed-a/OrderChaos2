// Compatible461 execution -> ordered presentation events. This is a web host
// adapter, not original activity/approval/cancel rules. No HTTP/WS/save code.
const copy=x=>structuredClone(x),BINDING='c03c5f0cd41117b7f88b32f41d6a9a299f5bf0e802a6ea307de22e92ad37a473';
export function createCompatible461GatherEvents({collection,readOwner,makeSourceSession,nextSessionKey,historyLimit,onFault=()=>{}}={}){
 if(collection?.questId!==461||!['begin','finish','cancel'].every(k=>typeof collection[k]==='function')||![readOwner,makeSourceSession,nextSessionKey,onFault].every(f=>typeof f==='function')||!Number.isInteger(historyLimit)||historyLimit<8||historyLimit>8192)throw Error('Explicit compatible461 presentation host capabilities required');
 const owners=new WeakMap(),streams=new Set(),roomPending=new Map(),roomTicks=new Map(),keys=new Set();let closed=false;
 const fault=(where,error)=>{try{onFault({where,error:String(error?.message||error),presentationOnly:true});}catch{}};
 function identity(owner){const r=readOwner(owner);if(!r||r.mapId!==1||typeof r.characterId!=='string'||!r.characterId||typeof r.actorKey!=='string'||!r.actorKey||typeof r.roomKey!=='string'||!r.roomKey||![1,2,3,4,5].includes(r.profession))return null;return{characterId:r.characterId,actorKey:r.actorKey,roomKey:r.roomKey,profession:r.profession,mapId:1};}
 const matches=(a,b)=>!!a&&!!b&&['characterId','actorKey','roomKey','profession','mapId'].every(k=>a[k]===b[k]);
 function enqueueRoom(room,record){const q=roomPending.get(room)||[];q.push(copy(record));roomPending.set(room,q);}
 function retire(r,reason){if(!r||r.retired)return;r.retired=true;streams.delete(r);if(owners.get(r.owner)===r)owners.delete(r.owner);try{r.source.session.dispose();}catch(e){fault('source-dispose',e);}enqueueRoom(r.roomKey,{kind:'retire-session',sessionKey:r.sessionKey,actorKey:r.actorKey,reason,presentationOnly:true,originalInterruptOrTaskCancel:false});}
 function append(r,record){if(r.retired)return;r.history.push(copy(record));enqueueRoom(r.roomKey,record);if(r.history.length>historyLimit)retire(r,'presentation-history-limit');}
 function emit(r,operation,fields={}){const event={sessionKey:r.sessionKey,actorKey:r.actorKey,sequence:++r.sequence,operation,scope:r.scope,...fields};append(r,{kind:'event',event});}
 function sourceFor(owner,ctx){const current=identity(owner),old=owners.get(owner);if(!current||current.characterId!==ctx.characterId){if(old)retire(old,'connection-or-character-changed');return null;}if(old&&matches(old,current)&&!old.retired)return old;if(old)retire(old,'identity-changed');
  for(const other of[...streams])if(other.actorKey===current.actorKey&&other.roomKey===current.roomKey){if(matches(other,identity(other.owner)))throw Error('One active source owner per room actor required');retire(other,'connection-replaced');}
  const sessionKey=nextSessionKey();if(typeof sessionKey!=='string'||!sessionKey||sessionKey.length>160||keys.has(sessionKey))throw Error('Unique host presentation session key required');
  const source=makeSourceSession({...current,sessionKey,owner});if(source===null)return null;
  if(source?.then||source?.session?.sessionKey!==sessionKey||source.session.actorKey!==current.actorKey||source.session.profession!==current.profession||typeof source.session.makeProducer!=='function'||typeof source.session.dispose!=='function'||!source.inputs||source.bindingId!==BINDING){try{source?.session?.dispose?.();}catch{}throw Error('Preloaded pinned world presentation session required');}keys.add(sessionKey);
  const r={...current,owner,sessionKey,source,sequence:0,scope:null,producer:null,phase:null,history:[],publishedLength:0,retired:false};owners.set(owner,r);streams.add(r);append(r,{kind:'init-session',sessionKey,actorKey:r.actorKey,profession:r.profession,bodyKey:'elf-female',bindingId:BINDING,inputs:copy(source.inputs),compatiblePresentation:true,originalInitialActorStateKnown:false});return r;
 }
 function safe(where,run,owner){try{run();}catch(error){fault(where,error);if(owner)retire(owners.get(owner),'presentation-source-failure');}}
 function terminal(r,kind){if(!r||r.retired||!r.producer||r.phase!=='chant')return;const out=r.producer.finish(kind);if(out?.scope!==r.scope||out.phase!==kind)throw Error('Original-source presentation terminal result differs');r.phase=kind;emit(r,kind);}
 const currentRecord=(owner,ctx,id)=>{const r=owners.get(owner);return r&&!r.retired&&r.characterId===ctx.characterId&&r.scope===id?r:null;};
 return Object.freeze({
  questId:461,
  begin(ctx,owner,command){const result=collection.begin(ctx,owner,command);safe('begin-projection',()=>{if(closed)return;const r=sourceFor(owner,ctx);if(!r)return;
    if(r.producer){r.producer.release();emit(r,'release');r.producer=null;r.phase=null;if(r.retired)return;}
    r.scope=result.id;const p=r.source.session.makeProducer({scope:r.scope,actorKey:r.actorKey,profession:r.profession});const out=p.begin();if(out?.scope!==r.scope||out.actorKey!==r.actorKey)throw Error('Current source begin result differs');r.producer=p;r.phase='chant';emit(r,'begin');},owner);return result;
  },
  finish(ctx,owner,id){let result;try{result=collection.finish(ctx,owner,id);}catch(error){safe('finish-error-retire',()=>{const r=currentRecord(owner,ctx,id);if(r)retire(r,'compatible-finish-rejected');});throw error;}
   if(result?.pending===false)safe('finish-projection',()=>{const r=currentRecord(owner,ctx,id);if(r&&matches(r,identity(owner)))terminal(r,'success');else if(r)retire(r,'connection-changed');},owner);return result;
  },
  cancel(ctx,owner,id){const r=currentRecord(owner,ctx,id),result=collection.cancel(ctx,owner,id);safe('cancel-projection',()=>{if(r&&matches(r,identity(owner)))terminal(r,'interrupt');else if(r)retire(r,'connection-changed');},owner);return result;},
  tickRoom(roomKey,{tick,milliseconds,serverTime}={}){
   if(closed)throw Error('Presentation event owner disposed');if(typeof roomKey!=='string'||!Number.isSafeInteger(tick)||tick<0||!Number.isInteger(milliseconds)||milliseconds<0||milliseconds>1000||!Number.isSafeInteger(serverTime)||serverTime<0||serverTime>=2147483648000)throw Error('Authoritative existing room tick/time required');
   const previous=roomTicks.get(roomKey);if(previous!==undefined&&tick<=previous)return{origin:'compatible-461-gather-events-v1',mapId:1,roomKey,tick,records:[],rejectedTick:true};roomTicks.set(roomKey,tick);
   if(previous!==undefined&&tick!==previous+1)for(const r of[...streams])if(r.roomKey===roomKey)retire(r,'missing-authoritative-tick');
   for(const r of[...streams])if(r.roomKey===roomKey){
    let now;try{now=identity(r.owner);}catch(error){fault('read-owner',error);}if(!matches(r,now)){retire(r,'connection-or-character-changed');continue;}if(!r.producer)continue;
    try{const timeval=[Math.floor(serverTime/1000),serverTime%1000*1000],out=r.producer.frame(milliseconds,timeval);if(out?.scope!==r.scope||out.actorKey!==r.actorKey||out.pose?.bindingId!==BINDING||out.pose?.valueBytes!==1536||typeof out.settled!=='boolean')throw Error('Bound current world pose result required');emit(r,'frame',{milliseconds,timeval});
     if(!r.retired&&out.settled&&r.phase!=='chant'){r.producer.release();emit(r,'release');r.producer=null;r.phase=null;}
    }catch(error){fault('frame-projection',error);retire(r,'presentation-source-failure');}
   }
   const records=roomPending.get(roomKey)||[];roomPending.delete(roomKey);
   // HTTP callbacks may append between room ticks. A replay at tick N must
   // contain only the prefix actually published by N, otherwise N+1 repeats
   // that same begin/terminal event in the strict original-source receiver.
   for(const r of streams)if(r.roomKey===roomKey)r.publishedLength=r.history.length;
   return{origin:'compatible-461-gather-events-v1',mapId:1,roomKey,tick,records};
  },
  replayRoom(roomKey){if(closed)throw Error('Presentation event owner disposed');return[...streams].filter(r=>r.roomKey===roomKey&&!r.retired).map(r=>({sessionKey:r.sessionKey,actorKey:r.actorKey,records:copy(r.history)}));},
  snapshotRoom(roomKey){if(closed||!roomTicks.has(roomKey))throw Error('Current room tick required before replay');return{origin:'compatible-461-gather-events-v1',mapId:1,roomKey,tick:roomTicks.get(roomKey),records:[...streams].filter(r=>r.roomKey===roomKey&&!r.retired&&r.publishedLength>0).flatMap(r=>copy(r.history.slice(0,r.publishedLength)))};},
  closeOwner(owner){retire(owners.get(owner),'connection-closed');},
  inspect(){return{streams:streams.size,pendingRooms:roomPending.size,closed};},
  dispose(){if(closed)return;closed=true;for(const r of[...streams])retire(r,'event-owner-disposed');roomPending.clear();roomTicks.clear();keys.clear();}
 });
}

/** A receive capability held by the existing authenticated WS owner. The
 * caller preloads exact source bytes/body targets; this has no network API.
 * rAF may reapply a cached pose, but never advances its original-source clock. */
export function createCompatible461GatherInbox({readHost,readActor,makeReceiver,onFault=()=>{}}={}){
 if(![readHost,readActor,makeReceiver,onFault].every(f=>typeof f==='function'))throw Error('Current host/actor/receiver capabilities required');
 const initial=readHost(),required=['connection','epoch','characterId','roomKey'];
 if(!initial?.connected||!initial.connection||!['object','function'].includes(typeof initial.connection)||!required.every(k=>Object.hasOwn(initial,k))||typeof initial.characterId!=='string'||!initial.characterId||typeof initial.roomKey!=='string'||!initial.roomKey)throw Error('Explicit connected host session required');
 const owned=Object.fromEntries(required.map(k=>[k,initial[k]])),streams=new Map();let closed=false,lastTick=null,needsReplay=false;
 const report=e=>{try{onFault({error:String(e?.message||e),presentationOnly:true});}catch{}};
 function drop(r){streams.delete(r.sessionKey);try{r.port.dispose();}catch(e){report(e);}}
 function invalidate(){if(closed)return;closed=true;for(const r of[...streams.values()])drop(r);}
 function current(){let h;try{h=readHost();}catch(e){report(e);}if(!h?.connected||!required.every(k=>h[k]===owned[k])){invalidate();return false;}return!closed;}
 function actorNow(r){const a=readActor(r.actorKey);return a?.displayed===true&&a.actorKey===r.actorKey&&a.bodyKey==='elf-female'&&a.bindingId===BINDING&&a.profession===r.profession&&Object.hasOwn(a,'epoch')?a:null;}
 function sameActor(r,a){return!!a&&a.epoch===r.actor.epoch;}
 function consume(packet,replay){
  if(!current())return null;
  if(packet?.origin!=='compatible-461-gather-events-v1'||packet.mapId!==1||packet.roomKey!==owned.roomKey||!Number.isSafeInteger(packet.tick)||packet.tick<0||!Array.isArray(packet.records))throw Error('Owned authoritative room packet required');
  if(replay){if(lastTick!==null||streams.size)throw Error('Replay must initialize a fresh inbox');}
  else if(lastTick!==null){if(packet.tick<=lastTick)return{ignored:true,needsReplay};if(packet.tick!==lastTick+1){needsReplay=true;for(const r of[...streams.values()])drop(r);lastTick=packet.tick;return{needsReplay:true};}}
  lastTick=packet.tick;let applied=0;
  for(const record of packet.records){if(!current())return null;try{
   if(record?.kind==='init-session'){
    if(typeof record.sessionKey!=='string'||!record.sessionKey||typeof record.actorKey!=='string'||!record.actorKey||streams.has(record.sessionKey)||[...streams.values()].some(r=>r.actorKey===record.actorKey)||record.bodyKey!=='elf-female'||record.bindingId!==BINDING||!record.inputs)throw Error('Unique pinned actor initialization required');
    const actor=actorNow(record);if(!actor){needsReplay=true;continue;}
    const port=makeReceiver(copy(record),actor);if(!port){needsReplay=true;continue;}
    if(port.then||!['consume','apply','dispose'].every(k=>typeof port[k]==='function')){try{port.dispose?.();}catch{}throw Error('Preloaded synchronous own actor receiver required');}
    streams.set(record.sessionKey,{...record,actor:{epoch:actor.epoch},port,last:null});
   }else if(record?.kind==='retire-session'){
    const r=streams.get(record.sessionKey);if(r){if(record.actorKey!==r.actorKey)throw Error('Retirement actor mismatch');drop(r);}
   }else if(record?.kind==='event'){
    const r=streams.get(record.event?.sessionKey);if(!r){needsReplay=true;continue;}
    if(!sameActor(r,actorNow(r))){drop(r);needsReplay=true;continue;}
    const out=r.port.consume(record.event);if(out?.pose){r.port.apply(out.pose);r.last=copy(out.pose);applied++;}else if(record.event.operation==='release')r.last=null;
   }else throw Error('Unknown presentation record refused');
  }catch(error){report(error);const key=record?.event?.sessionKey??record?.sessionKey,r=streams.get(key);if(r)drop(r);needsReplay=true;}}
  return{applied,needsReplay};
 }
 return Object.freeze({consume:packet=>consume(packet,false),replay:packet=>consume(packet,true),
  afterBaseUpdate(){if(!current())return 0;let n=0;for(const r of[...streams.values()]){try{if(!sameActor(r,actorNow(r))){drop(r);needsReplay=true;continue;}if(r.last){r.port.apply(r.last);n++;}}catch(e){report(e);drop(r);needsReplay=true;}}return n;},
  inspect(){return{closed,lastTick,needsReplay,streams:streams.size};},invalidate,dispose:invalidate});
}
