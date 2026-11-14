// Web persistence adapter. Original UI callbacks are not original account services.
import {createHash,randomUUID,randomInt,timingSafeEqual} from 'node:crypto';
import {mkdirSync,writeFileSync} from 'node:fs';
import {dirname,join} from 'node:path';
import {observeServer} from './observe_server.mjs';
import {entryNameError} from './entry_name.mjs';

export function entryServer(source,traceURL){
  const observed=observeServer(source,traceURL),anchor='    server, rooms, combatRooms,';
  if(observed.split(anchor).length!==2)throw Error('Entry store anchor differs');
  const spawn='x: restorePosition ? position.x : world.spawn.x + index * 35,';
  if(observed.split(spawn).length!==2)throw Error('Entry placement anchor differs');
  const scene="        const scene = msg.scene || 'camp';";
  if(observed.split(scene).length!==2)throw Error('Entry scene anchor differs');
  let result=observed.replace(anchor,anchor+'\n    entryStore:store,entryActive:activeCharacters,')
    .replace(spawn,'x: restorePosition ? position.x : world.spawn.x + (sourceWindow?0:index * 35),')
    .replace(scene,"        if(msg.lab!==undefined)return reject(ws,'本地碰撞测试入口已停用，请从正式地图入口进入');\n"+scene);
  const replace=(from,to)=>{if(result.split(from).length!==2)throw Error('Runtime recovery anchor differs');result=result.replace(from,to);};
  replace('createGameServer({ maxPlayersPerRoom=8,','createGameServer({ onRuntimeFailure=null, maxPlayersPerRoom=8,');
  replace('  let storageError = null;','  let storageError = null, runtimeError = null;');
  replace("wss.emit('connection', ws)","wss.emit('connection', ws, req)");
  replace("  wss.on('connection', ws => {", "  wss.on('connection', (ws,request) => {\n    ws.entryConnection=readConnectionInfo(request,{trustRailway:Boolean(process.env.RAILWAY_ENVIRONMENT_ID)});");
  replace("    ws.on('pong', () => { ws.alive = true; });", "    ws.on('pong', () => { ws.alive = true;noteConnectionPong(ws); });");
  replace("    ws.on('message', (buffer, binary) => {", "    ws.on('message', (buffer, binary) => {\n      ws.entryLastPacketAt=Date.now();");
  replace('      ws.alive = false; ws.ping();','      ws.alive = false;ws.entryPingAt=Date.now();ws.ping();');
  replace('        activeCharacters.set(ws.player.id, ws);','        ws.entryJoinedAt=Date.now();activeCharacters.set(ws.player.id, ws);');
  replace("        res.writeHead(200, { 'Content-Type': 'application/json' });", "        res.writeHead(storageError||runtimeError?503:200, { 'Content-Type': 'application/json' });");
  replace('ok: !storageError,','ok: !storageError&&!runtimeError,');
  replace('  const storageFailure = error => {',`  const storageFailure = error => {
    if(isPhysicsTransportFailure(error)){
      if(runtimeError)return;
      runtimeError=error;console.error(error.message);
      for(const ws of activeCharacters.values())notice(ws,'场景计算暂时中断，服务正在恢复，请稍后重新进入');
      onRuntimeFailure?.(error);return;
    }`);
  replace("      if (storageError) return reject(ws, '存档当前不可用，请检查服务器后重试');", "      if(runtimeError)return reject(ws,'场景服务正在恢复，请稍后重新进入');\n      if (storageError) return reject(ws, '存档当前不可用，请检查服务器后重试');");
  replace('    if (storageError) return;','    if (storageError||runtimeError) return;');
  return `import {isPhysicsTransportFailure} from ${JSON.stringify(new URL('./runtime_recovery.mjs',import.meta.url).href)};\nimport{readConnectionInfo,noteConnectionPong}from ${JSON.stringify(new URL('./connection_info.mjs',import.meta.url).href)};\n`+result;
}

export function trialRoleManager(store,active,{archive=record=>{
  if(!store.saveFile)return;
  const folder=join(dirname(store.saveFile),'deleted-roles');mkdirSync(folder,{recursive:true,mode:0o700});
  writeFileSync(join(folder,record.id+'-'+randomUUID()+'.json'),JSON.stringify(record,null,2),{flag:'wx',mode:0o600});
},now=Date.now,entryPosition=null,backupEntry=record=>{
  if(!store.saveFile)return;
  const folder=join(dirname(store.saveFile),'entry-backups');mkdirSync(folder,{recursive:true,mode:0o700});
  writeFileSync(join(folder,record.id+'-'+randomUUID()+'.json'),JSON.stringify(record,null,2),{flag:'wx',mode:0o600});
}}={}){
  const challenges=new Map();
  function own(identity){
    const record=store.records.get(identity?.characterId),token=identity?.resumeToken;
    if(!record||typeof token!=='string'||! /^[0-9a-f]{64}$/.test(token)||
       !timingSafeEqual(createHash('sha256').update(token).digest(),Buffer.from(record.tokenHash,'hex')))throw Error('角色凭据不匹配，未修改存档');
    return record;
  }
  function offline(record){if(active.has(record.id))throw Error('角色仍在线，请先退出游戏再删除');}
  return {
    returnEntry(data){
      const record=own(data);
      if(data.anchor!=='cinematic7'||!entryPosition)throw Error('未知试玩起点');
      if(active.has(record.id))throw Error('角色仍在线，请关闭原游戏页后重试');
      const target=entryPosition();
      if(!target||!['x','y','groundY'].every(k=>Number.isFinite(target[k])))throw Error('原落点碰撞尚未就绪');
      const positions=record.positions,dirty=store.dirty,savedAt=store.savedAt;
      backupEntry(structuredClone(record));
      try{record.positions={...positions,resources:{...target}};store.dirty=true;store.flush();}
      catch(error){record.positions=positions;store.dirty=dirty;store.savedAt=savedAt;throw error;}
      return {returned:record.id,anchor:'cinematic7',originalFirstSpawn:false};
    },
    create(data){
      // Only the avatar actually supported by the current preview may be created.
      // No substitute human/orc model, appearance or village/spawn is invented.
      if(data.race!==2||data.gender!==1)throw Error('此种族或性别的角色外观尚未接入，未创建角色');
      if(![1,2,3,4,5].includes(data.profession))throw Error('职业无效');
      const name=data.name;
      const error=entryNameError(name);if(error)throw Error(error);
      const entries=[...store.records],dirty=store.dirty,savedAt=store.savedAt;
      try{
        const identity=store.resolveCharacter(name,undefined,undefined,data.profession);
        return {character:{id:identity.record.id,name:identity.record.name,level:identity.record.level,profession:identity.record.profession},resumeToken:identity.resumeToken};
      }catch(error){store.records.clear();for(const[id,value]of entries)store.records.set(id,value);store.dirty=dirty;store.savedAt=savedAt;throw error;}
    },
    challenge(identity){
      const record=own(identity);offline(record);
      for(const[key,value]of challenges)if(value.until<now()||value.id===record.id)challenges.delete(key);
      if(challenges.size>=256)throw Error('请稍后重试');
      const challenge=randomUUID(),code=String(randomInt(1000,9000));
      // Expiry and ownership are web transport protections, not recovered game rules.
      challenges.set(challenge,{id:record.id,code,until:now()+600000});
      return {challenge,code};
    },
    remove(data){
      const record=own(data);offline(record);const proof=challenges.get(data.challenge);
      if(!proof||proof.id!==record.id||proof.until<now()||proof.code!==data.code)throw Error('删除确认已失效或验证码有误');
      archive(structuredClone(record));
      const entries=[...store.records],dirty=store.dirty,savedAt=store.savedAt;
      try{store.records.delete(record.id);store.dirty=true;store.flush();}
      catch(error){store.records.clear();for(const[id,value]of entries)store.records.set(id,value);store.dirty=dirty;store.savedAt=savedAt;throw error;}
      challenges.delete(data.challenge);return {deleted:record.id};
    }
  };
}

export function installEntryManagement(server,manager){
  const original=server.listeners('request');for(const listener of original)server.removeListener('request',listener);
  server.on('request',async(req,res)=>{
    const path=new URL(req.url,'http://localhost').pathname,actions={'/__entry/create':'create','/__entry/delete-challenge':'challenge','/__entry/delete':'remove','/__entry/return':'returnEntry'};
    if(!Object.hasOwn(actions,path)){for(const listener of original)listener.call(server,req,res);return;}
    const reply=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(data));};
    if(req.method!=='POST'||req.headers['content-type']?.split(';')[0]!=='application/json')return reply(405,{error:'请求无效'});
    try{if(!req.headers.origin||new URL(req.headers.origin).host!==req.headers.host)return reply(403,{error:'请求来源无效'});}catch{return reply(403,{error:'请求来源无效'});}
    try{
      const chunks=[];let bytes=0;
      for await(const chunk of req){bytes+=chunk.length;if(bytes>4096){reply(413,{error:'请求过大'});req.resume();return;}chunks.push(chunk);}
      const data=JSON.parse(Buffer.concat(chunks).toString());
      reply(200,manager[actions[path]](data));
    }catch(error){reply(400,{error:error.message});}
  });
}
