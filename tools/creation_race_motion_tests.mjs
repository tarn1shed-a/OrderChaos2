import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readdir} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {webcrypto,createHash} from 'node:crypto';
import {createCreationMotionHistory} from '../deploy/creation_motion_history.mjs';
import {creationMotionEventPlan,creationMotionResourceURL,createCreationMotionLibrary} from '../deploy/creation_motion.mjs';
import {sourceMotionStaticImports,checkedCreationMotionDelivery} from '../deploy/creation_motion_delivery.mjs';
import {validateCreationStagesDelivery,CREATION_STAGES_PROFILE_V6} from '../deploy/creation_stages_profile.mjs';

test('v6 source event ordering retains only actual counter and independent owner.class',()=>{
 const h=createCreationMotionHistory({counter:7,selected:4}),owner={race:2,gender:1,professionIndex:4},target={race:2,gender:1,professionIndex:0};
 const plan=creationMotionEventPlan({version:2,screen:'CharacterChooseRace',event:'page-enter',target,ownerSelection:owner,history:h});
 assert.equal(plan.kind,'race-initial');assert.deepEqual(plan.initialGlobals,{counter:7,selected:0});assert.deepEqual(plan.ownerBefore,owner);assert.equal(h.read(),null);
 h.raceFrame({counter:1,selected:0});
 const noop=creationMotionEventPlan({version:2,screen:'CharacterChooseRace',event:'race-selection',target,ownerSelection:owner,requested:{screen:'CharacterChooseRace',...target},history:h});
 assert.equal(noop.noop,true);assert.deepEqual(h.read(),{counter:1,selected:0});
 const changed=creationMotionEventPlan({version:2,screen:'CharacterChooseRace',event:'race-selection',target:{race:3,gender:0,professionIndex:0},ownerSelection:owner,requested:{screen:'CharacterChooseRace',...target},history:h});
 assert.equal(changed.kind,'race-show');assert.equal(changed.ownerBefore.professionIndex,4);assert.equal(h.read(),null);
 h.enterRace({race:0,gender:0},{sourceQueueEnabled:true});assert.equal(h.read(),null); // selected write cannot resolve unknown counter.
 h.raceFrame({counter:1,selected:6});
 const part=creationMotionEventPlan({version:2,screen:'CharacterChoosePart',event:'page-enter',target,ownerSelection:owner,history:h});
 assert.equal(part.kind,null);assert.deepEqual(h.read(),{counter:1,selected:6});
 const back=creationMotionEventPlan({version:2,screen:'CharacterChooseClass',event:'page-enter',target,ownerSelection:owner,history:h});
 assert.equal(back.kind,'initial');assert.deepEqual(back.initialGlobals,{counter:1,selected:6});assert.equal(h.read(),null);
});

test('v5 finite Race fallback remains unknown and UI enterRace is not repeated',()=>{
 const h=createCreationMotionHistory({counter:3,selected:4});let writes=0;
 const history={...h,enterRace(...args){writes++;return h.enterRace(...args);}};
 history.enterRace({race:0,gender:0});assert.equal(writes,1);
 const plan=creationMotionEventPlan({version:1,screen:'CharacterChooseRace',event:'page-enter',target:{race:0,gender:0,professionIndex:0},ownerSelection:{race:0,gender:0,professionIndex:4},history});
 assert.equal(plan.kind,null);assert.equal(h.read(),null);assert.equal(writes,1);
});

test('same-source-class binding keeps carrier while Class page-enter supersedes show',()=>{
 const h=createCreationMotionHistory({counter:1,selected:2}),target={race:0,gender:0,professionIndex:1},requested={screen:'CharacterChooseClass',...target};
 assert.equal(creationMotionEventPlan({version:2,screen:requested.screen,event:'class-selection',target,requested,ownerSelection:target,history:h}).noop,true);
 const enter=creationMotionEventPlan({version:2,screen:requested.screen,event:'page-enter',target,requested,ownerSelection:{...target,professionIndex:4},history:h});
 assert.equal(enter.kind,'initial');assert.equal(h.read(),null);
});

test('known same-origin absolute dependencies and real compact static imports are checked',async()=>{
 const base='/assets/source-creation-partial-class-v1/manifest.json';
 assert.equal(creationMotionResourceURL(base,'/assets/source-creation-initial-all-v1/profiles/elf-male-mage.json'),'/assets/source-creation-initial-all-v1/profiles/elf-male-mage.json');
 for(const bad of ['https://external.invalid/a.mjs','//external.invalid/a.mjs','/assets/other/a.mjs','/assets/source-creation-control-v1/%2e%2e/a.mjs','../../private/a.mjs','./a.mjs?x=1'])assert.throws(()=>creationMotionResourceURL(base,bad));
 const result=await sourceMotionStaticImports([{url:base,source:"import{a}from'./tight.mjs';export{b}from'./reexport.mjs';// from './not-an-import.mjs'"}]);
 assert.deepEqual(result[0].imports,['./tight.mjs','./reexport.mjs']);
});

const privateRoot=process.env.OC2_CREATION_QA_ROOT;
test('actual v6 libraries cover Race9, initial45 and partial2 without seeds, stale writes or foreign clips',{skip:!privateRoot},async()=>{
 const root=resolve(privateRoot),json=async p=>JSON.parse(await readFile(p,'utf8')),bytes=async p=>new Uint8Array(await readFile(p)),files={};
 const roots=[
  'creation-all-stage-control-20261116/candidate-v1/game-data/converted','creation-queue-runtime-20261116/candidate-v1/game-data/converted',
  'creation-initial-all-20261116/assets-v1/game-data/converted','creation-race-control-20261116/candidate-v1/game-data/converted','creation-partial-class-20261116/candidate-v1/game-data/converted'];
 async function walk(dir,base){for(const row of await readdir(dir,{withFileTypes:true})){const p=join(dir,row.name);if(row.isDirectory())await walk(p,base);else{
  const url='/assets/'+p.slice(base.length+1),sha256=createHash('sha256').update(await readFile(p)).digest('hex');if(files[url])assert.equal(files[url].sha256,sha256,url);files[url]={path:p,sha256};
 }}}
 for(const name of roots){const base=join(root,'analysis/raw',name);await walk(base,base);}
 const file=url=>{assert.ok(files[url],url);return files[url].path;};
 const library=createCreationMotionLibrary({version:2,json:url=>json(file(url)),bytes:url=>bytes(file(url)),crypto:webcrypto,importModule:url=>import(pathToFileURL(file(url)))});
 const strip=f=>({...f,requests:[],callbacks:[],clockFinishes:[]}),actor={applySourcePose(pose){assert.equal(pose.format,'oc2-creation-pure-source-pose-v1');}};
 const raceArea=join(root,'analysis/raw/creation-race-control-20261116/candidate-v1'),races=(await json(join(raceArea,'index-v2.json'))).choices,ro=(await json(join(raceArea,'source-queue-v1.json'))).choices;
 let raceFrames=0,initialFrames=0,classFrames=0,partialFrames=0,negatives=0;
 for(const row of races){
  const data=await json(join(root,row.modelFile)),identity={panel:0,race:row.uiRace,gender:row.gender,professionIndex:0};let live=true;
  const ownerBefore={race:row.uiRace===0?2:0,gender:row.gender,professionIndex:4};
  const motion=await library.prepare({identity,data,kind:'race-show',ownerBefore,initialGlobals:null,current:()=>live});
  assert.equal(motion.inspect().historyKnown,false);assert.equal(motion.inspect().sourceFrame,null);assert.throws(()=>motion.update(16,actor));negatives++;
  const own=ro.find(r=>r.key===row.key);let at=0;
  for(const expected of own.frames){motion.update(expected.atMs-at,actor);at=expected.atMs;assert.deepEqual(motion.inspect().sourceFrame,strip(expected));raceFrames++;}
  live=false;assert.throws(()=>motion.update(0,actor));motion.dispose();negatives++;
  // Actual Init acceptance can change body before ENTER_RACE; retain class4.
  for(const before of [ownerBefore,{race:identity.race,gender:identity.gender,professionIndex:4}]){
   const idle=await library.prepare({identity,data,kind:'race-initial',ownerBefore:before,initialGlobals:{counter:7,selected:row.body==='human-male'?6:0},current:()=>true});
   assert.ok(idle);assert.equal(idle.inspect().historyKnown,false);idle.update(0,actor);idle.dispose();
  }
  assert.equal(await library.prepare({identity,data,kind:'race-initial',initialGlobals:null,current:()=>true}),null);negatives++;
  await assert.rejects(library.prepare({identity,data,kind:'race-show',ownerBefore:{race:identity.race,gender:identity.gender,professionIndex:4},initialGlobals:null,current:()=>true}));negatives++;
 }
 const routes=(await json(join(root,'analysis/raw/creation-all-stage-integration-20261116/matrix-v1.json'))).routes;
 const classes=(await json(join(root,'analysis/raw/creation-all-stage-control-20261116/coverage-native-v1/queue-oracles-v1.json'))).choices;
 const partial=(await json(join(root,'analysis/raw/creation-partial-class-20261116/native-v1/native-v1.json'))).cases;
 const oldInitial=(await json(join(root,'analysis/raw/creation-initial-idle-20261116/native-v4/native-controls-v1.json'))).choices;
 const newInitial=await json(join(root,'analysis/raw/creation-initial-all-20261116/queues-native-v1/native-controls-v1.json'));
 for(const row of routes.filter(r=>r.panel===1)){
  const m=await json(join(root,row.sourceCandidate,'manifest.json')),data=await json(join(root,row.sourceCandidate,m.model));
  const identity={panel:1,race:m.race,gender:m.gender,professionIndex:m.professionIndex,request:{displayId:row.displayId}},ownerBefore={race:m.race,gender:m.gender,professionIndex:-1};
  const key=row.body+'-'+['warrior','ranger','mage','ds','monk'][m.professionIndex];
  const show=await library.prepare({identity,data,kind:'show',ownerBefore,initialGlobals:null,current:()=>true});assert.ok(show);assert.equal(show.inspect().sourceFrame,null);
  const frames=classes[key]?.frames??partial.find(r=>r.key===key)?.frames;assert.ok(frames);let at=0;
  for(const expected of frames){show.update(expected.atMs-at,actor);at=expected.atMs;assert.deepEqual(show.inspect().sourceFrame,strip(expected));if(classes[key])classFrames++;else partialFrames++;}show.dispose();
  const base=oldInitial.find(r=>r.key===key)??newInitial.choices.find(r=>r.key===key),extra=key===newInitial.extraHistoricalFamily.key?newInitial.extraHistoricalFamily.controls:[];
  for(const c of [...base.controls,...extra]){
   const idle=await library.prepare({identity,data,kind:'initial',ownerBefore,initialGlobals:c.explicitInitialGlobals,current:()=>true});assert.ok(idle);at=0;
   for(const expected of c.frames){idle.update(expected.atMs-at,actor);at=expected.atMs;assert.deepEqual(idle.inspect().sourceFrame,strip(expected));initialFrames++;}idle.dispose();
  }
 }
 assert.deepEqual({raceFrames,initialFrames,classFrames,partialFrames},{raceFrames:117,initialFrames:890,classFrames:559,partialFrames:21});
 const profile=await json(join(resolve('.'),'analysis/raw/creation-race-motion-candidate-20261116/manifest-stages-v6.json'));
 assert.equal(validateCreationStagesDelivery(profile,{profileURL:CREATION_STAGES_PROFILE_V6}),profile);
 await checkedCreationMotionDelivery(profile.sourceMotion,{required:url=>{assert.ok(files[url],url);return files[url];},read:url=>json(file(url))});
 const some='/assets/source-creation-race-control-v1/modules/source_race_runtime_v1.mjs',saved=files[some];files[some]={...saved,sha256:'0'.repeat(64)};
 await assert.rejects(checkedCreationMotionDelivery(profile.sourceMotion,{required:url=>files[url],read:url=>json(file(url))}));files[some]=saved;negatives++;
 // An asynchronous own bank failure cannot install a controller for a retired epoch.
 let live=true,release;const gate=new Promise(resolve=>release=resolve);
 const late=createCreationMotionLibrary({version:2,json:async url=>{await gate;return json(file(url));},bytes:url=>bytes(file(url)),crypto:webcrypto,importModule:url=>import(pathToFileURL(file(url)))});
 const row=races[0],data=await json(join(root,row.modelFile));
 const pending=late.prepare({identity:{panel:0,race:row.uiRace,gender:row.gender,professionIndex:0},data,kind:'race-show',ownerBefore:{race:2,gender:1,professionIndex:4},initialGlobals:null,current:()=>live});live=false;release();assert.equal(await pending,null);negatives++;
 console.log(JSON.stringify({actualRaceQueues:9,raceFrames,actualClassQueues:45,classFrames,partialFrames,initialFrames,negativeControls:negatives,compiledRealStaticClosure:true}));
});
