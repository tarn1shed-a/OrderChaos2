import{WORLD_BODY_CONTRACTS,selectWorldContract,LEGACY_WORLD_CONTRACT_SET,assertTrustedWorldContractSet,worldContractSetReceiptMatches}from'./contracts.mjs';
// Web command admission, not original-server game rules or asset readiness.
// One source-body policy; the original 461 executor keeps its own validation.
const own=(v,k)=>!!v&&Object.hasOwn(v,k),plain=v=>!!v&&typeof v==='object'&&!Array.isArray(v);
const exact=(v,ks)=>plain(v)&&Object.keys(v).sort().join(',')===[...ks].sort().join(',');
const source=r=>own(r,'sourceAvatar');
const error=()=>Error('该角色的此项操作尚未接入');

export function createCommonSourceWorldCommandGate({registry,contractSet=LEGACY_WORLD_CONTRACT_SET,resolveContract=null,resolveCapability=null,canGather=null}={}){
 if(registry?.count!==45||typeof registry.check!=='function'||resolveContract!==null&&typeof resolveContract!=='function'||resolveCapability!==null&&typeof resolveCapability!=='function'||canGather!==null&&typeof canGather!=='function')throw Error('Explicit registry and trusted host ports required');
 assertTrustedWorldContractSet(contractSet);
 const owners=new WeakMap();
 function checked(record){
  const avatar=registry.check(record.sourceAvatar,record.profession),contract=selectWorldContract(registry,record,resolveContract,contractSet);
  if(!contract||
    !plain(record.equipment)||Object.values(record.equipment).some(v=>v!==null)||
    record.hotbar!==null||record.sourceInventoryPolicy!=='empty-compatible-container-v1'||
    !plain(record.inventory)||Object.keys(record.inventory).length)throw error();
  // Compare exact original registry output, not message-supplied appearance.
  return JSON.stringify({id:record.id,profession:record.profession,avatar});
 }
 function capability(record){
  const contract=selectWorldContract(registry,record,resolveContract,contractSet),c=resolveCapability?.(record);
  if(!contract||!c||!worldContractSetReceiptMatches(c,contractSet)||Object.entries(contract.policy).some(([k,v])=>c[k]!==v))throw error();
  return c;
 }
 function current(ws){
  if(!source(ws?.character)&&!owners.has(ws))return null;
  const r=owners.get(ws);
  if(!r||r.record!==ws.character||r.stamp!==checked(ws.character)||capability(ws.character)!==r.capability||
   ws.player?.id!==ws.character.id||ws.player.profession!==ws.character.profession||
   JSON.stringify(registry.check(ws.player.sourceAvatar,ws.player.profession))!==r.avatar||
   ws.ordinaryQuestMap!==r.contract.policy.mapId||selectWorldContract(registry,ws.character,resolveContract,contractSet)!==r.contract)throw error();
  return r;
 }
 function requireCurrent(ws){try{return current(ws);}catch{throw error();}}
 return Object.freeze({
  join(ws,record,msg){
   if(!source(record))return true;
   try{
    if(!plain(msg)||msg.scene!=='resources'||msg.mapWindow!=='heaven-landing'||own(msg,'lab')||
     own(msg,'sourceAvatar')||msg.profession!==record.profession)throw error();
    const stamp=checked(record),c=capability(record);
    owners.set(ws,{record,stamp,capability:c,contract:selectWorldContract(registry,record,resolveContract,contractSet),avatar:JSON.stringify(registry.check(record.sourceAvatar,record.profession))});return true;
   }catch{return false;}
  },
  message(ws,msg){
   if(!source(ws?.character)&&!owners.has(ws))return true;
   try{
    const r=requireCurrent(ws);
    if(msg?.type==='input')return exact(msg,['type','x','y'])&&[msg.x,msg.y].every(n=>typeof n==='number'&&Number.isFinite(n)&&Math.abs(n)<=1);
    if(msg?.type==='jump')return r.contract.capabilities.jump&&exact(msg,['type','pressed'])&&typeof msg.pressed==='boolean';
    if(msg?.type==='ping')return exact(msg,['type','at'])&&Number.isFinite(msg.at)||exact(msg,['type']);
    if(msg?.type==='save')return exact(msg,['type']);
    return false;
   }catch{return false;}
  },
  assertQuest(ws,operation,command){
   if(!source(ws?.character)&&!owners.has(ws))return;
   const r=requireCurrent(ws);
   if(operation==='state'||operation==='presentation')return;
   if(operation==='query'){if(command!==461)throw error();return;}
   if(!plain(command))throw error();
   if(['accept','complete','abandon','cancel'].includes(command.type)&&command.questId===461)return;
   if(command.type==='collect-cancel')return; // Id/owner are validated by the existing collection.
   if(['collect-start','collect-finish'].includes(command.type)&&
     (command.type!=='collect-start'||command.questId===461)&&r.contract.capabilities.gatherHostPort&&canGather?.(ws,r.contract)===true)return;
   throw error();
  },
  forget(ws){owners.delete(ws);},
  inspect(){return {defaultSourceJoinClosed:resolveCapability===null||resolveContract===null,sourceBody:null,sourcePolicyIndex:Object.keys(contractSet.contracts),
   ordinaryQuestIds:[461],unknownMessagesRefused:true,combat:false,equipment:false,hotbar:false,lookMutation:false,
   gatherRequiresExplicitHostPort:true,originalServerRulesRecovered:false};}
 });
}

// Reuse actual ledger/collection, not a second task state machine.
export function guardQuestPorts({gate,ledger,collection,active,store}){
 if(ledger?.profile?.mapId!==1||ledger.profile.quests?.length!==1||ledger.profile.quests[0].id!==461||
   collection&&collection.questId!==461)throw Error('Only the authorized compatible461 executor may be wrapped');
 const owner=ctx=>{
  const ws=active.get(ctx.characterId);
  if(!ws||ws.character!==store.records.get(ctx.characterId)||ws.player?.id!==ctx.characterId)throw error();
  return ws;
 };
 const wrappedLedger=Object.create(ledger);
 wrappedLedger.query=(ctx,id)=>{gate.assertQuest(owner(ctx),'query',id);return ledger.query(ctx,id);};
 wrappedLedger.snapshot=id=>{const ws=active.get(id);if(!ws||ws.character!==store.records.get(id))throw error();gate.assertQuest(ws,'state');return ledger.snapshot(id);};
 wrappedLedger.act=(ctx,c)=>{gate.assertQuest(owner(ctx),'action',c);return ledger.act(ctx,c);};
 const wrappedCollection=collection?{
  questId:collection.questId,
  begin(ctx,ws,c){if(ws!==owner(ctx))throw error();gate.assertQuest(ws,'action',c);return collection.begin(ctx,ws,c);},
  finish(ctx,ws,id){if(ws!==owner(ctx))throw error();gate.assertQuest(ws,'action',{type:'collect-finish'});return collection.finish(ctx,ws,id);},
  cancel(ctx,ws,id){if(ws!==owner(ctx))throw error();gate.assertQuest(ws,'action',{type:'collect-cancel'});return collection.cancel(ctx,ws,id);},
  ...(collection.snapshotRoom?{snapshotRoom:room=>collection.snapshotRoom(room)}:{})
 }:null;
 return {ledger:wrappedLedger,collection:wrappedCollection};
}
