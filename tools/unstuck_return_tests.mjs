import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createUnstuckReturn} from '../deploy/unstuck_return.mjs';

const ONLINE='角色仍在线，请关闭原游戏页后重试';
const session=()=>({characterId:'00000000-0000-0000-0000-000000000001',resumeToken:'a'.repeat(64),name:'运输夹具',room:'TEST-01',profession:3,epoch:1});
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
const success=id=>response({returned:id,anchor:'cinematic7',originalFirstSpawn:false});
const turn=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((ok,fail)=>{resolve=ok;reject=fail;});return {promise,resolve,reject};}
function fixture(overrides={}){
  const state={selected:session(),allowed:true,calls:[],requests:[],waits:[]};
  const options={captureSession:()=>state.selected,canReturn:()=>state.allowed,
    releaseSession:async snapshot=>{state.calls.push({method:'release',snapshot});},
    reconnect:async snapshot=>{state.calls.push({method:'reconnect',snapshot});},
    fetcher:async(url,options)=>{state.requests.push({url,options});return success(state.selected?.characterId??session().characterId);},
    wait:async milliseconds=>{state.waits.push(milliseconds);},...overrides};
  return {state,controller:createUnstuckReturn(options)};
}

test('waits for asynchronous close confirmation, freezes current identity, and blocks duplicate activation',async()=>{
  const close=deferred(),f=fixture({releaseSession:async snapshot=>{f.state.calls.push({method:'release',snapshot});await close.promise;}});
  const pending=f.controller.returnEntry();assert.equal(f.controller.busy,true);await turn();assert.equal(f.state.requests.length,0);
  assert.equal((await f.controller.returnEntry()).reason,'busy');assert(Object.isFrozen(f.state.calls[0].snapshot));
  close.resolve();const result=await pending;assert(result.ok);assert.equal(result.resetConfirmed,true);assert.equal(f.controller.busy,false);
  assert.deepEqual(f.state.calls.map(c=>c.method),['release','reconnect']);assert.equal(f.state.requests.length,1);
  const request=f.state.requests[0];assert.equal(request.url,'/__entry/return');assert.equal(request.options.method,'POST');assert.equal(request.options.credentials,'same-origin');
  assert.deepEqual(JSON.parse(request.options.body),{characterId:session().characterId,resumeToken:session().resumeToken,anchor:'cinematic7'});
  assert.deepEqual(f.state.calls[1].snapshot,session());assert.equal(result.reconnectRequested,true);
});

test('injected eligibility blocks without releasing, posting, inventing a cooldown or reconnecting',async()=>{
  const f=fixture();f.state.allowed=false;const r=await f.controller.returnEntry();assert.equal(r.reason,'blocked');assert.equal(f.state.calls.length,0);assert.equal(f.state.requests.length,0);assert.equal(f.controller.busy,false);
});

test('missing or malformed captured identity fails before any session or network mutation',async()=>{
  for(const change of [null,{characterId:'wrong'},{resumeToken:'x'},{room:'../x'},{profession:6},{epoch:null}]){
    const f=fixture();f.state.selected=change===null?null:{...session(),...change};const r=await f.controller.returnEntry();
    assert.equal(r.reason,'session-unavailable');assert.equal(f.state.calls.length,0);assert.equal(f.state.requests.length,0);
  }
});

test('only the exact current handler online error is retried, with a bounded budget',async()=>{
  let attempts=0;const f=fixture({fetcher:async()=>{attempts++;return attempts<4?response({error:ONLINE},400):success(session().characterId);}});
  const r=await f.controller.returnEntry();assert(r.ok);assert.equal(r.requests,4);assert.deepEqual(f.state.waits,[100,200,300]);
  assert.equal(f.state.calls.filter(c=>c.method==='reconnect').length,1);
  const g=fixture({fetcher:async()=>response({error:ONLINE},400)});const exhausted=await g.controller.returnEntry();
  assert.equal(exhausted.ok,false);assert.equal(exhausted.requests,4);assert.equal(exhausted.resetConfirmed,false);assert.deepEqual(g.state.waits,[100,200,300]);assert(exhausted.reconnectRequested);
});

test('other HTTP failures and similar text are never retried',async()=>{
  for(const [status,error]of [[403,ONLINE],[502,ONLINE],[400,ONLINE+'。'],[400,'角色凭据不匹配，未修改存档']]){
    const f=fixture({fetcher:async()=>response({error},status)}),r=await f.controller.returnEntry();
    assert.equal(r.ok,false);assert.equal(r.requests,1);assert.deepEqual(f.state.waits,[]);assert.equal(f.state.calls.filter(c=>c.method==='reconnect').length,1);
  }
});

test('malformed JSON and mismatched returned UUID/anchor fail once and recover only captured identity',async()=>{
  const bad=[response({returned:'00000000-0000-0000-0000-000000000002',anchor:'cinematic7'}),response({returned:session().characterId,anchor:'other'}),response([]),response(null),{ok:true,status:200,json:async()=>{throw Error('bad JSON');}}];
  for(const value of bad){const f=fixture({fetcher:async()=>value}),r=await f.controller.returnEntry();assert.equal(r.reason,'invalid-response');assert.equal(r.requests,1);assert.deepEqual(f.state.waits,[]);assert.deepEqual(f.state.calls.at(-1).snapshot,session());assert.equal(r.resetConfirmed,false);}
});

test('a real asynchronous request rejection falls back once without claiming unchanged position',async()=>{
  const failure=deferred(),f=fixture({fetcher:()=>failure.promise}),pending=f.controller.returnEntry();await turn();assert(f.controller.busy);
  failure.reject(Error('network failed after request might have arrived'));const r=await pending;
  assert.equal(r.reason,'request-failed');assert.equal(r.requests,1);assert.equal(r.resetConfirmed,false);assert(r.reconnectRequested);assert(!r.message.includes('未修改'));assert.equal(f.controller.busy,false);
});

test('role switch during close cancels before POST and cannot reconnect the new role',async()=>{
  const close=deferred(),f=fixture({releaseSession:()=>close.promise}),pending=f.controller.returnEntry();await turn();
  f.state.selected={...session(),characterId:'00000000-0000-0000-0000-000000000002',epoch:2};close.resolve();const r=await pending;
  assert.equal(r.reason,'cancelled');assert.equal(f.state.requests.length,0);assert.equal(f.state.calls.length,0);
});

test('page exit guard during close prevents subsequent POST or reconnect',async()=>{
  const close=deferred(),f=fixture({releaseSession:()=>close.promise}),pending=f.controller.returnEntry();await turn();f.state.allowed=false;close.resolve();
  const r=await pending;assert.equal(r.reason,'cancelled');assert.equal(r.requests,0);assert.equal(f.state.calls.length,0);
});

test('switch after an in-flight response and epoch change during retry never reconnect stale identity',async()=>{
  const reply=deferred(),f=fixture({fetcher:()=>reply.promise}),pending=f.controller.returnEntry();await turn();
  f.state.selected={...session(),epoch:2};reply.resolve(success(session().characterId));const r=await pending;
  assert.equal(r.reason,'cancelled');assert.equal(r.resetConfirmed,true);assert.equal(f.state.calls.filter(c=>c.method==='reconnect').length,0);
  const delay=deferred(),g=fixture({fetcher:async()=>response({error:ONLINE},400),wait:()=>delay.promise}),next=g.controller.returnEntry();await turn();g.state.selected={...session(),epoch:2};delay.resolve();
  const cancelled=await next;assert.equal(cancelled.reason,'cancelled');assert.equal(cancelled.requests,1);assert.equal(g.state.calls.filter(c=>c.method==='reconnect').length,0);
});

test('release rejection, explicit false and timeout never send a reset or create a duplicate connection',async()=>{
  for(const releaseSession of [async()=>{await turn();throw Error('close failed');},async()=>false,()=>new Promise(()=>{})]){
    const f=fixture({releaseSession,releaseTimeoutMs:10}),r=await f.controller.returnEntry();assert.equal(r.ok,false);assert.equal(r.requests,0);assert.equal(f.state.calls.length,0);assert.equal(f.controller.busy,false);
  }
  const late=deferred(),f=fixture({releaseSession:()=>late.promise,releaseTimeoutMs:10});await f.controller.returnEntry();late.resolve();await turn();assert.equal(f.state.requests.length,0);
});

test('request deadline aborts the fetch, bounds busy, and attempts only one same-identity recovery',async()=>{
  let signal;const f=fixture({fetcher:async(url,options)=>{signal=options.signal;return new Promise(()=>{});},requestTimeoutMs:10});
  const r=await f.controller.returnEntry();assert.equal(r.reason,'timeout');assert(signal.aborted);assert.equal(r.requests,1);assert.equal(f.controller.busy,false);assert(r.reconnectRequested);
});

test('confirmed reset followed by reconnect failure does not repeat either request or reconnect',async()=>{
  let reconnects=0;const f=fixture({reconnect:async()=>{reconnects++;await turn();throw Error('connect failed');}}),r=await f.controller.returnEntry();
  assert.equal(r.reason,'reconnect-failed');assert.equal(r.resetConfirmed,true);assert.equal(r.requests,1);assert.equal(reconnects,1);assert.equal(f.controller.busy,false);
});

test('failure recovery rejection and declined reconnect settle without leaking busy or secrets',async()=>{
  let attempts=0;const f=fixture({fetcher:async()=>{throw Error('network');},reconnect:async()=>{attempts++;await turn();throw Error('recover failed');}}),r=await f.controller.returnEntry();
  assert.equal(attempts,1);assert.equal(r.reconnectRequested,false);assert.equal(f.controller.busy,false);assert(!JSON.stringify(r).includes(session().resumeToken));
  const g=fixture({reconnect:async()=>false}),declined=await g.controller.returnEntry();assert.equal(declined.reason,'cancelled');assert.equal(declined.requests,1);assert.equal(declined.resetConfirmed,true);
});

test('intent guard can retain the captured identity while the socket is intentionally absent',async()=>{
  const f=fixture({releaseSession:async()=>{f.state.selected=null;}}),r=await f.controller.returnEntry();assert(r.ok);assert.deepEqual(f.state.calls.at(-1).snapshot,session());
});

test('busy clears after failure and a later explicit attempt can proceed; timings are copied and bounded',async()=>{
  let first=true;const f=fixture({releaseSession:async()=>{if(first){first=false;throw Error('not closed');}}});assert.equal((await f.controller.returnEntry()).ok,false);assert.equal((await f.controller.returnEntry()).ok,true);
  const delays=[0],g=fixture({retryDelays:delays,fetcher:async()=>response({error:ONLINE},400)});delays.push(1000);const r=await g.controller.returnEntry();assert.equal(r.requests,2);assert.deepEqual(g.state.waits,[0]);
  for(const config of [{retryDelays:[1,2,3,4]},{retryDelays:[-1]},{releaseTimeoutMs:0},{requestTimeoutMs:30001}])assert.throws(()=>fixture(config));
});
