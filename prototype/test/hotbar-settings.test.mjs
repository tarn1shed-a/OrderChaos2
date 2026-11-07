import test from 'node:test';
import assert from 'node:assert/strict';
import {defaultHotbar,validHotbar,validBinding,swapHotbarSlots,rebindHotbarSlot,hotbarSkillForEvent,bindingLabel,loadHotbar,saveHotbar,HOTBAR_STORAGE_PREFIX} from '../public/hotbar-settings.js';

test('dragging preserves both skill identities and leaves hotkeys attached to their slots',()=>{
  const initial=defaultHotbar(),moved=swapHotbarSlots(initial,0,7),swapped=swapHotbarSlots(moved,7,1);
  assert(validHotbar(initial));assert.equal(moved.slots[7],'fireball');assert.equal(moved.slots[0],null);
  assert.equal(swapped.slots[1],'fireball');assert.equal(swapped.slots[7],'frost_blast');
  assert.equal(hotbarSkillForEvent(moved,{code:'Digit8'}),'fireball');
  assert.equal(hotbarSkillForEvent(moved,{code:'Digit1'}),null);
  assert.equal(initial.slots[0],'fireball');assert.deepEqual(moved.bindings,initial.bindings);
  assert.throws(()=>swapHotbarSlots(initial,0,10),/格子无效/);
});
test('rebind validates reserved movement/UI keys and rejects conflicts without modifying settings',()=>{
  const initial=defaultHotbar();
  for(const code of ['KeyW','KeyA','KeyS','KeyD','KeyF','Space','KeyB','KeyC','KeyH','ArrowUp','Escape','Tab','F5','__proto__']){
    assert.equal(validBinding({code,shift:false}),false);assert(rebindHotbarSlot(initial,0,{code,shift:false}).error);
  }
  assert(rebindHotbarSlot(initial,0,{code:'Digit2',shift:false}).error.includes('第 2 格'));
  const next=rebindHotbarSlot(initial,0,{code:'KeyQ',shift:false}).settings;
  assert.equal(hotbarSkillForEvent(next,{code:'KeyQ'}),'fireball');
  assert.equal(hotbarSkillForEvent(next,{code:'Digit1'}),null);
  for(const flags of [{ctrlKey:true},{metaKey:true},{altKey:true},{repeat:true},{isComposing:true},{shiftKey:true}])assert.equal(hotbarSkillForEvent(next,{code:'KeyQ',...flags}),null);
  const shifted=rebindHotbarSlot(next,1,{code:'KeyQ',shift:true}).settings;
  assert.equal(hotbarSkillForEvent(shifted,{code:'KeyQ',shiftKey:true}),'frost_blast');
  assert.equal(bindingLabel(shifted.bindings[1]),'Shift+Q');
  assert.equal(initial.bindings[0].code,'Digit1');
});
test('settings restore per character, round-trip moves and bindings, and keep corrupt or inaccessible storage safe',()=>{
  const data=new Map(),storage={getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value)};
  const next=rebindHotbarSlot(swapHotbarSlots(defaultHotbar(),0,7),7,{code:'KeyE',shift:false}).settings;
  assert.equal(saveHotbar(storage,'character-a',next).saved,true);
  assert.deepEqual(loadHotbar(storage,'character-a').settings,next);
  assert.deepEqual(loadHotbar(storage,'character-b').settings,defaultHotbar());
  const bad='{"version":1,"slots":["forged"]}';data.set(HOTBAR_STORAGE_PREFIX+'bad',bad);
  assert(loadHotbar(storage,'bad').warning);assert.equal(data.get(HOTBAR_STORAGE_PREFIX+'bad'),bad);
  assert(loadHotbar(null,'a').warning);assert(saveHotbar(null,'a',next).error);
  assert(saveHotbar(storage,'a',{...next,gold:100}).error);
  const duplicate=defaultHotbar();duplicate.slots[1]='fireball';assert.equal(validHotbar(duplicate),false);
  const forged=defaultHotbar();forged.bindings[0].code='KeyW';assert.equal(validHotbar(forged),false);
  const collisions=defaultHotbar();collisions.bindings[1]={...collisions.bindings[0]};assert.equal(validHotbar(collisions),false);
  assert(saveHotbar(storage,'character-a',defaultHotbar()).saved);
  assert.deepEqual(loadHotbar(storage,'character-a').settings,defaultHotbar());
});
