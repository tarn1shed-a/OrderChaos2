import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Run the actual client API body without importing its private WebGL assets.
// The deferred HTTP boundary models replies arriving during a role switch.
const source=readFileSync(new URL('../deploy/quest_world.mjs',import.meta.url),'utf8');
const start=source.indexOf('async function api('),end=source.indexOf('\nfunction applyQuestState',start);
assert.ok(start>=0&&end>start);
const body=source.slice(start,end);
function client(){
 let finish;const applied=[],requests=[];
 const ctx={identity:{characterId:'role-A',resumeToken:'A'},generation:1,connected:true,
  applyQuestState:v=>applied.push(v),
  fetch:(url,options)=>{requests.push({url,data:JSON.parse(options.body)});return new Promise(resolve=>finish=resolve);}};
 const api=vm.runInNewContext(body+'\napi',ctx);
 return {ctx,api,applied,requests,reply:(value,ok=true)=>finish({ok,json:async()=>value})};
}

test('late role-A details cannot be returned or applied to role-B',async()=>{
 const c=client(),pending=c.api('query',{questId:461});
 assert.equal(c.requests[0].data.identity.characterId,'role-A');
 c.ctx.identity={characterId:'role-B',resumeToken:'B'};c.ctx.generation++;
 c.reply({info:{role:'role-A',Status:4},state:{role:'role-A'}});
 await assert.rejects(pending,/角色连接已变更/);assert.deepEqual(c.applied,[]);
});

test('reconnecting the same role and a disconnected session also invalidate in-flight details',async()=>{
 for(const change of [c=>c.generation++,c=>c.connected=false]){
  const c=client(),pending=c.api('query',{questId:461});change(c.ctx);
  c.reply({info:{Status:4},state:{revision:2}});
  await assert.rejects(pending,/角色连接已变更/);assert.deepEqual(c.applied,[]);
 }
});

test('a stale server error does not escape as the new role response',async()=>{
 const c=client(),pending=c.api('action',{command:{type:'complete'}});
 c.ctx.identity={characterId:'role-B',resumeToken:'B'};c.ctx.generation++;
 c.reply({error:'old-role-rejection'},false);
 await assert.rejects(pending,/角色连接已变更/);assert.deepEqual(c.applied,[]);
});

test('current-session details and state remain available and server errors still reject',async()=>{
 const c=client(),value={info:{Status:4},state:{revision:3}},pending=c.api('query',{questId:461});
 c.reply(value);assert.equal(await pending,value);assert.equal(c.applied[0],value.state);
 const denied=c.api('action');c.reply({error:'current-role-rejection'},false);
 await assert.rejects(denied,/current-role-rejection/);assert.equal(c.applied.length,1);
});
