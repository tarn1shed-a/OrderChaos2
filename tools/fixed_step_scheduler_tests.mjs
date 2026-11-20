import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {startFixedStepScheduler,stageFixedStepServer} from '../deploy/fixed_step_scheduler.mjs';
import {entryServer} from '../deploy/entry_manage.mjs';
import {stageSourceAvatarServer} from '../deploy/source_avatar_server.mjs';
import {stagePlayerChoiceServer} from '../deploy/player_choice_server.mjs';
import {stageInspectorServer} from '../deploy/map_inspector.mjs';
import {stageOrdinaryQuestServer} from '../deploy/quest_server_overlay.mjs';
import {stageSourceWorldCommandGate} from '../deploy/source_world_command_stage.mjs';
import {stageHumanFemalePendingServer} from '../deploy/source_world_pending_stage.mjs';

// Deterministic timer driver. Advancing this clock models event-loop lateness
// and synchronous work; it never invokes the game or native worker.
function timers(){
  let time=0,serial=0,maxPending=0;
  const pending=new Map(),delays=[];
  const options={now:()=>time,setTimer(fn,delay){
    const id=++serial;delays.push(delay);pending.set(id,{id,fn,at:time+Math.max(1,delay)});
    maxPending=Math.max(maxPending,pending.size);return id;
  },clearTimer:id=>pending.delete(id)};
  function next(at){
    const task=[...pending.values()].sort((a,b)=>a.at-b.at||a.id-b.id)[0];
    assert(task,'expected one scheduled wake');pending.delete(task.id);
    time=at??Math.max(time,task.at);task.fn();
  }
  return {options,next,advance:ms=>time+=ms,pending,delays,
    get time(){return time;},get maxPending(){return maxPending;}};
}

test('twenty fixed steps stay on absolute deadlines despite synchronous work',()=>{
  const t=timers(),starts=[],argumentsSeen=[];
  const scheduler=startFixedStepScheduler(function(){starts.push(t.time);argumentsSeen.push([...arguments]);t.advance(7);},50,t.options);
  assert.deepEqual(starts,[]);
  for(let i=0;i<20;i++)t.next();
  assert.deepEqual(starts,Array.from({length:20},(_,i)=>(i+1)*50));
  assert(argumentsSeen.every(args=>args.length===0),'waiting clock/delta must never enter the step');
  assert.equal(scheduler.inspect().completedSteps,20);
  assert.equal(scheduler.inspect().nextDeadlineMs,1050);
  assert.equal(scheduler.inspect().maxStepDurationMs,7);
  assert.equal(t.maxPending,1);scheduler.stop();
});

test('a late timer does not turn its lateness or step cost into cumulative drift',()=>{
  const t=timers(),starts=[];
  const scheduler=startFixedStepScheduler(()=>{starts.push(t.time);t.advance(5);},50,t.options);
  t.next(57);t.next();t.next();
  assert.deepEqual(starts,[57,100,150]);
  assert.equal(scheduler.inspect().maxLatenessMs,7);
  assert.equal(scheduler.inspect().catchUpSteps,0);scheduler.stop();
});

test('an early timer only rearms; it cannot run a premature game step',()=>{
  const t=timers(),starts=[];
  const scheduler=startFixedStepScheduler(()=>starts.push(t.time),50,t.options);
  t.next(49.25);assert.deepEqual(starts,[]);assert.equal(t.pending.size,1);
  t.next();assert.equal(starts.length,1);assert(starts[0]>=50);
  assert.equal(scheduler.inspect().earlyWakes,1);scheduler.stop();
});

test('a long external stall permits one extra overdue step, then discards scheduling debt',()=>{
  const t=timers(),starts=[];
  const scheduler=startFixedStepScheduler(()=>{starts.push(t.time);t.advance(5);},50,t.options);
  t.next(1000);assert.deepEqual(starts,[1000]);
  t.next();assert.deepEqual(starts,[1000,1006]);
  assert.equal(scheduler.inspect().catchUpSteps,1);
  assert.equal(scheduler.inspect().rebases,1);
  assert.equal(scheduler.inspect().nextDeadlineMs,1056);
  assert.equal(scheduler.inspect().discardedScheduleDebtMs,906);
  t.next();assert.deepEqual(starts,[1000,1006,1056]);
  assert.equal(scheduler.inspect().completedSteps,3,'no synthetic ticks for missed deadlines');
  assert.equal(t.maxPending,1);scheduler.stop();
});

test('one transient overrun catches up on a separate timer turn and recovers the original phase',()=>{
  const t=timers(),starts=[];
  const scheduler=startFixedStepScheduler(()=>{starts.push(t.time);t.advance(starts.length===1?80:5);},50,t.options);
  t.next();assert.deepEqual(starts,[50]);
  t.next();assert.deepEqual(starts,[50,131]);
  t.next();assert.deepEqual(starts,[50,131,150]);
  assert.equal(scheduler.inspect().rebases,0);scheduler.stop();
});

for(const workMs of [50,70])test(`sustained ${workMs}ms work runs at its available rate without another 50ms sleep or an unbounded loop`,()=>{
  const t=timers(),starts=[];let inside=false;
  const scheduler=startFixedStepScheduler(()=>{
    assert.equal(inside,false);inside=true;starts.push(t.time);t.advance(workMs);inside=false;
  },50,t.options);
  for(let i=0;i<12;i++){
    const before=starts.length;t.next();assert.equal(starts.length,before+1,'only one step per timer turn');
    assert.equal(t.pending.size,1);
  }
  assert.deepEqual(starts,Array.from({length:12},(_,i)=>50+i*(workMs+1)));
  assert(scheduler.inspect().rebases>0);
  assert(scheduler.inspect().nextDeadlineMs>=t.time-50,'scheduling debt must stay bounded');
  assert.equal(t.maxPending,1);scheduler.stop();
});

test('stop cancels the sole wake and a delivered stale callback cannot mutate the game',()=>{
  const t=timers();let calls=0;
  const scheduler=startFixedStepScheduler(()=>calls++,50,t.options);
  const stale=[...t.pending.values()][0].fn;
  scheduler.stop();scheduler.stop();stale();
  assert.equal(calls,0);assert.equal(t.pending.size,0);
  assert.equal(scheduler.inspect().active,false);assert.equal(scheduler.inspect().pending,false);
});

test('stop during a step cannot schedule another step',()=>{
  const t=timers();let scheduler,calls=0;
  scheduler=startFixedStepScheduler(()=>{calls++;scheduler.stop();},50,t.options);
  t.next();assert.equal(calls,1);assert.equal(t.pending.size,0);
  assert.equal(scheduler.inspect().completedSteps,1);
});

test('step exceptions propagate unchanged and stop scheduling; handled server errors remain handled',()=>{
  const t=timers(),original=Error('fixture storage failure');
  const scheduler=startFixedStepScheduler(()=>{throw original;},50,t.options);
  assert.throws(()=>t.next(),error=>error===original);
  assert.equal(t.pending.size,0);assert.equal(scheduler.inspect().failed,true);
  assert.equal(scheduler.inspect().completedSteps,0);
  const handled=timers();let faults=0;
  const next=startFixedStepScheduler(()=>{try{throw original;}catch{faults++;}},50,handled.options);
  handled.next();assert.equal(faults,1);assert.equal(next.inspect().failed,false);assert.equal(handled.pending.size,1);next.stop();
});

test('invalid intervals, callbacks and non-monotonic test clocks fail explicitly',()=>{
  for(const period of [0,-1,1.5,Infinity,NaN,2147483648])assert.throws(()=>startFixedStepScheduler(()=>{},period),TypeError);
  assert.throws(()=>startFixedStepScheduler(null,50),TypeError);
  assert.throws(()=>startFixedStepScheduler(()=>{},50,{now:()=>NaN}),/monotonic/);
  const t=timers(),scheduler=startFixedStepScheduler(()=>{},50,t.options);
  assert.throws(()=>t.next(-1),/monotonic/);assert.equal(scheduler.inspect().failed,true);assert.equal(t.pending.size,0);
});

const importLine=`import {startFixedStepScheduler} from ${JSON.stringify(new URL('../deploy/fixed_step_scheduler.mjs',import.meta.url).href)};\n`;
function undoStage(staged){
  assert(staged.startsWith(importLine));
  return staged.slice(importLine.length)
    .replace('  const ticker = startFixedStepScheduler(() => {','  const ticker = setInterval(() => {')
    .replace('ticker.stop();','clearInterval(ticker);');
}

test('generated ticker executes the unchanged closure and its close cancels it; other timers are preserved',()=>{
  const source=`const seen=[];
  const ticker = setInterval(() => {
    seen.push({dt:.05,wall:sourceClock()});
  }, 50);
  const close=()=>{clearInterval(ticker);clearInterval(heartbeat);};`;
  const generated=stageFixedStepServer(source),t=timers(),closed=[];
  assert.equal(undoStage(generated),source);
  const build=new Function('startFixedStepScheduler','sourceClock','setInterval','clearInterval','heartbeat',
    generated.slice(importLine.length)+'\nreturn {seen,close};');
  let wall=700;
  const fixture=build((fn,ms)=>startFixedStepScheduler(fn,ms,t.options),()=>wall,
    ()=>assert.fail('original ticker still installed'),timer=>closed.push(timer),'unchanged-heartbeat');
  t.next();wall=900;t.next();
  assert.deepEqual(fixture.seen,[{dt:.05,wall:700},{dt:.05,wall:900}]);
  fixture.close();assert.equal(t.pending.size,0);assert.deepEqual(closed,['unchanged-heartbeat']);
  for(const changed of [source.replace('  const ticker',' const ticker'),source.replace('clearInterval(ticker);',''),source+'\nclearInterval(ticker);'])
    assert.throws(()=>stageFixedStepServer(changed),/anchor/);
  assert.throws(()=>stageFixedStepServer(generated),/anchor|already staged/);
});

test('deployment applies this stage after existing guarded transforms, before writing/importing the generated copy',()=>{
  const source=readFileSync(new URL('../deploy/server.mjs',import.meta.url),'utf8');
  const staging='serverSource=stageFixedStepServer(serverSource);';
  assert.equal(source.split(staging).length,2);
  assert(source.indexOf('sourceWorld.stageServer(serverSource)')<source.indexOf(staging));
  assert(source.indexOf(staging)<source.indexOf('writeFileSync(observed,serverSource)'));
  assert(source.indexOf(staging)<source.indexOf('await import(observed)'));
});

const template=process.env.OC2_SCHEDULER_TEMPLATE;
test('actual SHA-pinned template and all current legacy/source staging combinations keep every game-step byte',
  {skip:!template},()=>{
    const original=readFileSync(template,'utf8'),manifest=JSON.parse(readFileSync(new URL('./local_mvp_runtime.json',import.meta.url),'utf8'));
    const digest=createHash('sha256').update(original).digest('hex');
    assert.equal(digest,manifest.files['prototype/server.mjs']);
    const entry=entryServer(original,new URL('../deploy/movement_trace.mjs',import.meta.url).href);
    const legacy=stageInspectorServer(stageSourceAvatarServer(entry));
    const ordinary=stageOrdinaryQuestServer(legacy);
    let source=stageOrdinaryQuestServer(stageInspectorServer(stagePlayerChoiceServer(entry,'file:///reviewed/registry.mjs')));
    const storeAnchor="from './game/character-store.mjs'";
    assert.equal(source.split(storeAnchor).length,2);
    source=stageHumanFemalePendingServer(stageSourceWorldCommandGate(source.replace(storeAnchor,"from './game/character-store-source-world.mjs'")));
    for(const candidate of [legacy,ordinary,source]){
      const generated=stageFixedStepServer(candidate);
      assert.equal(undoStage(generated),candidate);
      assert.equal(generated.split('startFixedStepScheduler(() => {').length,2);
      assert.equal(generated.split('const heartbeat = setInterval').length,2);
      assert.equal(generated.split('const saveTimer = setInterval').length,2);
    }
    assert.throws(()=>entryServer(original+'\n','file:///trace.mjs'),/identity/,'base SHA guard must still reject changed templates');
  });
