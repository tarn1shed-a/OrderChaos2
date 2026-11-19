import test from 'node:test';
import assert from 'node:assert/strict';
import {createHumanFemalePendingJoins,HUMAN_FEMALE_POLICY} from './world_admission/human_female.mjs';

function fixture({clock=()=>100,prepareJoin=null,step=true,acceptFailure=false}={}){
 const policy=HUMAN_FEMALE_POLICY,registry={count:45,check:()=>({key:'human-female',sourceModelId:32})};
 const record={id:'a',profession:1,sourceAvatar:{key:'human-female'},sourceInventoryPolicy:'empty-compatible-container-v1',hotbar:null,inventory:{},equipment:{hand:null}},player={id:'a',profession:1,sourceAvatar:{key:'human-female'}};
 const ws={readyState:1,character:record,player,input:{},world:{}},active=new Map(),room=new Map(),rooms=new Map(),store={records:new Map([['a',record]])};
 let ready,advances=0,forgotten=0;const rejected=[],faults=[];
 const pending=createHumanFemalePendingJoins({registry,policy,clock,prepareJoin,onFault:error=>faults.push(error),readPreparedBody:()=>({key:'human-female',ready:true,pose:{field:'sourceFemalePose',bindingId:policy.bindingId,valueBytes:1928}}),readNativeReady:()=>ready});
 ws.motion={move(p=player){advances++;const owner=pending.readOwner(p,'native:a');ready={actorKey:p.id,identity:'native:a',generation:owner.generation,roomKey:'room',mapId:1,sourceModelId:32,bindingId:policy.bindingId,valueBytes:1928,sourceMotion:policy.motionSHA256,actualNativeActorAndConsumedPose:true};},forget(){forgotten++;}};
 pending.attach({store,active,rooms,combatRooms:new Map(),clock,reject(ws,message){if(!acceptFailure)throw Error('Unexpected rejection');rejected.push(message);},storageFailure(){throw Error('Unexpected storage failure');},gate:{join:()=>true,forget(){}}});
 const message={scene:'resources',mapWindow:'heaven-landing',profession:1};
 pending.stage(ws,{room,roomKey:'room',message,commit(){active.set('a',ws);room.set('a',ws);rooms.set('room',room);}});
 if(step)pending.step(1);
 return {pending,ws,record,player,active,room,rooms,store,message,rejected,faults,advances:()=>advances,forgotten:()=>forgotten};
}
test('active source uses the one existing movement callback',()=>{const f=fixture();let calls=0;f.pending.withMotion(f.ws,2,()=>calls++);assert.equal(calls,1);assert.equal(f.advances(),1);});
for(const readyState of [2,3])test('closing state '+readyState+' skips final native tick and forgets its actual actor once',()=>{const f=fixture();f.ws.readyState=readyState;let calls=0;assert.doesNotThrow(()=>f.pending.withMotion(f.ws,2,()=>calls++));assert.equal(calls,0);assert.equal(f.advances(),1);assert.equal(f.pending.readOwner(f.player,'native:a'),null);f.pending.close(f.ws);assert.equal(f.pending.inspect().trackedCharacters,0);assert.equal(f.forgotten(),1);f.pending.close(f.ws);assert.equal(f.forgotten(),1);});
test('active close forgets before retiring owner without hiding the final position from the server',()=>{
 const f=fixture(),forget=f.ws.motion.forget;let seen;
 f.ws.motion.forget=p=>{seen=p;assert.equal(f.active.get(f.record.id),f.ws);assert.equal(f.room.get(f.record.id),f.ws);forget(p);};
 f.ws.readyState=3;f.pending.close(f.ws);
 assert.equal(seen,f.player);assert.equal(f.forgotten(),1);
 assert.equal(f.pending.readOwner(f.player,'native:a'),null);assert.equal(f.pending.capability(f.record),null);
 // These are the actual maps read by the unchanged server close/save path.
 assert.equal(f.active.get(f.record.id),f.ws);assert.equal(f.room.get(f.record.id),f.ws);assert.equal(f.rooms.get('room'),f.room);
 f.pending.dispose();f.pending.close(f.ws);assert.equal(f.forgotten(),1);
});
test('late close from a retired generation cannot forget or replace the newly joined actor',()=>{
 const f=fixture(),oldOwner=f.pending.readOwner(f.player,'native:a');
 f.ws.readyState=3;f.pending.close(f.ws);
 // The existing server completes its own membership cleanup after close().
 f.active.delete('a');f.room.delete('a');f.rooms.delete('room');
 const player={...f.player},ws={...f.ws,readyState:1,player};
 f.pending.stage(ws,{room:f.room,roomKey:'room',message:f.message,commit(){f.active.set('a',ws);f.room.set('a',ws);f.rooms.set('room',f.room);}});
 f.pending.step(2);const owner=f.pending.readOwner(player,'native:a');
 assert.ok(owner.generation>oldOwner.generation);assert.equal(f.active.get('a'),ws);
 f.pending.close(f.ws);assert.equal(f.forgotten(),1);assert.equal(f.pending.readOwner(f.player,'native:a'),null);
 assert.equal(f.pending.readOwner(player,'native:a').generation,owner.generation);assert.equal(f.pending.capability(f.record).generation,owner.generation);
 ws.readyState=3;f.pending.close(ws);assert.equal(f.forgotten(),2);f.pending.close(ws);assert.equal(f.forgotten(),2);
});
test('failed active forget reports the fault and lets original server save and cleanup continue',()=>{
 const f=fixture();let attempts=0;f.ws.motion.forget=()=>{attempts++;throw Error('fixture native forget failure');};
 f.ws.readyState=3;assert.doesNotThrow(()=>f.pending.close(f.ws));
 assert.equal(attempts,1);assert.equal(f.pending.inspect().trackedCharacters,0);assert.equal(f.pending.readOwner(f.player,'native:a'),null);
 assert.equal(f.faults.length,1);assert.equal(f.faults[0].message,'fixture native forget failure');
 assert.equal(f.active.get('a'),f.ws);assert.equal(f.room.get('a'),f.ws);
 assert.doesNotThrow(()=>f.pending.close(f.ws));assert.equal(attempts,1);assert.equal(f.faults.length,1);
});
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

const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};};
const settled=()=>new Promise(resolve=>setImmediate(resolve));
test('actual asynchronous resources retain the existing reservation without advancing native motion',async()=>{
 const resource=deferred();let received;const f=fixture({step:false,prepareJoin:input=>{received=input;return resource.promise;}});
 f.pending.step(1);await settled();
 assert.equal(received.record,f.record);assert.equal(received.contract.bodyKey,'human-female');
 assert.equal(f.pending.count('room'),1);assert.equal(f.pending.totalNewRooms(),1);assert.equal(f.pending.entryActiveView(f.active).has('a'),true);
 assert.equal(f.advances(),0);assert.equal(f.pending.capability(f.record),null);assert.equal(f.active.size,0);
 resource.resolve(true);await settled();assert.equal(f.advances(),0);
 f.pending.step(2);assert.equal(f.advances(),1);assert.equal(f.pending.count('room'),0);assert.equal(f.active.get('a'),f.ws);assert.ok(f.pending.capability(f.record));
});
test('disconnect during actual preparation cannot later commit or consume a native frame',async()=>{
 const resource=deferred(),f=fixture({step:false,prepareJoin:()=>resource.promise});await settled();
 f.ws.readyState=3;f.pending.close(f.ws);resource.resolve(true);await settled();f.pending.step(2);
 assert.equal(f.advances(),0);assert.equal(f.active.size,0);assert.equal(f.pending.inspect().trackedCharacters,0);assert.equal(f.pending.count('room'),0);assert.equal(f.forgotten(),1);
});
test('late resource completion belongs to its original pending generation',async()=>{
 const resources=[deferred(),deferred()];let calls=0;const f=fixture({step:false,prepareJoin:()=>resources[calls++].promise});await settled();
 f.pending.close(f.ws);const ws={...f.ws,readyState:1};
 f.pending.stage(ws,{room:f.room,roomKey:'room',message:f.message,commit(){f.active.set('a',ws);f.room.set('a',ws);f.rooms.set('room',f.room);}});await settled();
 resources[0].resolve(true);await settled();f.pending.step(2);assert.equal(f.advances(),0);assert.equal(f.active.size,0);assert.equal(f.pending.count('room'),1);
 resources[1].resolve(true);await settled();f.pending.step(3);assert.equal(f.advances(),1);assert.equal(f.active.get('a'),ws);
});
test('resource failure clears the existing reservation and does not poison a later attempt',async()=>{
 const resource=deferred();let calls=0;const f=fixture({step:false,acceptFailure:true,prepareJoin:()=>++calls===1?resource.promise:Promise.resolve(true)});await settled();
 resource.reject(Error('source bytes refused'));await settled();f.pending.step(1);
 assert.equal(f.advances(),0);assert.equal(f.pending.count('room'),0);assert.equal(f.active.size,0);assert.equal(f.rejected.length,1);assert.equal(f.faults[0].message,'source bytes refused');
 f.pending.stage(f.ws,{room:f.room,roomKey:'room',message:f.message,commit(){f.active.set('a',f.ws);}});await settled();f.pending.step(2);assert.equal(f.advances(),1);assert.equal(f.active.get('a'),f.ws);
});
for(const value of [undefined,false,{ready:true}])test('resource completion '+JSON.stringify(value)+' is not an admission receipt',async()=>{
 const f=fixture({step:false,acceptFailure:true,prepareJoin:()=>Promise.resolve(value)});await settled();f.pending.step(1);
 assert.equal(f.advances(),0);assert.equal(f.active.size,0);assert.equal(f.pending.count('room'),0);assert.equal(f.rejected.length,1);
});
test('replaced saved record invalidates an outstanding resource preparation',async()=>{
 const resource=deferred(),f=fixture({step:false,acceptFailure:true,prepareJoin:()=>resource.promise});await settled();
 f.store.records.set('a',{...f.record});resource.resolve(true);await settled();f.pending.step(1);
 assert.equal(f.advances(),0);assert.equal(f.active.size,0);assert.equal(f.rejected.length,1);assert.equal(f.pending.inspect().trackedCharacters,0);
});
