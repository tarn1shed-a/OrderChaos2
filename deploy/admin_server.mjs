// A separate, read-only operator interface. Never export recovery credentials.
import {randomBytes,scrypt,timingSafeEqual} from 'node:crypto';
import {promisify} from 'node:util';
import {readFile} from 'node:fs/promises';
const derive=promisify(scrypt),COOKIE='oc2-admin-session';
const fields=['id','name','profession','level','xp','gold','kills','hp','maxHp','createdAt','updatedAt'];
export function playerReport(store,active,now=Date.now(),sourcePoint=null){
 const players=[...store.records.values()].map(record=>{
  const ws=active.get(record.id),online=ws?.readyState===1;
  const view=Object.fromEntries(fields.map(key=>[key,record[key]??null]));
  const stored=record.positions?.resources||record.positions?.camp,position=online&&ws.player?{x:ws.player.x,y:ws.player.y,height:ws.player.worldY??null}:stored?{x:stored.x,y:stored.y,height:stored.groundY??null}:null;
  const client=online?ws.entryConnection:null;let worldPosition=null;
  if(sourcePoint&&position&&(online?ws.scene==='resources':Boolean(record.positions?.resources))&&Number.isFinite(position.x)&&Number.isFinite(position.y)){const p=sourcePoint(position.x,position.y);if(Number.isFinite(p.x)&&Number.isFinite(p.z))worldPosition={x:p.x,y:position.height,z:p.z};}
  return {...view,online,room:online?ws.roomId:null,scene:online?ws.scene:null,
   connectedAt:online?ws.entryJoinedAt??null:null,
   onlineSeconds:online&&Number.isFinite(ws.entryJoinedAt)?Math.max(0,Math.floor((now-ws.entryJoinedAt)/1000)):null,
   lastPacketAt:online?ws.entryLastPacketAt??null:null,rttMs:online&&Number.isFinite(ws.entryRttMs)?ws.entryRttMs:null,
   client:client?{ip:client.ip??null,ipSource:client.ipSource??null,browser:client.browser??null,platform:client.platform??null,userAgent:client.userAgent??null}:null,
   position,positionKind:online?'current':position?'saved':null,worldPosition,
   equipment:Object.fromEntries(Object.entries(record.equipment||{}).filter(([slot,item])=>typeof slot==='string'&&typeof item==='string')),
   inventory:Object.fromEntries(Object.entries(record.inventory||{}).filter(([item,count])=>typeof item==='string'&&Number.isFinite(count)&&count>=0)),
   inventoryItems:Object.values(record.inventory||{}).reduce((sum,count)=>sum+(Number.isFinite(count)&&count>0?count:0),0)};
 }).sort((a,b)=>Number(b.online)-Number(a.online)||String(a.name).localeCompare(String(b.name),'zh-CN'));
 return {at:now,savedAt:store.savedAt??null,online:players.filter(p=>p.online).length,total:players.length,players,
  server:{rooms:new Set(players.filter(p=>p.online).map(p=>p.room)).size,uptimeSeconds:Math.floor(process.uptime()),memoryMiB:Math.round(process.memoryUsage().rss/1048576)}};
}
export function adminPasswordConfigured(value){return typeof value==='string'&&/^scrypt\$[0-9a-f]{32}\$[0-9a-f]{64}$/.test(value);}
export async function makeAdminPasswordHash(password,salt=randomBytes(16).toString('hex')){
 if(typeof password!=='string'||password.length<16||password.length>128||! /^[0-9a-f]{32}$/.test(salt))throw Error('Invalid administrator password');
 const hash=await derive(password,Buffer.from(salt,'hex'),32);return 'scrypt$'+salt+'$'+hash.toString('hex');
}
export function installAdmin(server,{store,active,passwordHash,secureCookies=true,now=Date.now,sourcePoint=null}){
 const enabled=adminPasswordConfigured(passwordHash),sessions=new Map(),attempts=new Map(),ttl=8*3600000;
 const original=server.listeners('request');for(const listener of original)server.removeListener('request',listener);
 const security={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
  'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"};
 const cookie=value=>`${COOKIE}=${value}; Path=/; HttpOnly; SameSite=Strict${secureCookies?'; Secure':''}; Max-Age=${value?ttl/1000:0}`;
 function prune(){for(const[key,end]of sessions)if(end<=now())sessions.delete(key);for(const[key,state]of attempts)if(state.until<=now())attempts.delete(key);}
 function identity(req){const match=(req.headers.cookie||'').split(';').map(v=>v.trim()).find(v=>v.startsWith(COOKIE+'='));const value=match?.slice(COOKIE.length+1);return /^[0-9a-f]{64}$/.test(value||'')&&sessions.get(value)>now()?value:null;}
 server.on('request',async(req,res)=>{
  const path=new URL(req.url,'http://localhost').pathname;
  const files={'/admin/':'admin.html','/admin/admin.js':'admin.js','/admin/admin.css':'admin.css'};
  if(path==='/admin'){res.writeHead(302,{...security,Location:'/admin/'});res.end();return;}
  if(!Object.hasOwn(files,path)&&!path.startsWith('/__admin/')){for(const listener of original)listener.call(server,req,res);return;}
  const reply=(status,data,headers={})=>{res.writeHead(status,{...security,'Content-Type':'application/json; charset=utf-8',...headers});res.end(JSON.stringify(data));};
  try{
   prune();
   if(Object.hasOwn(files,path)){
    if(req.method!=='GET')return reply(405,{error:'请求无效'});
    const name=files[path],data=await readFile(new URL('./'+name,import.meta.url));
    res.writeHead(200,{...security,'Content-Type':name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.js')?'text/javascript; charset=utf-8':'text/css; charset=utf-8'});res.end(data);return;
   }
   if(req.method==='GET'&&path==='/__admin/session')return reply(200,{enabled,authenticated:enabled&&Boolean(identity(req))});
   if(!enabled)return reply(503,{error:'管理后台尚未启用'});
   if(req.method==='GET'&&path==='/__admin/players'){
    if(!identity(req))return reply(401,{error:'请先登录管理后台'});
    return reply(200,playerReport(store,active,now(),sourcePoint));
   }
   if(req.method!=='POST'||!['/__admin/login','/__admin/logout'].includes(path))return reply(405,{error:'请求无效'});
   if(!req.headers.origin||new URL(req.headers.origin).host!==req.headers.host)return reply(403,{error:'请求来源无效'});
   if(path==='/__admin/logout'){const token=identity(req);if(token)sessions.delete(token);return reply(200,{ok:true},{'Set-Cookie':cookie('')});}
   const address=req.socket.remoteAddress||'unknown',state=attempts.get(address)||{count:0,until:now()+60000};
   if(state.count>=5)return reply(429,{error:'尝试过于频繁，请一分钟后再试'});
   state.count++;attempts.set(address,state);
   if(req.headers['content-type']?.split(';')[0]!=='application/json')return reply(415,{error:'请求无效'});
   const chunks=[];let bytes=0;
   for await(const chunk of req){bytes+=chunk.length;if(bytes>1024){req.resume();return reply(413,{error:'请求过大'});}chunks.push(chunk);}
   const data=JSON.parse(Buffer.concat(chunks).toString());
   if(typeof data.password!=='string'||data.password.length>128)return reply(401,{error:'管理密码不正确'});
   const [,salt,expected]=passwordHash.split('$'),actual=await derive(data.password,Buffer.from(salt,'hex'),32);
   if(!timingSafeEqual(actual,Buffer.from(expected,'hex')))return reply(401,{error:'管理密码不正确'});
   attempts.delete(address);while(sessions.size>=16)sessions.delete(sessions.keys().next().value);
   const token=randomBytes(32).toString('hex');sessions.set(token,now()+ttl);
   reply(200,{ok:true},{'Set-Cookie':cookie(token)});
  }catch{if(!res.headersSent)reply(400,{error:'请求无法完成'});else res.end();}
 });
}
