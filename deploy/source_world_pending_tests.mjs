import test from 'node:test';
import assert from 'node:assert/strict';
import {createHumanFemalePendingJoins,HUMAN_FEMALE_POLICY} from './world_admission/human_female.mjs';

function fixture({clock=()=>100}={}){
 const policy=HUMAN_FEMALE_POLICY,registry={count:45,check:()=>({key:'human-female',sourceModelId:32})};
 const record={id:'a',profession:1,sourceAvatar:{key:'human-female'},sourceInventoryPolicy:'empty-compatible-container-v1',hotbar:null,inventory:{},equipment:{hand:null}},player={id:'a',profession:1,sourceAvatar:{key:'human-female'}};
 const ws={readyState:1,character:record,player,input:{},world:{}},active=new Map(),room=new Map(),rooms=new Map(),store={records:new Map([['a',record]])};
 let ready,advances=0,forgotten=0;
 const pending=createHumanFemalePendingJoins({registry,policy,clock,readPreparedBody:()=>({key:'human-female',ready:true,pose:{field:'sourceFemalePose',bindingId:policy.bindingId,valueBytes:1928}}),readNativeReady:()=>ready});
 ws.motion={move(){advances++;const owner=pending.readOwner(player,'native:a');ready={actorKey:'a',identity:'native:a',generation:owner.generation,roomKey:'room',mapId:1,sourceModelId:32,bindingId:policy.bindingId,valueBytes:1928,sourceMotion:policy.motionSHA256,actualNativeActorAndConsumedPose:true};},forget(){forgotten++;}};
 pending.attach({store,active,rooms,combatRooms:new Map(),clock,reject(){throw Error('Unexpected rejection');},storageFailure(){throw Error('Unexpected storage failure');},gate:{join:()=>true}});
 const message={scene:'resources',mapWindow:'heaven-landing',profession:1};
 pending.stage(ws,{room,roomKey:'room',message,commit(){active.set('a',ws);room.set('a',ws);rooms.set('room',room);}});
 pending.step(1);
 return {pending,ws,record,player,active,advances:()=>advances,forgotten:()=>forgotten};
}
test('active source uses the one existing movement callback',()=>{const f=fixture();let calls=0;f.pending.withMotion(f.ws,2,()=>calls++);assert.equal(calls,1);assert.equal(f.advances(),1);});
for(const readyState of [2,3])test('closing state '+readyState+' skips final native tick and retires normally',()=>{const f=fixture();f.ws.readyState=readyState;let calls=0;assert.doesNotThrow(()=>f.pending.withMotion(f.ws,2,()=>calls++));assert.equal(calls,0);assert.equal(f.advances(),1);assert.equal(f.pending.readOwner(f.player,'native:a'),null);f.pending.close(f.ws);assert.equal(f.pending.inspect().trackedCharacters,0);assert.equal(f.forgotten(),0);});
test('changed live record is still refused',()=>{const f=fixture();f.ws.character={...f.record};assert.throws(()=>f.pending.withMotion(f.ws,2,()=>{}),/current source motion owner/);});
test('untracked source player cannot use a closing socket as authorization',()=>{const f=fixture();f.ws.readyState=2;f.pending.close(f.ws);assert.throws(()=>f.pending.withMotion(f.ws,2,()=>{}),/current source motion owner/);});
test('legacy motion remains on its unchanged callback',()=>{const f=fixture();let calls=0;f.pending.withMotion({player:{}},2,()=>calls++);assert.equal(calls,1);});
test('native reset and press reuse the captured authoritative frame without taking another clock',()=>{
 let reads=0;const f=fixture({clock:()=>1794847000000+reads++}),before=reads;
 f.pending.withMotion(f.ws,2,()=>{
  const expected=[1794847000,before*1000];
  assert.deepEqual(f.pending.readNativeTimeval('reset',{identity:'native:a'}),expected);
  assert.deepEqual(f.pending.readNativeTimeval('press',{identity:'native:a'}),expected);
  assert.deepEqual(f.pending.sourceTimeval(f.player,'native:a'),expected);
  assert.equal(reads,before+1);
  assert.throws(()=>f.pending.readNativeTimeval('reset',{identity:'another-fork'}),/outside its current frame/);
 });assert.equal(reads,before+1);
});
test('startup and disconnected release use trusted clock, while unowned motion cannot request one',()=>{
 let reads=0;const f=fixture({clock:()=>1794847000000+reads++});
 for(const op of ['cold-rng','cold-origin','prepareOwnBody','forget']){const before=reads;assert.deepEqual(f.pending.readNativeTimeval(op,{}),[1794847000,before*1000]);assert.equal(reads,before+1);}
 for(const op of ['reset','press','release','tick','client-chosen'])assert.throws(()=>f.pending.readNativeTimeval(op,{identity:'native:a'}));
});
