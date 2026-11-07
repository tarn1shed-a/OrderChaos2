import test from 'node:test';
import assert from 'node:assert/strict';
import {createHotbarSync} from '../public/hotbar-sync.js';
import {defaultHotbar,swapHotbarSlots,rebindHotbarSlot} from '../public/hotbar-settings.js';

const customized=()=>rebindHotbarSlot(swapHotbarSlots(defaultHotbar(),0,7),7,{code:'KeyQ',shift:false}).settings;
function harness(options={}){
  const sent=[],states=[],cached=[],timers=new Map();let serial=0;
  const sync=createHotbarSync({send:msg=>{sent.push(structuredClone(msg));return options.sendResult!==false;},
    onState:state=>states.push(structuredClone(state)),loadLegacy:options.loadLegacy,
    cache:(id,value)=>cached.push({id,value}),schedule:callback=>{timers.set(++serial,callback);return serial;},cancel:id=>timers.delete(id)});
  return {sync,sent,states,cached,timers,last:()=>states.at(-1)};
}
test('legacy settings import only into an uninitialized server record; rapid edits wait for matching acknowledgements',()=>{
  const first=customized(),last=rebindHotbarSlot(first,1,{code:'KeyE',shift:true}).settings;
  const h=harness({loadLegacy:()=>({found:true,settings:first})});
  h.sync.connect({id:'a',hotbar:null});assert(h.sent[0].initializeOnly);assert(h.last().pending);assert(!h.last().message.includes('已保存'));
  h.sync.change(last);assert.equal(h.sent.length,1);
  h.sync.progress({id:'a',hotbar:defaultHotbar()});assert.deepEqual(h.last().settings,last);
  h.sync.result({requestId:1,ok:true,hotbar:first});assert.equal(h.sent.length,2);assert.deepEqual(h.sent[1].settings,last);
  assert.deepEqual(h.last().settings,last);assert(h.last().pending);
  h.sync.result({requestId:1,ok:true,hotbar:first});assert(h.last().pending,'Stale acknowledgement cannot complete the newer edit');
  h.sync.result({requestId:2,ok:true,hotbar:last});assert.equal(h.last().pending,false);assert(h.last().message.includes('已保存到服务器'));
  assert.deepEqual(h.cached.at(-1).value,last);assert.equal(h.timers.size,0);
});
test('server preferences win over an old browser cache and over rejected initialization',()=>{
  let reads=0;const h=harness({loadLegacy:()=>{reads++;return {found:true,settings:customized()};}});
  h.sync.connect({id:'a',hotbar:defaultHotbar()});assert.equal(reads,0);assert.equal(h.sent.length,0);
  h.sync.connect({id:'b',hotbar:null});assert.equal(reads,1);
  h.sync.result({requestId:1,ok:false,hotbar:defaultHotbar(),message:'已恢复服务器技能栏'});
  assert.deepEqual(h.last().settings,defaultHotbar());assert.equal(h.last().canRetry,false);
  h.sync.progress({id:'someone-else',hotbar:customized()});assert.deepEqual(h.last().settings,defaultHotbar());
});
test('timeouts, disconnects, unavailable transport and malformed acknowledgements never claim a durable save',()=>{
  const h=harness();h.sync.connect({id:'a',hotbar:defaultHotbar()});h.sync.change(customized());
  h.sync.result({requestId:1,ok:true,hotbar:null});assert(h.last().pending);
  [...h.timers.values()][0]();assert(h.last().canRetry);assert.equal(h.cached.length,0);
  h.sync.retry();assert.equal(h.sent.length,2);
  h.sync.result({requestId:1,ok:true,hotbar:defaultHotbar()});assert(h.last().pending);
  h.sync.result({requestId:2,ok:true,hotbar:customized()});assert(h.last().message.includes('已保存'));
  h.sync.change(defaultHotbar());h.sync.disconnect();assert.equal(h.cached.length,1);assert.deepEqual(h.last().settings,customized());
  h.sync.connect({id:'a',hotbar:customized()});assert(h.last().message.includes('未确认'));
  const offline=harness({sendResult:false});offline.sync.connect({id:'a',hotbar:null});assert(offline.last().canRetry);assert.equal(offline.cached.length,0);
});
