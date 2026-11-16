import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFile} from 'node:fs/promises';
import {createCreationMotionHistory} from '../deploy/creation_motion_history.mjs';
import {creationMotionEventPlan} from '../deploy/creation_motion.mjs';

const source=await readFile(new URL('../deploy/entry_ui.mjs',import.meta.url),'utf8');
const start=source.indexOf("  function updateRacePreview(event='page-enter'){");
const actual=source.slice(start,source.indexOf('  const blocked=new Map();',start));
assert.equal(start>=0,true);assert.equal(actual.split("import('./creation_stages.mjs')").length,2);
// Execute the actual UI function, controlling only its dynamic-import boundary.
const input=actual.replace("import('./creation_stages.mjs')",'controlledImport()');
const hideStart=source.indexOf('  function hideRoot(){'),hide=source.slice(hideStart,source.indexOf('  const api=',hideStart));
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function setup(version=2){
 let resolveImport;const gate=new Promise(resolve=>resolveImport=resolve),observed=[];
 const history=createCreationMotionHistory({counter:0,selected:0});
 const context={previewURL:`/assets/source-creation-stage/manifest-stages-v${version===2?6:version===1?5:4}.json`,root:{dataset:{sourceScreen:'CharacterChooseRace'},hidden:false},draft:{race:0,gender:0,cls:0,name:''},previewPromise:null,racePreview:null,previewGeneration:0,blocked:new Map(),stagedPreview:true,motionHistory:history,controlledImport:()=>gate};
 vm.createContext(context);vm.runInContext(input+hide+';globalThis.run=updateRacePreview;globalThis.hide=hideRoot;',context);
 const resolve=()=>resolveImport({createSourceCreationStages(_root,{initialOwnerSelection}){
  observed.push({initialOwnerSelection:{...initialOwnerSelection}});let requested=null;
  return{show(current){
   const plan=creationMotionEventPlan({version,screen:current.screen,event:current.event,target:current,ownerSelection:initialOwnerSelection,requested,history});
   observed.push({event:current.event,target:{race:current.race,gender:current.gender},plan});requested={...current};
  },dispose(){observed.push({disposed:true});}};
 }});
 return{context,history,observed,resolve};
}

test('cold import retains first game owner when Race selection changes before module completion',async()=>{
 const {context:c,history,observed,resolve}=setup();
 c.run('page-enter');const before={...c.draft};c.draft.race=2;history.raceInput(before,c.draft);c.run('race-selection');
 resolve();await flush();
 assert.equal(observed.length,2);assert.deepEqual(observed[0].initialOwnerSelection,{race:0,gender:0,professionIndex:0});
 assert.equal(observed[1].event,'race-selection');assert.deepEqual(observed[1].target,{race:2,gender:0});
 assert.equal(observed[1].plan.kind,'race-show');assert.equal(observed[1].plan.initialGlobals,null);
 assert.deepEqual(observed[1].plan.ownerBefore,{race:0,gender:0,professionIndex:0});assert.equal(history.read(),null);
});

test('multiple cold Race inputs install only current target and retain first owner profession',async()=>{
 const {context:c,history,observed,resolve}=setup();c.draft.cls=4;c.run('page-enter');
 for(const race of [1,3,2]){const before={...c.draft};c.draft.race=race;c.draft.cls=0;history.raceInput(before,c.draft);c.run('race-selection');}
 resolve();await flush();assert.equal(observed.length,2);
 assert.deepEqual(observed[0].initialOwnerSelection,{race:0,gender:0,professionIndex:4});
 assert.deepEqual(observed[1].target,{race:2,gender:0});assert.equal(observed[1].plan.kind,'race-show');assert.equal(observed[1].plan.ownerBefore.professionIndex,4);
});

test('stable cold Race entry keeps actual known counter and unknown remains unknown',async()=>{
 const {context:c,history,observed,resolve}=setup();c.run();resolve();await flush();
 assert.equal(observed[1].plan.kind,'race-initial');assert.deepEqual(observed[1].plan.initialGlobals,{counter:0,selected:6});assert.equal(history.read(),null);
});

test('cold module completion after leaving Race cannot issue stale show',async()=>{
 const {context:c,observed,resolve}=setup();c.run();c.root.dataset.sourceScreen='CharacterChoosePart';resolve();await flush();
 assert.equal(observed.length,1);
});

test('retired cold import cannot create or replace the new session preview',async()=>{
 const {context:c,observed,resolve}=setup();c.run();c.hide();
 assert.equal(c.previewGeneration,1);assert.equal(c.previewPromise,null);
 const newObserved=[];let resolveNew;const newGate=new Promise(resolve=>resolveNew=resolve);
 c.controlledImport=()=>newGate;c.root.hidden=false;c.draft.race=2;c.run();
 const preview={show(current){newObserved.push(current);},dispose(){}};
 resolveNew({createSourceCreationStages(){return preview;}});await flush();assert.equal(c.racePreview,preview);assert.equal(newObserved.length,1);
 resolve();await flush();assert.equal(observed.length,0);assert.equal(c.racePreview,preview);assert.equal(newObserved.length,1);
});

test('ordinary same-session Race, Class and Part changes reuse one preview',async()=>{
 const {context:c,observed,resolve}=setup();c.run();resolve();await flush();const preview=c.racePreview;
 for(const name of ['CharacterChooseClass','CharacterChoosePart','CharacterChooseClass']){c.root.dataset.sourceScreen=name;c.run();await flush();assert.equal(c.racePreview,preview);}
 assert.equal(observed.filter(r=>r.initialOwnerSelection).length,1);assert.equal(c.previewGeneration,0);
});

test('a retired show rejection cannot overwrite the new session error state',async()=>{
 const {context:c,resolve}=setup();c.run();resolve();await flush();
 let rejectOld;const old=new Promise((_resolve,reject)=>rejectOld=reject);c.racePreview.show=()=>old;
 c.run();await flush();c.hide();c.root.hidden=false;c.root.dataset.sourceCreationError='new-session-state';
 rejectOld(Error('retired source show'));await flush();assert.equal(c.root.dataset.sourceCreationError,'new-session-state');
});

test('v4 and v5 keep legacy finite Race behavior without new motion assets',async()=>{
 for(const version of [0,1]){
  const {context:c,history,observed,resolve}=setup(version);history.enterRace(c.draft);c.run();
  const before={...c.draft};c.draft.race=2;history.raceInput(before,c.draft);c.run('race-selection');resolve();await flush();
  assert.equal(observed.length,2);assert.deepEqual(observed[0].initialOwnerSelection,{race:0,gender:0,professionIndex:0});
  assert.equal(observed[1].plan.kind,null);assert.equal(history.read(),null);
 }
});
