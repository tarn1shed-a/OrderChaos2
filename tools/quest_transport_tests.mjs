import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {createHash} from 'node:crypto';
import {questContext,installQuestTransport} from '../deploy/quest_transport.mjs';

const id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',token='12'.repeat(32);
function fixture(){
  const role={id,level:1,hp:100,tokenHash:createHash('sha256').update(token).digest('hex')};
  const ws={character:role,player:{x:1,y:2,worldY:3,hp:100},ordinaryQuestMap:1,motion:{point:(x,y)=>({x:x+10,z:y+20})}};
  return {role,ws,store:{records:new Map([[id,role]])},active:new Map([[id,ws]])};
}
test('only authenticated active role and authoritative scene position enter the task layer',()=>{
  const f=fixture();const actual=questContext(f.store,f.active,{characterId:id,resumeToken:token,level:100,position:[0,0,0]},1);
  assert.deepEqual(actual,{characterId:id,mapId:1,level:1,position:[11,3,22],alive:true,inspector:false});
  assert.throws(()=>questContext(f.store,f.active,{characterId:id,resumeToken:'00'.repeat(32)},1),/凭据无效/);
  f.ws.ordinaryQuestMap=5;assert.throws(()=>questContext(f.store,f.active,{characterId:id,resumeToken:token},1),/任务地图/);
  f.active.clear();assert.throws(()=>questContext(f.store,f.active,{characterId:id,resumeToken:token},1),/任务地图/);
});
test('HTTP routes enforce origin/size/auth and do not leak private credentials',async()=>{
  const f=fixture(),calls=[];
  const server=http.createServer((req,res)=>{res.writeHead(200);res.end('base');});
  const ledger={profile:{mapId:1},snapshot:characterId=>({quests:[],characterId}),query:(ctx,questId)=>({questId,level:ctx.level}),act:(ctx,command)=>{calls.push({ctx,command});return {revision:1};}};
  installQuestTransport(server,{ledger,store:f.store,active:f.active});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url='http://127.0.0.1:'+server.address().port,identity={characterId:id,resumeToken:token};
  const post=(path,body,origin=url)=>fetch(url+path,{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify(body)});
  try{
    assert.equal(await(await fetch(url+'/base')).text(),'base');
    assert.equal((await fetch(url+'/__quests/state')).status,405);
    assert.equal((await post('/__quests/state',{identity},'https://elsewhere.test')).status,403);
    assert.equal((await post('/__quests/state',{identity:{characterId:id,resumeToken:'00'.repeat(32)}})).status,400);
    assert.equal((await post('/__quests/state',{identity,junk:'x'.repeat(4096)})).status,413);
    const query=await post('/__quests/query',{identity,questId:1,position:[0,0,0],level:99});
    const raw=await query.text();assert.equal(query.status,200);assert.equal(raw.includes(token),false);assert.equal(JSON.parse(raw).info.level,1);
    const action=await post('/__quests/action',{identity,command:{questId:1,revision:0,type:'accept'}});
    assert.equal(action.status,200);assert.deepEqual(calls[0].ctx.position,[11,3,22]);
    assert.equal(calls[0].ctx.level,1);
  }finally{await new Promise(resolve=>server.close(resolve));}
});
test('optional channel routes use the active connection and block direct collection bypass',async()=>{
  const f=fixture(),calls=[];
  const ledger={profile:{mapId:1},snapshot:()=>({revision:0}),act:()=>{throw Error('direct ledger called');}};
  const collection={questId:461,
    begin:(ctx,owner,command)=>{calls.push({ctx,owner,command});return {id:'fixture-channel'};},
    finish:(ctx,owner,id)=>{calls.push({ctx,owner,id});return {pending:true,retryAfterMs:5};},
    cancel:(ctx,owner,id)=>{calls.push({ctx,owner,id});return {revision:0};}};
  const server=http.createServer();installQuestTransport(server,{ledger,store:f.store,active:f.active,collection});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const url='http://127.0.0.1:'+server.address().port;
  const post=command=>fetch(url+'/__quests/action',{method:'POST',headers:{'Content-Type':'application/json',Origin:url},
    body:JSON.stringify({identity:{characterId:id,resumeToken:token},command,position:[0,0,0]})});
  try{
    const start=await post({type:'collect-start',questId:461,revision:0,objectId:'object:1'});
    assert.equal(start.status,200);assert.equal((await start.json()).channel.id,'fixture-channel');
    assert.equal(calls[0].owner,f.ws);assert.deepEqual(calls[0].ctx.position,[11,3,22]);
    assert.equal((await post({type:'collect',questId:461,revision:0})).status,400);
    const finish=await post({type:'collect-finish',channelId:'fixture-channel'});
    assert.deepEqual(await finish.json(),{pending:true,retryAfterMs:5});
    f.active.set(id,{...f.ws});await post({type:'collect-cancel',channelId:'fixture-channel'});
    assert.notEqual(calls.at(-1).owner,f.ws);
    f.active.clear();assert.equal((await post({type:'collect-finish',channelId:'fixture-channel'})).status,400);
  }finally{await new Promise(resolve=>server.close(resolve));}
});
