import assert from 'node:assert/strict';
import {test} from 'node:test';
import {OrdinaryQuestLedger} from '../deploy/ordinary_quests.mjs';
import {createQuestCollection,checkCollectionProfile} from '../deploy/quest_collection.mjs';

const A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',B='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';
// Authored task transport fixtures: no original text, art or complete table rows.
const data=()=>({format:'oc2-compatible-ordinary-quests-v1',originalServerRecovered:false,mapId:1,
 actors:[{id:'npc:1',entry:1,mapId:1,position:[0,0,0],range:3}],
 objects:[1,2,3,4].map(i=>({id:'object:'+i,entry:467,mapId:1,position:[i,0,0],range:2})),
 quests:[{id:461,sourceScript:'',minLevel:1,title:'fixture',detail:'fixture',objectiveText:'fixture',incomplete:'fixture',completion:'fixture',
  startActor:'npc:1',finishActor:'npc:1',prerequisites:[],removeQuests:[],finishSourceType:6,takeBackAll:true,
  collect:{itemId:2,count:4,sourceType:2,sourceIndex:1,text:'fixture',objectIds:[1,2,3,4].map(i=>'object:'+i)},
  reward:{money:2,xp:3,favor:4,items:[{id:3,count:1,guaranteed:true}]}}]});
const profile=()=>({format:'oc2-compatible-461-channel-v1',originalServerRecovered:false,mapId:1,questId:461,objectEntry:467,
 skillProtoId:15,skillChannelTime:1500,isChannel:false,
 programSHA256:'4aed22d400be720600dfa91a4030b6dd7ef3cd43b04728f07f5898d46b134be2',
 visualSHA256:'8b47d8cf5395ae2f60beacc81564b559f1f5f2fe287d262b4f59c07609a1fc0c',
 artSHA256:'6f3f2ae104dc1eb5d659b30136a5137ef2d718a8e7833514490d3218e69e10b3'});
const ctx=(id=A,x=0)=>({characterId:id,mapId:1,level:1,position:[x,0,0],alive:true,inspector:false});
function fixture(){
 let now=0,writes=0,failure=false;
 const ledger=new OrdinaryQuestLedger(data(),{write:()=>{if(failure)throw Error('disk unavailable');writes++;}}),owner={};
 const collection=createQuestCollection({ledger,profile:profile(),clock:()=>now});
 const revision=id=>ledger.snapshot(id).revision;
 const accept=(id=A)=>ledger.act(ctx(id),{questId:461,type:'accept',revision:revision(id)});
 const begin=(id=A,n=1,connection=owner)=>collection.begin(ctx(id,n),connection,{type:'collect-start',questId:461,revision:revision(id),objectId:'object:'+n});
 return {ledger,collection,owner,accept,begin,advance:ms=>now+=ms,writes:()=>writes,fail:value=>failure=value};
}
test('collection timer cannot write, grant early, or bypass the original-data ledger',()=>{
 const f=fixture();f.accept();const before=f.ledger.snapshot(A),writes=f.writes(),cast=f.begin();
 assert.deepEqual(f.ledger.snapshot(A),before);assert.equal(f.writes(),writes);
 assert.deepEqual(f.collection.finish(ctx(A,1),f.owner,cast.id),{pending:true,retryAfterMs:1500});
 f.advance(1499);assert.equal(f.collection.finish(ctx(A,1),f.owner,cast.id).retryAfterMs,1);
 assert.deepEqual(f.ledger.snapshot(A),before);
 f.advance(1);const done=f.collection.finish(ctx(A,1),f.owner,cast.id);
 assert.equal(done.pending,false);assert.equal(done.state.inventory['2'],1);assert.equal(done.state.rewards.xp,0);
 assert.throws(()=>f.collection.finish(ctx(A,1),f.owner,cast.id),/失效/);
});
test('four actual collections, turn-in, and repeat rejection retain one reward commit',()=>{
 const f=fixture();f.accept();
 for(let n=1;n<=4;n++){const cast=f.begin(A,n);f.advance(1500);f.collection.finish(ctx(A,n),f.owner,cast.id);}
 assert.equal(f.ledger.snapshot(A).quests[0].status,9);
 f.ledger.act(ctx(),{type:'complete',questId:461,revision:f.ledger.snapshot(A).revision});
 assert.deepEqual(f.ledger.snapshot(A).rewards,{xp:3,money:2,favor:4,items:{'3':1}});
 assert.throws(()=>f.begin(),/先接取/);
 assert.deepEqual(f.ledger.snapshot(B).inventory,{});
});
test('disconnect/replaced connection and foreign roles cannot finish an old attempt',()=>{
 const f=fixture();f.accept();f.accept(B);const cast=f.begin();f.advance(1500);
 assert.throws(()=>f.collection.finish(ctx(A,1),{},cast.id),/失效/);
 assert.throws(()=>f.collection.finish(ctx(B,1),f.owner,cast.id),/失效/);
 assert.deepEqual(f.ledger.snapshot(A).inventory,{});assert.deepEqual(f.ledger.snapshot(B).inventory,{});
});
test('cancel and supersession cannot cancel or complete a newer attempt',()=>{
 const f=fixture();f.accept();const old=f.begin(),fresh=f.begin();
 f.collection.cancel(ctx(A,1),f.owner,old.id);f.advance(1500);
 assert.throws(()=>f.collection.finish(ctx(A,1),f.owner,old.id),/失效/);
 assert.equal(f.collection.finish(ctx(A,1),f.owner,fresh.id).state.inventory['2'],1);
 const next=f.begin(A,2);f.collection.cancel(ctx(A,2),f.owner,next.id);
 assert.throws(()=>f.collection.finish(ctx(A,2),f.owner,next.id),/失效/);
});
test('out-of-range, death, revision changes and write errors never commit a collection',()=>{
 for(const type of ['distance','death','revision','write']){
  const f=fixture();f.accept();const cast=f.begin(),before=f.ledger.snapshot(A);f.advance(1500);
  let c=ctx(A,1);if(type==='distance')c=ctx(A,30);if(type==='death')c.alive=false;
  if(type==='revision')f.ledger.act(ctx(),{type:'abandon',questId:461,revision:before.revision});
  if(type==='write')f.fail(true);
  assert.throws(()=>f.collection.finish(c,f.owner,cast.id));
  assert.deepEqual(f.ledger.snapshot(A).inventory,{});assert.equal(f.ledger.snapshot(A).rewards.xp,0);
  assert.throws(()=>f.collection.finish(ctx(A,1),f.owner,cast.id),/失效/);
 }
});
test('missing or foreign source configuration never enables other quests or durations',()=>{
 for(const change of [{questId:208},{objectEntry:218},{skillChannelTime:1},{originalServerRecovered:true},{visualSHA256:'0'.repeat(64)}])
  assert.throws(()=>checkCollectionProfile({...profile(),...change}));
 assert.throws(()=>checkCollectionProfile(null));
});
