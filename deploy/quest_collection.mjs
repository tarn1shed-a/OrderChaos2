// Rebuilt execution for the already authorized compatible quest461 only.
// Original skill15 rune rows all specify 1500ms; using that duration here is
// an explicit local-server policy, not a recovered original-server approval.
import {randomUUID} from 'node:crypto';

export const COLLECTION_PROFILE='/assets/source-quest461-channel-v1/execution.json';
export function checkCollectionProfile(p){
  if(p?.format!=='oc2-compatible-461-channel-v1'||p.originalServerRecovered!==false||
    p.questId!==461||p.mapId!==1||p.objectEntry!==467||p.skillProtoId!==15||
    p.skillChannelTime!==1500||p.isChannel!==false||
    p.programSHA256!=='4aed22d400be720600dfa91a4030b6dd7ef3cd43b04728f07f5898d46b134be2'||
    p.visualSHA256!=='8b47d8cf5395ae2f60beacc81564b559f1f5f2fe287d262b4f59c07609a1fc0c'||
    p.artSHA256!=='6f3f2ae104dc1eb5d659b30136a5137ef2d718a8e7833514490d3218e69e10b3')
    throw Error('原收集流程资料不符');
  return Object.freeze(structuredClone(p));
}

export function createQuestCollection({ledger,profile,clock=()=>performance.now(),nonce=randomUUID}){
  const p=checkCollectionProfile(profile),pending=new WeakMap();
  if(ledger?.profile?.mapId!==p.mapId||typeof clock!=='function'||typeof nonce!=='function')throw Error('收集地图未就绪');
  const ownerRequired=owner=>{if(!owner||typeof owner!=='object')throw Error('角色连接已变更');};
  return Object.freeze({
    questId:p.questId,
    begin(ctx,owner,command){
      ownerRequired(owner);
      const source={...command,type:'collect'};
      if(command?.type!=='collect-start'||command.questId!==p.questId)throw Error('此收集流程尚未恢复');
      const checked=ledger.validateCollect(ctx,source);
      if(checked.object.entry!==p.objectEntry)throw Error('原收集对象不符');
      const cast={id:nonce(),characterId:ctx.characterId,command:source,startedAt:clock()};
      // A fresh request supersedes this connection's earlier uncommitted attempt.
      pending.set(owner,cast);
      return {origin:'compatible-quest-channel-v1',id:cast.id,skillProtoId:p.skillProtoId,
        skillChannelTime:p.skillChannelTime,isChannel:p.isChannel};
    },
    finish(ctx,owner,id){
      ownerRequired(owner);const cast=pending.get(owner);
      if(!cast||cast.characterId!==ctx.characterId||cast.id!==id)throw Error('收集操作已失效，请重新操作');
      try{
        ledger.validateCollect(ctx,cast.command);
        const remaining=p.skillChannelTime-(clock()-cast.startedAt);
        if(remaining>0)return {pending:true,retryAfterMs:Math.ceil(remaining)};
        // The same checked ledger performs the only durable item mutation.
        const state=ledger.act(ctx,cast.command);pending.delete(owner);
        return {pending:false,state};
      }catch(error){pending.delete(owner);throw error;}
    },
    cancel(ctx,owner,id){
      ownerRequired(owner);const cast=pending.get(owner);
      if(cast?.characterId===ctx.characterId&&cast.id===id)pending.delete(owner);
      return ledger.snapshot(ctx.characterId);
    },
  });
}
