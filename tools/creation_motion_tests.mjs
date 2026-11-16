import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {webcrypto,createHash} from 'node:crypto';
import {createCreationMotionHistory} from '../deploy/creation_motion_history.mjs';
import {createCreationMotionLibrary,CLASS_MOTION_MANIFEST,INITIAL_MOTION_MANIFEST} from '../deploy/creation_motion.mjs';
import {checkedCreationMotionDelivery} from '../deploy/creation_motion_delivery.mjs';
import {createSourcePoseWriter} from './creation_control/source_pose_writer_v1.mjs';

test('Race writes, actual binding inputs, and observed Class frames keep unknown history explicit',()=>{
 const h=createCreationMotionHistory({counter:7,selected:4});
 h.enterRace({race:0,gender:0});assert.equal(h.read(),null);
 h.classFrame({counter:7,selected:6});
 h.raceInput({race:0,gender:0},{race:0,gender:0});assert.deepEqual(h.read(),{counter:7,selected:6});
 h.raceInput({race:0,gender:0},{race:2,gender:1});assert.equal(h.read(),null);
 h.enterRace({race:2,gender:1});assert.equal(h.read(),null);
 h.classFrame({counter:1,selected:3});assert.deepEqual(h.read(),{counter:1,selected:3});
 const copy=h.read();copy.counter=0;assert.equal(h.read().counter,1);
 h.unresolvedClassCarrier();assert.equal(h.read(),null);h.classFrame({counter:0,selected:2});assert.deepEqual(h.read(),{counter:0,selected:2});
 for(const bad of [{counter:-1,selected:0},{counter:0,selected:7},{counter:NaN,selected:0}])assert.throws(()=>createCreationMotionHistory(bad));
 assert.throws(()=>h.enterRace({race:4,gender:1}));assert.throws(()=>h.classFrame({counter:0,selected:8}));
});

test('one writer stops finite animation before applying source poses and refuses retired owners',()=>{
 let current=true,stopped=0,finite=0,poses=0,disposed=false;
 const w=createSourcePoseWriter({current:()=>current,isDisposed:()=>disposed,stopFinite:()=>stopped++,updateFinite:()=>finite++,applySourcePose:()=>poses++});
 assert.throws(()=>w.apply({}));w.update(.016);assert.equal(finite,1);
 w.claim();assert.equal(stopped,1);assert.equal(w.update(.016),false);w.apply({});assert.equal(poses,1);assert.throws(()=>w.claim());
 current=false;assert.throws(()=>w.apply({}));assert.throws(()=>w.update(.016));w.dispose();disposed=true;assert.throws(()=>w.claim());
});

test('Part and unknown initial history cannot fetch or create a Class queue',async()=>{
 const fail=()=>{throw Error('No Class resources may be requested');};
 const library=createCreationMotionLibrary({json:fail,bytes:fail,crypto:webcrypto,importModule:fail});
 await assert.rejects(library.prepare({identity:{panel:2},kind:'show',current:()=>true}));
 assert.equal(await library.prepare({identity:{panel:1},kind:'initial',initialGlobals:null,current:()=>true}),null);
});

const privateRoot=process.env.OC2_CREATION_QA_ROOT;
test('actual 43 own queues, finite gaps, retired callbacks, and eight initial queues use frozen source bytes',{skip:!privateRoot},async()=>{
 const root=resolve(privateRoot),runtime=join(root,'analysis/raw/creation-all-stage-control-20261116/candidate-v1/game-data/converted');
 const fast=join(root,'analysis/raw/creation-queue-runtime-20261116/candidate-v1/game-data/converted');
 const file=url=>join(url.startsWith('/assets/source-creation-control-runtime-v1/')?fast:runtime,url.replace(/^\/assets\//,'')),json=async p=>JSON.parse(await readFile(p,'utf8'));
 const library=createCreationMotionLibrary({json:url=>json(file(url)),bytes:async url=>new Uint8Array(await readFile(file(url))),crypto:webcrypto,importModule:url=>import(pathToFileURL(file(url)))});
 const contract=await json(join(root,'analysis/raw/creation-class-entry-20261116/source-v1/contract-runtime.json'));
 const {selectStageIdentity}=await import('./creation_class_stage/stage_switch.mjs');
 const routes=(await json(join(root,'analysis/raw/creation-all-stage-integration-20261116/matrix-v1.json'))).routes;
 const oracles=await json(join(root,'analysis/raw/creation-all-stage-control-20261116/coverage-native-v1/queue-oracles-v1.json'));
 const initial=await json(file(INITIAL_MOTION_MANIFEST));
 const initialOracle=await json(join(root,'analysis/raw/creation-initial-idle-20261116/native-v4/native-controls-v1.json'));
 let complete=0,gaps=0,frames=0,initials=0;
 for(const row of routes.filter(r=>r.panel===1)){
  const directory=join(root,row.sourceCandidate),manifest=await json(join(directory,'manifest.json')),data=await json(join(directory,manifest.model));
  const identity=selectStageIdentity(contract,{screen:manifest.screen,race:manifest.race,gender:manifest.gender,professionIndex:manifest.professionIndex});
  let live=true;const current=()=>live,ownerBefore={race:identity.race,gender:identity.gender,professionIndex:-1};
  const motion=await library.prepare({identity,data,kind:'show',ownerBefore,initialGlobals:null,current});
  if(!motion){gaps++;continue;}
  assert.equal(motion.inspect().historyKnown,false);let pose=null;
  const actor={applySourcePose:value=>{pose=value;}};let time=0;
  for(const expected of oracles.choices[motion.key].frames){
   const state=motion.update(expected.atMs-time,actor);time=expected.atMs;
   assert.equal(state.counter,expected.counter);assert.equal(state.selected,expected.selected);
   const withoutTrace=frame=>({...frame,requests:[],callbacks:[],clockFinishes:[]});
   assert.deepEqual(motion.inspect().sourceFrame,withoutTrace(expected));assert.equal(pose.identity.displayId,identity.request.displayId);frames++;
  }
  complete++;live=false;assert.throws(()=>motion.update(0,actor));motion.dispose();
  if(initial.profiles[motion.key]){
   live=true;const idle=await library.prepare({identity,data,kind:'initial',initialGlobals:initialOracle.choices.find(c=>c.key===motion.key).controls[0].explicitInitialGlobals,current});
   assert.ok(idle);const state=idle.update(0,actor);assert.equal(state.clip,'idle');idle.update(100,actor);idle.dispose();initials++;
  }
 }
 assert.deepEqual({complete,gaps,initials},{complete:43,gaps:2,initials:8});assert.equal(frames,559);
 // Actual private closure, not a fabricated set of URL names.
 const files={};
 const {readdir}=await import('node:fs/promises');
 async function walk(dir,base=runtime){for(const entry of await readdir(dir,{withFileTypes:true})){const p=join(dir,entry.name);if(entry.isDirectory())await walk(p,base);else{const raw=await readFile(p),url='/assets/'+p.slice(base.length+1);files[url]={path:p,sha256:createHash('sha256').update(raw).digest('hex')};}}}
 await walk(runtime);await walk(fast,fast);const required=url=>{assert.ok(files[url],url);return files[url];};
 const scope={version:1,classManifestURL:CLASS_MOTION_MANIFEST,initialManifestURL:INITIAL_MOTION_MANIFEST};
 await checkedCreationMotionDelivery(scope,{required,read:url=>json(file(url))});
 const changed={...files[CLASS_MOTION_MANIFEST]};files[CLASS_MOTION_MANIFEST]={...changed};
 const manifest=await json(file(CLASS_MOTION_MANIFEST)),own=Object.values(manifest.profiles)[0],ownURL='/assets/source-creation-control-v1/'+own.url.slice(2);
 files[ownURL].sha256='0'.repeat(64);await assert.rejects(checkedCreationMotionDelivery(scope,{required,read:url=>json(file(url))}));
 console.log(JSON.stringify({actualClassQueues:complete,strictOwnGaps:gaps,sourceBoundaryFrames:frames,initialQueues:initials}));
});
