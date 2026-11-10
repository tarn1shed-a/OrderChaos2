// Requires the ignored inspection runtime. Uses memory-only characters and an
// ephemeral loopback listener; never connects to the user's or friend's DB.
import assert from'node:assert/strict';
import {createGameServer}from'../analysis/raw/showcase-20261110/running-preview/prototype/server.mjs';
import WebSocket from'../analysis/raw/showcase-20261110/running-preview/prototype/node_modules/ws/wrapper.mjs';
const game=createGameServer({ai:false,casting:false}),sockets=[];
try{
  await new Promise(r=>game.server.listen(0,'127.0.0.1',r));const url=`ws://127.0.0.1:${game.server.address().port}/ws`;
  async function join(name,mapWindow){
    const ws=new WebSocket(url);sockets.push(ws);const received=[];
    ws.on('message',b=>received.push(JSON.parse(b.toString())));
    await new Promise((r,j)=>{ws.once('open',r);ws.once('error',j);});
    ws.send(JSON.stringify({type:'join',scene:'resources',name,room:'ISOLATE-01',...(mapWindow?{mapWindow:'tutorial'}:{})}));
    await until(()=>received.some(v=>v.type==='welcome'));return {ws,received,welcome:received.find(v=>v.type==='welcome')};
  }
  async function until(check){const end=Date.now()+3000;while(!check()){if(Date.now()>end)throw Error('No expected local snapshot');await new Promise(r=>setTimeout(r,20));}}
  const a=await join('window-a',true),b=await join('window-b',true),old=await join('old-frame',false);
  assert(a.welcome.world.bounds.minX<0);assert(a.welcome.world.bounds.maxX>1280);assert(!old.welcome.world.bounds);
  assert.equal(game.combatRooms.get('resources:source-map:ISOLATE-01').motion.profile.instances.length,217);
  assert.equal(game.combatRooms.get('resources:ISOLATE-01').motion.profile.instances.length,39);
  const room=game.rooms.get('resources:source-map:ISOLATE-01'),serverA=room.get(a.welcome.id),before=serverA.player.x;
  a.ws.send(JSON.stringify({type:'jump',pressed:true}));
  if(serverA.motion.sourceNative){
    await until(()=>!serverA.player.grounded);a.ws.send(JSON.stringify({type:'jump',pressed:false}));
    await until(()=>serverA.player.grounded);
  }else{
    await until(()=>a.received.some(v=>v.type==='notice'&&v.message.includes('尚未恢复腾空')));
    assert.equal(serverA.player.jump,null);
  }
  a.ws.send(JSON.stringify({type:'input',x:1,y:0}));await until(()=>serverA.player.x>before+1);
  a.ws.send(JSON.stringify({type:'input',x:0,y:0}));
  await until(()=>b.received.some(v=>v.type==='state'&&v.players?.some(p=>p.id===a.welcome.id&&p.x>before+1)));
  assert(!old.received.some(v=>v.players?.some(p=>p.id===a.welcome.id)));
  console.log(JSON.stringify({roomIsolation:true,twoConnectionMovement:true,oldCoordinateFramePreserved:true,originalAirborne:Boolean(serverA.motion.sourceNative),sourceInstances:217}));
}finally{for(const ws of sockets)ws.terminate();await game.close();}
