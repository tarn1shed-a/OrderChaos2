// Direct regression of the actual public controller. No browser/server/save.
// Public cases use a named HOST lifecycle VM fixture, not recovered Flash AS.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {createQuestController} from '../deploy/quest_ui.mjs';
import {createMissionProgramRuntime} from './tutorial_npc_mission_bridge_program.mjs';
const root=new URL('../',import.meta.url),area=new URL('analysis/raw/ordinary-npc-quest-20261115/',root),args=process.argv.slice(2);
const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
const info={origin:'compatible-quest-layer',questId:461,revision:'A',Status:6,Title:'HOST fixture title',Detail:'HOST fixture detail',Objective:'HOST fixture objective',Incomplete:'HOST fixture incomplete',Completion:'HOST fixture completion',
  hasReward:true,NumGold:9,NumXp:512,NumFever:5,NumAdvExp:0,NumItem:1,NumItemOp:0,NumItemTb:0,
  fixedItems:[{id:20028,count:1,icon:'ui/icons/item/red_skull_plan.png',quality:3,isGem:false,hasPromo:false,restricted:false}],returnItems:[],
  HasCollectedTbItem:false,IsFailed:false,IsInTuto:false};
const ready={...info,Status:9,HasCollectedTbItem:true,NumItemTb:1,
  returnItems:[{id:50125,count:4,icon:'ui/icons/item/service_part.png',quality:1,isGem:false,hasPromo:false,restricted:false}]};
// Minimal interface only: exercises host promises without private AS.
function hostLifecycleVM(_program,value){
  let finished=0,actions=[];
  const inspect=()=>({statusFinished:finished,displayFlag:value.Status===9?(finished?3:4):0,
    okVisible:[5,6,8,9].includes(value.Status),grayVisible:[1,2,4].includes(value.Status),
    body:value.Status===9?(finished?value.Completion:value.Incomplete):value.Detail,actions:structuredClone(actions)});
  return {open:inspect,inspect,close:()=>{},ok(){if(value.Status===9&&value.NumItemTb>0&&!finished)finished=1;
    else actions.push({nativeCallback:'Hero_SendAcceptQuestN'});return inspect();}};
}
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++;},yes=v=>{assert.ok(v);assertions++;};
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const drain=()=>new Promise(resolve=>setImmediate(resolve)),cases=[];
async function runSuite(factory,program,label){
  for(const kind of ['initial-query','validation-query','action-reject','action-success','initial-render','confirmation-render','recovery-render','fresh-reopen-query','fresh-reopen-render']){
    const gate=deferred(),calls=[],frames=[],errors=[],commands=[];let role='A',number=0,renderNumber=0;
    const current=()=>({...((kind==='confirmation-render'&&role==='A')?ready:info),revision:role==='A'&&kind.startsWith('fresh-reopen')&&number>=2?'A-new':role});
    const c=createQuestController({program,programFactory:factory,query:async id=>{
        calls.push({role,id});number++;
        if(kind==='initial-query'&&number===1||kind==='validation-query'&&number===2)return gate.promise;
        if(kind==='fresh-reopen-query'&&number===3)return gate.promise;
        if(kind==='recovery-render'&&number===2)throw Error('same-session validation rejected');
        return current();},action:async a=>{commands.push({role,...a});return gate.promise;},
      render:async frame=>{renderNumber++;frames.push({revision:frame.info.revision,number:renderNumber});
        if(kind==='initial-render'&&renderNumber===1||['confirmation-render','recovery-render','fresh-reopen-render'].includes(kind)&&renderNumber===2)await gate.promise;},
      hide:()=>{},onError:e=>errors.push(e.message)});
    yes(typeof c.invalidate==='function');let pending;
    if(['initial-query','initial-render'].includes(kind))pending=c.open(461);
    else{await c.open(461);pending=c.pressOK();}
    await drain();
    if(kind==='validation-query'||kind.startsWith('action'))eq(await c.close(),false);
    eq(c.invalidate(),true);eq(c.inspect().visible,false);eq(c.inspect().pending,false);role='B';
    await c.open(461);const afterNew=calls.length;
    if(kind==='action-reject'||kind==='validation-query')gate.reject(Error('old session rejected'));
    else gate.resolve(kind==='action-success'?{ok:true}:kind==='initial-query'?{...info,revision:'A'}:kind==='fresh-reopen-query'?{...info,revision:'A-new'}:undefined);
    eq(await pending,null);eq(calls.length,afterNew);eq(c.inspect().revision,'B');eq(frames.at(-1).revision,'B');eq(errors,[]);
    eq(commands.length,kind.startsWith('action')?1:0);
    cases.push({runtime:label,name:kind,staleResult:null,newRevision:c.inspect().revision,
      queryCalls:calls,commands:commands.map(v=>({role:v.role,type:v.type})),staleErrors:errors});c.dispose();
  }
  {
    let current={...info},commands=[],frames=[];
    const c=createQuestController({program,programFactory:factory,query:async()=>structuredClone(current),action:async a=>{commands.push(a);return {ok:true};},
      render:async f=>frames.push(f),hide:()=>{}});
    await c.open(461);eq((await c.pressOK()).type,'accept');eq(commands.length,1);
    current={...ready,revision:'ready'};await c.open(461);eq(c.inspect().stage,'return-items');
    eq(await c.pressOK(),{sent:false,confirmation:true});eq(commands.length,1);eq(frames.at(-1).body,info.Completion);
    eq((await c.pressOK()).type,'complete');eq(commands.map(v=>v.type),['accept','complete']);
    current={...info,Status:4};await c.open(461);eq(await c.pressOK(),null);eq(await c.close(),true);eq(commands.at(-1).type,'cancel');
    c.dispose();eq(c.invalidate(),false);cases.push({runtime:label,name:'normal-accept-two-stage-return-cancel',commands:commands.map(v=>v.type)});
  }
  {
    let n=0,errors=[];
    const c=createQuestController({program,programFactory:factory,query:async()=>{if(++n===2)throw Error('current error');return info;},
      action:async()=>({ok:true}),render:async()=>{},hide:()=>{},onError:e=>errors.push(e.message)});
    await c.open(461);await assert.rejects(c.pressOK(),/current error/);assertions++;eq(errors,['current error']);eq(c.inspect().revision,'A');
    c.dispose();cases.push({runtime:label,name:'current-error-not-suppressed',queryCalls:n,errors});
  }
}
await runSuite(hostLifecycleVM,null,'host-lifecycle-vm-fixture-not-original-AS');
const programPath=new URL('analysis/raw/tutorial-npc-mission-resources-20261115/qa-v1/program-v1.json',root);
const hasOriginal=!args.includes('--public-only')&&fs.existsSync(programPath);
if(hasOriginal)await runSuite(createMissionProgramRuntime,JSON.parse(fs.readFileSync(programPath)),'pinned-original-AS-branch-interpreter-not-Flash');
let baselineReplay=[];
if(args.includes('--baseline-replay')){
  const original=(await import(new URL('quest-ui-baseline.mjs',area))).createQuestController;
  const factory=hasOriginal?createMissionProgramRuntime:hostLifecycleVM,program=hasOriginal?JSON.parse(fs.readFileSync(programPath)):null;
  for(const kind of ['query','action']){
    const gate=deferred(),calls=[],frames=[];let role='A',n=0;
    const c=original({program,programFactory:factory,query:async id=>{calls.push({role,id});if(kind==='query'&&++n===2)return gate.promise;return {...info,revision:role};},
      action:async()=>gate.promise,render:async f=>frames.push(f.info.revision),hide:()=>{},onError:()=>{}});
    await c.open(461);const pending=c.pressOK();await drain();eq(await c.close(),false);eq(c.inspect().visible,true);
    role='B';gate.reject(Error('old session rejected'));await pending.catch(()=>{});eq(calls.at(-1),{role:'B',id:461});eq(frames.at(-1),'B');
    baselineReplay.push({kind,reopenedRole:'B',runtime:hasOriginal?'pinned-original-AS':'host-lifecycle-fixture'});c.dispose();
  }
}
const report={format:'oc2-ordinary-npc-quest-lifecycle-check-v2',assertions,cases,baselineReplay,
  testedModule:'deploy/quest_ui.mjs',testedSourceSHA256:sha(fs.readFileSync(new URL('deploy/quest_ui.mjs',root))),
  originalProgramSHA256:hasOriginal?sha(fs.readFileSync(programPath)):null,publicHostFixtureAlwaysExecuted:true,
  originalFlashOrAndroidExecuted:false,compatibilityDTOs:true,serversStarted:0,browserUsed:false,existingSavesReadOrWritten:false};
if(args.includes('--report')){fs.mkdirSync(area,{recursive:true});fs.writeFileSync(new URL('lifecycle-check-v2.json',area),JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify({assertions,cases:cases.length,baselineReplay:baselineReplay.length,testedActualDeployController:true,
  publicFixture:true,privateOriginalAS:hasOriginal,serversStarted:0,browserUsed:false}));
