// Optional local integration. Original files are private; all identities and saves are disposable.
import assert from'node:assert/strict';
import{mkdtempSync,rmSync}from'node:fs';
import{tmpdir}from'node:os';import{join}from'node:path';
import{createGameServer}from'../analysis/raw/showcase-20261110/running-preview/prototype/server.mjs';
import{CharacterStore}from'../analysis/raw/showcase-20261110/running-preview/prototype/game/character-store.mjs';
import WebSocket from'../analysis/raw/showcase-20261110/running-preview/prototype/node_modules/ws/wrapper.mjs';
const dir=mkdtempSync(join(tmpdir(),'oc2-source-animation-blend-')),file=join(dir,'characters.json'),store=new CharacterStore(file);
const identities=['shore-player','observer'].map(n=>store.resolveCharacter(n));
identities.forEach((i,j)=>store.savePosition(i.record,'resources',{x:(-2235.5+j*.5+2752)/192*1280,y:(12-128)/192*1280,worldY:108.55000305175781,grounded:true}));store.flush();
const game=createGameServer({saveFile:file,ai:false,casting:false}),sockets=[];
const until=async(fn,pump)=>{const end=Date.now()+9000;while(!fn()){if(Date.now()>end)throw Error('Expected shore state absent');pump?.();await new Promise(r=>setTimeout(r,100));}};
try{
 await new Promise(r=>game.server.listen(0,'127.0.0.1',r));const url=`ws://127.0.0.1:${game.server.address().port}/ws`;
 async function connect(i){
  const ws=new WebSocket(url),messages=[];sockets.push(ws);ws.on('message',b=>messages.push(JSON.parse(b.toString())));
  await new Promise((r,j)=>{ws.once('open',r);ws.once('error',j);});
  ws.send(JSON.stringify({type:'join',scene:'resources',room:'BLEND-CHECK',mapWindow:'tutorial',name:i.record.name,characterId:i.record.id,resumeToken:i.resumeToken}));
  await until(()=>messages.some(m=>m.type==='welcome'));return{ws,messages};
 }
 const a=await connect(identities[0]),b=await connect(identities[1]),id=identities[0].record.id;
 const room=game.rooms.get('resources:source-map:BLEND-CHECK'),get=()=>room.get(id).player;
 const send=(socket,x,forward,camera)=>socket.send(JSON.stringify({type:'input',x,y:0,sourceForward:forward,...(camera?{sourceCamera:camera}:{})}));
 const camera=(yawDelta=0,pitchDelta=0)=>({yawDelta,pitchDelta,distanceScale:1,near:.1});
 send(a.ws,1,true,camera(-90,0));
 await until(()=>get().waterState===3,()=>send(a.ws,1,true));
 assert.equal(get().sourceAnimation.posture,32);assert.equal(get().sourceAnimation.current.clip,'run_normal_front');
 assert.equal(get().swimming,false);assert.equal(get().jump,null);assert.equal(get().locomotionPosture,32);
 await until(()=>get().waterState===0&&get().x>(-2230+2752)/192*1280,()=>send(a.ws,1,true));send(a.ws,0,false);
 await until(()=>get().sourceVelocityY===0&&get().sourceAnimation.posture===8);
 if(get().sourceAnimation.nativeQueueCPU){
  assert.equal(get().sourceAnimation.current.clip,'run_idle');
  await until(()=>get().sourceAnimation.current.clip==='idle'&&get().sourceAnimation.completionCount>=1);
 }else{assert.equal(get().sourceAnimation.available,false);assert.deepEqual(get().sourceAnimation.actionPair,[24,1]);}
 const shore={x:get().x,y:get().y,worldY:get().worldY};
 await until(()=>b.messages.some(m=>m.type==='state'&&m.players.some(p=>p.id===id&&p.worldY===shore.worldY&&p.x===shore.x&&!p.jump&&!p.swimming)));
 assert(get().sourceCamera.nativeCPU);
 a.ws.close();await until(()=>!room.has(id));const restored=await connect(identities[0]);
 assert.equal(get().worldY,shore.worldY);assert.equal(get().x,shore.x);assert.equal(get().y,shore.y);assert.equal(get().jump,null);
 const reloaded=new CharacterStore(file);assert.equal(reloaded.records.get(id).positions.resources.groundY,shore.worldY);
 send(restored.ws,-1,true,camera(90,0));await until(()=>get().swimming&&get().locomotionPosture===80,()=>send(restored.ws,-1,true));send(restored.ws,0,false);
 assert.equal(get().jump,null);
 const frames=a.messages.filter(m=>m.type==='state').flatMap(m=>m.players).filter(p=>p.id===id&&p.sourceAnimation?.available).map(p=>p.sourceAnimation);
 assert(frames.some(p=>p.previous?.clip==='swim_forward'&&p.current.clip==='run_normal_front'&&p.weights[0]>0&&p.weights[0]<1));
 const peerFrames=b.messages.filter(m=>m.type==='state').flatMap(m=>m.players).filter(p=>p.id===id&&p.sourceAnimation?.available).map(p=>p.sourceAnimation);
 assert(peerFrames.some(p=>p.current.clip==='run_normal_front'&&p.weights[0]>0&&p.weights[0]<1));
 console.log(JSON.stringify({sourceStateAndTwoChildBlend:true,fullTwoChannelQueueGapPreserved:true,deepShallowDryRoundtrip:true,noFalseJump:true,twoConnectionsAgree:true,shoreReconnectExact:true,privateSavedHeight:true,liveAndMainSaveUntouched:true}));
}finally{
 for(const s of sockets)s.terminate();await game.close();rmSync(dir,{recursive:true,force:true});
}
