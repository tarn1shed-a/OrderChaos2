import assert from 'node:assert/strict';
import fs from 'node:fs';
import {validateQuestView,createQuestController,questRewardLayout} from '../deploy/quest_ui.mjs';
import {createMissionProgramRuntime} from './tutorial_npc_mission_bridge_program.mjs';
const base=new URL('../analysis/raw/tutorial-npc-mission-resources-20261115/qa-v1/',import.meta.url);
const program=JSON.parse(fs.readFileSync(new URL('program-v1.json',base)));
const optional=JSON.parse(fs.readFileSync(new URL('assets/source-mission-optional/optional-assets.json',base)));
let count=0;const eq=(a,b)=>{assert.deepEqual(a,b);count++;},yes=v=>{assert.ok(v);count++;};
const info={origin:'compatible-quest-layer',questId:461,revision:'a',Status:6,Title:'原文标题',Detail:'原文详情',Objective:'原文目标',Incomplete:'原文未完成',Completion:'原文完成',
  hasReward:true,NumGold:9,NumXp:512,NumFever:5,NumAdvExp:0,NumItem:1,NumItemOp:0,NumItemTb:1,
  fixedItems:[{id:20028,count:1,icon:'ui/icons/item/red_skull_plan.png',quality:3,isGem:false,hasPromo:false,restricted:false}],
  returnItems:[{id:50125,count:4,icon:'ui/icons/item/service_part.png',quality:1,isGem:false,hasPromo:false,restricted:false}],
  HasCollectedTbItem:false,IsFailed:false,IsInTuto:false};
let current=structuredClone(info),commands=[],frames=[],hidden=0,errors=[];
const controller=createQuestController({query:async()=>structuredClone(current),action:async a=>{commands.push(a);return {ok:true};},program,programFactory:createMissionProgramRuntime,
  render:async s=>frames.push(s),hide:()=>hidden++,onError:e=>errors.push(e.message)});
await controller.open(461);eq(frames.at(-1).title,info.Title);eq(frames.at(-1).body,info.Detail);eq(frames.at(-1).objective,info.Objective);eq(frames.at(-1).okVisible,true);
await Promise.all([controller.pressOK(),controller.pressOK()]);eq(commands.map(v=>v.type),['accept']);eq(controller.inspect().visible,false);
current={...info,Status:9,revision:'b',HasCollectedTbItem:true};await controller.open(461);
eq(frames.at(-1).displayFlag,4);eq(frames.at(-1).statusFinished,0);eq(frames.at(-1).body,info.Incomplete);
const first=await controller.pressOK();eq(first,{sent:false,confirmation:true});eq(commands.length,1);eq(frames.at(-1).statusFinished,1);eq(frames.at(-1).displayFlag,3);
eq(frames.at(-1).body,info.Completion);
const second=await controller.pressOK();eq(second.type,'complete');eq(commands.at(-1).revision,'b');eq(commands.length,2);eq(controller.inspect().visible,false);
await controller.open(461);await controller.close();eq(commands.at(-1).type,'cancel');eq(controller.inspect().visible,false);
current={...info,Status:4,revision:'c'};await controller.open(461);eq(frames.at(-1).okVisible,false);eq(frames.at(-1).grayVisible,true);eq(await controller.pressOK(),null);eq(commands.length,3);
current={...info,revision:'d'};await controller.open(461);current={...current,revision:'e'};eq(await controller.pressOK(),{sent:false,reason:'state-changed'});eq(commands.length,3);eq(controller.inspect().revision,'e');
current={...info,NumItemTb:0,returnItems:[],Status:9,revision:'f'};await controller.open(461);eq(frames.at(-1).statusFinished,1);await controller.pressOK();eq(commands.at(-1).type,'complete');
for(const patch of [{origin:'Hero_GetQuestInfoNPC'},{NumItem:4},{returnItems:[]},{NumItemOp:1},{revision:null},{fixedItems:[{...info.fixedItems[0],icon:''}]}]){
  assert.throws(()=>validateQuestView({...info,...patch}));count++;
}
for(const flag of [0,1,2,3,4,5,6,7]){const layout=questRewardLayout(optional,flag);yes(Number.isFinite(layout.y));yes(Number.isFinite(layout.Board.height));}
// A superseded async query may not re-open a cancelled/new window.
let release;const slow=createQuestController({query:()=>new Promise(r=>release=r),action:async()=>({ok:true}),program,programFactory:createMissionProgramRuntime,
  render:async()=>{throw Error('Stale result must not render');},hide:()=>{}});
const loading=slow.open(461);slow.dispose();release(info);eq(await loading,null);eq(slow.inspect().visible,false);
controller.dispose();yes(hidden>0);eq(errors,[]);
console.log(JSON.stringify({assertions:count,originalProgramBranches:true,compatibilityCommandsOnly:true,livePlayerOrSaveChanged:false}));
