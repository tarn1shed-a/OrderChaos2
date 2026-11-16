import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {webcrypto} from 'node:crypto';
const controllerText=await readFile(new URL('./quest_source_players.mjs',import.meta.url),'utf8');
const originalScene=await readFile(new URL('./player_choice_scene.mjs',import.meta.url),'utf8');
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
async function fixture({holdActor=false,holdInputs=false}={}){
 const firstInputs=deferred(),firstActor=deferred(),installed=[],removed=[],faults=[],views=[],frames=[];
 let inputDisposals=0,hostDisposals=0,loadCalls=0;const renderer={},scene={},camera={},sourceMap={},origin={},owner={};
 let scope={owner,active:true,mapGeneration:1,contextGeneration:1,renderer,scene,sourceMap};
 const inputs={dispose(){inputDisposals++;},inspect:()=>({disposed:inputDisposals>0})};
 const modules={
  '/human-female-world-common-v1/inputs.mjs':{loadHumanFemaleWorldInputs:async()=>{if(holdInputs)await firstInputs.promise;return inputs;}},
  '/world-character-peer-v1/human_female_material_host.mjs':{createHumanFemaleWorldMaterialHost:async()=>({dispose(){hostDisposals++;},prepareBeforeWorldRender(token){frames.push(['before',token]);},afterWorldRender(token){frames.push(['after',token]);}})},
  '/human-female-world-v1/actor_factory.mjs':{createHumanFemaleWorldActorFactory:()=>async(record,{current,actorEpoch})=>{
   loadCalls++;if(holdActor)await firstActor.promise;
   const view={body:{id:record.id},applied:[],disposals:0,apply(next){if(!current())throw Error('stale');if(next.badPose)throw Error('own pose rejected');this.applied.push(next.sequence);},dispose(){this.disposals++;},inspect:()=>({actorEpoch})};
   views.push(view);if(!current()){view.dispose();return null;}return view;
  }},
 };
 const context=vm.createContext({structuredClone,console,crypto:webcrypto});
 const source=new vm.SourceTextModule(controllerText,{context});
 await source.link(async id=>{
  if(id==='/__delivery/player_choice_scene.mjs'){const m=new vm.SourceTextModule(originalScene,{context});await m.link(()=>assert.fail('unexpected import'));return m;}
  const exports=modules[id];assert.ok(exports,id);const names=Object.keys(exports);
  return new vm.SyntheticModule(names,function(){for(const name of names)this.setExport(name,exports[name]);},{context});
 });await source.evaluate();
 const creating=source.namespace.createQuestSourcePlayers({renderer,scene,camera,sourceMap,origin,crypto:webcrypto,
  registry:{count:45,check(value){if(!value?.key)throw Error('identity');return value;}},readScope:()=>scope,
  install(view,p){const entry={view,id:p.id};installed.push(entry);return entry;},
  update(entry,p){entry.view.apply(p);},remove:entry=>removed.push(entry),onError:e=>faults.push(e),
 });
 return {creating,firstInputs,firstActor,installed,removed,faults,views,frames,
  changeScope:values=>scope={...scope,...values},read:()=>({inputDisposals,hostDisposals,loadCalls}),record:(id,sequence=1)=>({id,profession:1,sourceAvatar:{key:'human-female'},sequence})};
}
test('latest authenticated snapshot wins a pending actor load',async()=>{
 const f=await fixture({holdActor:true}),c=await f.creating;const first=c.sync([f.record('A',1)],10,{current:()=>true});
 const second=c.sync([f.record('A',2)],20,{current:()=>true});f.firstActor.resolve();await Promise.all([first,second]);
 assert.equal(f.installed.length,1);assert.deepEqual(f.views[0].applied,[2,2]);assert.equal(f.read().loadCalls,1);c.dispose();
});
test('clear retires an in-flight actor without publishing or leaking it',async()=>{
 const f=await fixture({holdActor:true}),c=await f.creating;const p=c.sync([f.record('A')],10,{current:()=>true});c.clear();f.firstActor.resolve();await p;
 assert.equal(f.installed.length,0);assert.equal(f.views[0].disposals,1);assert.equal(c.inspect().actors.actors,0);c.dispose();
});
test('connection changes prevent delayed actor installation',async()=>{
 const f=await fixture({holdActor:true}),c=await f.creating;let connection=true;const p=c.sync([f.record('A')],10,{current:()=>connection});connection=false;f.firstActor.resolve();await p;
 assert.equal(f.installed.length,0);assert.equal(f.views[0].disposals,1);c.dispose();
});
test('map lifetime changes release late decoded inputs',async()=>{
 const f=await fixture({holdInputs:true});f.changeScope({mapGeneration:2});f.firstInputs.resolve();await assert.rejects(f.creating,/owner expired/);
 assert.equal(f.read().inputDisposals,1);assert.equal(f.read().hostDisposals,0);
});
test('unsupported body never reaches the own actor factory',async()=>{
 const f=await fixture(),c=await f.creating;const p={...f.record('A'),sourceAvatar:{key:'orc-female'}};assert.equal(c.accepts(p),false);
 await c.sync([p],10,{current:()=>true});assert.equal(f.read().loadCalls,0);assert.equal(f.faults.length,1);assert.equal(c.inspect().failed,true);c.dispose();
});
test('removing A disposes only A; B continues applying its own snapshots',async()=>{
 const f=await fixture(),c=await f.creating;await c.sync([f.record('A'),f.record('B')],10,{current:()=>true});
 await c.sync([f.record('B',2)],20,{current:()=>true});assert.equal(f.views[0].disposals,1);assert.equal(f.views[1].disposals,0);assert.equal(f.views[1].applied.at(-1),2);assert.equal(f.removed.length,1);c.dispose();
});
test('one world render forwards the identical opaque token without driving pose time',async()=>{
 const f=await fixture(),c=await f.creating;await c.sync([f.record('A')],10,{current:()=>true});const count=f.views[0].applied.length,token={};
 assert.equal(c.beforeRender(token),true);c.afterRender(token);assert.equal(f.frames.length,2);assert.equal(f.frames[0][1],token);assert.equal(f.frames[1][1],token);assert.equal(f.views[0].applied.length,count);c.dispose();
});
test('a rejected native pose clears source actors and reports one failure',async()=>{
 const f=await fixture(),c=await f.creating;await c.sync([f.record('A')],10,{current:()=>true});await c.sync([{...f.record('A',2),badPose:true}],20,{current:()=>true});
 assert.equal(f.faults.length,1);assert.equal(f.views[0].disposals,1);assert.equal(f.removed.length,1);assert.equal(f.read().hostDisposals,1);
 assert.equal(c.beforeRender({}),false);c.dispose();
});
