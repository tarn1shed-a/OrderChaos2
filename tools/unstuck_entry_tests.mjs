import {test} from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
import {createUnstuckEntrySession,stageUnstuckEntry} from '../deploy/unstuck_entry.mjs';
import {createUnstuckReturn} from '../deploy/unstuck_return.mjs';
import {browserBreakAwayClock} from '../deploy/unstuck_state.mjs';
import {stageEntry} from '../deploy/stage_runtime.mjs';
import {stageInsideEntry} from './preview/map-runtime-inside-overlay.mjs';
import {stageCharacterPanelsEntry} from './preview/character-panel-runtime-overlay.mjs';
import {stageCharacterHotbarEntry} from './preview/character-hotbar-overlay.mjs';
import {stageSceneEffectsEntry} from './preview/source-scene-effect-overlay.mjs';
import {stageFire10Entry} from './preview/source-scene-effect-fire10-overlay.mjs';

const id='00000000-0000-0000-0000-000000000001',otherId='00000000-0000-0000-0000-000000000002';
const turn=()=>new Promise(resolve=>setImmediate(resolve));
const event=(code='Escape',repeat=false)=>({code,repeat,prevented:false,preventDefault(){this.prevented=true;}});
class Socket extends EventTarget{
  readyState=1;closes=0;
  close(){this.closes++;this.readyState=2;}
  closed(){this.readyState=3;this.dispatchEvent(new Event('close'));}
}
function fixture({fetcher,releaseTimeoutMs=100,connectFailure=false,earlyWelcome=false,clock=null}={}){
  const state={connected:true,generation:1,credentials:{characterId:id,resumeToken:'a'.repeat(64),name:'会话夹具'},room:'TEST-01',profession:3,
    otherPanel:false,casting:false,allowRequest:true,requests:[],connects:[],notices:[],returned:0,resets:0,autoReconnects:0,retriesCleared:0,stops:0,opened:0};
  let api,ui;state.socket=new Socket();
  const reset=()=>{state.resets++;state.connected=false;state.target=null;state.buffer=[];state.avatars=[];};
  function register(ws,generation){ws.addEventListener('close',()=>{if(generation!==state.generation)return;reset();if(api.onClose(ws))return;state.autoReconnects++;});}
  function connect(snapshot){
    if(connectFailure)throw Error('fixture connect failure');
    api.onConnectAttempt();state.generation++;state.credentials={characterId:snapshot.characterId,resumeToken:snapshot.resumeToken,name:snapshot.name};state.room=snapshot.room;state.profession=snapshot.profession;
    state.socket=new Socket();register(state.socket,state.generation);api.onSocketCreated(state.socket,state.generation);state.connects.push(snapshot);
    if(earlyWelcome){state.connected=true;api.onWelcome(state.socket,{id:snapshot.characterId,character:{id:snapshot.characterId}});}
  }
  api=createUnstuckEntrySession({
    createTransport:callbacks=>createUnstuckReturn({...callbacks,releaseTimeoutMs,requestTimeoutMs:100,wait:async()=>{},
      fetcher:async(url,options)=>{state.requests.push({url,options});if(fetcher)return fetcher(url,options);return {ok:true,status:200,json:async()=>({returned:id,anchor:'cinematic7'})};}}),
    createUI:callbacks=>{ui={isOpen:false,callbacks,open(){callbacks.stop();callbacks.beforeOpen();this.isOpen=true;state.opened++;},close(){this.isOpen=false;},canRequest:()=>state.allowRequest&&(!clock||clock.remaining()===0),notice:message=>state.notices.push(message),returned(){state.returned++;clock?.returned();this.close();}};return ui;},
    readSession:()=>state.connected?{...state.credentials,room:state.room,profession:state.profession,epoch:state.generation,socket:state.socket}:null,
    readGeneration:()=>state.generation,readSocket:()=>state.socket,resetConnection:reset,stop:()=>state.stops++,clearRetry:()=>state.retriesCleared++,connectSession:connect,focusGame:()=>{},beforeOpen:()=>{state.target=null;},
    canOpen:()=>state.connected&&!state.otherPanel&&!state.casting
  });
  register(state.socket,state.generation);
  return {api,state,ui,manualConnect(next=id){connect({characterId:next,resumeToken:next===id?'a'.repeat(64):'b'.repeat(64),name:'会话夹具',room:'TEST-01',profession:next===id?3:1});},welcome(ws=state.socket,characterId=id){state.connected=true;api.onWelcome(ws,{id:characterId,character:{id:characterId}});}};
}

test('Escape is the only open route and connected/panel/cast eligibility is external',()=>{
  const f=fixture();assert.equal(f.api.escape(event('KeyC')),false);
  for(const blocked of ['connected','otherPanel','casting']){
    f.state.connected=blocked!=='connected';f.state.otherPanel=blocked==='otherPanel';f.state.casting=blocked==='casting';assert.equal(f.api.escape(event()),false);
  }
  Object.assign(f.state,{connected:true,otherPanel:false,casting:false});const e=event();assert(f.api.escape(e));assert(e.prevented);assert(f.api.isOpen);assert.equal(f.state.target,null);
  assert(f.api.escape(event()));assert(!f.api.isOpen);f.api.escape(event('Escape',true));assert(!f.api.isOpen);
});

test('UI canRequest refusal does not close a session or send a return request',async()=>{
  const f=fixture();f.state.allowRequest=false;const r=await f.ui.callbacks.action();assert.equal(r.reason,'blocked');assert.equal(f.state.socket.closes,0);assert.equal(f.state.requests.length,0);assert.equal(f.state.notices.length,1);assert.equal(f.api.busy,false);
});

test('actual close event runs reset, suppresses old automatic reconnect, and waits for matching welcome',async()=>{
  const f=fixture();f.api.escape(event());const old=f.state.socket,pending=f.ui.callbacks.action();await turn();
  assert.equal(old.closes,1);assert.equal(f.state.requests.length,0);assert(f.api.busy);old.closed();const r=await pending;
  assert(r.ok);assert.equal(f.state.resets,1);assert.equal(f.state.autoReconnects,0);assert.equal(f.state.retriesCleared,1);assert.equal(f.state.requests.length,1);
  assert.equal(f.state.connects.length,1);assert.equal(f.state.generation,2);assert.equal(f.state.returned,0);assert.equal(f.api.busy,false);
  f.api.onWelcome(old,{id,character:{id}});assert.equal(f.state.returned,0);
  f.welcome(f.state.socket,otherId);assert.equal(f.state.returned,0);f.welcome();assert.equal(f.state.returned,1);assert(!f.api.isOpen);f.welcome();assert.equal(f.state.returned,1);
});

test('same-role failure recovery welcome does not confirm a reset or trigger returned',async()=>{
  const f=fixture({fetcher:async()=>{await turn();throw Error('network');}}),old=f.state.socket,pending=f.api.returnEntry();await turn();old.closed();const r=await pending;
  assert.equal(r.ok,false);assert.equal(f.state.connects.length,1);assert.equal(f.state.notices.length,1);f.welcome();assert.equal(f.state.returned,0);assert.equal(f.api.busy,false);
});

test('switch during release never posts for or reconnects the new role',async()=>{
  const f=fixture(),old=f.state.socket,pending=f.api.returnEntry();await turn();f.manualConnect(otherId);old.closed();const r=await pending;
  assert.equal(r.reason,'cancelled');assert.equal(f.state.requests.length,0);assert.equal(f.state.credentials.characterId,otherId);assert.equal(f.state.connects.length,1);assert.equal(f.state.notices.length,0);assert.equal(f.state.returned,0);
});

test('pagehide suppresses later automatic recovery and any matching welcome',async()=>{
  const f=fixture(),old=f.state.socket,pending=f.api.returnEntry();await turn();f.api.pagehide();old.closed();const r=await pending;
  assert.equal(r.reason,'cancelled');assert.equal(f.state.requests.length,0);assert.equal(f.state.autoReconnects,0);assert.equal(f.state.connects.length,0);assert.equal(f.state.notices.length,0);assert.equal(f.api.escape(event()),false);
});

test('late close after bounded release failure still cannot reopen session or retry',async()=>{
  const f=fixture({releaseTimeoutMs:10}),old=f.state.socket,r=await f.api.returnEntry();assert.equal(r.ok,false);assert.equal(f.api.busy,false);assert.equal(f.state.requests.length,0);assert.equal(f.state.notices.length,1);
  old.closed();await turn();assert.equal(f.state.autoReconnects,0);assert.equal(f.state.connects.length,0);
});

test('disconnect confirmation and failed reconnect cleanup leave no returned marker',async()=>{
  const f=fixture({connectFailure:true}),old=f.state.socket,pending=f.api.returnEntry();await turn();old.closed();const r=await pending;
  assert.equal(r.resetConfirmed,true);assert.equal(r.ok,false);assert.equal(f.state.notices.length,1);assert.equal(f.api.busy,false);f.welcome(old);assert.equal(f.state.returned,0);
});

test('opening role selection clears a pending welcome and cancels later notification',async()=>{
  const f=fixture(),old=f.state.socket,pending=f.api.returnEntry();await turn();old.closed();await pending;f.api.onSessionOpen();f.welcome();assert.equal(f.state.returned,0);assert(!f.api.isOpen);
});

test('welcome delivered before transport settles waits for confirmed success, not HTTP alone',async()=>{
  const f=fixture({earlyWelcome:true}),old=f.state.socket,pending=f.api.returnEntry();await turn();old.closed();const result=await pending;
  assert(result.ok);assert.equal(f.state.returned,1);f.welcome();assert.equal(f.state.returned,1);
  const g=fixture({earlyWelcome:true,fetcher:async()=>{throw Error('network');}}),prior=g.state.socket,failed=g.api.returnEntry();await turn();prior.closed();await failed;assert.equal(g.state.returned,0);
});

test('real return controller plus entry EventTarget chain writes real clock only once after confirmed matching welcome',async()=>{
  const writes=[],values=new Map([['oc2.break-away.client.v1','8200']]);
  const clock=browserBreakAwayClock({storage:{getItem:key=>values.get(key)??null,setItem(key,value){writes.push([key,value]);values.set(key,value);}},now:()=>10000});
  const f=fixture({clock}),old=f.state.socket,pending=f.ui.callbacks.action();await turn();assert.equal(writes.length,0);old.closed();const result=await pending;
  assert.equal(result.ok,true);assert.equal(result.resetConfirmed,true);assert.equal(writes.length,0);assert.equal(clock.remaining(),0);
  f.welcome(f.state.socket,otherId);assert.equal(writes.length,0);f.welcome();assert.deepEqual(writes,[['oc2.break-away.client.v1','10000']]);assert.equal(clock.remaining(),30);f.welcome();assert.equal(writes.length,1);
  const failedWrites=[],failedClock=browserBreakAwayClock({storage:{getItem:()=> '8200',setItem:(...args)=>failedWrites.push(args)},now:()=>10000});
  const g=fixture({clock:failedClock,fetcher:async()=>{await turn();throw Error('unconfirmed network failure');}}),prior=g.state.socket,failed=g.ui.callbacks.action();await turn();prior.closed();const failure=await failed;
  assert.equal(failure.ok,false);assert.equal(failure.resetConfirmed,false);g.welcome();assert.equal(g.state.returned,0);assert.deepEqual(failedWrites,[]);
});

test('switch during an in-flight return and pagehide before welcome cannot finish another identity',async()=>{
  let resolve;const response=new Promise(ok=>resolve=ok),f=fixture({fetcher:()=>response}),old=f.state.socket,pending=f.api.returnEntry();await turn();old.closed();await turn();f.manualConnect(otherId);
  resolve({ok:true,status:200,json:async()=>({returned:id,anchor:'cinematic7'})});const result=await pending;
  assert.equal(result.reason,'cancelled');assert.equal(f.state.connects.length,1);assert.equal(f.state.credentials.characterId,otherId);assert.equal(f.state.notices.length,0);f.welcome(f.state.socket,otherId);assert.equal(f.state.returned,0);
  const g=fixture(),previous=g.state.socket,next=g.api.returnEntry();await turn();previous.closed();await next;g.api.pagehide();g.welcome();assert.equal(g.state.returned,0);
});

test('stage rejects missing prerequisites without generating a new game entry',()=>{
  assert.throws(()=>stageUnstuckEntry('unknown'),/requires staged/);
  assert.throws(()=>stageUnstuckEntry("import {createCharacterHotbar} from '/__delivery/character_hotbar.mjs';"),/requires staged/);
});

const runtime=new URL('../analysis/raw/showcase-20261110/running-preview/prototype/public/explore-map.js',import.meta.url);
test('actual complete staged entry compiles, guards anchors, and preserves render/effect/restore code',{skip:!existsSync(runtime)},()=>{
  const raw=readFileSync(runtime,'utf8');let before=stageEntry(raw,{entryUI:true});before=stageInsideEntry(before);before=stageCharacterPanelsEntry(before);before=stageCharacterHotbarEntry(before);before=stageSceneEffectsEntry(before);before=stageFire10Entry(before);
  const staged=stageUnstuckEntry(before);assert.throws(()=>stageUnstuckEntry(staged),/already applied/);
  assert.throws(()=>stageUnstuckEntry(before.replace('function resetConnection() {','function changedReset() {')),/anchor differs/);
  assert.throws(()=>stageUnstuckEntry(before+'\nlet activeCredentials=null;'),/anchor differs/);
  const syntax=spawnSync(process.execPath,['--check','--input-type=module'],{input:staged,encoding:'utf8'});assert.equal(syntax.status,0,syntax.stderr);
  for(const anchor of ['sourcePresentation.reset();connected = false','sourceSceneEffects.update(now','sourceSceneFire10.update(now','characterHotbar.apply();','renderAttributePreview(THREE,renderer','sceneStages.start();'])assert(staged.includes(anchor));
  assert(staged.includes('unstuckEntry?.onWelcome(ws,msg)'));assert(staged.includes("if(unstuckEntry?.onClose(ws)){status('正在恢复连接');return;}"));
  assert(staged.includes('sourceCameraInput.packet(false,camera.near);pointer=null;'));assert(!staged.includes('positions.resources'));
});

test('actual emitted input gate blocks C/K and pointer/wheel while unstuck modal is open',{skip:!existsSync(runtime)},()=>{
  const raw=readFileSync(runtime,'utf8'),before=stageCharacterHotbarEntry(stageCharacterPanelsEntry(stageInsideEntry(stageEntry(raw,{entryUI:true})))),source=stageUnstuckEntry(before);
  const begin=source.indexOf("window.addEventListener('keydown', e => {"),end=source.indexOf("window.addEventListener('keyup'",begin),code=source.slice(begin,end);let handler;const calls=[];
  const api={isOpen:true,escape:()=>false};
  new Function('window','document','unstuckEntry',code)({addEventListener(type,fn){assert.equal(type,'keydown');handler=fn;}},{activeElement:{tagName:'CANVAS'}},api);
  for(const code of ['KeyC','KeyK','KeyW','Space'])handler({...event(code)});assert.deepEqual(calls,[]);
  assert(source.includes("canvas.addEventListener('pointerdown', e => { if(unstuckEntry?.isOpen)return;"));
  assert(source.includes("canvas.addEventListener('wheel', e => { e.preventDefault();if(unstuckEntry?.isOpen)return;"));
  assert(source.includes('function inputBlocked(){return unstuckEntry?.isOpen||attributeUI?.isOpen||'));
});
