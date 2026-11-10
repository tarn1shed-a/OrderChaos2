// Optional local integration. Original files are private; all identities and saves are disposable.
import assert from'node:assert/strict';
import{mkdtempSync,readFileSync,rmSync}from'node:fs';
import{tmpdir}from'node:os';import{join}from'node:path';
import{createGameServer}from'../analysis/raw/showcase-20261110/running-preview/prototype/server.mjs';
import{CharacterStore}from'../analysis/raw/showcase-20261110/running-preview/prototype/game/character-store.mjs';
import WebSocket from'../analysis/raw/showcase-20261110/running-preview/prototype/node_modules/ws/wrapper.mjs';
const dir=mkdtempSync(join(tmpdir(),'oc2-source-diving-')),file=join(dir,'characters.json'),store=new CharacterStore(file);
const identities=['diver','observer'].map(n=>store.resolveCharacter(n));
identities.forEach((i,j)=>store.savePosition(i.record,'resources',{x:(-2324+j*2+2752)/192*1280,y:-400,worldY:108.55000305175781,grounded:true}));store.flush();
const game=createGameServer({saveFile:file,ai:false,casting:false}),sockets=[];
const until=async(fn,pump)=>{const end=Date.now()+9000;while(!fn()){if(Date.now()>end)throw Error('Expected diving state absent');pump?.();await new Promise(r=>setTimeout(r,100));}};
try{
 await new Promise(r=>game.server.listen(0,'127.0.0.1',r));const url=`ws://127.0.0.1:${game.server.address().port}/ws`;
 async function connect(i){
  const ws=new WebSocket(url),messages=[];sockets.push(ws);ws.on('message',b=>messages.push(JSON.parse(b.toString())));
  await new Promise((r,j)=>{ws.once('open',r);ws.once('error',j);});
  ws.send(JSON.stringify({type:'join',scene:'resources',room:'DIVE-CHECK',mapWindow:'tutorial',name:i.record.name,characterId:i.record.id,resumeToken:i.resumeToken}));
  await until(()=>messages.some(m=>m.type==='welcome'));return{ws,messages};
 }
 const a=await connect(identities[0]),b=await connect(identities[1]),id=identities[0].record.id;
 const room=game.rooms.get('resources:source-map:DIVE-CHECK'),get=()=>room.get(id).player;
 const send=(socket,x,forward,camera)=>socket.send(JSON.stringify({type:'input',x,y:0,sourceForward:forward,...(camera?{sourceCamera:camera}:{})}));
 const camera=(yawDelta=0,pitchDelta=0)=>({yawDelta,pitchDelta,distanceScale:1,near:.1});
 send(a.ws,1,true,camera(-90,-40));await until(()=>get().submerged&&get().worldY<104,()=>send(a.ws,1,true));send(a.ws,0,false);
 await until(()=>get().sourceVelocityY===0);const under={x:get().x,y:get().y,worldY:get().worldY};
 await until(()=>b.messages.some(m=>m.type==='state'&&m.players.some(p=>p.id===id&&p.worldY===under.worldY&&p.submerged)));
 assert(get().sourceCamera.nativeCPU);await until(()=>get().sourceCamera.underwaterFlag);
 a.ws.close();await until(()=>!room.has(id));const restored=await connect(identities[0]);
 await until(()=>get().submerged);assert.equal(get().worldY,under.worldY);assert.equal(get().x,under.x);assert.equal(get().y,under.y);
 const reloaded=new CharacterStore(file);assert.equal(reloaded.records.get(id).positions.resources.groundY,under.worldY);
 send(restored.ws,-1,true,camera(90,45));await until(()=>!get().submerged&&get().worldY>108.5,()=>send(restored.ws,-1,true));send(restored.ws,0,false);
 await until(()=>get().sourceVelocityY===0&&!get().sourceCamera.underwaterFlag);assert.equal(get().sourceCamera.pitch,355);
 console.log(JSON.stringify({nativeDiveAndRise:true,twoConnectionsAgree:true,underwaterReconnectExact:true,privateSavedWaterHeight:true,originalCameraSurfaceReset:true,liveAndMainSaveUntouched:true}));
}finally{
 for(const s of sockets)s.terminate();await game.close();rmSync(dir,{recursive:true,force:true});
}
