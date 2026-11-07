import test from 'node:test';
import assert from 'node:assert/strict';
import {createContextControl} from '../public/context-control.js';

function fixture(t){
  const previous=[globalThis.window,globalThis.document];globalThis.window=new EventTarget();globalThis.document=new EventTarget();
  t.after(()=>{[globalThis.window,globalThis.document]=previous;});
  const element=new EventTarget(),captures=new Set(),sent=[],image={};let enabled=true;
  Object.assign(element,{dataset:{},classList:{add(){},remove(){}},setAttribute(){},querySelector:()=>image,
    setPointerCapture:id=>captures.add(id),hasPointerCapture:id=>captures.has(id),releasePointerCapture:id=>captures.delete(id),
    getBoundingClientRect:()=>({left:0,top:0,right:100,bottom:100}),contains:value=>value===element});
  document.elementFromPoint=()=>element;
  const control=createContextControl(element,{enabled:()=>enabled,send:v=>sent.push(v),icons:{loot:{url:'loot.png'},jump:{url:'jump.png'}}});
  function emit(type,fields={}){const event=new Event(type,{cancelable:true});Object.assign(event,{button:0,pointerId:1,clientX:50,clientY:50,...fields});element.dispatchEvent(event);}
  return {element,control,sent,image,emit,disable(){enabled=false;}};
}
const loot=generation=>({kind:'loot',targetId:'wolf',generation});
test('source contextual handoff releases held jump first and a tap sends only a typed claim',t=>{
  const f=fixture(t);f.emit('pointerdown');f.control.update(loot('life-1'));
  assert.deepEqual(f.sent,[{type:'jump',pressed:true},{type:'jump',pressed:false}]);
  f.emit('pointerup');assert.equal(f.sent.length,2);assert.equal(f.image.src,'loot.png');
  f.emit('pointerdown');assert.equal(f.sent.length,2);f.emit('pointerup');
  assert.deepEqual(f.sent.at(-1),{type:'loot',targetId:'wolf',generation:'life-1'});
  f.control.update(null);assert.equal(f.image.src,'jump.png');f.emit('pointerdown');f.emit('pointerup');
  assert.deepEqual(f.sent.slice(-2),[{type:'jump',pressed:true},{type:'jump',pressed:false}]);
});
test('cancel, release outside, disabled, blur and changed corpse generation cannot trigger a pickup',t=>{
  const f=fixture(t);f.control.update(loot('life-1'));
  for(const cancel of [()=>f.emit('pointercancel'),()=>f.emit('lostpointercapture'),()=>f.emit('pointerup',{clientX:101}),
    ()=>window.dispatchEvent(new Event('blur')),()=>f.control.update(loot('life-2'))]){
    f.emit('pointerdown');cancel();f.emit('pointerup');
  }
  assert.deepEqual(f.sent,[]);
  f.emit('pointerdown');f.disable();f.emit('pointerup');f.control.activate();assert.deepEqual(f.sent,[]);
});
test('keyboard tap, repeat suppression and contextual hotkey preserve claim generation',t=>{
  const f=fixture(t);f.control.update(loot('life-1'));
  f.emit('keydown',{code:'Enter',repeat:true});f.emit('keyup',{code:'Enter'});assert.equal(f.sent.length,0);
  f.emit('keydown',{code:'Space'});assert.equal(f.sent.length,0);f.emit('keyup',{code:'Space'});f.control.activate();
  assert.equal(f.sent.length,2);assert(f.sent.every(v=>v.type==='loot'&&v.generation==='life-1'));
});
