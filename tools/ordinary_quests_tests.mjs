import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,rmSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {OrdinaryQuestLedger,checkOrdinaryQuestProfile} from '../deploy/ordinary_quests.mjs';

// Authored transport fixtures. No original table rows, text or artwork in Git.
const A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
function profile(){return {format:'oc2-compatible-ordinary-quests-v1',originalServerRecovered:false,mapId:1,
  actors:[{id:'npc:10',entry:10,mapId:1,position:[0,0,0],range:3}],
  objects:[1,2,3,4,5].map(n=>({id:'object:'+n,entry:20,mapId:1,position:[n,0,0],range:2})),
  quests:[{id:1,sourceScript:'',minLevel:1,title:'fixture',detail:'detail',objectiveText:'collect',incomplete:'not yet',completion:'done',
    startActor:'npc:10',finishActor:'npc:10',prerequisites:[],removeQuests:[],finishSourceType:6,takeBackAll:true,
    collect:{itemId:30,count:4,sourceType:2,sourceIndex:1,text:'fixture target',objectIds:[1,2,3,4,5].map(n=>'object:'+n)},
    reward:{money:2,xp:3,favor:4,items:[{id:40,count:1,guaranteed:true}]}}]};}
const context=(id=A,position=[0,0,0])=>({characterId:id,mapId:1,position,level:1,alive:true,inspector:false});
const act=(ledger,type,extra={},ctx=context())=>ledger.act(ctx,{type,questId:1,revision:ledger.snapshot(ctx.characterId).revision,...extra});
function ready(ledger,id=A){act(ledger,'accept',{},context(id));for(let n=1;n<=4;n++)act(ledger,'collect',{objectId:'object:'+n},context(id,[n,0,0]));}

test('viewing a quest does not accept it, create records, or write a file',()=>{
  const dir=mkdtempSync(join(tmpdir(),'oc2-quests-'));try{
    const file=join(dir,'quests.json'),ledger=new OrdinaryQuestLedger(profile(),{saveFile:file});
    assert.equal(ledger.query(context(),1).Status,6);assert.deepEqual(ledger.snapshot(A).quests,[]);
    assert.equal(existsSync(file),false);assert.deepEqual(ledger.roles,{});
  }finally{rmSync(dir,{recursive:true,force:true});}
});
test('accept, collect four distinct objects, return items, grant rewards exactly once, restart',()=>{
  const dir=mkdtempSync(join(tmpdir(),'oc2-quests-'));try{
    const file=join(dir,'quests.json');let ledger=new OrdinaryQuestLedger(profile(),{saveFile:file});
    ready(ledger);assert.equal(ledger.query(context(),1).Status,9);
    assert.deepEqual(ledger.snapshot(A).inventory,{'30':4});
    const revision=ledger.snapshot(A).revision;act(ledger,'complete');
    assert.deepEqual(ledger.snapshot(A).rewards,{xp:3,money:2,favor:4,items:{'40':1}});
    assert.deepEqual(ledger.snapshot(A).inventory,{});assert.equal(ledger.query(context(),1).Status,0);
    assert.throws(()=>ledger.act(context(),{type:'complete',questId:1,revision}),/状态已更新/);
    assert.throws(()=>act(ledger,'complete'),/尚未完成或已经交付/);
    ledger=new OrdinaryQuestLedger(profile(),{saveFile:file});
    assert.deepEqual(ledger.snapshot(A).rewards,{xp:3,money:2,favor:4,items:{'40':1}});
    assert.throws(()=>act(ledger,'accept'),/已经接取或完成/);
  }finally{rmSync(dir,{recursive:true,force:true});}
});
test('each character has independent progress and collection rights',()=>{
  const ledger=new OrdinaryQuestLedger(profile());ready(ledger,A);
  assert.deepEqual(ledger.snapshot(B).quests,[]);assert.equal(ledger.query(context(B),1).Status,6);
  ready(ledger,B);act(ledger,'complete',{},context(B));
  assert.equal(ledger.query(context(A),1).Status,9);assert.equal(ledger.snapshot(A).rewards.xp,0);
  assert.equal(ledger.snapshot(B).rewards.xp,3);
});
test('wrong map, distance, vertical floor, dead and inspector cannot interact',()=>{
  const ledger=new OrdinaryQuestLedger(profile());
  for(const patch of [{mapId:5},{position:[100,0,0]},{position:[0,-20,0]},{alive:false},{inspector:true}]){
    assert.throws(()=>act(ledger,'accept',{}, {...context(),...patch}));
    assert.equal(ledger.snapshot(A).revision,0);
  }
});
test('unaccepted, foreign, duplicate and premature actions leave state unchanged',()=>{
  const ledger=new OrdinaryQuestLedger(profile());
  assert.throws(()=>act(ledger,'collect',{objectId:'object:1'}),/先接取/);
  act(ledger,'accept');assert.throws(()=>act(ledger,'complete'),/尚未完成/);
  assert.throws(()=>act(ledger,'collect',{objectId:'object:99'}),/不属于/);
  act(ledger,'collect',{objectId:'object:1'});
  assert.throws(()=>act(ledger,'collect',{objectId:'object:1'}),/已经收集/);
  assert.equal(ledger.snapshot(A).inventory['30'],1);
});
test('abandon clears only this unfinished task and its carried items; reaccept is explicit',()=>{
  const ledger=new OrdinaryQuestLedger(profile());act(ledger,'accept');act(ledger,'collect',{objectId:'object:1'});
  act(ledger,'abandon');assert.deepEqual(ledger.snapshot(A).inventory,{});assert.equal(ledger.query(context(),1).Status,6);
  ready(ledger);act(ledger,'complete');assert.throws(()=>act(ledger,'abandon'),/没有可放弃/);
});
test('failed durable write does not mark completion or grant any reward',()=>{
  let failure=false;const ledger=new OrdinaryQuestLedger(profile(),{write:()=>{if(failure)throw Error('disk full');}});
  ready(ledger);const before=ledger.snapshot(A);failure=true;
  assert.throws(()=>act(ledger,'complete'),/disk full/);assert.deepEqual(ledger.snapshot(A),before);
  failure=false;act(ledger,'complete');assert.equal(ledger.snapshot(A).rewards.money,2);
});
test('corrupt or forged reward totals are rejected without rewriting the file',()=>{
  const dir=mkdtempSync(join(tmpdir(),'oc2-quests-'));try{
    const file=join(dir,'quests.json'),ledger=new OrdinaryQuestLedger(profile(),{saveFile:file});ready(ledger);
    const forged=JSON.parse(readFileSync(file,'utf8'));forged.roles[A].rewards.money=1000;
    writeFileSync(file,JSON.stringify(forged));const before=readFileSync(file);
    assert.throws(()=>new OrdinaryQuestLedger(profile(),{saveFile:file}),/奖励总计/);assert.deepEqual(readFileSync(file),before);
  }finally{rmSync(dir,{recursive:true,force:true});}
});
test('profile mutation, unsupported scripts, missing objects and unproved reward modes cannot enable quests',()=>{
  const p=profile(),ledger=new OrdinaryQuestLedger(p);p.quests[0].reward.money=1000;
  ready(ledger);act(ledger,'complete');assert.equal(ledger.snapshot(A).rewards.money,2);
  const scripted=profile();scripted.quests[0].sourceScript='missing-body';assert.throws(()=>checkOrdinaryQuestProfile(scripted));
  const missing=profile();missing.objects=[];assert.throws(()=>checkOrdinaryQuestProfile(missing));
  const unknown=profile();delete unknown.quests[0].reward.items[0].guaranteed;assert.throws(()=>checkOrdinaryQuestProfile(unknown));
});
test('level and original prerequisite gates cannot be bypassed by action type',()=>{
  const ledger=new OrdinaryQuestLedger(profile());assert.throws(()=>act(ledger,'accept',{}, {...context(),level:0}),/等级不足/);
  const p=profile();p.quests[0].prerequisites=[2];const gated=new OrdinaryQuestLedger(p);
  assert.throws(()=>act(gated,'accept'),/原前置/);assert.equal(gated.snapshot(A).revision,0);
});
