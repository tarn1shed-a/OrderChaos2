// Session tests use explicit fake AS/HTTP ports. They verify transport guards,
// not original AVM execution, artwork, or native/server task approvals.
import test from 'node:test';
import assert from 'node:assert/strict';
import {journalRows,journalDetail,createJournalController,JOURNAL_FORMAT}from'../deploy/quest_journal_state.mjs';
const profile={format:JOURNAL_FORMAT,questId:461,mapId:1,displayLevel:2,questType:2,
  sourceSHA256:'bd5c5a2d392dd63b872104148a74e075f8ec05c887a246015490ed16c95bf851',
  methods:{getQuestList:'4a61cda6e462fc9916af21bb18b4277491eb015ef5c5c14e9d4dd4260c227f13'},
  steps:[{sourceType:2,total:4,text:'Collect fixture',icon:'ui/icons/quest/task_collect.png'},
    {sourceType:6,total:0,text:'Return fixture',icon:'ui/icons/quest/task_talk.png'}],
  reward:{id:20028,count:1,icon:'ui/icons/item/red_skull_plan.png',slotType:9,quality:0}};
const state=(n=0,revision=n)=>({origin:'compatible-quest-layer',mapId:1,revision,
  quests:[{id:461,title:'Fixture',status:n===4?9:4,current:n,required:4}],completedQuestIds:[]});
const empty=(revision=0,completed=false)=>({...state(0,revision),quests:[],completedQuestIds:completed?[461]:[]});
const info=s=>({origin:'compatible-quest-layer',questId:461,revision:s.revision,Status:s.quests[0].status,
  Title:'Fixture',Objective:'Summary',Detail:'Details',progress:{current:s.quests[0].current,required:4},
  hasReward:true,NumGold:9,NumXp:512,NumFever:5,NumAdvExp:0,NumItem:1,NumItemOp:0,
  fixedItems:[{id:20028,count:1,icon:profile.reward.icon,quality:3}]});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(overrides={}){
  let session={connected:true,characterId:'A',epoch:1},snapshot=state(),queries=0,callbacks=[];const actions=[],frames=[],errors=[];
  const f={profile,program:'explicit test AS port',readSession:()=>session,readTrackedQuest:()=>snapshot.quests.length?461:null,
    readState:async()=>structuredClone(snapshot),query:async()=>{queries++;return info(snapshot);},
    action:async c=>{actions.push(c);snapshot=empty(snapshot.revision+1);return{ok:true,state:snapshot};},
    programFactory:async(_program,control)=>({
      abandon(){callbacks.push('question');return{actions:[{boundary:'ShowMsg'}]};},
      messageButton(name){callbacks.push(name);return{actions:name==='onOkClick'?[{boundary:'Hero_AbandonQuest',arguments:[control.rows[control.selectedIndex].questId]}]:[]};}
    }),onChange:v=>frames.push(v),onError:e=>errors.push(e)};
  const controller=createJournalController({...f,...overrides});
  return{controller,f,actions,frames,errors,callbacks,get queries(){return queries;},get snapshot(){return snapshot;},
    set snapshot(v){snapshot=v;},get session(){return session;},set session(v){session=v;}};
}
test('static/available/catalog data cannot become an accepted list',()=>{
  assert.throws(()=>journalRows(profile,{quests:[{id:461}]}));
  assert.throws(()=>journalRows(profile,{...state(),quests:[{...state().quests[0],status:6}]}));
  assert.throws(()=>journalRows(profile,{...state(),completedQuestIds:[461]}));
  assert.deepEqual(journalRows(profile,empty(3,true)),[]);
});
test('display level is the checked field, not MinLevel',()=>{
  const p={...profile,minLevel:0};assert.equal(journalRows(p,state())[0].displayLevel,2);
  assert.throws(()=>journalRows({...p,displayLevel:0},state()));
});
test('actual collect and return phases choose their separate source objectives',()=>{
  const first=journalDetail(profile,state(2),info(state(2)),461);
  assert.deepEqual([first.step.sourceType,first.step.total,first.step.current],[2,4,2]);
  const ready=journalDetail(profile,state(4),info(state(4)),461);
  assert.deepEqual([ready.step.sourceType,ready.step.total,ready.step.current],[6,0,0]);
});
test('type9 reward keeps source quality0 and never exports a fake ActionID',()=>{
  const d=journalDetail(profile,state(),info(state()),461);
  assert.equal(d.rewards.items[0].quality,0);assert.equal(d.rewards.items[0].nativeActionID,null);
  assert.equal(d.nativeMessage,false);assert.equal(d.rewards.items[0].count,1);
});
test('mismatched detail, original item and numeric rewards are refused',()=>{
  for(const bad of [{...info(state()),revision:7},{...info(state()),Status:6},{...info(state()),NumXp:1},
    {...info(state()),fixedItems:[{id:1,count:1,icon:profile.reward.icon}]},
    {...info(state()),progress:{current:3,required:4}}])assert.throws(()=>journalDetail(profile,state(),bad,461));
});
test('open queries only an actual accepted row, empty/completed creates no detail query',async()=>{
  const f=fixture();await f.controller.open();assert.equal(f.queries,1);assert.equal(f.controller.inspect().detail.accepted,true);
  f.snapshot=empty(2,true);f.controller.update(f.snapshot);await settle();assert.equal(f.queries,1);assert.equal(f.controller.inspect().detail,null);
});
test('host state callback during readState does not query twice',async()=>{
  let f;f=fixture({readState:async()=>{f.controller.update(f.snapshot);return f.snapshot;}});
  await f.controller.open();assert.equal(f.queries,1);
});
test('progress refresh replaces old data and completion clears it',async()=>{
  const f=fixture();await f.controller.open();f.snapshot=state(3);f.controller.update(f.snapshot);await settle();
  assert.equal(f.controller.inspect().detail.step.current,3);
  f.snapshot=empty(4,true);f.controller.update(f.snapshot);await settle();assert.equal(f.controller.inspect().rows.length,0);assert.equal(f.actions.length,0);
});
test('old character query cannot reappear in a newer character window',async()=>{
  const old=deferred();let requests=0;const f=fixture({query:()=>++requests===1?old.promise:Promise.resolve(info(state()))});
  const opening=f.controller.open();await settle();f.controller.invalidate();f.session={connected:true,characterId:'B',epoch:2};
  await f.controller.open();old.resolve({...info(state()),Title:'Wrong old character'});await opening;
  assert.equal(f.controller.inspect().detail.title,'Fixture');assert.equal(f.errors.length,0);
});
test('close and reopen same character suppresses an older readState response',async()=>{
  const old=deferred();let requests=0;const f=fixture({readState:()=>++requests===1?old.promise:Promise.resolve(state())});
  const opening=f.controller.open();await settle();f.controller.close();await f.controller.open();old.resolve(empty(9,true));await opening;
  assert.equal(f.controller.inspect().detail.title,'Fixture');
});
test('cancel uses the original cancel port without a game command',async()=>{
  const f=fixture();await f.controller.open();await f.controller.askAbandon();assert.equal(f.controller.inspect().modal,'abandon');
  assert.deepEqual(await f.controller.answerAbandon(false),{sent:false,cancelled:true});assert.deepEqual(f.callbacks,['question','onCancelClick']);assert.equal(f.actions.length,0);
});
test('repeated abandon while source factory is loading cannot reopen a cancelled question',async()=>{
  const wait=deferred();let calls=0;const f=fixture({programFactory:async(...args)=>{calls++;await wait.promise;return f.f.programFactory(...args);}});
  await f.controller.open();const first=f.controller.askAbandon(),second=await f.controller.askAbandon();
  assert.equal(second,null);assert.equal(calls,1);assert.equal(f.controller.inspect().pending,true);
  wait.resolve();await first;assert.equal(f.controller.inspect().pending,false);assert.equal(f.controller.inspect().modal,'abandon');
  await f.controller.answerAbandon(false);await settle();assert.equal(f.controller.inspect().modal,null);assert.deepEqual(f.actions,[]);
});
test('old source-factory error cannot be reported in a newer character session',async()=>{
  const wait=deferred(),f=fixture({programFactory:()=>wait.promise});await f.controller.open();const old=f.controller.askAbandon();
  f.controller.close();f.session={connected:true,characterId:'B',epoch:2};await f.controller.open();wait.reject(Error('Old A source failure'));
  assert.equal(await old,null);assert.equal(f.controller.inspect().modal,null);assert.equal(f.controller.inspect().pending,false);assert.deepEqual(f.errors,[]);
});
test('old same-revision query cannot clear a reopened window pending query',async()=>{
  const oldQuery=deferred(),newQuery=deferred(),newRead=deferred();let reads=0,queries=0;
  const f=fixture({readState:()=>++reads===2?newRead.promise:Promise.resolve(state()),query:()=>++queries===1?oldQuery.promise:newQuery.promise});
  const old=f.controller.open();await settle();f.controller.close();const reopened=f.controller.open();f.controller.update(state());
  oldQuery.resolve(info(state()));await old;newRead.resolve(state());await settle();assert.equal(queries,2);
  newQuery.resolve(info(state()));await reopened;assert.equal(f.controller.inspect().detail.questId,461);
});
test('confirmed intent reaches existing abandon once and clears the accepted view',async()=>{
  const wait=deferred(),f=fixture({action:async c=>{f.actions.push(c);return wait.promise;}});
  await f.controller.open();await f.controller.askAbandon();const answer=f.controller.answerAbandon(true);await settle();
  assert.equal(await f.controller.answerAbandon(true),null);wait.resolve({ok:true,state:empty(1)});await answer;
  assert.deepEqual(f.actions,[{type:'abandon',questId:461,revision:0,origin:'compatible-quest-layer'}]);assert.equal(f.controller.inspect().detail,null);
});
test('changed progress during confirmation cannot abandon with an obsolete revision',async()=>{
  const f=fixture();await f.controller.open();await f.controller.askAbandon();f.snapshot=state(1);
  assert.deepEqual(await f.controller.answerAbandon(true),{sent:false,reason:'state-changed'});assert.equal(f.actions.length,0);assert.equal(f.controller.inspect().detail.step.current,1);
});
test('a new state invalidates an already displayed question',async()=>{
  const f=fixture();await f.controller.open();await f.controller.askAbandon();f.snapshot=state(2);f.controller.update(f.snapshot);await settle();
  assert.equal(f.controller.inspect().modal,null);assert.equal(await f.controller.answerAbandon(true),null);assert.equal(f.actions.length,0);
});
test('character switch while original program hashing is pending discards it',async()=>{
  const wait=deferred(),f=fixture({programFactory:()=>wait.promise});await f.controller.open();const question=f.controller.askAbandon();
  f.session={connected:true,characterId:'B',epoch:2};f.controller.invalidate();wait.resolve({abandon:()=>{throw Error('stale VM executed');}});
  assert.equal(await question,null);assert.equal(f.controller.inspect().visible,false);
});
test('closing a task book sends no NPC cancel or abandon command',async()=>{
  const f=fixture();await f.controller.open();f.controller.close();assert.equal(f.actions.length,0);assert.equal(f.controller.inspect().visible,false);
});
test('lower revisions are ignored and same-revision contradictory rows rejected',async()=>{
  const f=fixture();f.snapshot=state(2);await f.controller.open();assert.equal(f.controller.update(state(0)),false);
  assert.throws(()=>f.controller.update(state(3,2)));assert.equal(f.controller.inspect().detail.step.current,2);
});
test('refused game command does not clear accepted progress as if it succeeded',async()=>{
  const f=fixture({action:async()=>({ok:false})});await f.controller.open();await f.controller.askAbandon();
  await assert.rejects(()=>f.controller.answerAbandon(true));assert.equal(f.controller.inspect().detail.step.current,0);assert.equal(f.controller.inspect().pending,false);
});
