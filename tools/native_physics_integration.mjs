// Local optional integration: private original files are not CI inputs.
// Uses disposable characters, its own save and an ephemeral loopback listener.
import assert from'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync}from'node:fs';
import {tmpdir}from'node:os';import{join as pathJoin}from'node:path';
import {createGameServer}from'../analysis/raw/showcase-20261110/running-preview/prototype/server.mjs';
import {CharacterStore}from'../analysis/raw/showcase-20261110/running-preview/prototype/game/character-store.mjs';
import WebSocket from'../analysis/raw/showcase-20261110/running-preview/prototype/node_modules/ws/wrapper.mjs';
const temp=mkdtempSync(pathJoin(tmpdir(),'oc2-native-physics-')),saveFile=pathJoin(temp,'characters.json');
const store=new CharacterStore(saveFile),identities=Array.from({length:3},(_,i)=>store.resolveCharacter('native-'+i));
for(const i of identities)store.savePosition(i.record,'resources',{x:1460,y:500,worldY:136.53165});store.flush();
const game=createGameServer({saveFile,ai:false,casting:false}),sockets=[];
const config=JSON.parse(readFileSync(new URL('../analysis/raw/showcase-20261110/running-preview/prototype/native-physics.json',import.meta.url),'utf8'));
const sourceCount=JSON.parse(readFileSync(config.collision,'utf8')).instances.length;
const until=async check=>{const end=Date.now()+5000;while(!check()){if(Date.now()>end)throw Error('Expected native-physics snapshot absent');await new Promise(r=>setTimeout(r,15));}};
let savedPosition;
try{
  await new Promise(r=>game.server.listen(0,'127.0.0.1',r));const url=`ws://127.0.0.1:${game.server.address().port}/ws`;
  async function connect(i,mapWindow=true){
    const ws=new WebSocket(url);sockets.push(ws);const messages=[];
    ws.on('message',b=>messages.push(JSON.parse(b.toString())));await new Promise((r,j)=>{ws.once('open',r);ws.once('error',j);});
    ws.send(JSON.stringify({type:'join',scene:'resources',room:'PHYSICS-01',name:i.record.name,characterId:i.record.id,resumeToken:i.resumeToken,...(mapWindow?{mapWindow:'tutorial'}:{})}));
    await until(()=>messages.some(m=>m.type==='welcome'));return {ws,messages,welcome:messages.find(m=>m.type==='welcome')};
  }
  const a=await connect(identities[0]),b=await connect(identities[1]),old=await connect(identities[2],false);
  const room=game.rooms.get('resources:source-map:PHYSICS-01'),actor=room.get(a.welcome.id).player;
  assert.equal(game.combatRooms.get('resources:source-map:PHYSICS-01').motion.profile.instances.length,sourceCount);
  assert.equal(game.combatRooms.get('resources:PHYSICS-01').motion.profile.instances.length,39);
  const y=actor.worldY;a.ws.send(JSON.stringify({type:'jump',pressed:true}));
  await until(()=>b.messages.some(m=>m.type==='state'&&m.players.some(p=>p.id===actor.id&&!p.grounded&&p.worldY>y+.5)));
  assert(actor.jump);assert.equal(actor.jump.stationaryAvailable,false);
  a.ws.send(JSON.stringify({type:'jump',pressed:false}));await until(()=>actor.grounded);
  assert(Math.abs(actor.worldY-y)<.001);assert.equal(actor.sourcePosture,0x38);
  a.ws.send(JSON.stringify({type:'input',x:.5,y:0}));await until(()=>actor.x>1461);
  a.ws.send(JSON.stringify({type:'input',x:0,y:0}));
  await until(()=>b.messages.some(m=>m.type==='state'&&m.players.some(p=>p.id===actor.id&&p.x>1461)));
  assert(!old.messages.some(m=>m.players?.some(p=>p.id===actor.id)));
  savedPosition={x:actor.x,y:actor.y,worldY:actor.worldY};a.ws.close();await until(()=>!room.has(actor.id));
  const rejoined=await connect(identities[0]);const restored=room.get(rejoined.welcome.id).player;
  assert(Math.abs(restored.worldY-savedPosition.worldY)<.001);assert(Math.abs(restored.x-savedPosition.x)<.001);
  console.log(JSON.stringify({originalStaticPhysics:true,twoConnectionJumpAndLanding:true,reconnectBridgeHeight:true,oldRoomIsolated:true,privateMainSaveUntouched:true}));
}finally{
  for(const s of sockets)s.terminate();await game.close();
  const saved=JSON.parse(readFileSync(saveFile,'utf8')).characters.find(c=>c.id===identities[0].record.id);
  if(savedPosition)assert(Math.abs(saved.positions.resources.groundY-savedPosition.worldY)<.001);
  rmSync(temp,{recursive:true,force:true});
}
