// Real pinned source branches + actual journal controller, explicit in-memory
// compatible-state/action ports. No browser, server, ledger file or native VM.
import fs from 'node:fs';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createJournalController,journalRows}from'../deploy/quest_journal_state.mjs';
import {createOriginalJournalControls}from'./preview/quest_journal_program.mjs';
const root=new URL('../',import.meta.url),args=process.argv.slice(2),results=[];
const paths={program:'analysis/raw/ordinary-quest-journal-20261116/cpu-v3/source-program-v1.json',
  profile:'analysis/raw/ordinary-quest-journal-live-20261116/assets-v2/profile.json',
  ordinary:'analysis/raw/ordinary-quest-journal-art-20261116/existing-quest-profile.json'};
const hash=text=>crypto.createHash('sha256').update(text).digest('hex');
const sources=Object.fromEntries(Object.entries(paths).map(([k,p])=>[k,new URL(p,root)]));
const available=!args.includes('--public-only')&&Object.values(sources).every(fs.existsSync);
async function record(name,fn){try{await fn();results.push({name,passed:true});}catch(e){results.push({name,passed:false,error:e.message});}}
const defer=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return{promise,resolve,reject};};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
await record('browser helper rejects unpinned source before controller construction',()=>assert.rejects(()=>createOriginalJournalControls('{}')));
let inputProofs=null;
if(available){
  const source=fs.readFileSync(sources.program,'utf8'),program=JSON.parse(source),profile=JSON.parse(fs.readFileSync(sources.profile));
  const ordinary=JSON.parse(fs.readFileSync(sources.ordinary)),quest=ordinary.quests.find(q=>q.id===461);
  inputProofs=Object.fromEntries(Object.entries(sources).map(([key,p])=>[key,{path:paths[key],sha256:hash(fs.readFileSync(p))}]));
  const state=(n=0,revision=n)=>({origin:'compatible-quest-layer',mapId:1,revision,quests:[{id:461,title:quest.title,status:n===4?9:4,current:n,required:4}],completedQuestIds:[]});
  const empty=(revision=0,completed=false)=>({...state(0,revision),quests:[],completedQuestIds:completed?[461]:[]});
  const info=s=>({origin:'compatible-quest-layer',questId:461,revision:s.revision,Status:s.quests[0].status,
    Title:quest.title,Objective:quest.objectiveText,Detail:quest.detail,progress:{current:s.quests[0].current,required:4},
    hasReward:true,NumGold:quest.reward.money,NumXp:quest.reward.xp,NumFever:quest.reward.favor,NumAdvExp:0,NumItem:1,NumItemOp:0,
    fixedItems:[{id:20028,count:1,icon:profile.reward.icon}]});
  function fixture(overrides={}){
    let session={connected:true,characterId:'isolated-A',epoch:1},snapshot=state(),queries=0;
    const actions=[],frames=[],errors=[],vms=[];
    const ports={profile,program:source,readSession:()=>session,readState:async()=>structuredClone(snapshot),
      query:async()=>{queries++;return info(snapshot);},readTrackedQuest:()=>snapshot.quests.length?461:null,
      action:async command=>{actions.push(command);snapshot=empty(snapshot.revision+1);return{ok:true,state:structuredClone(snapshot)};},
      programFactory:async(...args)=>{const vm=await createOriginalJournalControls(...args);vms.push(vm);return vm;},
      onChange:v=>frames.push(v),onError:e=>errors.push(e)};
    const controller=createJournalController({...ports,...overrides});
    return{controller,ports,actions,frames,errors,vms,get snapshot(){return snapshot;},set snapshot(v){snapshot=v;},
      get session(){return session;},set session(v){session=v;},get queries(){return queries;}};
  }
  await record('profile matches all three frozen original consumers and program hash',()=>{
    assert.equal(hash(source),'fb5f7211e4a9353ed025a30e6beb4863276437fd6adfb395ed93d340fba71c7a');
    for(const name of ['getQuestList','displayCurrQuest','MessageBoxYesNo'])assert.equal(profile.methods[name],program.methods['QuestListHero.'+name].codeSHA256);
  });
  await record('empty and completed accepted lists never create detail or original question',async()=>{
    for(const completed of [false,true]){const f=fixture();f.snapshot=empty(3,completed);await f.controller.open();
      assert.deepEqual(f.controller.inspect().rows,[]);assert.equal(f.queries,0);assert.equal(await f.controller.askAbandon(),null);
      assert.equal(f.vms.length,0);assert.deepEqual(f.actions,[]);f.controller.dispose();}
  });
  await record('current only-supported accepted row keeps original level2 and type9 Quality0 without ActionID16',async()=>{
    const f=fixture();await f.controller.open();const d=f.controller.inspect().detail;
    assert.equal(d.questId,461);assert.equal(d.displayLevel,2);assert.equal(d.rewards.items[0].quality,0);assert.equal(d.rewards.items[0].nativeActionID,null);
    assert.equal(d.step.sourceType,2);assert.equal(d.step.current,0);f.controller.dispose();
  });
  await record('actual original cancel callback has NO=1 and cannot become abandon command',async()=>{
    const f=fixture();await f.controller.open();await f.controller.askAbandon();const vm=f.vms[0];
    const show=vm.inspect().actions[0];assert.deepEqual(show.arguments.slice(0,3),['MessageBoxYesNo','Test',5]);
    assert.equal(show.arguments[3].msg,program.strings.GENERAL_QUESTBOOK_CONFIRM.text);
    assert.deepEqual(await f.controller.answerAbandon(false),{sent:false,cancelled:true});
    assert.equal(vm.inspect().actions.find(v=>v.boundary==='MessageBox.OnBtnClick').arguments[0],1);
    assert.equal(vm.inspect().actions.filter(v=>v.boundary==='Hero_AbandonQuest').length,0);assert.deepEqual(f.actions,[]);f.controller.dispose();
  });
  await record('actual original YES intent reaches existing compatible abandon shape once',async()=>{
    const gate=defer();let f;f=fixture({action:async c=>{f.actions.push(c);return gate.promise;}});
    await f.controller.open();await f.controller.askAbandon();const answer=f.controller.answerAbandon(true);await settle();
    assert.equal(await f.controller.answerAbandon(true),null);
    assert.deepEqual(f.actions,[{type:'abandon',questId:461,revision:0,origin:'compatible-quest-layer'}]);
    const vm=f.vms[0];assert.deepEqual(vm.inspect().actions.find(v=>v.boundary==='Hero_AbandonQuest').arguments,[461]);
    gate.resolve({ok:true,state:empty(1)});assert.equal((await answer).sent,true);assert.deepEqual(f.controller.inspect().rows,[]);f.controller.dispose();
  });
  await record('return-state9 still uses original YES branch and source talk objective',async()=>{
    const f=fixture();f.snapshot=state(4,5);await f.controller.open();assert.equal(f.controller.inspect().detail.step.sourceType,6);
    await f.controller.askAbandon();await f.controller.answerAbandon(true);assert.equal(f.actions[0].revision,5);assert.equal(f.actions[0].questId,461);f.controller.dispose();
  });
  await record('progress refresh invalidates displayed original question before confirmation',async()=>{
    const f=fixture();await f.controller.open();await f.controller.askAbandon();f.snapshot=state(2,2);f.controller.update(f.snapshot);await settle();
    assert.equal(f.controller.inspect().modal,null);assert.equal(await f.controller.answerAbandon(true),null);assert.deepEqual(f.actions,[]);f.controller.dispose();
  });
  await record('fresh-state mismatch refreshes without invoking original YES or command',async()=>{
    const f=fixture();await f.controller.open();await f.controller.askAbandon();f.snapshot=state(1,1);
    assert.deepEqual(await f.controller.answerAbandon(true),{sent:false,reason:'state-changed'});
    assert.equal(f.vms[0].inspect().actions.filter(v=>v.boundary==='Hero_AbandonQuest').length,0);assert.deepEqual(f.actions,[]);f.controller.dispose();
  });
  await record('old-character detail response cannot replace new character detail',async()=>{
    const gate=defer();let count=0;const f=fixture({query:()=>++count===1?gate.promise:Promise.resolve(info(state(2,5)))});
    const opening=f.controller.open();await settle();f.controller.invalidate();f.session={connected:true,characterId:'isolated-B',epoch:2};f.snapshot=state(2,5);
    await f.controller.open();gate.resolve(info(state()));assert.equal(await opening,null);assert.equal(f.controller.inspect().revision,5);assert.equal(f.controller.inspect().detail.step.current,2);f.controller.dispose();
  });
  await record('session change during real-source factory preparation refuses stale question',async()=>{
    const gate=defer();let constructed=0;const f=fixture({programFactory:async(...args)=>{await gate.promise;constructed++;return createOriginalJournalControls(...args);}});
    await f.controller.open();const asking=f.controller.askAbandon();f.controller.invalidate();f.session={connected:true,characterId:'isolated-B',epoch:2};gate.resolve();
    assert.equal(await asking,null);assert.equal(constructed,1);assert.equal(f.controller.inspect().visible,false);assert.deepEqual(f.actions,[]);f.controller.dispose();
  });
  await record('pending pre-confirm read cannot roll back newer completed accepted state',async()=>{
    const gate=defer();let reads=0,queries=0;const f=fixture({readState:()=>++reads===1?Promise.resolve(state()):gate.promise,
      query:async()=>++queries===1?info(state()):info(state(1,1))});
    await f.controller.open();await f.controller.askAbandon();const answer=f.controller.answerAbandon(true);await settle();
    f.snapshot=empty(5,true);f.controller.update(f.snapshot);await settle();assert.equal(f.controller.inspect().revision,5);
    gate.resolve(state(1,1));await answer;const observed=f.controller.inspect();
    assert.equal(observed.revision,5,'Late readState revision1 must not replace already observed completed revision5');
    assert.deepEqual(observed.rows,[]);assert.deepEqual(f.actions,[]);f.controller.dispose();
  });
  await record('question refresh awaiting detail returns null after character session changes',async()=>{
    const gate=defer();let q=0;const f=fixture({query:()=>++q===1?Promise.resolve(info(state())):gate.promise});
    await f.controller.open();await f.controller.askAbandon();f.snapshot=state(1,1);const answer=f.controller.answerAbandon(true);await settle();
    f.controller.invalidate();f.session={connected:true,characterId:'isolated-B',epoch:2};gate.resolve(info(state(1,1)));
    assert.equal(await answer,null,'Old session continuation must return null after awaited refresh');assert.equal(f.controller.inspect().visible,false);assert.deepEqual(f.actions,[]);f.controller.dispose();
  });
  await record('authorized old-character action may commit but reply cannot return after refresh closes its session',async()=>{
    let f,switched=false;f=fixture({onChange:v=>{
      f.frames.push(v);
      if(v.visible&&v.revision===1&&v.rows.length===0&&!switched){switched=true;f.controller.invalidate();f.session={connected:true,characterId:'isolated-B',epoch:2};}
    }});
    await f.controller.open();await f.controller.askAbandon();const result=await f.controller.answerAbandon(true);
    assert.equal(f.actions.length,1,'A previously authorized action is not undone by UI invalidation');
    assert.equal(f.actions[0].questId,461);assert.equal(switched,true);
    assert.equal(result,null,'Old result must not return after awaited refresh changes session');assert.equal(f.controller.inspect().visible,false);f.controller.dispose();
  });
  await record('unsupported task and available state cannot create an accepted selection',()=>{
    assert.throws(()=>journalRows(profile,{...state(),quests:[{...state().quests[0],id:208}]}));
    assert.throws(()=>journalRows(profile,{...state(),quests:[{...state().quests[0],status:6}]}));
  });
}
const report={format:'oc2-journal-real-source-controller-audit-v1',sourceAvailable:available,inputProofs,
  controllerSHA256:hash(fs.readFileSync(new URL('deploy/quest_journal_state.mjs',root))),
  browserSourceHelperSHA256:hash(fs.readFileSync(new URL('tools/preview/quest_journal_program.mjs',root))),
  results,passed:results.filter(v=>v.passed).length,failed:results.filter(v=>!v.passed).length,
  originalBranchesExecuted:available,originalASVMExecuted:false,networkOrBrowser:false,ledgerOrSavesChanged:false,
  boundaries:['Real pinned source branch instructions interpreted by frozen helper','Accepted state/action/session are explicit in-memory compatible transport ports','No original task approval, GUI modal reachability or original cache delivery is implied']};
const output=args.indexOf('--report');if(output>=0){const file=new URL(args[output+1],root);if(fs.existsSync(file))throw Error('Preserve audit receipt');fs.mkdirSync(new URL('./',file),{recursive:true});fs.writeFileSync(file,JSON.stringify(report,null,2)+'\n');}
console.log(JSON.stringify(report,null,2));if(report.failed)process.exitCode=1;
