// Independent READ-ONLY review. Deferred AS/HTTP ports are explicit test
// fixtures: no native approval, browser, game server or save is executed.
import assert from'node:assert/strict';
import{readFileSync,writeFileSync,mkdirSync,existsSync,copyFileSync}from'node:fs';
import{resolve,join}from'node:path';
import{pathToFileURL}from'node:url';
import{createHash}from'node:crypto';
const root=resolve('.'),out=resolve(process.argv[2]||'analysis/raw/quest-journal-independent-review-20261116/run-v1');
if(!out.startsWith(join(root,'analysis/raw')+'/')||existsSync(out))throw Error('Fresh ignored review directory required');
mkdirSync(join(out,'source'),{recursive:true});
const files=['quest_journal_state.mjs','quest_journal.mjs','quest_journal_delivery.mjs','quest_delivery.mjs','quest_tracking.mjs','quest_world.mjs'];
const sha=p=>createHash('sha256').update(readFileSync(p)).digest('hex');
for(const name of files)copyFileSync(join(root,'deploy',name),join(out,'source',name));
const {createJournalController}=await import(pathToFileURL(join(out,'source/quest_journal_state.mjs')));
const {prepareJournalDelivery,stageQuestJournalWorld}=await import(pathToFileURL(join(out,'source/quest_journal_delivery.mjs')));
const profilePath=join(root,'analysis/raw/ordinary-quest-journal-live-20261116/assets-v5/profile.json');
const profile=JSON.parse(readFileSync(profilePath));
const state=(revision=1,n=0)=>({origin:'compatible-quest-layer',mapId:1,revision,
  quests:[{id:461,title:'Independent host fixture',status:n===4?9:4,current:n,required:4}],completedQuestIds:[]});
const info=s=>({origin:'compatible-quest-layer',questId:461,revision:s.revision,Status:s.quests[0].status,
  Title:s.quests[0].title,Objective:'Explicit fixture summary',Detail:'Explicit fixture detail',
  progress:{current:s.quests[0].current,required:4},hasReward:true,NumGold:9,NumXp:512,NumFever:5,
  NumAdvExp:0,NumItem:1,NumItemOp:0,fixedItems:[{id:20028,count:1,icon:profile.reward.icon}]});
const defer=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return{promise,resolve,reject};};
const settle=()=>new Promise(setImmediate),checks=[],findings=[];
const vm=()=>({abandon:()=>({actions:[{boundary:'ShowMsg'}]}),messageButton:()=>({actions:[]})});
function fixture(overrides={}){
  const f={session:{connected:true,characterId:'fixture-A',epoch:1},state:state(),actions:[],errors:[],frames:[]};
  f.controller=createJournalController({profile,program:'EXPLICIT MOCK AS PORT',readSession:()=>f.session,
    readState:async()=>f.state,query:async()=>info(f.state),action:async command=>{
      f.actions.push(command);return{ok:true,state:{...state(2),quests:[]}};
    },readTrackedQuest:()=>461,programFactory:async()=>vm(),onChange:value=>f.frames.push(value),
    onError:error=>f.errors.push(error.message),...overrides});return f;
}
async function check(name,fn){const result=await fn();checks.push({name,passed:true,...result});}
await check('repeated-question-cancel-must-not-reopen-after-late-factory',async()=>{
  const factories=[],f=fixture({programFactory:()=>{const d=defer();factories.push(d);return d.promise;}});
  await f.controller.open();const first=f.controller.askAbandon(),second=f.controller.askAbandon();
  factories[0].resolve(vm());await first;await f.controller.answerAbandon(false);
  assert.equal(f.controller.inspect().modal,null);
  if(factories[1])factories[1].resolve(vm());await second;
  const reopened=f.controller.inspect().modal!==null;
  if(reopened)findings.push({id:'question-reopens-after-cancel',priority:2,
    file:'deploy/quest_journal_state.mjs',function:'askAbandon',factoryRequests:factories.length});
  assert.equal(f.actions.length,0);f.controller.dispose();return{factoryRequests:factories.length,reopened};
});
await check('old-character-factory-rejection-must-not-escape-to-new-character-button-error',async()=>{
  const old=defer(),f=fixture({programFactory:()=>old.promise}),uiErrors=[];
  await f.controller.open();
  // Same external .catch(onError) boundary as the real SVG button handler.
  const waiting=f.controller.askAbandon().catch(error=>uiErrors.push({character:f.session.characterId,message:error.message}));
  f.controller.close();f.session={connected:true,characterId:'fixture-B',epoch:2};await f.controller.open();
  old.reject(Error('OLD-A-FACTORY-ERROR'));await waiting;
  if(uiErrors.length)findings.push({id:'old-factory-error-escapes-new-session',priority:3,
    file:'deploy/quest_journal_state.mjs',function:'askAbandon',observed:uiErrors});
  assert.equal(f.controller.inspect().detail.title,'Independent host fixture');assert.equal(f.actions.length,0);
  f.controller.dispose();return{staleErrors:uiErrors.length};
});
await check('older-same-key-query-finally-must-not-clear-new-query-dedup-record',async()=>{
  const query1=defer(),query2=defer(),state2=defer();let queries=0,reads=0;
  const f=fixture({readState:()=>++reads===1?Promise.resolve(state()):state2.promise,
    query:()=>++queries===1?query1.promise:queries===2?query2.promise:Promise.resolve(info(state()))});
  const old=f.controller.open();await settle();f.controller.close();const current=f.controller.open();
  f.controller.update(state());query1.resolve(info(state()));await old;state2.resolve(state());await settle();
  query2.resolve(info(state()));await current;await settle();
  if(queries>2)findings.push({id:'old-query-finally-clears-new-same-key-load',priority:3,
    file:'deploy/quest_journal_state.mjs',function:'loadDetail finally',queries,expected:2});
  assert.equal(f.controller.inspect().detail.title,'Independent host fixture');f.controller.dispose();return{queries};
});
await check('switch-and-close-ignore-old-successful-query-and-dispatch-no-action',async()=>{
  const old=defer();let q=0;const f=fixture({query:()=>++q===1?old.promise:Promise.resolve(info(state()))});
  const waiting=f.controller.open();await settle();f.controller.invalidate();
  f.session={connected:true,characterId:'fixture-B',epoch:2};await f.controller.open();
  old.resolve({...info(state()),Title:'MUST-NOT-REPLACE-NEW-CHARACTER'});await waiting;
  assert.equal(f.controller.inspect().detail.title,'Independent host fixture');assert.equal(f.actions.length,0);
  assert.equal(f.errors.length,0);f.controller.dispose();return{oldReplySuppressed:true};
});
await check('missing-new-profile-keeps-legacy-delivery-optional',async()=>{
  let additions=0;const result=await prepareJournalDelivery(root,{},()=>{additions++;});
  assert.equal(result,false);assert.equal(additions,0);return{oldPackageProfileAbsent:true,additions};
});
await check('present-but-incomplete-new-profile-fails-closed-before-module-admission',async()=>{
  let additions=0;await assert.rejects(()=>prepareJournalDelivery(root,
    {'/assets/source-quest-journal/profile.json':{path:profilePath}},()=>{additions++;}));
  assert.equal(additions,0);return{partialClosureRejected:true};
});
await check('world-stage-retains-session-checks-and-closes-other-input-owners',async()=>{
  const source=readFileSync(join(out,'source/quest_world.mjs'),'utf8'),staged=stageQuestJournalWorld(source);
  assert(staged.includes('const blocked=()=>!connected||journal?.isOpen||skills?.isOpen'));
  assert(staged.includes('questState=null;journal?.invalidate();skills?.disconnect()'));
  assert(staged.includes('identity?.characterId!==caller||generation!==connection'));
  assert(staged.includes('stop();journal?.dispose();skills?.dispose();socket?.close();'));
  assert(staged.includes('if(document.documentElement.dataset.sourceQuestJournal'));
  assert(staged.includes('journal?.update(state)'));assert.throws(()=>stageQuestJournalWorld(staged));
  return{staticGeneratedWiringChecked:true,DOMOrModalExecuted:false};
});
await check('accepted-only-and-explicit-compatible-markers-remain-in-state-contract',async()=>{
  const f=fixture({readState:async()=>({...state(),quests:[],completedQuestIds:[461]})});
  await f.controller.open();assert.equal(f.controller.inspect().rows.length,0);
  assert.equal(f.controller.inspect().nativeMessage,false);assert.equal(f.controller.inspect().compatibilityLayer,true);
  assert.equal(await f.controller.askAbandon(),null);assert.equal(f.actions.length,0);f.controller.dispose();
  return{staticOrCompletedQuestNotAccepted:true};
});
const report={format:'oc2-quest-journal-independent-review-v1',passed:findings.length===0,checks,findings,
  reviewed:files.map(name=>({path:'deploy/'+name,sha256:sha(join(out,'source',name))})),
  sourceProfile:{path:profilePath.slice(root.length+1),sha256:sha(profilePath)},
  evidencePorts:'Explicit deferred mock AS/HTTP; no game action/ledger was run',
  remaining:['Parent owns actual browser modal/layout acceptance','Optional-delivery branch tests are not complete Linux/package acceptance'],
  noOperations:['native-VM','browser','game-server','Docker','save-write','shared-runtime-edit','Git-write','deployment']};
writeFileSync(join(out,'review.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({passed:report.passed,checks:checks.length,findings,output:out}));
