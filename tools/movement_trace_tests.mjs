import {test} from 'node:test';
import assert from 'node:assert/strict';
import {movementTrace} from '../deploy/movement_trace.mjs';
import {observeServer} from '../deploy/observe_server.mjs';
import {readFileSync,existsSync} from 'node:fs';

test('trace separates queue and CPU wall time and only decorates its own next state',()=>{
  let clock=0;const t=movementTrace(()=>clock),a={},b={},original={type:'state',players:[{id:'unchanged'}]};
  t.input(a,{type:'input',_timing:7});clock=2;t.accepted(a);clock=27;t.before(a);clock=38;t.after(a);clock=40;
  assert.strictEqual(t.reply(b,original),original);
  assert.deepEqual(t.reply(a,original),{...original,_timing:{seq:7,handlerMs:2,queueMs:25,moveMs:11,afterMoveMs:2,serverMs:40}});
  assert.strictEqual(t.reply(a,original),original);assert.deepEqual(original,{type:'state',players:[{id:'unchanged'}]});
});
test('untraced, rejected and superseded input cannot attach old timing to a later state',()=>{
  const t=movementTrace(()=>1),ws={},state={type:'state'};
  for(const _timing of [undefined,null,-1,1.2,'1',Infinity,Number.MAX_SAFE_INTEGER+1]){
    t.input(ws,{type:'input',_timing});t.accepted(ws);t.before(ws);t.after(ws);assert.strictEqual(t.reply(ws,state),state);
  }
  t.input(ws,{type:'input',_timing:1});t.before(ws);t.after(ws);assert.strictEqual(t.reply(ws,state),state);
  t.input(ws,{type:'input'});assert.strictEqual(t.reply(ws,state),state);
});
const runtime='analysis/raw/showcase-20261110/running-preview/prototype/server.mjs';
test('reviewed server copy preserves gameplay source except timing hooks',{skip:!existsSync(runtime)},()=>{
  const source=readFileSync(runtime,'utf8'),observed=observeServer(source,'file:///trace.mjs');
  assert(observed.includes('}, 50);'));assert(observed.includes('ws.motion.move(ws.player,input,.05,ws.world)'));
  assert.throws(()=>observeServer(source+' ','file:///trace.mjs'),/identity differs/);
  assert.equal(readFileSync(runtime,'utf8'),source);
});
