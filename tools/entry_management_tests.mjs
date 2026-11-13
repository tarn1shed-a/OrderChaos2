import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {trialRoleManager,installEntryManagement,entryServer} from '../deploy/entry_manage.mjs';
import {entryNameError} from '../deploy/entry_name.mjs';
import http from 'node:http';
const token='a'.repeat(64),otherToken='b'.repeat(64),hash=x=>createHash('sha256').update(x).digest('hex');
const id='00000000-0000-0000-0000-000000000001',otherID='00000000-0000-0000-0000-000000000002';
function fixture(){
 const own={id,name:'精灵甲',tokenHash:hash(token),positions:{resources:{x:17,y:30,groundY:172}},inventory:{special:4}};
 const other={id:otherID,name:'精灵乙',tokenHash:hash(otherToken),positions:{resources:{x:91,y:80,groundY:132}},inventory:{special:99}};
 let flushes=0;const store={records:new Map([[id,own],[otherID,other]]),dirty:false,savedAt:123,flush(){flushes++;this.dirty=false;this.savedAt=456;}};
 return {store,active:new Map(),own,other,flushes:()=>flushes};
}
const identity={characterId:id,resumeToken:token};
test('delete requires ownership, original four-digit confirmation, and an offline role; only selected record changes',()=>{
 const f=fixture(),before=structuredClone(f.other),archived=[],m=trialRoleManager(f.store,f.active,{archive:r=>archived.push(r)});
 assert.throws(()=>m.challenge({...identity,resumeToken:otherToken}));assert.equal(f.flushes(),0);
 f.active.set(id,{});assert.throws(()=>m.challenge(identity),/在线/);f.active.clear();
 const p=m.challenge(identity);assert.match(p.code,/^[1-8][0-9]{3}$/);
 assert.throws(()=>m.remove({...identity,...p,code:''}));assert.throws(()=>m.remove({...identity,...p,code:p.code==='1000'?'1001':'1000'}));
 assert.throws(()=>m.remove({characterId:otherID,resumeToken:otherToken,...p}));assert.equal(f.flushes(),0);
 assert.deepEqual(m.remove({...identity,...p}),{deleted:id});assert.equal(f.flushes(),1);
 assert(!f.store.records.has(id));assert.deepEqual(f.store.records.get(otherID),before);assert.deepEqual(archived,[f.own]);
 assert.throws(()=>m.remove({...identity,...p}));
});
test('expired/online confirmations and failed archives or persistence never remove a role',()=>{
 for(const fail of ['expired','online','archive','flush']){
  const f=fixture(),before=[...f.store.records],oldTime=f.store.savedAt;let now=10;
  const m=trialRoleManager(f.store,f.active,{now:()=>now,archive:()=>{if(fail==='archive')throw Error('archive fail');}}),p=m.challenge(identity);
  if(fail==='expired')now+=600001;if(fail==='online')f.active.set(id,{});if(fail==='flush')f.store.flush=()=>{throw Error('disk fail');};
  assert.throws(()=>m.remove({...identity,...p}));assert.deepEqual([...f.store.records],before);assert.equal(f.store.dirty,false);assert.equal(f.store.savedAt,oldTime);
 }
});
test('creation refuses an unsupported avatar and rolls back a failed write without moving existing records',()=>{
 const f=fixture(),before=structuredClone([...f.store.records]),m=trialRoleManager(f.store,f.active,{archive:()=>{}});
 assert.throws(()=>m.create({name:'精灵丙',race:0,gender:1,profession:2}),/尚未接入/);
 f.store.resolveCharacter=()=>{f.store.records.set('new',{name:'failed'});f.store.dirty=true;throw Error('disk fail');};
 assert.throws(()=>m.create({name:'精灵丙',race:2,gender:1,profession:2}),/disk fail/);assert.deepEqual([...f.store.records],before);assert.equal(f.store.dirty,false);
});
test('name checks retain source-visible boundaries without claiming an original account approval',()=>{
 assert.equal(entryNameError('精灵甲'),null);assert.equal(entryNameError('abc'),null);
 assert.equal(entryNameError('ab'),'GENERAL_ERROR_CREATION_NAME_LESS');assert.equal(entryNameError('精灵'),null);assert.equal(entryNameError('精灵甲乙丙丁'),null);assert.equal(entryNameError('一二三四五六七八'),'GENERAL_CH_SELEC_45');
 assert.equal(entryNameError('abc def'),'GENERAL_ERROR_GUILD_NAME_ILLEGAL');assert.equal(entryNameError('123'),'GENERAL_ERROR_CREATION_ENTER_NAME_NUMBER');
});
test('management HTTP mutations reject cross-origin, missing origin, GET and oversized requests',async()=>{
 const f=fixture(),m=trialRoleManager(f.store,f.active,{archive:()=>{}}),server=http.createServer((req,res)=>res.end('base'));
 installEntryManagement(server,m);await new Promise(ok=>server.listen(0,'127.0.0.1',ok));const url='http://127.0.0.1:'+server.address().port;
 const options={method:'POST',headers:{'Content-Type':'application/json',origin:url},body:JSON.stringify(identity)};
 try{
  assert.equal((await fetch(url+'/__entry/delete')).status,405);
  assert.equal((await fetch(url+'/__entry/delete',{...options,headers:{'Content-Type':'application/json'}})).status,403);
  assert.equal((await fetch(url+'/__entry/delete',{...options,headers:{...options.headers,origin:'https://outside.invalid'}})).status,403);
  assert.equal((await fetch(url+'/__entry/delete',{...options,body:'x'.repeat(4097)})).status,413);
  const p=await(await fetch(url+'/__entry/delete-challenge',options)).json();
  const response=await fetch(url+'/__entry/delete',{...options,body:JSON.stringify({...identity,...p})});assert.equal(response.status,200);assert.equal(response.headers.get('cache-control'),'no-store');
 }finally{await new Promise(ok=>server.close(ok));}
});
test('store adapter refuses an unreviewed runtime',()=>assert.throws(()=>entryServer('unknown','file:///trace.mjs'),/identity differs/));
