// Optional local acceptance using real sockets, original physics and a disposable save.
import assert from 'node:assert/strict';
import {existsSync,mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {startLocalMvp,ROOT} from './local_mvp.mjs';

const runtime=resolve(ROOT,'analysis/raw/showcase-20261110/running-preview');
if(!existsSync(resolve(runtime,'prototype/server.mjs'))){console.log('SKIP: original inputs and reviewed private runtime stay local');process.exit(0);}
const {default:WebSocket}=await import(pathToFileURL(resolve(runtime,'prototype/node_modules/ws/wrapper.mjs')));
const directory=mkdtempSync(resolve(ROOT,'analysis/raw/mvp-integration-'));
let service;const peers=[];
const until=async(check,label,timeout=12000)=>{const end=Date.now()+timeout;while(!check()){if(Date.now()>end)throw Error('MVP timeout: '+label);await new Promise(r=>setTimeout(r,25));}};
async function connect(name,identity){
 const socket=new WebSocket(service.url.replace(/^http/,'ws').replace(/\/explore-map.html.*/, '/ws'));
 const messages=[];const peer={socket,messages,send:m=>socket.send(JSON.stringify(m))};peers.push(peer);
 socket.on('message',b=>messages.push(JSON.parse(b.toString())));
 await new Promise((ok,fail)=>{socket.once('open',ok);socket.once('error',fail);});
 peer.send({type:'join',scene:'resources',mapWindow:'tutorial',room:'MVP-CHECK-01',name,profession:2,...identity});
 await until(()=>messages.some(m=>m.type==='welcome'),'join');
 peer.welcome=messages.find(m=>m.type==='welcome');
 peer.state=()=>messages.findLast(m=>m.type==='state');
 peer.progress=()=>messages.findLast(m=>m.type==='progress')?.character||peer.welcome.character;
 return peer;
}
try{
 service=await startLocalMvp({port:0,maxPlayers:4,dataDir:directory});
 await assert.rejects(startLocalMvp({port:0,dataDir:directory}),/服务锁/);
 const a=await connect('mvp-check-a');
 await until(()=>a.state()?.players.length===1,'single-player entry');
 assert.equal(a.welcome.roomCapacity,4);
 const b=await connect('mvp-check-b');
 await until(()=>a.state()?.players.length===2&&b.state()?.players.length===2,'two players');
 const initial=a.state().players.find(p=>p.id===a.welcome.id);assert(Number.isFinite(initial.worldY));
 const monster=a.state().monsters[0];
 a.send({type:'skill',skillId:'fireball',targetId:monster.id});
 b.send({type:'skill',skillId:'frost_blast',targetId:monster.id});
 await until(()=>!a.state().monsters[0].alive,'cooperative kill');
 await until(()=>a.progress().kills===1&&b.progress().kills===1,'reward both contributors');
 for(const peer of [a,b]){
  const c=peer.progress();assert.equal(c.xp,30);assert.equal(c.gold,10);
  const id=peer.welcome.id;
  const end=Date.now()+7000;
  while(peer.state().interaction?.kind!=='loot'&&Date.now()<end){
   const player=peer.state().players.find(p=>p.id===id),m=peer.state().monsters[0];
   const dx=m.x-player.x,dy=m.y-player.y,n=Math.max(1,Math.hypot(dx,dy));
   peer.send({type:'input',x:dx/n,y:dy/n});
   await new Promise(r=>setTimeout(r,90));
  }
  peer.send({type:'input',x:0,y:0});
  // The authoritative context snapshot is per client, not a shared map.
  await until(()=>peer.state()?.interaction?.kind==='loot','reachable corpse');
  const context=peer.state().interaction;
  peer.send({type:'loot',targetId:context.targetId,generation:context.generation});
  await until(()=>peer.progress().inventory.wolfPelt===1,'loot persisted');
  peer.send({type:'loot',targetId:context.targetId,generation:context.generation});
 }
 a.send({type:'equip',slot:'chest',itemId:'linenArmor'});
 await until(()=>a.progress().equipment.chest==='linenArmor','equip');
 await until(()=>b.state().players.some(p=>p.id===a.welcome.id&&p.equipment.chest==='linenArmor'),'equipment broadcast');
 assert.equal(a.progress().inventory.wolfPelt,1);assert.equal(b.progress().inventory.wolfPelt,1);
 const c=await connect('mvp-check-c'),d=await connect('mvp-check-d');
 await until(()=>[a,b,c,d].every(p=>p.state()?.players.length===4),'four-player room');
 for(const peer of [a,b,c,d])assert.equal(peer.welcome.roomCapacity,4);
 for(const p of a.state().players){assert(Number.isFinite(p.worldY));assert.match(p.color,/^#[0-9a-f]{6}$/i);}
 const extra=new WebSocket(service.url.replace(/^http/,'ws').replace(/\/explore-map.html.*/, '/ws'));
 const rejected=[];extra.on('message',v=>rejected.push(JSON.parse(v.toString())));
 await new Promise((ok,fail)=>{extra.once('open',ok);extra.once('error',fail);});
 extra.send(JSON.stringify({type:'join',scene:'resources',mapWindow:'tutorial',room:'MVP-CHECK-01',name:'over-capacity'}));
 await until(()=>rejected.some(m=>m.type==='error'),'configured room limit');extra.terminate();
 const identity={characterId:a.welcome.id,resumeToken:a.welcome.resumeToken},before=a.progress();
 for(const p of peers)p.socket.terminate();await service.close();service=null;
 service=await startLocalMvp({port:0,maxPlayers:4,dataDir:directory});
 const resumed=await connect('mvp-check-a',identity);
 assert(resumed.welcome.restored);assert.equal(resumed.welcome.character.xp,before.xp);
 assert.equal(resumed.welcome.character.gold,before.gold);assert.equal(resumed.welcome.character.equipment.chest,'linenArmor');
 assert.equal(resumed.welcome.character.inventory.wolfPelt,1);
 const saved=JSON.parse(readFileSync(service.saveFile,'utf8'));assert.equal(saved.characters.length,4);
 console.log(JSON.stringify({singlePlayerEntry:true,twoPlayerDemonstration:true,fourConnections:true,configuredRoomLimit:true,originalPhysics:true,cooperativeKill:true,rewardBoth:true,lootOnce:true,equipmentBroadcast:true,restartAndRecover:true,saveLock:true}));
}finally{
 for(const p of peers)p.socket.terminate();if(service)await service.close();rmSync(directory,{recursive:true,force:true});
}
