import assert from 'node:assert/strict';
import {createOrdinaryNPCQuestMarkerReader} from '../deploy/ordinary_npc_marker.mjs';
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++;},throws=f=>{assert.throws(f);assertions++;};
let host={mapId:1,entry:2079,sourceID:'npc:6598',displayed:true};
const r=createOrdinaryNPCQuestMarkerReader({readHost:()=>host}),a=r.beginSession();
const info=(Status,revision)=>({origin:'compatible-quest-layer',questId:461,revision,Status,
  phase:{6:'available',4:'accepted',9:'ready'}[Status],progress:{current:Status===9?4:Status===4?1:0,required:4},
  Title:'HOST fixture',Detail:'HOST fixture',Objective:'HOST fixture',Incomplete:'HOST fixture',Completion:'HOST fixture',
  hasReward:false,HasCollectedTbItem:false,IsFailed:false,IsInTuto:false,NumGold:0,NumXp:0,NumFever:0,NumAdvExp:0,NumItem:0,NumItemOp:0,NumItemTb:0,fixedItems:[],returnItems:[]});
const response=(status,rev)=>({info:info(status,rev),state:{origin:'compatible-quest-layer',mapId:1,revision:rev,
  quests:status===6?[]:[{id:461,status,current:status===9?4:1,required:4}],completedQuestIds:[]}});
eq(r.inspect(a).selected,false);
for(const [i,status]of [6,4,9].entries()){
  eq(r.receiveQuery(a,response(status,i)),true);const plan=r.inspect(a);eq(plan.status,status);eq(plan.selected,true);
  eq(plan.display,false);eq(plan.originalActorQualification,false);eq(plan.requiresListCommon,false);
  eq(r.detailIntent(a),{kind:'compatible-open-quest-detail',questId:461,window:'MissionDialog',isOpenedFromList:false,isAutoAccepted:false,requiresListCommon:false,networkSent:false,taskApproved:false});
}
eq(r.receiveQuery(a,response(6,0)),false);eq(r.inspect(a).status,9);
for(const patch of [{entry:750},{sourceID:'npc:2482'},{mapId:5},{displayed:false}]){
  const before=host;host={...host,...patch};eq(r.inspect(a).selected,false);eq(r.detailIntent(a),null);host=before;
}
const b=r.beginSession();eq(r.inspect(a).selected,false);eq(r.receiveQuery(a,response(9,8)),false);eq(r.inspect(b).selected,false);
eq(r.receiveQuery(b,response(6,0)),true);eq(r.inspect(b).status,6);
eq(r.receiveState(b,{origin:'compatible-quest-layer',mapId:1,revision:1,quests:[{id:461,status:4,current:0,required:4}],completedQuestIds:[]}),true);
eq(r.inspect(b).selected,false);eq(r.receiveQuery(b,response(6,0)),false);
eq(r.receiveQuery(b,response(4,1)),true);
const bad=response(9,2);bad.state.quests[0].status=4;throws(()=>r.receiveQuery(b,bad));eq(r.inspect(b).selected,false);
throws(()=>r.receiveQuery(b,{...response(6,2),info:{...info(6,2),questId:208}}));
eq(r.receiveQuery(b,response(9,2)),true);
eq(r.receiveState(b,{origin:'compatible-quest-layer',mapId:1,revision:3,quests:[],completedQuestIds:[461]}),true);eq(r.inspect(b).selected,false);
throws(()=>r.receiveState(b,{origin:'compatible-quest-layer',mapId:1,revision:4,quests:[{id:202,status:4,current:0,required:4}],completedQuestIds:[]}));
r.invalidate();eq(r.receiveQuery(b,response(6,5)),false);eq(r.detailIntent(b),null);
r.dispose();throws(()=>r.beginSession());
console.log(JSON.stringify({assertions,publicHostFixturesOnly:true,originalASOrNativeRun:false,nativeDisplayAdmissionNeverSynthesized:true,serversStarted:0,browserUsed:false,savesChanged:false}));
