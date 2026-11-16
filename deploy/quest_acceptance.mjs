// Explicitly disposable Linux integration: real HTTP, two WS clients and the
// original native walking worker. Never loads or imports an existing save.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {setTimeout as delay} from 'node:timers/promises';
import WebSocket from 'ws';
if(process.env.OC2_DISPOSABLE_QUEST_QA!=='1')throw Error('Explicit isolated QA container required');
const phase=process.argv[2]||'initial';assert.ok(['initial','restore'].includes(phase));
const origin='http://127.0.0.1:'+Number(process.env.PORT||8080),folder='/data/qa',file=folder+'/quest-channel-acceptance.json';
const profile=await(await fetch(origin+'/assets/ordinary-quests/profile.json')).json(),task=profile.quests.find(q=>q.id===461);
const manifest=await(await fetch(origin+'/assets/source-ordinary-quest-map1/manifest.json')).json();
const terrain=await(await fetch(origin+manifest.terrain)).json(),peers=[];
const report={phase,compatibleQuestId:461,originalServerRecovered:false,existingSavesImported:false,walks:[],checks:[]};
const until=async(check,label,ms=20000)=>{const end=Date.now()+ms;while(Date.now()<end){const v=check();if(v)return v;await delay(25);}throw Error('Timeout: '+label);};
async function post(path,body,{expect=200}={}){const r=await fetch(origin+path,{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await r.json();assert.equal(r.status,expect,v.error||path);return v;}
async function create(name,profession){const v=await post('/__entry/create',{name,profession,race:2,gender:1});return {name,profession,characterId:v.character.id,resumeToken:v.resumeToken};}
async function connect(identity){
 const ws=new WebSocket(origin.replace(/^http/,'ws')+'/ws',{origin}),client={ws,identity,messages:[],packets:new Map(),closed:false};peers.push(client);
 client.send=m=>ws.send(JSON.stringify(m));
 ws.on('message',raw=>{const m=JSON.parse(raw);client.messages.push(m);if(m.type==='welcome')client.welcome=m;if(m.type==='state'){client.state=m;client.player=m.players.find(p=>p.id===identity.characterId);if(m.questGather)client.packets.set(m.questGather.tick,m.questGather);}});
 ws.on('error',()=>{});await new Promise((ok,fail)=>{ws.once('open',ok);ws.once('error',fail);});
 client.send({type:'join',scene:'resources',mapWindow:'heaven-landing',room:'CHANNEL-WIRE-QA',...identity});
 await until(()=>client.welcome||client.messages.some(m=>m.type==='error'),'welcome');assert.ok(client.welcome,client.messages.find(m=>m.type==='error')?.message);
 await until(()=>client.player,'authoritative player');return client;
}
const source=c=>[terrain.bounds.min[0]+c.player.x/c.welcome.world.width*(terrain.bounds.max[0]-terrain.bounds.min[0]),c.player.worldY,terrain.bounds.min[2]+c.player.y/c.welcome.world.height*(terrain.bounds.max[2]-terrain.bounds.min[2])];
async function walk(c,target,range){
 const begin=source(c),start=Date.now();let previous=Infinity,stalled=0;
 while(Date.now()-start<45000){
  const p=source(c),dx=target[0]-p[0],dz=target[2]-p[2],d=Math.hypot(dx,dz);
  if(d<range){c.send({type:'input',x:0,y:0});await delay(150);report.walks.push({from:begin,to:source(c),target,durationMs:Date.now()-start});return;}
  stalled=d>=previous-.02?stalled+1:0;previous=d;
  if(stalled>25){const sign=report.walks.length%2?1:-1;c.send({type:'input',x:-dz/d*sign,y:dx/d*sign});await delay(700);stalled=0;}
  else{c.send({type:'input',x:dx/d,y:dz/d});await delay(70);}
 }
 c.send({type:'input',x:0,y:0});throw Error('Original collision walk did not reach '+JSON.stringify(target)+'; last '+JSON.stringify(source(c)));
}
const state=c=>post('/__quests/state',{identity:c.identity}).then(v=>v.state);
const query=c=>post('/__quests/query',{identity:c.identity,questId:461}).then(v=>v.info);
const action=(c,command,expect=200)=>post('/__quests/action',{identity:c.identity,command},{expect});
const operations=(c,actor,scope)=>[...c.packets.values()].flatMap(p=>p.records).filter(r=>r.kind==='event'&&r.event.actorKey===actor&&(!scope||r.event.scope===scope)).map(r=>r.event);
async function begin(c,object){const before=await state(c);return (await action(c,{type:'collect-start',questId:461,revision:before.revision,objectId:object.id})).channel;}
try{
 if(phase==='initial'){
  mkdirSync(folder,{recursive:true});const suffix=Date.now().toString(36).slice(-4);
  const a=await connect(await create('采集联验甲'+suffix,2)),b=await connect(await create('采集联验乙'+suffix,3));
  await until(()=>a.state.players.length===2&&b.state.players.length===2,'two same-room connections');
  await action(a,{type:'accept',questId:461,revision:(await state(a)).revision});assert.equal((await query(a)).Status,4);assert.equal((await query(b)).Status,6);
  const objects=[...profile.objects].sort((x,y)=>Math.hypot(x.position[0]-profile.actors[0].position[0],x.position[2]-profile.actors[0].position[2])-Math.hypot(y.position[0]-profile.actors[0].position[0],y.position[2]-profile.actors[0].position[2])).slice(0,4);
  for(const[index,object]of objects.entries()){
   await walk(a,object.position,object.range*.6);await until(()=>a.player.grounded===true,'grounded at object');
   if(index===0){
    const cancelled=await begin(a,object),unchanged=await state(a);
    await action(a,{type:'collect-cancel',channelId:'wrong-scope'});await delay(100);
    assert.ok(!operations(b,a.identity.characterId,cancelled.id).some(e=>e.operation==='interrupt'));
    await action(a,{type:'collect-cancel',channelId:cancelled.id});
    await until(()=>operations(b,a.identity.characterId,cancelled.id).some(e=>e.operation==='interrupt'),'peer matching interrupt');
    await action(a,{type:'collect-finish',channelId:cancelled.id},400);assert.deepEqual(await state(a),unchanged);report.checks.push('wrong-cancel-does-not-interrupt; matching-cancel-has-no-item');
   }
   const channel=await begin(a,object),before=await state(a);
   assert.equal(channel.skillChannelTime,1500);
   const pending=await action(a,{type:'collect-finish',channelId:channel.id});assert.equal(pending.pending,true);assert.deepEqual(await state(a),before);
   await until(()=>operations(b,a.identity.characterId,channel.id).some(e=>e.operation==='begin'),'peer source begin');
   const replay=await post('/__quests/presentation',{identity:b.identity,roomKey:'foreign-room'});assert.equal(replay.presentation.roomKey,'resources:ordinary-map:CHANNEL-WIRE-QA');
   await delay(channel.skillChannelTime);
   const finish=await action(a,{type:'collect-finish',channelId:channel.id});assert.equal(finish.pending,false);
   await until(()=>operations(b,a.identity.characterId,channel.id).some(e=>e.operation==='success'),'peer source success');
   await until(()=>operations(b,a.identity.characterId,channel.id).some(e=>e.operation==='release'),'original source settlement release');
   await action(a,{type:'collect-finish',channelId:channel.id},400);
   assert.deepEqual(await state(a),finish.state);console.log(JSON.stringify({collected:object.id,count:index+1,realSourceWalk:true,sourcePresentation:true}));
  }
  assert.equal((await query(a)).Status,9);assert.equal((await query(b)).Status,6);
  const shared=[...a.packets.keys()].filter(t=>b.packets.has(t));assert.ok(shared.length>20);for(const t of shared)assert.deepEqual(a.packets.get(t),b.packets.get(t));
  report.checks.push('four-timed-collections; early-and-repeat-finish-rejected','self-and-peer-receive-identical-authoritative-events','other-role-task-stays-unaccepted');
  await walk(a,profile.actors[0].position,profile.actors[0].range*.6);
  const complete=await action(a,{type:'complete',questId:461,revision:(await state(a)).revision});
  assert.deepEqual(complete.state.rewards,{xp:task.reward.xp,money:task.reward.money,favor:task.reward.favor,items:Object.fromEntries(task.reward.items.map(r=>[String(r.id),r.count]))});
  assert.deepEqual(complete.state.inventory,{});await action(a,{type:'complete',questId:461,revision:complete.state.revision},400);assert.deepEqual(await state(a),complete.state);
  report.checks.push('original-row-reward-once; returned-items-consumed');
  writeFileSync(file,JSON.stringify({identities:[a.identity,b.identity],state:complete.state,position:source(a)},null,2),{mode:0o600,flag:'wx'});
 }else{
  const saved=JSON.parse(readFileSync(file,'utf8')),a=await connect(saved.identities[0]),b=await connect(saved.identities[1]);
  assert.equal((await query(a)).Status,0);assert.equal((await query(b)).Status,6);assert.deepEqual(await state(a),saved.state);
  assert.ok(source(a).every((v,i)=>Math.abs(v-saved.position[i])<.02));report.checks.push('disk-restart-restores-position-and-once-only-task-rewards');
 }
 report.pass=true;
}catch(error){report.pass=false;report.error=error.stack;throw error;}
finally{
 for(const c of peers)c.ws.close();await delay(300);for(const c of peers)c.ws.terminate();
 mkdirSync(folder,{recursive:true});writeFileSync(folder+'/quest-channel-'+phase+'-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
}
