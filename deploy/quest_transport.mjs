// Same-origin web transport for the compatible task layer. Original Android
// account services and protobuf transport are not impersonated by this route.
import {createHash,timingSafeEqual} from 'node:crypto';

export function questContext(store,active,identity,mapId){
  const id=identity?.characterId,token=identity?.resumeToken;
  if(typeof id!=='string'||typeof token!=='string'||!/^[0-9a-f]{64}$/.test(token))throw Error('角色凭据无效');
  const role=store.records.get(id);
  if(!role||typeof role.tokenHash!=='string'||!/^[0-9a-f]{64}$/.test(role.tokenHash)||
    !timingSafeEqual(createHash('sha256').update(token).digest(),Buffer.from(role.tokenHash,'hex')))throw Error('角色凭据无效');
  const ws=active.get(id);
  if(!ws?.player||ws.character!==role||ws.ordinaryQuestMap!==mapId||!ws.motion?.point)throw Error('请先进入原任务地图');
  const point=ws.motion.point(ws.player.x,ws.player.y);
  return {characterId:id,mapId,level:role.level,position:[point.x,ws.player.worldY,point.z],
    alive:ws.player.hp>0&&role.hp>0,inspector:ws.player.mapInspector===true};
}

export function installQuestTransport(server,{ledger,store,active,collection=null,context=identity=>questContext(store,active,identity,ledger.profile.mapId)}){
  const original=server.listeners('request');for(const handler of original)server.removeListener('request',handler);
  const paths=new Set(['/__quests/query','/__quests/action','/__quests/state',...(collection?.snapshotRoom?['/__quests/presentation']:[])]);
  server.on('request',async(req,res)=>{
    let path;try{path=new URL(req.url,'http://localhost').pathname;}catch{res.writeHead(400);res.end();return;}
    if(!paths.has(path)){for(const handler of original)handler.call(server,req,res);return;}
    const reply=(status,body)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(body));};
    if(req.method!=='POST'||req.headers['content-type']?.split(';')[0]!=='application/json')return reply(405,{error:'请求格式无效'});
    try{if(!req.headers.origin||new URL(req.headers.origin).host!==req.headers.host)return reply(403,{error:'请求来源无效'});}catch{return reply(403,{error:'请求来源无效'});}
    try{
      let size=0;const chunks=[];
      for await(const chunk of req){size+=chunk.length;if(size>4096){reply(413,{error:'请求过大'});req.resume();return;}chunks.push(chunk);}
      const data=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(Buffer.concat(chunks)));
      if(!data||typeof data!=='object'||Array.isArray(data))throw Error('任务请求无效');
      // Position, map, level and reward fields supplied by a client are never
      // used. The active authoritative connection owns this context.
      const ctx=context(data.identity);
      if(path==='/__quests/presentation'){
        const owner=active.get(ctx.characterId);
        if(!owner?.roomId)throw Error('当前房间已变更');
        return reply(200,{presentation:collection.snapshotRoom(owner.roomId)});
      }
      if(path==='/__quests/state')return reply(200,{state:ledger.snapshot(ctx.characterId)});
      if(path==='/__quests/query')return reply(200,{info:ledger.query(ctx,data.questId),state:ledger.snapshot(ctx.characterId)});
      if(collection){
        const owner=active.get(ctx.characterId),command=data.command;
        if(command?.type==='collect-start')return reply(200,{channel:collection.begin(ctx,owner,command)});
        if(command?.type==='collect-finish')return reply(200,collection.finish(ctx,owner,command.channelId));
        if(command?.type==='collect-cancel')return reply(200,{state:collection.cancel(ctx,owner,command.channelId)});
        if(command?.type==='collect'&&command.questId===collection.questId)throw Error('请先完成原收集进度');
      }
      if(data.command?.type==='cancel')return reply(200,{ok:true,state:ledger.snapshot(ctx.characterId)});
      const state=ledger.act(ctx,data.command);return reply(200,{ok:true,state});
    }catch(error){reply(400,{error:error.message});}
  });
}
