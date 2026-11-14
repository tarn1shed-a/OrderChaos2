import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {sourceBreakAwayMinutes,browserBreakAwayClock} from '../deploy/unstuck_state.mjs';

function memoryStorage(initial={}){
  const values=new Map(Object.entries(initial)),reads=[],writes=[];
  return {values,reads,writes,getItem(key){reads.push(key);return values.get(key)??null;},setItem(key,value){writes.push([key,value]);values.set(key,value);}};
}
const KEY='oc2.break-away.client.v1';

test('original integer minute boundaries include the1740/1741 early zero branch',()=>{
  const now=100000;
  for(const [elapsed,want]of [[0,30],[1,29],[59,29],[60,29],[61,28],[1739,1],[1740,1],[1741,0],[1799,0],[1800,0],[1801,0]])
    assert.deepEqual(sourceBreakAwayMinutes(now,now-elapsed),{minutes:want,initialValue:null});
});

test('future preference keys stay capped at30 minutes in the checked original clock domain',()=>{
  for(const future of [1,59,60,1800])assert.deepEqual(sourceBreakAwayMinutes(100000,100000+future),{minutes:30,initialValue:null});
});

test('fresh missing key initializes now minus1800 once and remains immediately available',()=>{
  const storage=memoryStorage(),clock=browserBreakAwayClock({storage,now:()=>10000});
  assert.equal(clock.remaining(),0);assert.deepEqual(storage.writes,[[KEY,'8200']]);
  for(let i=0;i<10;i++)assert.equal(clock.remaining(),0);assert.equal(storage.writes.length,1);
  assert.deepEqual(sourceBreakAwayMinutes(1800,null),{minutes:0,initialValue:0});
});

test('actual returned writer persists and a new clock instance restores the browser key',()=>{
  let now=10000;const storage=memoryStorage({[KEY]:'8200'}),clock=browserBreakAwayClock({storage,now:()=>now});
  assert.equal(clock.remaining(),0);assert.equal(storage.writes.length,0);clock.returned();assert.deepEqual(storage.writes,[[KEY,'10000']]);
  const reloaded=browserBreakAwayClock({storage,now:()=>now});assert.equal(reloaded.remaining(),30);now++;assert.equal(reloaded.remaining(),29);
  now=11740;assert.equal(reloaded.remaining(),1);now=11741;assert.equal(reloaded.remaining(),0);assert.equal(storage.writes.length,1);
});

test('malformed browser strings are host input rejection, not an inferred original atoll parser',()=>{
  for(const value of ['', 'not-a-time','-1','8200.5','Infinity','9007199254740992']){
    const storage=memoryStorage({[KEY]:value}),clock=browserBreakAwayClock({storage,now:()=>10000});
    assert.equal(clock.remaining(),0);assert.deepEqual(storage.writes,[[KEY,'8200']]);
  }
  const storage=memoryStorage({[KEY]:'00010000'});assert.equal(browserBreakAwayClock({storage,now:()=>10000}).remaining(),30);assert.equal(storage.writes.length,0);
});

test('throwing storage methods and property accessors fall back to instance memory without claiming reload persistence',()=>{
  const broken=[undefined,{getItem(){throw Error('read denied');},setItem(){throw Error('write denied');}},
    {get getItem(){throw Error('getItem getter denied');},get setItem(){throw Error('setItem getter denied');}},
    {getItem:()=>null,setItem(){throw Error('quota');}}];
  for(const storage of broken){
    let now=10000;const clock=browserBreakAwayClock({storage,now:()=>now});assert.equal(clock.remaining(),0);clock.returned();assert.equal(clock.remaining(),30);now=10001;assert.equal(clock.remaining(),29);
  }
});

test('an available read can restore existing cooldown even if writes are denied',()=>{
  const storage={getItem:()=> '10000',setItem(){throw Error('write denied');}};
  assert.equal(browserBreakAwayClock({storage,now:()=>10001}).remaining(),29);
});

test('pure minute helper rejects unsupported host clock values without creating source state',()=>{
  for(const now of [1799,-1,NaN,Infinity,10000.5,'10000',true])assert.throws(()=>sourceBreakAwayMinutes(now,null));
  for(const last of [-1,undefined,NaN,Infinity,10000.5,'10000',true])assert.throws(()=>sourceBreakAwayMinutes(10000,last));
});

test('real lazy UI construction survives a global localStorage getter failure before any resource or DOM use',async()=>{
  // Only the two module import locations are rebound to explicit fixtures.
  // No UI rendering/Flash/browser clone is claimed by this constructor test.
  const svgStub='data:text/javascript,'+encodeURIComponent('export function sourceDrawing(){throw Error("unexpected drawing")}export function sourceFrameLayout(){throw Error("unexpected layout")}');
  let source=readFileSync(new URL('../deploy/unstuck_ui.mjs',import.meta.url),'utf8');
  assert(source.includes("from '/source-ui-svg.js'"));assert(source.includes("from './unstuck_state.mjs'"));
  source=source.replace("from '/source-ui-svg.js'",'from '+JSON.stringify(svgStub)).replace("from './unstuck_state.mjs'",'from '+JSON.stringify(new URL('../deploy/unstuck_state.mjs',import.meta.url).href));
  const original=Object.getOwnPropertyDescriptor(globalThis,'localStorage'),fetch=globalThis.fetch;let fetched=0;
  Object.defineProperty(globalThis,'localStorage',{configurable:true,get(){throw Error('storage security getter');}});
  globalThis.fetch=async()=>{fetched++;throw Error('unexpected resource request');};
  try{
    const {createUnstuckUI}=await import('data:text/javascript,'+encodeURIComponent(source));
    const ui=createUnstuckUI({stop(){},beforeOpen(){},focusGame(){},action(){throw Error('unexpected action');}});
    assert.equal(ui.isOpen,false);assert.equal(ui.canRequest(),false);ui.close();assert.equal(fetched,0);
  }finally{globalThis.fetch=fetch;if(original)Object.defineProperty(globalThis,'localStorage',original);else delete globalThis.localStorage;}
});
