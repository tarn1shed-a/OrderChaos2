import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {questListAppearance,questListGroup,isEmptyQuestList} from '../public/quest-list-state.js';
const profile={statusIcons:{4:'unfinished',8:'dailyComplete',9:'complete'},failedIcon:'failed',bookGroups:{normal:[1,2],daily:[9]}};
test('only an authoritative empty accepted list enables the recovered empty branch; a catalog is not that list',()=>{
 assert(isEmptyQuestList({mode:'source-reference',active:[]}));
 for(const value of [null,{}, {catalog:[{id:572}]},{active:null},{active:[{questId:572}]}])assert(!isEmptyQuestList(value));
});
test('original list failure overrides completion while missing flags do not invent a state',()=>{
 assert.equal(questListAppearance(4,false,profile).icon,'unfinished');assert.equal(questListAppearance(9,false,profile).icon,'complete');
 assert.equal(questListAppearance(8,false,profile).icon,'dailyComplete');assert.equal(questListAppearance(9,true,profile).icon,'failed');
 for(const [status,failed]of [[null,false],[9,null],[9,undefined],[NaN,false],[57,false]])assert.equal(questListAppearance(status,failed,profile).icon,null);
});
test('original book groups use quest type separately from status',()=>{
 assert.equal(questListGroup(1,profile),'normal');assert.equal(questListGroup(2,profile),'normal');assert.equal(questListGroup(9,profile),'daily');
 for(const type of [0,3,4,8,10,undefined])assert.equal(questListGroup(type,profile),null);
});
const path=new URL('../../game-data/converted/gameplay/native.json',import.meta.url);
test('converted original constants drive list appearance without treating source quest rows as accepted', {skip:!existsSync(path)},()=>{
 const quests=JSON.parse(readFileSync(path,'utf8')).quests,p=quests.clientStates;
 assert.equal(p.status.QMGR_QUEST_NOT_FINISHED,4);assert.equal(p.status.QMGR_QUEST_FINISHED,9);
 assert.equal(questListAppearance(p.status.QMGR_QUEST_DAILY_FINISHED,false,p).icon,'dailyComplete');
 assert(quests.catalog.every(q=>!Object.hasOwn(q,'status')&&!Object.hasOwn(q,'failed')));
});
