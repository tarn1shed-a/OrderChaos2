import test from 'node:test';
import assert from 'node:assert/strict';
import {QuestState} from '../game/quest-state.mjs';
import {emptyInteractionState,mergeInteractionState,interactionStateText} from '../public/object-interaction-state.js';
test('source spawn State never invents runtime quest/loot flags or accepted tasks',()=>{
 const state=new QuestState({objects:[{id:'object-1',spawnId:3064,entry:621,sourceState:0}]});
 const view=state.snapshot('char-a');assert.deepEqual(view.active,[]);assert.equal(view.mode,'source-reference');
 assert.deepEqual(view.objects[0].state,emptyInteractionState());assert.equal(interactionStateText(view.objects[0].state),'交互状态未知');
 view.objects[0].state.canLoot=true;assert.equal(state.snapshot('char-a').objects[0].state.canLoot,null);
});
test('partial source state retains absent fields and explicit false, validates before changing revision',()=>{
 const state=new QuestState({objects:[{id:'object-1',spawnId:1,entry:621}]});
 state.applySourceState('char-a','object-1',{questStatus:0,canLoot:false});
 let object=state.snapshot('char-a').objects[0];assert.equal(object.revision,1);assert.equal(object.state.hasChatMenu,null);assert.equal(interactionStateText(object.state),'交互状态未知');
 state.applySourceState('char-a','object-1',{hasChatMenu:false,interactives:[]});object=state.snapshot('char-a').objects[0];assert.equal(object.state.questStatus,0);assert.equal(interactionStateText(object.state),'当前无可用交互');
 state.applySourceState('char-a','object-1',{canLoot:true});assert.equal(interactionStateText(state.snapshot('char-a').objects[0].state),'可拾取');
 state.applySourceState('char-a','object-1',{canLoot:true});assert.equal(state.snapshot('char-a').objects[0].revision,3);
 assert.throws(()=>state.applySourceState('char-a','object-1',{canLoot:1}));assert.equal(state.snapshot('char-a').objects[0].revision,3);
 assert.throws(()=>state.applySourceState('char-a','other',{canLoot:true}));
 assert.equal(state.snapshot('char-b').objects[0].state.canLoot,null);
});
test('quest interactions validate field types without interpreting unknown status numbers as unlocks',()=>{
 const current=mergeInteractionState(null,{questStatus:57,questType:3,interactives:[{questId:632,questType:2,questInteractType:1,interactId:12,instantQuestFirst:false}]});
 assert.equal(interactionStateText(current),'1 项任务交互');
 for(const invalid of [{questStatus:NaN},{questStatus:2**32},{hasChatMenu:0},{interactives:[{questId:632}]},{interactives:[{questId:632,questType:2,questInteractType:1,Function:'evil()'}]},{Function:'evil()'}])assert.throws(()=>mergeInteractionState(current,invalid));
 assert.equal(current.questStatus,57);assert.equal(mergeInteractionState(current,{interactives:null}).interactives,null);
});
