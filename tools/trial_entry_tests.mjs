import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {trialEntryLogical,trialEntryPosition,configureTrialEntry,stageTrialWorld,TRIAL_ENTRY} from '../deploy/tutorial_entry.mjs';
import {trialRoleManager,entryServer} from '../deploy/entry_manage.mjs';
const frame={min:[-2752,114.62,128],max:[-2560,132.35,320],width:1280,height:1280};
function motion(){
  const calls=[],m={sourceNative:true,world:{spawn:{x:900,y:360},speed:32},calls,
    logical:p=>trialEntryLogical(frame),support:(x,z,top)=>{calls.push([x,z,top]);return 135.72999572753906;},
    place:e=>{calls.push({placedHeight:e.worldY});e.worldY=135.72999572753906;e.grounded=true;},fork:motion};return m;
}
test('approved anchor keeps original coordinates and source support height, not highest-floor or invented first-spawn claims',()=>{
 assert.deepEqual(TRIAL_ENTRY.position,[-2594,136,-64]);assert.equal(TRIAL_ENTRY.originalFirstSpawn,false);
 assert.deepEqual(trialEntryLogical(frame),{x:1053.3333333333333,y:-1280});
 const m=motion(),p=trialEntryPosition(m);assert.equal(p.groundY,135.72999572753906);assert.deepEqual(m.calls,[[-2594,-64,141]]);
 for(const bad of [null,{}, {...frame,width:0},{...frame,max:frame.min}])assert.throws(()=>trialEntryLogical(bad));
});
test('configuring/forking world changes no role; old places retain height and spawn supplies source height for fresh join/respawn',()=>{
 const m=motion(),oldSpawn=m.world.spawn;configureTrialEntry(m);assert.deepEqual(oldSpawn,{x:900,y:360});assert.equal(m.world.speed,32);
 const old={x:900,y:360,worldY:172};m.place(old);assert.deepEqual(m.calls.at(-1),{placedHeight:172});
 const fresh={...m.world.spawn,worldY:0};m.place(fresh);assert.deepEqual(m.calls.at(-1),{placedHeight:136});assert.equal(fresh.grounded,true);
 const child=m.fork();assert.deepEqual(child.world.spawn,m.world.spawn);assert.notEqual(child,m);
});
function fixture(){
 const token='a'.repeat(64),own={id:'own',tokenHash:createHash('sha256').update(token).digest('hex'),positions:{camp:{x:1,y:2},resources:{x:900,y:360,groundY:132}},xp:120,inventory:{unique:8},equipment:{hand:'staff'}};
 const other={id:'other',positions:{resources:{x:19,y:20,groundY:172}},xp:99},store={records:new Map([['own',own],['other',other]]),savedAt:1,dirty:false,flush(){this.dirty=false;this.savedAt=2;}};
 const active=new Map(),copies=[],identity={characterId:'own',resumeToken:token,anchor:'cinematic7'};
 const manager=trialRoleManager(store,active,{entryPosition:()=>trialEntryPosition(motion()),backupEntry:r=>copies.push(r)});
 return {own,other,store,active,copies,identity,manager};
}
test('selected-role reset requires ownership and offline state, backs up first, and preserves all non-position data and other roles',()=>{
 const f=fixture(),before=structuredClone(f.own),other=structuredClone(f.other);
 assert.throws(()=>f.manager.returnEntry({...f.identity,resumeToken:'b'.repeat(64)}));
 assert.throws(()=>f.manager.returnEntry({...f.identity,anchor:'other'}));
 f.active.set('own',{});assert.throws(()=>f.manager.returnEntry(f.identity),/在线/);f.active.clear();assert.equal(f.copies.length,0);
 f.manager.returnEntry(f.identity);assert.deepEqual(f.copies,[before]);assert.deepEqual(f.other,other);
 assert.deepEqual(f.own,{...before,positions:{...before.positions,resources:trialEntryPosition(motion())}});
});
test('archive and flush failures preserve complete old record and dirty/save state',()=>{
 for(const fail of ['backup','flush']){
  const f=fixture(),before=structuredClone(f.own);
  const manager=trialRoleManager(f.store,f.active,{entryPosition:()=>trialEntryPosition(motion()),backupEntry:()=>{if(fail==='backup')throw Error('backup failed');}});
  if(fail==='flush')f.store.flush=()=>{throw Error('write failed');};
  assert.throws(()=>manager.returnEntry(f.identity));assert.deepEqual(f.own,before);assert.equal(f.store.dirty,false);assert.equal(f.store.savedAt,1);
 }
});
test('private runtime overlay preserves original files, restore branch and unrelated world; unknown files fail closed',t=>{
 const root=new URL('../analysis/raw/showcase-20261110/running-preview/prototype/',import.meta.url);let source,server;
 try{source=readFileSync(new URL('public/world.js',root),'utf8');server=readFileSync(new URL('server.mjs',root),'utf8');}catch{t.skip('Private reviewed runtime is not in Git');return;}
 const changed=stageTrialWorld(source,frame),p=trialEntryLogical(frame);
 assert.equal(changed.replace(`spawn: { x: ${p.x}, y: ${p.y} }`,'spawn: { x: 900, y: 360 }'),source);
 assert.throws(()=>stageTrialWorld(source+' ',frame),/identity/);
 const patched=entryServer(server,'file:///trace.mjs');assert(patched.includes('restorePosition ? position.x'));assert(patched.includes('sourceWindow?0:index * 35'));
 assert(patched.includes('ws.motion.restoreHeight(ws.player,position.groundY)'));
});
