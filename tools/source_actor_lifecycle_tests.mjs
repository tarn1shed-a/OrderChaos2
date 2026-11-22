// Ownership fixtures only. No original body data, Uc, renderer or network.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createSourceActorLifecycle,createSourceResourceScope} from '../deploy/source_actor_lifecycle.mjs';
import {createPlayerChoiceScene} from '../deploy/player_choice_scene.mjs';

class Session {}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
const record=(id,body='A',profession=1,revision=1)=>({id,profession,sourceAvatar:{key:body},revision});
function view(record,{ready=false,onApply=()=>{},onDispose=()=>{}}={}){
  return{body:{visible:true},ready,disposed:0,applied:[],record,
    apply(next){assert.equal(this.disposed,0);this.applied.push(next);onApply(next);},
    dispose(){this.disposed++;this.body.visible=false;onDispose();},
    inspect(){return{clientReady:this.ready&&this.disposed===0};}};
}
function harness(options={}){
  const created=[],installed=[],removed=[],errors=[];
  const actors={async create(r,ports){const a=options.create?await options.create(r,ports):view(r);if(a)created.push(a);return a;}};
  const core=createSourceActorLifecycle({actors,
    resolve:r=>{if(!['A','B'].includes(r.sourceAvatar?.key))throw Error('Unknown verified fixture');return Object.freeze({definitionKey:'fixture-v1:'+r.sourceAvatar.key});},
    install:(a,r,at)=>{const entry={actor:a,id:r.id,record:r,at};installed.push(entry);options.install?.(entry);return entry;},
    update:(entry,r)=>{entry.actor.apply(r);entry.record=r;options.update?.(entry);},
    remove:entry=>{removed.push(entry);options.remove?.(entry);},
    readReady:entry=>options.readReady?options.readReady(entry):entry.actor.inspect().clientReady,
    onError:error=>errors.push(error)});
  const connection=new Session(),sync=(rows,options={})=>core.sync(rows,1,{current:()=>true,connection,...options});
  return{core,created,installed,removed,errors,connection,sync};
}

test('same world resource joins one pending/ready promise and releases once',async()=>{
  const gate=deferred(),scope=createSourceResourceScope({current:()=>true});let calls=0,releases=0;
  const prepare=async()=>{calls++;return gate.promise;},dispose=()=>releases++;
  const a=scope.load('verified-version-A',prepare,{dispose}),b=scope.load('verified-version-A',prepare,{dispose});
  assert.equal(a,b);await flush();assert.equal(calls,1);assert.equal(scope.inspect().ready,0);
  const input={};gate.resolve(input);assert.equal(await a,input);assert.equal(await b,input);
  assert.equal(await scope.load('verified-version-A',()=>{throw Error('Duplicate prepare');},{dispose}),input);
  assert.equal(scope.inspect().ready,1);scope.dispose();scope.dispose();await scope.drain();assert.equal(releases,1);
});

test('outer overlay inserted before base still releases overlay then base',async()=>{
  const scope=createSourceResourceScope({current:()=>true}),order=[];let baseLive=true;
  await scope.load('overlay',async()=>({base:await scope.load('base',async()=>({}),{priority:0,dispose(){baseLive=false;order.push('base');}})}),
    {priority:1,dispose(){assert.equal(baseLive,true);order.push('overlay');}});
  scope.dispose();assert.deepEqual(order,['overlay','base']);await scope.drain();
});

test('failed shared prepare is evicted and an explicit later load can retry',async()=>{
  const scope=createSourceResourceScope({current:()=>true});let attempts=0;
  const prepare=async()=>{if(++attempts===1)throw Error('Bad SHA');return{};};
  await assert.rejects(scope.load('A',prepare,{dispose(){}}),/Bad SHA/);
  assert.equal(scope.inspect().ready,0);assert.equal(scope.inspect().entries.length,0);
  await scope.load('A',prepare,{dispose(){}});assert.equal(attempts,2);scope.dispose();
});

test('world dispose before prepare starts never calls loader',async()=>{
  let calls=0;const scope=createSourceResourceScope({current:()=>true});
  const promise=scope.load('A',()=>{calls++;return{};},{dispose(){}});scope.dispose();
  await assert.rejects(promise,{name:'AbortError'});await scope.drain();assert.equal(calls,0);
});

test('expired world or dispose reclaims a late value without fake readiness',async()=>{
  for(const expire of ['owner','dispose']){
    let current=true,releases=0,signal;const gate=deferred(),scope=createSourceResourceScope({current:()=>current});
    const p=scope.load('A',async ports=>{signal=ports.signal;return gate.promise;},{dispose:()=>releases++});await flush();
    if(expire==='owner')current=false;else scope.dispose();
    const rejected=assert.rejects(p,{name:'AbortError'});gate.resolve({});await rejected;
    assert.equal(releases,1);assert.equal(scope.inspect().ready,0);assert.equal(signal.aborted,expire==='dispose');
    scope.dispose();await scope.drain();assert.equal(releases,1);
  }
});

test('all ready resources release even when one cleanup throws; late faults remain observable',async()=>{
  const order=[],scope=createSourceResourceScope({current:()=>true});
  await scope.load('base',async()=>({}),{dispose:()=>order.push('base')});
  await scope.load('overlay',async()=>({}),{priority:1,dispose(){order.push('overlay');throw Error('cleanup');}});
  assert.throws(()=>scope.dispose(),AggregateError);assert.deepEqual(order,['overlay','base']);assert.equal(scope.dispose(),false);
  await assert.rejects(scope.drain(),AggregateError);
  const gate=deferred(),late=createSourceResourceScope({current:()=>true});
  const p=late.load('late',()=>gate.promise,{dispose(){throw Error('late cleanup');}});await flush();late.dispose();
  const rejected=assert.rejects(p,/late cleanup/);gate.resolve({});await rejected;await assert.rejects(late.drain(),AggregateError);
});

test('one resource identity cannot silently change release priority',async()=>{
  const scope=createSourceResourceScope({current:()=>true});await scope.load('A',async()=>({}),{dispose(){},priority:1});
  assert.throws(()=>scope.load('A',async()=>({}),{dispose(){},priority:0}),/priority/);scope.dispose();
});

test('owner-check exception after prepare still releases the returned resource',async()=>{
  let throwOwner=false,releases=0;
  const scope=createSourceResourceScope({current:()=>{if(throwOwner)throw Error('Owner unavailable');return true;}});
  await assert.rejects(scope.load('A',async()=>{throwOwner=true;return{};},{dispose:()=>releases++}),/Owner unavailable/);
  assert.equal(releases,1);throwOwner=false;scope.dispose();await scope.drain();assert.equal(releases,1);
});

test('actual readiness rather than resolved factory promise controls Playable',async()=>{
  const h=harness();await h.sync([record('A')]);
  assert.equal(h.core.inspectLifecycle().states[0].state,'AuthorityBound');assert.equal(h.core.isPlayable('A'),false);
  h.created[0].ready=true;h.core.refreshReadiness();assert.equal(h.core.isPlayable('A'),true);
  h.created[0].ready=false;h.core.refreshReadiness();assert.equal(h.core.isPlayable('A'),false);
  h.core.clear();assert.deepEqual(h.core.inspect(),{actors:0,pending:0,epoch:1});assert.equal(h.created[0].disposed,1);
});

test('same actor pending mount consumes newest snapshot with one factory call',async()=>{
  const gate=deferred();let calls=0;
  const h=harness({create:async r=>{calls++;await gate.promise;return view(r);}});
  const a=h.sync([record('id','A',1,1)]);await flush();const b=h.sync([record('id','A',1,2)]);await flush();
  assert.equal(h.core.inspectLifecycle().states[0].state,'DataResolved');gate.resolve();await Promise.all([a,b]);
  assert.equal(calls,1);assert.equal(h.installed.length,1);assert.equal(h.installed[0].record.revision,2);
  assert(h.created[0].applied.every(r=>r.revision===2));h.core.dispose();
});

test('same id changed definition supersedes pending creation without waiting for old load',async()=>{
  const gate=deferred();const h=harness({create:async r=>{if(r.sourceAvatar.key==='A')await gate.promise;return view(r);}});
  const old=h.sync([record('same','A')]);await flush();await h.sync([record('same','B')]);
  assert.equal(h.installed.length,1);assert.equal(h.installed[0].record.sourceAvatar.key,'B');
  gate.resolve();await old;assert.equal(h.installed.length,1);assert.equal(h.created.find(v=>v.record.sourceAvatar.key==='A').disposed,1);
  assert.equal(h.core.inspect().actors,1);h.core.dispose();
});

test('live definition or profession changes release old view and use the same adapter again',async()=>{
  const h=harness();await h.sync([record('same','A',1)]);const first=h.created[0];
  await h.sync([record('same','A',3)]);assert.equal(first.disposed,1);assert.equal(h.created.length,2);
  await h.sync([record('same','B',3)]);assert.equal(h.created[1].disposed,1);assert.equal(h.created.length,3);
  assert.equal(h.core.inspect().actors,1);h.core.dispose();
});

test('actual new connection cancels old pending work even for identical actor definition',async()=>{
  const gate=deferred();let calls=0;
  const h=harness({create:async r=>{if(++calls===1)await gate.promise;return view(r);}});
  const old=h.sync([record('same')]);await flush();await h.sync([record('same')],{connection:new Session()});
  gate.resolve();await old;assert.equal(h.installed.length,1);assert.equal(h.created.at(-1).disposed,1);
  assert.equal(h.core.inspect().actors,1);h.core.dispose();
});

test('a later current callback cannot reauthorize an earlier pending job',async()=>{
  const gate=deferred();let oldCurrent=true,calls=0;
  const h=harness({create:async r=>{if(++calls===1)await gate.promise;return view(r);}});
  const old=h.sync([record('same')],{current:()=>oldCurrent});await flush();oldCurrent=false;
  await h.sync([record('same')],{current:()=>true});gate.resolve();await old;
  assert.equal(h.installed.length,1);assert.equal(h.created.at(-1).disposed,1);assert.deepEqual(h.errors,[]);h.core.dispose();
});

test('departed remote rejection does not report failure against the surviving local actor',async()=>{
  const gate=deferred();const h=harness({create:async r=>{if(r.id==='remote')await gate.promise;return view(r);}});
  const old=h.sync([record('own'),record('remote')]);await flush();await h.sync([record('own')]);
  gate.reject(Error('late resource failure'));await old;assert.deepEqual(h.errors,[]);assert.equal(h.core.inspect().actors,1);h.core.dispose();
});

test('late async factory that makes a body visible after clear must be actually disposed',async()=>{
  const gate=deferred();let late;
  const h=harness({create:async r=>{await gate.promise;late=view(r);late.body.visible=true;return late;}});
  const job=h.sync([record('old')]);await flush();h.core.clear();
  assert.equal(h.core.inspect().pending,0);assert.equal(h.core.inspectLifecycle().cancelledInflight,1);
  gate.resolve();await job;await h.core.drain();assert.equal(late.body.visible,false);assert.equal(late.disposed,1);
  assert.equal(h.installed.length,0);assert.equal(h.core.inspectLifecycle().inflight,0);
});

test('cancel during apply cannot enter install, and cancel during install removes the mount',async()=>{
  let h;
  h=harness({create:async r=>view(r,{onApply:()=>h.core.clear()})});await h.sync([record('A')]);
  assert.equal(h.installed.length,0);assert.equal(h.created[0].disposed,1);
  h=harness({install:()=>h.core.clear()});await h.sync([record('A')]);
  assert.equal(h.created[0].body.visible,false);assert.equal(h.removed.length,1);assert.equal(h.core.inspect().actors,0);
});

test('clear releases every actor and removes every entry despite cleanup exceptions',async()=>{
  const h=harness({create:async r=>view(r,{onDispose(){throw Error('dispose '+r.id);}}),remove(){throw Error('remove');}});
  await h.sync([record('A'),record('B')]);assert.throws(()=>h.core.clear(),AggregateError);
  assert.equal(h.created.filter(v=>v.disposed===1).length,2);assert.equal(h.removed.length,2);
  assert.equal(h.core.inspect().actors,0);await assert.rejects(h.core.drain(),AggregateError);
});

test('active update failure cleans mounted entry and reports only once to all waiters',async()=>{
  const gate=deferred(),error=Error('bad actual pose');
  const h=harness({create:async r=>{await gate.promise;return view(r);},update(){throw error;}});
  const first=h.sync([record('A')]);await flush();const second=h.sync([record('A')]);
  const checks=Promise.all([assert.rejects(first,/bad actual pose/),assert.rejects(second,/bad actual pose/)]);gate.resolve();await checks;
  assert.equal(h.errors.length,1);assert.equal(h.removed.length,1);assert.equal(h.created[0].disposed,1);
});

test('invalid definition/duplicates are rejected before removing a valid scene',async()=>{
  const h=harness();await h.sync([record('own')]);
  await assert.rejects(h.sync([record('new','unregistered')]),/verified fixture/);
  await assert.rejects(h.sync([record('x'),record('x')]),/Distinct/);
  assert.equal(h.created[0].disposed,0);assert.equal(h.core.inspect().actors,1);
  await assert.rejects(h.core.sync([],1,{current:()=>true,connection:{}}),/connection/);h.core.dispose();
});

test('already live update or readiness failures release the bound actor',async()=>{
  let failUpdate=false;
  const h=harness({update(){if(failUpdate)throw Error('Invalid subsequent pose');}});
  await h.sync([record('A')]);failUpdate=true;
  await assert.rejects(h.sync([record('A','A',1,2)]),/subsequent pose/);
  assert.equal(h.created[0].disposed,1);assert.equal(h.removed.length,1);assert.equal(h.core.inspect().actors,0);
  let failReady=false;
  const next=harness({readReady(){if(failReady)throw Error('Readiness failed');return false;}});
  await next.sync([record('A')]);failReady=true;
  assert.throws(()=>next.core.refreshReadiness(),/Readiness failed/);
  assert.equal(next.created[0].disposed,1);assert.equal(next.core.inspect().actors,0);
});

test('owner-check exception after actor creation cannot leak the created view',async()=>{
  let failOwner=false;const h=harness({create:async r=>{failOwner=true;return view(r);}});
  await assert.rejects(h.sync([record('A')],{current:()=>{if(failOwner)throw Error('Actor owner unavailable');return true;}}),/owner check failed/);
  assert.equal(h.created[0].disposed,1);assert.equal(h.created[0].body.visible,false);assert.equal(h.core.inspect().actors,0);
});

test('20 quick session switches release 19 late mounts and never install stale actors',async()=>{
  const gates=[],waiters=[];const h=harness({create:async r=>{const gate=deferred();gates.push(gate);await gate.promise;return view(r);}});
  for(let i=0;i<20;i++){waiters.push(h.sync([record('same',i%2?'A':'B',i%5+1,i)],{connection:new Session()}));await flush();}
  assert.equal(gates.length,20);for(let i=19;i>=0;i--){gates[i].resolve();await flush();}
  await Promise.all(waiters);assert.equal(h.installed.length,1);assert.equal(h.installed[0].record.revision,19);
  assert.equal(h.created.filter(v=>v.disposed===1).length,19);assert.equal(h.core.inspect().actors,1);
  h.core.dispose();await h.core.drain();assert.equal(h.created.filter(v=>v.disposed===1).length,20);
});

test('actor cancellation does not abort a peer shared world load or release factory backing',async()=>{
  const gate=deferred(),scope=createSourceResourceScope({current:()=>true});let loads=0,releases=0,worldSignal;
  const h=harness({create:async r=>{
    await scope.load('same-verified-input',async({signal})=>{loads++;worldSignal=signal;return gate.promise;},{dispose:()=>releases++});
    return view(r);
  }});
  const old=h.sync([record('A'),record('B')]);await flush();const survivor=h.sync([record('B')]);
  assert.equal(loads,1);assert.equal(worldSignal.aborted,false);gate.resolve({});await Promise.all([old,survivor]);
  assert.deepEqual(h.installed.map(v=>v.id),['B']);assert.equal(releases,0);
  h.core.clear();assert.equal(releases,0);scope.dispose();await scope.drain();assert.equal(releases,1);
});

test('legacy scene inspection shape remains exact and clear-only scope is not called session bound',async()=>{
  const made=[],scene=createPlayerChoiceScene({actors:{async create(r){const a=view(r);made.push(a);return a;}},
    install:actor=>({actor}),update:(e,r)=>e.actor.apply(r),remove(){}});
  await scene.sync([record('A')],1);assert.deepEqual(scene.inspect(),{actors:1,pending:0,epoch:0});
  assert.equal(scene.inspectLifecycle().connectionBound,false);assert.equal(scene.isPlayable('A'),false);
  scene.clear();assert.deepEqual(scene.inspect(),{actors:0,pending:0,epoch:1});assert.equal(made[0].disposed,1);
  await scene.sync([record('A')],2,{current:()=>true,connection:new Session()});
  assert.equal(scene.inspectLifecycle().connectionBound,true);scene.dispose();await scene.drain();
});
