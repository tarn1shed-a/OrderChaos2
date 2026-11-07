import test from 'node:test';
import assert from 'node:assert/strict';
import {createPressControl} from '../public/press-control.js';
function fixture(t){
  const previous=[globalThis.window,globalThis.document];globalThis.window=new EventTarget();globalThis.document=new EventTarget();
  t.after(()=>{[globalThis.window,globalThis.document]=previous;});
  const element=new EventTarget(),captures=new Set(),values=[];element.classList={add(){},remove(){}};element.setAttribute=()=>{};
  element.setPointerCapture=id=>captures.add(id);element.hasPointerCapture=id=>captures.has(id);element.releasePointerCapture=id=>captures.delete(id);
  element.getBoundingClientRect=()=>({left:0,top:0,right:100,bottom:100});let enabled=true;
  const control=createPressControl(element,{enabled:()=>enabled,change:v=>values.push(v)});
  function emit(type,fields={}){const e=new Event(type,{cancelable:true});Object.assign(e,{button:0,pointerId:1,clientX:50,clientY:50,...fields});element.dispatchEvent(e);}
  return {emit,control,values,disable:()=>{enabled=false;}};
}
test('jump Press/ReleaseOut uses true/false once, ignores other fingers and never toggles itself back on',t=>{
  const f=fixture(t);f.emit('pointerdown');f.emit('pointerdown',{pointerId:2});f.emit('pointerup',{pointerId:2});assert(f.control.pressed);
  f.emit('pointermove',{clientX:101});f.emit('pointerup');assert.deepEqual(f.values,[true,false]);
  f.emit('pointermove');assert(!f.control.pressed);
});
test('keyboard and all cancellation paths release the source jump state',t=>{
  const f=fixture(t);
  f.emit('keydown',{code:'Enter'});f.emit('keydown',{code:'Enter',repeat:true});f.emit('keyup',{code:'Enter'});assert.deepEqual(f.values,[true,false]);
  for(const stop of [()=>f.emit('pointercancel'),()=>f.emit('lostpointercapture'),()=>window.dispatchEvent(new Event('blur')),()=>f.control.reset(),()=>{document.hidden=true;document.dispatchEvent(new Event('visibilitychange'));}]){
    f.emit('pointerdown');assert(f.control.pressed);stop();assert(!f.control.pressed);assert.equal(f.values.at(-1),false);
  }
  f.disable();const count=f.values.length;f.emit('pointerdown');assert.equal(f.values.length,count);
});
