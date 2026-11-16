// Exact PR6 integration control-flow audit. No HTTP listener, WS connection,
// browser, original worker, save writes or parent-source modifications.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync,mkdirSync,symlinkSync} from 'node:fs';
import {resolve} from 'node:path';import {pathToFileURL} from 'node:url';import {createHash} from 'node:crypto';
import {runInNewContext} from 'node:vm';
const AREA=resolve('analysis/raw/ordinary-quest461-integration-audit-20261116'),WT=resolve(process.argv.find(x=>x.startsWith('--worktree='))?.slice(11)||'analysis/raw/creation-race-preview-20261115/release-parent-v1/worktree');
const reportPath=resolve(process.argv.find(x=>x.startsWith('--report='))?.slice(9)||AREA+'/audit-v1.json'),expectFixed=process.argv.includes('--expect-fixed');
if(!reportPath.startsWith(AREA+'/')||existsSync(reportPath))throw Error('New owned report path required');mkdirSync(AREA,{recursive:true});
const sha=b=>createHash('sha256').update(b).digest('hex'),ref=p=>({path:p,sha256:sha(readFileSync(p))});
const files=['deploy/quest_gather_server.mjs','deploy/quest_gather_presenter.mjs','deploy/quest_world.mjs','deploy/quest_transport.mjs','deploy/quest_server_overlay.mjs','deploy/quest_collection.mjs','deploy/ordinary_quests.mjs','tools/preview/ordinary-quest461-gather-events.mjs','tools/preview/ordinary-quest461-gather-browser.mjs'];
const eventsPath=resolve(process.argv.find(x=>x.startsWith('--events-module='))?.slice(16)||WT+'/tools/preview/ordinary-quest461-gather-events.mjs'),presenterPath=resolve(process.argv.find(x=>x.startsWith('--presenter-module='))?.slice(19)||WT+'/deploy/quest_gather_presenter.mjs'),worldPath=resolve(process.argv.find(x=>x.startsWith('--world-module='))?.slice(15)||WT+'/deploy/quest_world.mjs');
const sources=[...new Set(files.map(x=>x==='tools/preview/ordinary-quest461-gather-events.mjs'?eventsPath:x==='deploy/quest_gather_presenter.mjs'?presenterPath:x==='deploy/quest_world.mjs'?worldPath:WT+'/'+x))].map(ref),BINDING='c03c5f0cd41117b7f88b32f41d6a9a299f5bf0e802a6ea307de22e92ad37a473';
const {createCompatible461GatherEvents,createCompatible461GatherInbox}=await import(pathToFileURL(eventsPath));
const {createGatherBrowserLibrary,createGatherEventReceiver}=await import(pathToFileURL(WT+'/tools/preview/ordinary-quest461-gather-browser.mjs'));
const {createQuestCollection}=await import(pathToFileURL(WT+'/deploy/quest_collection.mjs'));
const {OrdinaryQuestLedger}=await import(pathToFileURL(WT+'/deploy/ordinary_quests.mjs'));
const S=resolve('analysis/raw/ordinary-quest461-browser-gather-20261116/source-v2'),sourceBytes=new Uint8Array(readFileSync(S+'/source.json')),bindingBytes=new Uint8Array(readFileSync(S+'/binding.json'));
const library=await createGatherBrowserLibrary({sourceBytes,bindingBytes}),results=[],findings=[],details=[];
const A='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',R='resources:ordinary-map:INTEGRATION-QA';
const sourceContext={movementState:5,postureState:8,actionState:0x800,actorFlag4c:0,actorPointer638:null,kindAttribute0:0x120a,rawActorByte114:1,cachedWeaponEvent:0,sourceClassWeaponRow:null,explicitNoWeaponRecord:true,loadedEngineFlags:3,sourceFilterByte:0};
const inputs=()=>({randomWords:['1','2','3','4'],initialIdleVariant:0,sourceContext:structuredClone(sourceContext)});
const profile={format:'oc2-compatible-461-channel-v1',originalServerRecovered:false,mapId:1,questId:461,objectEntry:467,skillProtoId:15,skillChannelTime:1500,isChannel:false,programSHA256:'4aed22d400be720600dfa91a4030b6dd7ef3cd43b04728f07f5898d46b134be2',visualSHA256:'8b47d8cf5395ae2f60beacc81564b559f1f5f2fe287d262b4f59c07609a1fc0c',artSHA256:'6f3f2ae104dc1eb5d659b30136a5137ef2d718a8e7833514490d3218e69e10b3'};
const data=()=>({format:'oc2-compatible-ordinary-quests-v1',originalServerRecovered:false,mapId:1,actors:[{id:'npc:1',entry:1,mapId:1,position:[0,0,0],range:3}],objects:[{id:'object:1',entry:467,mapId:1,position:[1,0,0],range:2}],quests:[{id:461,sourceScript:'',minLevel:1,title:'fixture',detail:'fixture',objectiveText:'fixture',incomplete:'fixture',completion:'fixture',startActor:'npc:1',finishActor:'npc:1',prerequisites:[],removeQuests:[],finishSourceType:6,takeBackAll:true,collect:{itemId:2,count:1,sourceType:2,sourceIndex:1,text:'fixture',objectIds:['object:1']},reward:{money:2,xp:3,favor:4,items:[]}}]});
const fixtures=[];let serial=0;
function fixture(){let now=0,tick=0;const owner={},ctx={characterId:A,mapId:1,level:1,position:[1,0,0],alive:true,inspector:false},ledger=new OrdinaryQuestLedger(data());const collection=createQuestCollection({ledger,profile,clock:()=>now,nonce:()=>`cast:${++serial}`});ledger.act({...ctx,position:[0,0,0]},{type:'accept',questId:461,revision:0});
 const tape=createCompatible461GatherEvents({collection,historyLimit:8192,readOwner:x=>x===owner?{characterId:A,actorKey:A,roomKey:R,profession:2,mapId:1}:null,nextSessionKey:()=>`session:${++serial}`,makeSourceSession:x=>{const i=inputs();return{session:library.createSession({...x,...i}),inputs:i,bindingId:BINDING};}});
 const f={tape,ledger,collection,ctx,begin:()=>tape.begin(ctx,owner,{type:'collect-start',questId:461,objectId:'object:1',revision:ledger.snapshot(A).revision}),finish:c=>tape.finish(ctx,owner,c.id),cancel:c=>tape.cancel(ctx,owner,c.id),advance:x=>now+=x,tick:()=>{now+=50;return tape.tickRoom(R,{tick:++tick,milliseconds:50,serverTime:1763251200000+now});}};fixtures.push(f);return f;}
async function check(name,run){await run();results.push({name,passed:true});}
const host=()=>({connected:true,connection:{},epoch:1,characterId:A,roomKey:R});
function inbox(){const h=host(),poses=[],errors=[];const box=createCompatible461GatherInbox({readHost:()=>h,readActor:key=>({actorKey:key,profession:2,displayed:true,bodyKey:'elf-female',bindingId:BINDING,epoch:1}),makeReceiver:(record,actor)=>{const s=library.createSession({sessionKey:record.sessionKey,actorKey:actor.actorKey,profession:2,...record.inputs}),r=createGatherEventReceiver({session:s,sessionKey:record.sessionKey,actorKey:actor.actorKey,profession:2,initialSequence:0});return{consume:e=>r.consume(e),apply:p=>poses.push(p),dispose:()=>r.dispose()};},onFault:e=>errors.push(e)});return{box,poses,errors};}
try{
await check('actual collection begin before next tick: replay watermark cannot include unpublished roomPending events',()=>{
 const f=fixture();f.tick();f.begin();const snapshot=f.tape.snapshotRoom(R),x=inbox();x.box.replay(snapshot);const next=f.tick(),state=x.box.consume(next);
 details.push({case:'pending-begin',snapshot,next,receiverState:state,receiverFaults:x.errors});
 if(!state.needsReplay)assert.equal(state.applied,1);
 if(state.needsReplay)findings.push({id:'snapshot-unpublished-events',severity:'replay lifecycle',observed:{snapshotTick:snapshot.tick,snapshotEvents:snapshot.records.map(r=>r.kind==='event'?r.event.operation:r.kind),nextTick:next.tick,nextEvents:next.records.map(r=>r.kind==='event'?r.event.operation:r.kind),receiverState:state,receiverFaults:x.errors},actualControllerAndFrozenSource:true,minimumSuggestion:'Snapshot only the history prefix already published by its returned room tick. Maintain a published history length/tick when tickRoom drains roomPending; omit brand-new sessions until their init has been published. Do not loosen receiver duplicate/sequence guards.'});x.box.dispose();
});
await check('actual success before next tick similarly duplicates a terminal event; no reward is inferred from this replay',()=>{
 const f=fixture();f.tick();const c=f.begin();f.tick();f.advance(1500);const result=f.finish(c);assert.equal(result.pending,false);const snapshot=f.tape.snapshotRoom(R),x=inbox();x.box.replay(snapshot);const next=f.tick(),state=x.box.consume(next);details.push({case:'pending-success',snapshot,next,receiverState:state,receiverFaults:x.errors});
 if(!state.needsReplay)assert.equal(state.applied,1);
 if(state.needsReplay)findings.push({id:'snapshot-unpublished-success',sameRootCause:'snapshot-unpublished-events',observed:{snapshotTick:snapshot.tick,nextTick:next.tick,receiverFaults:x.errors},minimumSuggestion:'Keep success queued for the next published tick; snapshot watermark and records must refer to the same boundary.'});assert.equal(f.ledger.snapshot(A).rewards.xp,0);x.box.dispose();
});
await check('actual gather server wrapper preserves pending/wrong-cancel semantics and rejects stale or unsupported presentation owners',async()=>{
 const runtime=AREA+'/source-layout-port',dir=runtime+'/game-data/converted/source-quest461-gather-v1';mkdirSync(dir,{recursive:true});
 for(const name of['source.json','binding.json']){const p=dir+'/'+name;if(!existsSync(p))symlinkSync(S+'/'+name,p);assert.equal(sha(readFileSync(p)),sha(readFileSync(S+'/'+name)));}
 const {createQuestGatherServer}=await import(pathToFileURL(WT+'/deploy/quest_gather_server.mjs'));
 const f=fixture(),role={id:A,profession:2,appearance:{race:2,gender:1},equipment:{mainHand:null}},player={id:A,hp:10,grounded:true,jump:null,cast:null},ws={character:role,player,input:{x:0,y:0},roomId:R,ordinaryQuestMap:1},game={entryStore:{records:new Map([[A,role]])},entryActive:new Map([[A,ws]])},faults=[];
 const server=await createQuestGatherServer({runtime,collection:f.collection,readGame:()=>game,onFault:e=>faults.push(e)});
 try{const command={type:'collect-start',questId:461,objectId:'object:1',revision:f.ledger.snapshot(A).revision},c=server.collection.begin(f.ctx,ws,command);
  assert.equal(server.collection.finish(f.ctx,ws,c.id).pending,true);server.collection.cancel(f.ctx,ws,'wrong:'+c.id);
  const first=server.tape.tickRoom(R,{tick:1,milliseconds:50,serverTime:1763251200050});assert(first.records.some(r=>r.event?.operation==='begin'));assert(first.records.some(r=>r.event?.operation==='frame'));assert(!first.records.some(r=>['interrupt','success'].includes(r.event?.operation)));
  server.collection.cancel(f.ctx,ws,c.id);const cancelled=server.tape.tickRoom(R,{tick:2,milliseconds:50,serverTime:1763251200100});assert.equal(cancelled.records.filter(r=>r.event?.operation==='interrupt').length,1);assert.deepEqual(f.ledger.snapshot(A).inventory,{});
  game.entryActive.set(A,{});const old=server.tape.tickRoom(R,{tick:3,milliseconds:50,serverTime:1763251200150});assert(old.records.some(r=>r.kind==='retire-session'));assert(!old.records.some(r=>r.event?.operation==='frame'));game.entryActive.set(A,ws);
  for(const condition of['mainHand','moving','airborne','sourceAvatar']){delete role.sourceAvatar;role.equipment.mainHand=null;ws.input.x=0;player.grounded=true;if(condition==='mainHand')role.equipment.mainHand='explicit-unknown-weapon';if(condition==='moving')ws.input.x=1;if(condition==='airborne')player.grounded=false;if(condition==='sourceAvatar')role.sourceAvatar={explicitUnsupported:true};
   server.collection.begin(f.ctx,ws,command);const p=server.tape.tickRoom(R,{tick:4+['mainHand','moving','airborne','sourceAvatar'].indexOf(condition),milliseconds:50,serverTime:1763251200200});assert(!p.records.some(r=>r.kind==='init-session'||r.event?.operation==='frame'));}
  assert.deepEqual(faults,[]);
 }finally{server.dispose();}
});
// Presenter import resolution only. Actual source producer/inbox/receiver stay
// unchanged; the target is a named async readiness/application port, not bones.
const targetFixture=AREA+'/controlled-target-fixture.mjs';if(!existsSync(targetFixture))writeFileSync(targetFixture,`export function createGatherPoseTarget(args){return globalThis[Symbol.for('oc2.integration.target.port')](args);}\n`);
const presenterOriginal=readFileSync(presenterPath,'utf8');let presenterText=presenterOriginal;
for(const name of['ordinary-quest461-gather-browser.mjs','ordinary-quest461-gather-events.mjs'])presenterText=presenterText.replace(JSON.stringify('./quest_gather/'+name),JSON.stringify(pathToFileURL(WT+'/tools/preview/'+name).href)).replace("'./quest_gather/"+name+"'",JSON.stringify(pathToFileURL(WT+'/tools/preview/'+name).href));
presenterText=presenterText.replace(pathToFileURL(WT+'/tools/preview/ordinary-quest461-gather-events.mjs').href,pathToFileURL(eventsPath).href);
presenterText=presenterText.replace("'./quest_gather/ordinary-quest461-gather-pose.mjs'",JSON.stringify(pathToFileURL(targetFixture).href));assert.equal(presenterText.slice(presenterText.indexOf('const BINDING=')),presenterOriginal.slice(presenterOriginal.indexOf('const BINDING=')));
const presenterCopy=AREA+'/presenter-resolved-'+sha(presenterText).slice(0,16)+'.mjs';if(!existsSync(presenterCopy))writeFileSync(presenterCopy,presenterText);else assert.equal(readFileSync(presenterCopy,'utf8'),presenterText);
const {createQuestGatherPresenter}=await import(pathToFileURL(presenterCopy));
const settle=async()=>{for(let n=0;n<12;n++)await Promise.resolve();};
await check('one failed target cannot prevent an otherwise ready actor from recovering after a legitimate packet gap',async()=>{
 const f=fixture(),h=host(),bodyA={},bodyB={},applied=[],errors=[],actors=new Map([[A,{actorKey:A,body:bodyA,epoch:1,profession:2,displayed:true}],['unsupported-peer',{actorKey:'unsupported-peer',body:bodyB,epoch:1,profession:2,displayed:true}]]);let queries=0;
 globalThis[Symbol.for('oc2.integration.target.port')]=async({body,actorKey})=>{if(body===bodyB)throw Error('explicit unsupported target port');return{apply:p=>applied.push(p),dispose(){}};};
 const presenter=await createQuestGatherPresenter({readHost:()=>h,readActor:key=>actors.get(key),queryReplay:async()=>{queries++;return{presentation:f.tape.snapshotRoom(R)};},legacyDataText:'explicit target port, not original model bytes',characterAnimationState:()=>null,load:async url=>({ok:true,arrayBuffer:async()=>(url.endsWith('source.json')?sourceBytes:bindingBytes).slice().buffer}),onFault:e=>errors.push(String(e?.message||e))});
 try{await presenter.register(A,bodyA,2,1);await presenter.register('unsupported-peer',bodyB,2,1);f.tick();f.begin();presenter.receive(f.tick());assert.equal(applied.length,1);f.tick();presenter.receive(f.tick());await settle();
  for(let n=0;n<16;n++){presenter.receive(f.tick());await settle();}presenter.afterBaseUpdate();
  details.push({case:'permanent-peer-target-failure',queries,appliedPoseCount:applied.length,faults:errors,packetsAfterGap:17});
  if(queries===0&&applied.length===1)findings.push({id:'all-ready-room-block',severity:'per-actor failure blocks room recovery',actualPresenterFunctionBody:true,explicitHostPorts:['async target ready/apply/dispose; no body success assumed'],observed:{queries,appliedPoseCount:applied.length,faults:errors,packetsAfterGap:17},minimumSuggestion:'Keep unsupported/failed actors strictly hidden without making them a global barrier. Recover ready actors, preserve per-stream sequence checks, and defer/replay only waiting actors when their actual target becomes ready. Do not replace a failed target with a fake ready object. Removing the allReady guard alone is insufficient if global wanted continues to queue every ready actor because another stream is refused.'});
  if(expectFixed){assert(queries>=1);assert(applied.length>1);assert(errors.includes('explicit unsupported target port'));}
 }finally{presenter.dispose();delete globalThis[Symbol.for('oc2.integration.target.port')];}
});
await check('late target completion and old replay completion after invalidation cannot apply to the new connection',async()=>{
 const f=fixture(),h=host(),body={},actor={actorKey:A,body,epoch:1,profession:2,displayed:true},applied=[];let resolveTarget,disposed=0,replayCalls=0;
 globalThis[Symbol.for('oc2.integration.target.port')]=()=>new Promise(resolve=>resolveTarget=()=>resolve({apply:p=>applied.push(p),dispose:()=>disposed++}));
 const presenter=await createQuestGatherPresenter({readHost:()=>h,readActor:()=>actor,queryReplay:async()=>{replayCalls++;return{presentation:f.tape.snapshotRoom(R)};},legacyDataText:'explicit target port',characterAnimationState:()=>null,load:async url=>({ok:true,arrayBuffer:async()=>(url.endsWith('source.json')?sourceBytes:bindingBytes).slice().buffer}),onFault:()=>{}});
 try{const pending=presenter.register(A,body,2,1);f.tick();f.begin();presenter.receive(f.tick());presenter.invalidate();h.epoch++;h.connection={};resolveTarget();await pending;await settle();assert.equal(disposed,1);assert.equal(applied.length,0);assert.equal(replayCalls,0);}
 finally{presenter.dispose();delete globalThis[Symbol.for('oc2.integration.target.port')];}
});
await check('an already in-flight replay response after invalidate cannot restore the old actor/connection',async()=>{
 const f=fixture(),h=host(),body={},actor={actorKey:A,body,epoch:1,profession:2,displayed:true},applied=[],errors=[];let resolveReplay,queries=0,disposals=0;
 globalThis[Symbol.for('oc2.integration.target.port')]=async()=>({apply:p=>applied.push(p),dispose:()=>disposals++});
 const presenter=await createQuestGatherPresenter({readHost:()=>h,readActor:()=>actor,queryReplay:()=>{queries++;const snapshot=f.tape.snapshotRoom(R);return new Promise(resolve=>resolveReplay=()=>resolve({presentation:snapshot}));},legacyDataText:'explicit target port',characterAnimationState:()=>null,load:async url=>({ok:true,arrayBuffer:async()=>(url.endsWith('source.json')?sourceBytes:bindingBytes).slice().buffer}),onFault:e=>errors.push(String(e?.message||e))});
 try{await presenter.register(A,body,2,1);f.tick();f.begin();presenter.receive(f.tick());assert.equal(applied.length,1);f.tick();presenter.receive(f.tick());await settle();assert.equal(queries,1);assert(resolveReplay);
  presenter.invalidate();h.epoch++;h.connection={};h.characterId='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb';resolveReplay();await settle();presenter.afterBaseUpdate();assert.equal(applied.length,1);assert.equal(disposals,1);assert.deepEqual(errors,[]);
 }finally{presenter.dispose();delete globalThis[Symbol.for('oc2.integration.target.port')];}
});
await check('a live target becoming ready replays exactly the published prefix and then follows the next frame continuously',async()=>{
 const f=fixture(),h=host(),body={},actor={actorKey:A,body,epoch:1,profession:2,displayed:true},applied=[],errors=[];let readyTarget,queries=0,disposals=0;
 globalThis[Symbol.for('oc2.integration.target.port')]=()=>new Promise(resolve=>readyTarget=()=>resolve({apply:p=>applied.push(p),dispose:()=>disposals++}));
 const presenter=await createQuestGatherPresenter({readHost:()=>h,readActor:()=>actor,queryReplay:async()=>{queries++;return{presentation:f.tape.snapshotRoom(R)};},legacyDataText:'explicit target port',characterAnimationState:()=>null,load:async url=>({ok:true,arrayBuffer:async()=>(url.endsWith('source.json')?sourceBytes:bindingBytes).slice().buffer}),onFault:e=>errors.push(String(e?.message||e))});
 try{const registration=presenter.register(A,body,2,1);f.tick();f.begin();presenter.receive(f.tick());presenter.receive(f.tick());assert.equal(applied.length,0);assert.equal(queries,0);
  const snapshot=f.tape.snapshotRoom(R),reference=inbox();reference.box.replay(snapshot);readyTarget();await registration;await settle();assert.equal(queries,1);assert.deepEqual(applied,reference.poses);assert.equal(applied.length,2);
  const next=f.tick();presenter.receive(next);reference.box.consume(next);assert.deepEqual(applied,reference.poses);assert.equal(applied.length,3);assert.deepEqual(errors,[]);assert.deepEqual(f.ledger.snapshot(A).inventory,{});reference.box.dispose();
 }finally{presenter.dispose();delete globalThis[Symbol.for('oc2.integration.target.port')];}assert.equal(disposals,1);
});
await check('stage overlay calls room tick once before per-recipient send and uses real WS close owner',async()=>{
 const {stageOrdinaryQuestServer}=await import(pathToFileURL(WT+'/deploy/quest_server_overlay.mjs'));
 const {entryServer}=await import(pathToFileURL(WT+'/deploy/entry_manage.mjs')),{stageSourceAvatarServer}=await import(pathToFileURL(WT+'/deploy/source_avatar_server.mjs')),{stageInspectorServer}=await import(pathToFileURL(WT+'/deploy/map_inspector.mjs'));
 const source=readFileSync('analysis/raw/showcase-20261110/running-preview/prototype/server.mjs','utf8'),staged=stageOrdinaryQuestServer(stageInspectorServer(stageSourceAvatarServer(entryServer(source,pathToFileURL(WT+'/deploy/movement_trace.mjs').href))));
 assert.equal(staged.split('ordinaryGatherEvents.tickRoom(').length-1,1);assert.equal(staged.split('ordinaryGatherEvents?.closeOwner(ws)').length-1,1);
 const tick=staged.indexOf('snapshot.questGather=ordinaryGatherEvents.tickRoom'),send=staged.indexOf('for (const ws of room.values()) send(ws, {...snapshot,');assert(tick>=0&&tick<send);assert(staged.includes('milliseconds:50,serverTime:snapshot.serverTime'));
});
await check('actual world current interrupt must stop the old finish waiter without cutting original1000ms interrupt display',async()=>{
 const world=readFileSync(worldPath,'utf8'),functionStart=world.indexOf('function invalidateCollection()'),functionEnd=world.indexOf('function approach(',functionStart),loopStart=world.indexOf('if(collectionAttempt?.id)for'),loopEnd=world.indexOf('if(msg.questState)',loopStart);
 assert(functionStart>=0&&functionEnd>functionStart&&loopStart>=0&&loopEnd>loopStart);
 const body=world.slice(functionStart,functionEnd),interrupt=world.slice(loopStart,loopEnd),{createSource461GatherProgress}=await import(pathToFileURL(WT+'/tools/preview/ordinary-quest461-gather.mjs')),{createChannelTimeline}=await import(pathToFileURL(WT+'/deploy/channel_timeline.mjs'));
 const program=readFileSync('analysis/raw/quest461-channel-parent-20261116/public/program.json','utf8'),profileText=readFileSync('analysis/raw/quest461-channel-parent-20261116/public/profile.json','utf8'),timeline=createChannelTimeline(await createSource461GatherProgress(program,profileText)),f=fixture(),timers=new Map(),calls=[];let timerSerial=0,channel,invalidations=0;
 const api=async(path,{command})=>{calls.push(command.type);if(command.type==='collect-start'){channel=f.begin();return{channel};}if(command.type==='collect-finish')return f.finish({id:command.channelId});throw Error('Unexpected explicit HTTP reply port');};
 const sandbox={api,gatherUI:{begin:c=>timeline.begin(c),end:(id,result)=>timeline.end(id,result),invalidate:()=>{invalidations++;timeline.invalidate();}},questState:f.ledger.snapshot(A),setTimeout:(callback,ms)=>{const id=++timerSerial;timers.set(id,{callback,ms});return id;},clearTimeout:id=>timers.delete(id)};
 runInNewContext(`let connected=true,generation=1,identity={characterId:${JSON.stringify(A)}},npcPageLive=true,collectionAttempt=null,selfId=${JSON.stringify(A)};\n${body}\nglobalThis.control={run:collectWithChannel,receive(msg){${interrupt}},inspect:()=>collectionAttempt};`,sandbox);
 const promise=sandbox.control.run({questId:461,id:'object:1'}).then(()=>({ok:true}),e=>({error:e.message}));await settle();assert(channel);assert.equal(timers.size,1);timeline.advance(1200);f.advance(1200);f.cancel(channel);
 const packet=f.tick();sandbox.control.receive({questGather:packet});assert.equal(timeline.inspect().phase,'interrupt');timeline.advance(300);const before=timeline.inspect().state.shown;
 for(const timer of[...timers.values()])timer.callback();await settle();const result=await promise,after=timeline.inspect();
 details.push({case:'world-matching-interrupt',commands:calls,invalidations,beforeOriginal1000ms:before,afterWaiter:after.id?{phase:after.phase,shown:after.state.shown}:{invalidated:true},result});
 if(calls.includes('collect-finish')||invalidations)findings.push({id:'interrupt-leaves-finish-waiter',severity:'current authorized cancel control cuts source interrupt UI',actualWorldFunctionAndWSEventLoop:true,explicitPorts:['HTTP replies delegate real collection','timeout scheduling only','actual source timeline used'],observed:{commands:calls,invalidations,interruptAgeWhenUIInvalidated:300,result},minimumSuggestion:'Only for matching current trusted self/scope interrupt, mark attempt cancelled and clear+wake its waiter; live() must reject cancelled. Preserve gatherUI.end interrupt and its1000ms source Timer. Do not call invalidateCollection for this path and do not add a movement cancel rule.'});
 if(expectFixed){assert.deepEqual(calls,['collect-start']);assert.equal(invalidations,0);assert.equal(after.phase,'interrupt');assert.equal(after.state.shown,true);timeline.advance(699);assert.equal(timeline.inspect().state.shown,true);timeline.advance(1);assert.equal(timeline.inspect().state.shown,false);}
 assert.deepEqual(f.ledger.snapshot(A).inventory,{});assert.equal(f.ledger.snapshot(A).rewards.xp,0);
});
await check('actual world API async response checks current role/generation/connected before applying received state',async()=>{
 const world=readFileSync(worldPath,'utf8'),start=world.indexOf('async function api('),end=world.indexOf('function refreshNPCMarker(',start);assert(start>=0&&end>start);
 for(const changed of['character','generation','disconnect']){let resolveBody;const applied=[],sandbox={fetch:async()=>({ok:true,json:()=>new Promise(resolve=>resolveBody=resolve)}),applyQuestState:s=>applied.push(s)};
  runInNewContext(`let identity={characterId:${JSON.stringify(A)},resumeToken:'explicit-fixture-token'},generation=1,connected=true,npcMarkerSession=null;\n${world.slice(start,end)}\nglobalThis.control={run:()=>api('action',{command:{type:'fixture-only'}}),change(kind){if(kind==='character')identity={characterId:'other'};if(kind==='generation')generation++;if(kind==='disconnect')connected=false;}};`,sandbox);
  const promise=sandbox.control.run().then(()=>({ok:true}),e=>({error:e.message}));await settle();sandbox.control.change(changed);resolveBody({state:{origin:'compatible-quest-layer',revision:99,owner:'old'}});const result=await promise;assert(result.error?.includes('连接已变更'));assert.equal(applied.length,0);
 }
});
await check('all five parent inputs and exact library/controller sources remain unchanged by this audit',()=>{for(const r of sources)assert.equal(sha(readFileSync(r.path)),r.sha256);});
}finally{for(const f of fixtures)f.tape.dispose();library.dispose();}
if(expectFixed)assert.deepEqual(findings,[],'Actual current source must close these concrete integration defects');
const report={format:'compatible461-integration-read-only-audit-v1',expectFixed,sources,passed:results.length,results,findings,actualPR6ControllerAndFrozenNoSOSource:true,authoredIsolatedLedgerRowsAndClock:true,presenterTargetReadinessIsExplicitPort:true,originalActivityQualificationOrTaskApprovalClaimed:false,browserOrServerOrSaveOrDockerOrProductionTouched:false,parentFilesEdited:false,details};writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,details:'Saved full packet controls only in receipt'},null,2));
