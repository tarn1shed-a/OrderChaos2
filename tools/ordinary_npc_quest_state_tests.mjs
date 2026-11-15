// Original-data compatible ledger + pinned original MissionDialog program.
// Explicit isolated in-memory actors/credentials only; no server or file save.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {OrdinaryQuestLedger,checkQuestRole} from '../deploy/ordinary_quests.mjs';
import {questContext} from '../deploy/quest_transport.mjs';
import {createQuestController} from '../deploy/quest_ui.mjs';
import {createMissionProgramRuntime} from './tutorial_npc_mission_bridge_program.mjs';
const root=new URL('../',import.meta.url),area=new URL('analysis/raw/ordinary-npc-quest-20261115/',root),args=process.argv.slice(2);
const paths={profile:'analysis/raw/plain-quest-feasibility-20261115/executor-profile-v3.json',
  program:'analysis/raw/tutorial-npc-mission-resources-20261115/qa-v1/program-v1.json',
  list:'analysis/raw/tutorial-npc-interaction-ui-20261115/candidate-v4/assets/profile.json'};
const sha=v=>crypto.createHash('sha256').update(v).digest('hex');
if(args.includes('--public-only')||Object.values(paths).some(p=>!fs.existsSync(new URL(p,root)))){
  console.log(JSON.stringify({privateOriginalDataCases:args.includes('--public-only')?'skipped: explicit public-only mode':'skipped: source profile/AS absent',serversStarted:0,browserUsed:false}));process.exit(0);
}
const {sourceQuestListIcon}=await import('./tutorial_npc_interaction_ui_state.mjs');
const inputs=Object.fromEntries(Object.entries(paths).map(([k,p])=>[k,JSON.parse(fs.readFileSync(new URL(p,root)))]));
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++;},yes=v=>{assert.ok(v);assertions++;},throws=(fn,why)=>{assert.throws(fn,why);assertions++;};
let serialized=null,t=1000;
const ledger=new OrdinaryQuestLedger(inputs.profile,{clock:()=>t++,write:raw=>{serialized=raw;}}),q=ledger.quest(461),npc=ledger.actors.get(q.startActor);
const ids=['00000000-0000-4000-8000-00000000000a','00000000-0000-4000-8000-00000000000b'];
const tokens=['a'.repeat(64),'b'.repeat(64)],store={records:new Map()},active=new Map();
for(let i=0;i<2;i++){
  const role={id:ids[i],tokenHash:sha(tokens[i]),level:0,hp:100};store.records.set(ids[i],role);
  active.set(ids[i],{character:role,ordinaryQuestMap:1,player:{x:npc.position[0],y:npc.position[2],worldY:npc.position[1],hp:100,mapInspector:false},motion:{point:(x,z)=>({x,z})}});
}
const identity=i=>({characterId:ids[i],resumeToken:tokens[i]});
const context=i=>questContext(store,active,identity(i),1);
const position=(i,p)=>Object.assign(active.get(ids[i]).player,{x:p[0],worldY:p[1],y:p[2]});
const act=(i,type,extra={})=>ledger.act(context(i),{type,questId:461,revision:ledger.role(ids[i]).revision,...extra});
const info=i=>{const v=ledger.query(context(i),461);return {...v,fixedItems:v.fixedItems.map(x=>({...x,hasPromo:false,restricted:false})),returnItems:v.returnItems.map(x=>({...x,hasPromo:false,restricted:false}))};};
const stages=[],commands=[],frames=[];let owner=0;
const c=createQuestController({program:inputs.program,programFactory:createMissionProgramRuntime,
  query:async()=>info(owner),action:async cmd=>{commands.push({owner,type:cmd.type});if(cmd.type!=='cancel')act(owner,cmd.type);return {ok:true};},
  render:async state=>frames.push({owner,Status:state.info.Status,body:state.body,ok:state.okVisible,gray:state.grayVisible,displayFlag:state.displayFlag,statusFinished:state.statusFinished}),hide:()=>{}});
eq(q.minLevel,0);eq(info(0).Status,6);eq(info(1).Status,6);
eq(sourceQuestListIcon(inputs.list,6),'ui/icons/head_obj/quest_available.png');
await c.open(461);eq(frames.at(-1).body,q.detail);eq(frames.at(-1).ok,true);stages.push({phase:'available',Status:6,listIcon:sourceQuestListIcon(inputs.list,6)});
// Source profile range is explicitly a compatibility web guard.
position(0,[npc.position[0]+npc.range+1,npc.position[1],npc.position[2]]);throws(()=>act(0,'accept'),/距离太远/);eq(ledger.role(ids[0]).revision,0);
position(0,npc.position);await c.pressOK();eq(ledger.query(context(0),461).Status,4);eq(ledger.snapshot(ids[1]).quests,[]);
await c.open(461);eq(frames.at(-1).body,q.incomplete);eq(frames.at(-1).gray,true);eq(await c.pressOK(),null);await c.close();
stages.push({phase:'accepted',Status:4,listIcon:sourceQuestListIcon(inputs.list,4)});
eq(sourceQuestListIcon(inputs.list,4),'ui/icons/head_obj/quest_unfinished.png');
for(let i=0;i<4;i++){
  const object=ledger.objects.get(q.collect.objectIds[i]);position(0,object.position);act(0,'collect',{objectId:object.id});
  eq(ledger.snapshot(ids[0]).quests[0].current,i+1);eq(info(1).progress.current,0);
  if(i===0){throws(()=>act(0,'collect',{objectId:object.id}),/已经收集/);eq(ledger.role(ids[0]).revision,2);}
}
eq(info(0).Status,9);eq(ledger.snapshot(ids[0]).inventory,{'50125':4});
eq(sourceQuestListIcon(inputs.list,9),'ui/icons/head_obj/quest_complete.png');
stages.push({phase:'ready',Status:9,listIcon:sourceQuestListIcon(inputs.list,9),item50125:4});
// A different character may collect the same source placement independently.
position(1,npc.position);act(1,'accept');const first=ledger.objects.get(q.collect.objectIds[0]);position(1,first.position);act(1,'collect',{objectId:first.id});
eq(info(1).Status,4);eq(info(1).progress.current,1);eq(info(0).progress.current,4);
// Valid token alone is insufficient: actual connection/map/role owns context.
throws(()=>questContext(store,active,{characterId:ids[0],resumeToken:tokens[1]},1),/凭据无效/);
const originalWS=active.get(ids[0]);active.delete(ids[0]);throws(()=>context(0),/先进入/);active.set(ids[0],originalWS);
eq(info(0).Status,9);eq(ledger.snapshot(ids[1]).quests[0].current,1);
position(0,npc.position);active.get(ids[0]).player.hp=0;throws(()=>act(0,'complete'),/不能交互/);active.get(ids[0]).player.hp=100;
active.get(ids[0]).player.mapInspector=true;throws(()=>act(0,'complete'),/不能交互/);active.get(ids[0]).player.mapInspector=false;
throws(()=>ledger.act(context(0),{type:'complete',questId:461,revision:0}),/状态已更新/);
await c.open(461);eq(c.inspect().stage,'return-items');eq(frames.at(-1).body,q.incomplete);
eq(await c.pressOK(),{sent:false,confirmation:true});eq(info(0).Status,9);eq(frames.at(-1).body,q.completion);eq(commands.filter(v=>v.type==='complete').length,0);
eq((await c.pressOK()).type,'complete');eq(info(0).Status,0);eq(ledger.snapshot(ids[0]).quests,[]);eq(ledger.snapshot(ids[0]).completedQuestIds,[461]);
eq(ledger.snapshot(ids[0]).inventory,{});eq(ledger.snapshot(ids[0]).rewards,{xp:512,money:9,favor:5,items:{'20028':1}});
throws(()=>act(0,'complete'),/已经交付/);eq(ledger.snapshot(ids[0]).rewards.money,9);eq(info(1).Status,4);eq(info(1).progress.current,1);
stages.push({phase:'completed',Status:0,StatusMeaning:'compatibility-internal-hide-only-not-source-QMGR-enum',listIcon:null,rewards:ledger.snapshot(ids[0]).rewards});
// In-memory serialized replay through the actual role validator, no old files.
const stored=JSON.parse(serialized),reloaded=new OrdinaryQuestLedger(inputs.profile);
for(const [id,role]of Object.entries(stored.roles)){checkQuestRole(role,reloaded.quests);reloaded.roles[id]=role;}
eq(reloaded.snapshot(ids[0]),ledger.snapshot(ids[0]));eq(reloaded.snapshot(ids[1]),ledger.snapshot(ids[1]));
const before=ledger.snapshot(ids[1]);c.invalidate();owner=1;await c.open(461);eq(frames.at(-1).Status,4);await c.close();eq(ledger.snapshot(ids[1]),before);c.dispose();
const report={format:'oc2-ordinary-npc-quest-state-check-v2',assertions,stages,commands,
  testedController:'deploy/quest_ui.mjs',testedControllerSHA256:sha(fs.readFileSync(new URL('deploy/quest_ui.mjs',root))),
  sourceFiles:Object.fromEntries(Object.entries(paths).map(([k,p])=>[k,{path:p,sha256:sha(fs.readFileSync(new URL(p,root)))}])),
  scope:{actualLedgerAndContextAndOriginalASProgram:true,explicitInMemoryConnectionAndIdentityFixtures:true,actualServerStarted:false,
    actualBrowserApproachOrReconnect:false,actualFileOrProcessRestart:false,inMemorySerializedReplay:true,existingSavesReadOrWritten:false,
    sourceNPCActivityGUIDCreated:false,completedStatus0OriginalEnum:false,headMarkerInstalled:false}};
if(args.includes('--report'))fs.writeFileSync(new URL('state-check-v2.json',area),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({assertions,phases:stages.length,originalASBranches:true,roles:2,inMemoryOnly:true,serversStarted:0,browserUsed:false}));
