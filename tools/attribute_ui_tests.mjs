import{test}from'node:test';import assert from'node:assert/strict';
import{sourceHPFrame,sourceScrollRatio,attributeRoleValues}from'../deploy/attribute_state.mjs';
import{readFileSync}from'node:fs';import{stageEntry}from'../deploy/stage_runtime.mjs';
test('original HP display keeps its 2-percent minimum and 60 source frames, including zero max HP',()=>{
  assert.equal(sourceHPFrame(0,100),1);assert.equal(sourceHPFrame(50,100),30);assert.equal(sourceHPFrame(100,100),60);assert.equal(sourceHPFrame(150,100),60);assert.equal(sourceHPFrame(0,0),60);
});
test('original scroll controls move ten percent internally and stop at either end',()=>{
  assert.equal(sourceScrollRatio(0,-1),0);assert.equal(sourceScrollRatio(1,1),1);assert.equal(sourceScrollRatio(.05,-1),0);assert.equal(sourceScrollRatio(.95,1),1);assert.equal(sourceScrollRatio(.5,0),.5);
});
test('read-only role bridge leaves unavailable original properties absent rather than mapping attack into physical strength',()=>{
 const character=Object.freeze({name:'角色',level:2,hp:88,maxHp:100,stats:Object.freeze({armor:0,attack:20}),xp:30});const before=JSON.stringify(character);
 const values=attributeRoleValues(character,{value:30,max:60});assert.deepEqual(values,{name:'角色',level:'2',hp:'88 / 100',armor:'0',xp:'30 / 60'});assert.equal(JSON.stringify(character),before);assert(!('physicalStrength'in values));assert(!('combatScore'in values));assert(!('xp'in attributeRoleValues(character)));
});
test('character window uses the existing C-key adapter and does not restore prototype menus or names',t=>{
 let original;try{original=readFileSync(new URL('../analysis/raw/showcase-20261110/running-preview/prototype/public/explore-map.js',import.meta.url),'utf8');}catch{t.skip('Private source stays local');return;}
 const output=stageEntry(original,{entryUI:true});assert(output.includes("if(e.code==='KeyC')"));assert(output.includes('attributeUI?.isOpen||'));assert(output.includes('attributeUI?.update(data)'));assert(output.includes('open=false;'));
 const controller=readFileSync(new URL('../deploy/attribute_ui.mjs',import.meta.url),'utf8');assert(!controller.includes('WebSocket'));assert(!controller.includes("method:'POST'"));assert(controller.includes('Unknown original-server fields stay blank'));
});
