import test from 'node:test';
import assert from 'node:assert/strict';
import {createPlayerChoiceActors} from '../deploy/player_choice_actors.mjs';

// Actor-provider fixtures test browser ownership/async boundaries, not native
// body recovery. Real geometry/poses and actual browsers are verified separately.
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const record=(key='human-female',id='one',profession=1)=>({id,profession,sourceAvatar:{format:'oc2-web-source-avatar-v1',key,race:0,gender:1,sourceModelId:32,appearance:{hair:1,face:0}}});
const fixtures=()=>{const views=[];return{views,create:p=>{const view={body:{id:p.id},applied:[],disposals:0,apply(next){view.applied.push(next.id);},dispose(){view.disposals++;},inspect:()=>({id:p.id})};views.push(view);return view;}};};
test('only the selected provider loads; same-body actors keep independent bodies and reuse its resource factory',async()=>{
 const f=fixtures(),loads=[],legacy=fixtures(),actors=createPlayerChoiceActors({bodyKeys:['human-female','elf-female'],loadBody:async key=>{loads.push(key);return f.create;},createLegacy:legacy.create});
 const [a,b]=await Promise.all([actors.create(record()),actors.create(record('human-female','two',3))]);
 assert.deepEqual(loads,['human-female']);assert.notEqual(a.body,b.body);assert.equal(legacy.views.length,0);
 a.apply(record());b.apply(record('human-female','two',3));assert.deepEqual(f.views.map(v=>v.applied),[['one'],['two']]);
 a.dispose();a.dispose();assert.equal(f.views[0].disposals,1);assert.equal(f.views[1].disposals,0);b.dispose();
});
test('a disconnected request never creates a body when its resource load finishes late',async()=>{
 const pending=deferred(),f=fixtures();let current=true;
 const actors=createPlayerChoiceActors({bodyKeys:['human-female'],loadBody:()=>pending.promise,createLegacy:()=>{throw Error('No fallback');}});
 const creating=actors.create(record(),{current:()=>current});current=false;pending.resolve(f.create);
 assert.equal(await creating,null);assert.equal(f.views.length,0);
});
test('a body created after a character switch is disposed and never returned for attachment',async()=>{
 const pending=deferred(),f=fixtures();let current=true;
 const actors=createPlayerChoiceActors({bodyKeys:['human-female'],loadBody:async()=>async p=>{const v=f.create(p);await pending.promise;return v;},createLegacy:()=>{throw Error('No fallback');}});
 const creating=actors.create(record(),{current:()=>current});await new Promise(ok=>setImmediate(ok));
 current=false;pending.resolve();assert.equal(await creating,null);assert.equal(f.views[0].disposals,1);
});
test('identity is captured before async work, while display name, position and object key order can change',async()=>{
 const pending=deferred(),f=fixtures(),actors=createPlayerChoiceActors({bodyKeys:['human-female'],loadBody:()=>pending.promise,createLegacy:f.create});
 const p=record(),creating=actors.create(p);p.profession=2;pending.resolve(f.create);const a=await creating;
 assert.throws(()=>a.apply(p),/identity changed/);
 const next=record();next.name='new display';next.x=23;next.sourceAvatar.appearance={face:0,hair:1};
 a.apply(next);assert.deepEqual(f.views[0].applied,['one']);a.dispose();assert.throws(()=>a.apply(next));
});
test('unsupported/mislabelled source bodies never fall back to the legacy elf actor',async()=>{
 const f=fixtures(),actors=createPlayerChoiceActors({bodyKeys:['human-female'],loadBody:async()=>f.create,createLegacy:f.create});
 const p=record();p.sourceAvatar.key='orc-female';assert.equal(actors.supports(p),false);await assert.rejects(actors.create(p));
 const q=record();q.sourceAvatar=null;assert.equal(actors.supports(q),false);await assert.rejects(actors.create(q));assert.equal(f.views.length,0);
 const old={id:'legacy',profession:3},a=await actors.create(old);assert.equal(a.source,false);a.apply({...old,x:2});a.dispose();
});
test('provider load failures may retry, but two actors can never own a shared body',async()=>{
 const f=fixtures();let attempts=0;
 const actors=createPlayerChoiceActors({bodyKeys:['human-female'],loadBody:async()=>{if(++attempts===1)throw Error('Fixture load failed');return f.create;},createLegacy:f.create});
 await assert.rejects(actors.create(record()),/Fixture load failed/);const a=await actors.create(record());assert.equal(attempts,2);a.dispose();
 const body={},shared=fixtures(),v=shared.create(record());v.body=body;
 const bad=createPlayerChoiceActors({bodyKeys:['human-female'],loadBody:async()=>()=>v,createLegacy:()=>v});
 const first=await bad.create(record());await assert.rejects(bad.create(record('human-female','two')),/cannot be shared/);
 assert.equal(v.disposals,0);first.dispose();assert.equal(v.disposals,1);
});

test('prototype names and coerced keys cannot become original body providers',async()=>{
 const f=fixtures(),options={loadBody:async()=>f.create,createLegacy:f.create};
 for(const key of ['__proto__','constructor','toString',{toString:()=> 'human-female'}]){
  assert.throws(()=>createPlayerChoiceActors({...options,bodyKeys:[key]}));
 }
 const actors=createPlayerChoiceActors({...options,bodyKeys:['human-female']});
 for(const key of ['__proto__','constructor','toString']){
  const p={id:'bad',profession:1,sourceAvatar:{format:'oc2-web-source-avatar-v1',key}};
  assert.equal(actors.supports(p),false);await assert.rejects(actors.create(p));
 }
 assert.equal(f.views.length,0);
});

test('invalid allocated views and thrown lifecycle predicates release their own body',async()=>{
 const f=fixtures();let mode='invalid';
 const actors=createPlayerChoiceActors({bodyKeys:['human-female'],loadBody:async()=>p=>{
  const view=f.create(p);if(mode==='invalid')delete view.apply;return view;
 },createLegacy:f.create});
 await assert.rejects(actors.create(record()),/Complete independent/);assert.equal(f.views[0].disposals,1);
 mode='valid';let checks=0;
 await assert.rejects(actors.create(record(),{current:()=>{if(++checks===3)throw Error('Lifecycle failed');return true;}}),/Lifecycle failed/);
 assert.equal(f.views[1].disposals,1);
 assert.equal(checks,3);
});
