import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';

// Host ownership fixtures, not original data or a Native/GPU-ready claim.
const sourceFiles=new Map(await Promise.all(['quest_source_players','player_choice_scene','source_actor_lifecycle'].map(async name=>
 ['/__delivery/'+name+'.mjs',await readFile(new URL('./'+name+'.mjs',import.meta.url),'utf8')])));
const keys=['human-female','human-male','elf-male','elf-female','orc-male','orc-female','mendel-male','mendel-female','kartan'];
const modelIDs=Object.fromEntries(keys.map((key,i)=>[key,i+1]));
class Connection {}
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const until=async(check,label)=>{for(let i=0;i<100&&!check();i++)await Promise.resolve();assert.ok(check(),label);};

async function fixture({holdActor=false,holdInputs=false,enabledBodyKeys=['human-female'],ready=true,failInputOnce=false,failInputFor=null}={}){
 const firstInputs=deferred(),firstActor=deferred(),installed=[],removed=[],faults=[],faultInfo=[],views=[],frames=[],releaseOrder=[];
 let inputDisposals=0,hostDisposals=0,loadCalls=0,factoryDisposals=0,hostCreations=0,factoryCreations=0,inputFailed=false;
 const renderer={},scene={},camera={},sourceMap={},origin={},owner={},connection=new Connection(),clock={now:1000};
 let scope={owner,active:true,mapGeneration:1,contextGeneration:1,renderer,scene,sourceMap};
 const inputLoads=[],airLoads=[],signals=[],requests=[];
 const makeInputs=(bodyKey,mode,base=null)=>{let closed=false;return{bodyKey,mode,
  ...(base?{materialInputs:base,sourcePoseContract:{bodyKey,bindingId:'a'.repeat(64)},sourceMotionProfile:{ranges:{idle:{},idle_02:{},run_normal_front:{}}}}:{}),
  dispose(){assert.equal(closed,false);closed=true;inputDisposals++;releaseOrder.push(mode+':'+bodyKey);},
  inspect:()=>({bodyKey,mode,disposed:closed})};};
 const modules={
  '/world-character-common-v1/inputs.mjs':{loadWorldCharacterInputs:async({bodyKey,mode,loadBytes})=>{
   inputLoads.push([bodyKey,mode]);await loadBytes('/fixture/'+bodyKey+'.json');
   if(holdInputs)await firstInputs.promise;return makeInputs(bodyKey,mode);
  }},
  '/world-own-air-actors-v3/inputs.mjs':{loadWorldOwnAirInputs:async({bodyKey,loadGroundInputs})=>{
   airLoads.push(bodyKey);const base=await loadGroundInputs({bodyKey,mode:'ground'});return makeInputs(bodyKey,'own-air',base);
  }},
  '/world-character-peer-v1/material_host.mjs':{createWorldCharacterMaterialHost:async({inputs})=>{
   hostCreations++;assert.equal(inputs.length,1);let closed=false;
   return{dispose(){assert.equal(closed,false);closed=true;hostDisposals++;releaseOrder.push('host');},
    prepareBeforeWorldRender(token){assert.equal(closed,false);frames.push(['before',token]);},
    afterWorldRender(token){assert.equal(closed,false);frames.push(['after',token]);}};
  }},
  '/world-own-air-actors-v3/entry.mjs':{createWorldNormalActorFactory:({loadInputs,ownAirBodyKeys})=>{
   factoryCreations++;let closed=false;
   return Object.assign(async(record,{current,actorEpoch})=>{
    assert.equal(closed,false);await loadInputs({bodyKey:record.sourceAvatar.key,mode:ownAirBodyKeys.includes(record.sourceAvatar.key)?'own-air':'normal15'});
    loadCalls++;if(holdActor)await firstActor.promise;
    const view={body:{id:record.id,visible:true},id:record.id,applied:[],disposals:0,ready,
     apply(next){if(!current())throw Error('stale');if(next.badPose)throw Error('own pose rejected');this.applied.push(next.sequence);},
     dispose(){assert.equal(this.disposals,0);this.disposals++;this.body.visible=false;releaseOrder.push('actor:'+record.id);},
     inspect(){return{actorEpoch,clientReady:this.ready&&this.disposals===0};}};
    views.push(view);if(!current()){view.dispose();return null;}return view;
   },{dispose(){assert.equal(closed,false);closed=true;factoryDisposals++;releaseOrder.push('factory');},
      inspect:()=>({disposed:closed,actorCount:views.filter(v=>!v.disposals).length})});
  }},
 };
 class FixtureDate extends Date {static now(){return clock.now;}}
 const context=vm.createContext({structuredClone,console,crypto:webcrypto,AbortController,AggregateError,Date:FixtureDate});
 const cache=new Map();
 function moduleFor(id){
  if(cache.has(id))return cache.get(id);
  let module;
  if(sourceFiles.has(id))module=new vm.SourceTextModule(sourceFiles.get(id),{context,identifier:id});
  else{const values=modules[id];assert.ok(values,id);const names=Object.keys(values);
   module=new vm.SyntheticModule(names,function(){for(const name of names)this.setExport(name,values[name]);},{context,identifier:id});}
  cache.set(id,module);return module;
 }
 const source=moduleFor('/__delivery/quest_source_players.mjs');
 await source.link((id,parent)=>moduleFor(new URL(id,'https://fixture.invalid'+parent.identifier).pathname));await source.evaluate();
 const definitions=Object.fromEntries(keys.map(bodyKey=>[bodyKey,Object.freeze({bodyKey,definitionKey:'verified-fixture:'+bodyKey,sourceModelId:modelIDs[bodyKey],normal:{mode:bodyKey==='human-female'?'normal15':'own-air'}})]));
 const registry={count:45,check(value,profession){
  if(!definitions[value?.key]||value.sourceModelId!==definitions[value.key].sourceModelId||!Number.isInteger(profession)||profession<1||profession>5)throw Error('identity');
  return value;
 }};
 const creating=source.namespace.createQuestSourcePlayers({renderer,scene,camera,sourceMap,origin,crypto:webcrypto,registry,catalog:{definitions},
  readScope:()=>scope,enabledBodyKeys,loadBytes:async(url,{signal}={})=>{
   signals.push(signal);requests.push(url);
   if(failInputOnce&&!inputFailed&&(failInputFor===null||url==='/fixture/'+failInputFor+'.json')){
    inputFailed=true;throw Object.assign(Error('HTTP 503 original resource unavailable'),{status:503,retryable:true});
   }
   return new Uint8Array([1]);
  },
  install(view,p){const entry={view,id:p.id};installed.push(entry);return entry;},
  update(entry,p){entry.view.apply(p);},remove:entry=>removed.push(entry),onError:(e,info)=>{faults.push(e);faultInfo.push(info);},
 });
 const api={creating,firstInputs,firstActor,installed,removed,faults,faultInfo,views,frames,inputLoads,airLoads,signals,requests,releaseOrder,connection,
  changeScope:values=>scope={...scope,...values},advance:ms=>clock.now+=ms,
  read:()=>({inputDisposals,hostDisposals,loadCalls,factoryDisposals,hostCreations,factoryCreations}),
  record:(id,sequence=1,key='human-female',profession=1)=>({id,profession,sourceAvatar:{key,sourceModelId:modelIDs[key]},sequence}),
  sync:(c,records,at=10,options={})=>c.sync(records,at,{current:()=>true,connection,...options}),
  view:id=>views.find(v=>v.id===id)};
 return api;
}

test('latest authenticated snapshot wins a pending actor load',async()=>{
 const f=await fixture({holdActor:true}),c=await f.creating;const first=f.sync(c,[f.record('A',1)]);
 await until(()=>f.read().loadCalls===1,'actual factory entered');
 const second=f.sync(c,[f.record('A',2)],20);f.firstActor.resolve();await Promise.all([first,second]);
 assert.equal(f.installed.length,1);assert.deepEqual(f.views[0].applied,[2,2]);assert.equal(f.read().loadCalls,1);c.dispose();
});
test('clear retires an in-flight actor without publishing or leaking it',async()=>{
 const f=await fixture({holdActor:true}),c=await f.creating;const p=f.sync(c,[f.record('A')]);
 await until(()=>f.read().loadCalls===1,'actual delayed factory entered');c.clear();f.firstActor.resolve();await p;await c.drain();
 assert.equal(f.installed.length,0);assert.equal(f.views[0].disposals,1);assert.equal(f.views[0].body.visible,false);assert.equal(c.inspect().actors.actors,0);c.dispose();
});
test('connection changes prevent delayed actor installation',async()=>{
 const f=await fixture({holdActor:true}),c=await f.creating;let current=true;const p=f.sync(c,[f.record('A')],10,{current:()=>current});
 await until(()=>f.read().loadCalls===1,'actual delayed factory entered');current=false;f.firstActor.resolve();await p;
 assert.equal(f.installed.length,0);assert.equal(f.views[0].disposals,1);c.dispose();
});
test('map lifetime changes release late decoded inputs',async()=>{
 const f=await fixture({holdInputs:true}),c=await f.creating;const p=f.sync(c,[f.record('A')]);
 await until(()=>f.inputLoads.length===1,'actual input load entered');f.changeScope({mapGeneration:2});f.firstInputs.resolve();await p;await c.drain();
 assert.equal(f.read().inputDisposals,1);assert.equal(f.read().hostDisposals,0);assert.equal(f.read().hostCreations,0);assert.equal(f.installed.length,0);c.dispose();
});
test('unsupported body never reaches the own actor factory',async()=>{
 const f=await fixture(),c=await f.creating,p=f.record('A',1,'orc-female');assert.equal(c.accepts(p),false);
 await f.sync(c,[p]);assert.equal(f.read().loadCalls,0);assert.equal(f.faults.length,1);assert.equal(c.inspect().failed,true);c.dispose();
});
test('removing A disposes only A; B continues applying its own snapshots',async()=>{
 const f=await fixture(),c=await f.creating;await f.sync(c,[f.record('A'),f.record('B')]);
 await f.sync(c,[f.record('B',2)],20);assert.equal(f.view('A').disposals,1);assert.equal(f.view('B').disposals,0);assert.equal(f.view('B').applied.at(-1),2);assert.equal(f.removed.length,1);c.dispose();
});
test('one world render forwards the identical opaque token without driving pose time',async()=>{
 const f=await fixture(),c=await f.creating;await f.sync(c,[f.record('A')]);const count=f.views[0].applied.length,token={};
 assert.equal(c.beforeRender(token),true);c.afterRender(token);assert.equal(f.frames.length,2);assert.equal(f.frames[0][1],token);assert.equal(f.frames[1][1],token);assert.equal(f.views[0].applied.length,count);c.dispose();
});
test('a rejected native pose clears source actors and reports one failure',async()=>{
 const f=await fixture(),c=await f.creating;await f.sync(c,[f.record('A')]);await f.sync(c,[{...f.record('A',2),badPose:true}],20);
 assert.equal(f.faults.length,1);assert.equal(f.views[0].disposals,1);assert.equal(f.removed.length,1);assert.equal(f.read().hostDisposals,1);
 assert.equal(c.beforeRender({}),false);c.dispose();
});
test('world cleanup releases the common actor pool once before borrowed world resources',async()=>{
 const f=await fixture(),c=await f.creating;await f.sync(c,[f.record('A'),f.record('B')]);c.dispose();c.dispose();await c.drain();
 assert.equal(f.read().factoryDisposals,1);assert.equal(f.read().hostDisposals,1);assert.equal(f.read().inputDisposals,1);assert.ok(f.views.every(v=>v.disposals===1));
 assert(f.releaseOrder.indexOf('factory')>f.releaseOrder.indexOf('actor:A'));assert(f.releaseOrder.indexOf('host')>f.releaseOrder.indexOf('factory'));
 assert(f.releaseOrder.indexOf('normal15:human-female')>f.releaseOrder.indexOf('host'));
});
test('all explicitly enabled bodies share one world factory while loading their own inputs once',async()=>{
 const f=await fixture({enabledBodyKeys:keys}),c=await f.creating;
 const records=keys.map((key,i)=>f.record('A'+i,1,key,i%5+1));
 assert(records.every(p=>c.accepts(p)));await f.sync(c,records);await f.sync(c,records,20);
 assert.equal(f.installed.length,9);assert.equal(f.read().loadCalls,9);assert.equal(f.inputLoads.length,9);assert.equal(f.airLoads.length,8);
 assert.equal(f.read().hostCreations,1);assert.equal(f.read().factoryCreations,1);
 await f.sync(c,[records[8]],30);assert(records.slice(0,8).every(r=>f.view(r.id).disposals===1));assert.equal(f.view('A8').disposals,0);assert.equal(f.read().hostDisposals,0);
 c.dispose();await c.drain();assert.equal(f.read().factoryDisposals,1);assert.equal(f.read().hostDisposals,1);assert.equal(f.read().inputDisposals,17);
 assert(f.releaseOrder.lastIndexOf('own-air:kartan')<f.releaseOrder.indexOf('ground:kartan'));
});
test('an unlisted body remains unavailable even when its model exists in the shared loader',async()=>{
 const f=await fixture({enabledBodyKeys:['human-female','orc-female']}),c=await f.creating;
 assert.equal(c.accepts(f.record('X',1,'human-male')),false);assert.equal(f.airLoads.length,0);c.dispose();
});

test('no selected character means zero body loads and no host/factory creation',async()=>{
 const f=await fixture({enabledBodyKeys:keys}),c=await f.creating;
 assert.equal(f.inputLoads.length,0);assert.equal(f.airLoads.length,0);assert.equal(f.read().hostCreations,0);assert.equal(f.read().factoryCreations,0);
 assert.equal(c.beforeRender({}),false);assert.equal(c.inspect().resources.ready,0);c.dispose();await c.drain();assert.equal(f.read().inputDisposals,0);
});
test('selecting only Elf never preloads HumanF and uses the same lazy world factory',async()=>{
 const f=await fixture({enabledBodyKeys:keys}),c=await f.creating;await f.sync(c,[f.record('elf',1,'elf-female')]);
 assert.deepEqual(f.inputLoads,[['elf-female','ground']]);assert.deepEqual(f.airLoads,['elf-female']);
 assert.equal(f.read().hostCreations,1);assert.equal(f.read().factoryCreations,1);c.dispose();await c.drain();
});
test('Playable waits for actual clientReady observed after existing render',async()=>{
 const f=await fixture({ready:false}),c=await f.creating;await f.sync(c,[f.record('A')]);
 assert.equal(c.isPlayable('A'),false);assert.equal(c.inspect().lifecycle.states[0].state,'AuthorityBound');
 let token={};c.beforeRender(token);c.afterRender(token);assert.equal(c.isPlayable('A'),false);
 f.view('A').ready=true;token={};c.beforeRender(token);c.afterRender(token);assert.equal(c.isPlayable('A'),true);
 c.clear();assert.equal(c.isPlayable('A'),false);c.dispose();
});
test('503 resources are evicted and can retry after the explicit resource retry window',async()=>{
 const f=await fixture({enabledBodyKeys:keys,failInputOnce:true}),c=await f.creating,p=f.record('elf',1,'elf-female');
 await f.sync(c,[p]);assert.equal(f.faults.length,1);assert.equal(f.faultInfo[0].retryable,true);assert.equal(c.inspect().failed,false);
 assert.equal(c.inspect().resources.entries.length,0);assert.equal(f.read().factoryCreations,0);assert.equal(f.inputLoads.length,1);
 await f.sync(c,[p]);assert.equal(f.inputLoads.length,1);f.advance(1001);await f.sync(c,[p],20);
 assert.equal(f.inputLoads.length,2);assert.equal(f.installed.length,1);assert.equal(c.isPlayable('elf'),true);
 assert.equal(f.faults.length,1);assert.deepEqual(f.inputLoads,[['elf-female','ground'],['elf-female','ground']]);c.dispose();await c.drain();
});
test('new peer resource 503 never drops Playable self snapshots or repeats HTTP during its resource window',async()=>{
 const f=await fixture({enabledBodyKeys:keys,failInputOnce:true,failInputFor:'elf-female'}),c=await f.creating;
 await f.sync(c,[f.record('self',1)]);const self=f.view('self'),initialApplications=self.applied.length;
 assert.equal(c.isPlayable('self'),true);assert.deepEqual(f.requests,['/fixture/human-female.json']);
 const peer=sequence=>f.record('peer',sequence,'elf-female');
 await f.sync(c,[f.record('self',2),peer(2)],100);
 assert.equal(f.faults.length,1);assert.equal(f.faultInfo[0].retryable,true);assert.equal(c.inspect().failed,false);
 assert.equal(c.isPlayable('self'),true);assert.equal(f.view('self'),self);assert.equal(self.disposals,0);
 assert.deepEqual(f.requests,['/fixture/human-female.json','/fixture/elf-female.json']);
 for(let sequence=3;sequence<=7;sequence++){
  f.advance(100);await f.sync(c,[f.record('self',sequence),peer(sequence)],sequence*50);
  assert.equal(self.applied.at(-1),sequence);assert.equal(self.applied.length,initialApplications+sequence-1);
  assert.equal(c.isPlayable('self'),true);assert.equal(self.disposals,0);
  assert.equal(f.requests.length,2);assert.equal(f.inputLoads.length,2);assert.equal(f.airLoads.length,1);
 }
 assert.deepEqual(self.applied.slice(initialApplications),[2,3,4,5,6,7]);
 assert.equal(f.view('peer'),undefined);assert.equal(f.faults.length,1);
 f.advance(501);await f.sync(c,[f.record('self',8),peer(8)],400);
 assert.deepEqual(self.applied.slice(initialApplications),[2,3,4,5,6,7,8]);
 assert.deepEqual(f.requests,['/fixture/human-female.json','/fixture/elf-female.json','/fixture/elf-female.json']);
 assert.equal(c.isPlayable('self'),true);assert.equal(c.isPlayable('peer'),true);assert.equal(f.view('self'),self);
 assert.equal(f.read().hostCreations,1);assert.equal(f.read().factoryCreations,1);assert.equal(f.faults.length,1);
 c.dispose();await c.drain();assert.equal(self.disposals,1);assert.equal(f.view('peer').disposals,1);
});
test('actual new socket supersedes a pending same-character mount',async()=>{
 const f=await fixture({holdActor:true}),c=await f.creating;const old=f.sync(c,[f.record('A')]);
 await until(()=>f.read().loadCalls===1,'first socket entered delayed factory');
 const next=f.sync(c,[f.record('A',2)],20,{connection:new Connection()});await until(()=>f.read().loadCalls===2,'new socket has its own actor request');
 f.firstActor.resolve();await Promise.all([old,next]);assert.equal(f.installed.length,1);assert.equal(f.views.filter(v=>v.disposals===1).length,1);
 assert.equal(f.installed[0].view.applied.at(-1),2);c.dispose();await c.drain();
});
test('world signal reaches resource fetch and is aborted on page/world disposal',async()=>{
 const f=await fixture({holdInputs:true}),c=await f.creating,p=f.sync(c,[f.record('A')]);
 await until(()=>f.signals.length===1,'resource fetch receives signal');assert.equal(f.signals[0].aborted,false);
 c.dispose();assert.equal(f.signals[0].aborted,true);f.firstInputs.resolve();await p;await c.drain();
 assert.equal(f.read().inputDisposals,1);assert.equal(f.installed.length,0);
});
