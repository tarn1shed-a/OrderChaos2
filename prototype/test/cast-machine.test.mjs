import test from 'node:test';
import assert from 'node:assert/strict';
import {CastMachine} from '../game/cast-machine.mjs';
import {SpellRuntime} from '../game/spell-runtime.mjs';
import {castPose} from '../public/cast-pose.js';
const visual=(clip,durationMs,loop=false)=>({id:1,movement:{stopOnEnter:false,interruptOnMove:false},[loop?'loop':'pre']:{clip,durationMs}});
const spec=()=>({sourceSkillId:101,chantMs:1000,channelMs:0,visuals:{'1':visual('skill_chant',400,true),'2':visual('skill_release',500),'6':visual('skill_back',200)}});
test('chant awaits an authoritative transition and times out at source duration plus 5000 ms',()=>{
 const c=new CastMachine(spec(),1000);assert.equal(c.stage,1);assert.equal(c.watchdogAt,7000);
 c.tick(6999);assert.equal(c.stage,1,'Elapsed chant time alone cannot release a client spell');
 c.tick(7000);assert.equal(c.stage,-2);assert.equal(c.signal(2,7001),false);
});
test('confirmed stages reject stale/duplicate transitions; release has its own animation timer and end visual',()=>{
 const c=new CastMachine(spec(),1000);assert.equal(c.signal(2,999),false);assert.equal(c.signal(6,1100),false);
 assert(c.signal(2,2000));assert.equal(c.signal(2,2000),false);assert.equal(c.watchdogAt,null);
 c.tick(2499);assert.equal(c.stage,2);c.tick(2500);assert.equal(c.stage,6);assert(c.done);
 assert.deepEqual(castPose(c.snapshot(),2600),{clip:'skill_back',time:.1});assert.equal(castPose(c.snapshot(),2700),null);
});
test('channel may follow chant or be entered directly, requires a completion signal and has an independent watchdog',()=>{
 const s=spec();s.channelMs=2000;s.visuals['3']=visual('skill_channel',500,true);
 const c=new CastMachine(s,0);assert(c.signal(3,1000));assert.equal(c.watchdogAt,8000);c.tick(3100);assert.equal(c.stage,3);assert(c.signal(6,3200));
 const direct=new CastMachine({...s,chantMs:0},100);assert.equal(direct.stage,3);direct.tick(7100);assert.equal(direct.stage,-2);
});
test('source animation loops use phase time and accept zero-chant release without stretching a clip over a cast',()=>{
 const c=new CastMachine(spec(),100);assert.deepEqual(castPose(c.snapshot(),1100),{clip:'skill_chant',time:.2});
 const instant=new CastMachine({...spec(),chantMs:0},100);assert.deepEqual(castPose(instant.snapshot(),350),{clip:'skill_release',time:.25});
});
function runtimeFixture(){
 const events=[],hits=[],executions=new Map(),profile={serverWaitExtraMs:5000};
 const runtime=new SpellRuntime(profile,{executions,emit:e=>events.push(structuredClone(e)),check:()=>null,hit:r=>hits.push(r.cast.id)});
 const ws={player:{id:'caster',hp:100},input:{x:0,y:0}};
 return {runtime,ws,events,hits,executions};
}
function cast(id,start,impact){return {id,skillId:'fireball',startedAt:start,releaseAt:start,impactAt:impact,targetId:'wolf'};}
test('execution and pending impact are independent; a later cast cannot erase or replay an earlier projectile',()=>{
 const {runtime,ws,hits,executions}=runtimeFixture();const native={...spec(),chantMs:0,visuals:{'2':visual('skill_release',100)}};
 runtime.start(ws,{native},cast('first',0,600));runtime.tick(100);assert.equal(executions.size,0);assert.equal(ws.player.cast,null);assert.equal(runtime.snapshot().length,1);
 runtime.start(ws,{native},cast('second',200,800));runtime.tick(600);assert.deepEqual(hits,['first']);assert.equal(runtime.pending.size,1);
 runtime.tick(800);runtime.tick(900);assert.deepEqual(hits,['first','second']);assert.equal(runtime.pending.size,0);
});
test('movement follows the per-stage source interruption flag, cancellation clears its impact and is idempotent',()=>{
 const {runtime,ws,hits,events}=runtimeFixture(),native=spec();native.visuals['1'].movement.interruptOnMove=true;
 const c=cast('moving',0,1500);c.releaseAt=1000;runtime.start(ws,{native},c);const record=runtime.pending.get(c.id);runtime.move(ws,{x:1,y:0},100);assert.equal(runtime.cancel(record,'duplicate',101),false);runtime.tick(2000);
 assert.equal(runtime.pending.size,0);assert.equal(ws.player.cast,null);assert.deepEqual(hits,[]);assert.equal(events.filter(e=>e.action==='skill-cancel').length,1);
});
