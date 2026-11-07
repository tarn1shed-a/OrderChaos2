import test from 'node:test';
import assert from 'node:assert/strict';
import {joystickVector,createTouchJoystick} from '../public/touch-joystick.js';

const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
test('joystick has a radial dead zone and caps diagonal/outside movement at unit speed',()=>{
  assert.deepEqual(joystickVector(0,0,40),{x:0,y:0,knobX:0,knobY:0});
  assert.equal(joystickVector(2,2,40).x,0);
  near(joystickVector(40,0,40).x,1);near(joystickVector(0,-40,40).y,-1);
  const diagonal=joystickVector(400,400,40);near(Math.hypot(diagonal.x,diagonal.y),1);near(Math.hypot(diagonal.knobX,diagonal.knobY),40);
  near(joystickVector(22.4,0,40).x,.5);
  assert.equal(joystickVector(NaN,0,40).x,0);assert.equal(joystickVector(1,1,0).y,0);
});

function fixture(t){
  const oldWindow=globalThis.window,oldDocument=globalThis.document;
  globalThis.window=new EventTarget();globalThis.document=new EventTarget();document.hidden=false;
  t.after(()=>{globalThis.window=oldWindow;globalThis.document=oldDocument;});
  const element=new EventTarget(),knob={style:{}},classes=new Set(),captures=new Set(),changes=[];
  element.querySelector=()=>knob;element.classList={add:v=>classes.add(v),remove:v=>classes.delete(v)};
  // Source stage 128px rendered at .5 scale.
  element.getBoundingClientRect=()=>({left:100,top:200,width:64,height:64});
  element.hasPointerCapture=id=>captures.has(id);element.setPointerCapture=id=>captures.add(id);
  element.releasePointerCapture=id=>{captures.delete(id);emit('lostpointercapture',{pointerId:id});};
  function emit(type,fields={}){const e=new Event(type,{cancelable:true});Object.assign(e,{pointerId:1,button:0,clientX:132,clientY:232,...fields});element.dispatchEvent(e);}
  let allowed=true;
  const controller=createTouchJoystick(element,{enabled:()=>allowed,change:v=>changes.push(v)});
  return {emit,controller,element,knob,changes,classes,captures,disallow:()=>{allowed=false;}};
}
test('scaled pointer drag uses correct axes, ignores another finger, and releases to exact zero',t=>{
  const f=fixture(t);f.emit('pointerdown');f.emit('pointermove',{clientX:152});
  near(f.changes.at(-1).x,1);assert.equal(f.knob.style.transform,'translate(40px,0px)');
  f.emit('pointerdown',{pointerId:2,clientX:100});f.emit('pointerup',{pointerId:2});
  assert.equal(f.controller.active,true);assert.equal(f.captures.size,1);
  f.emit('pointerup');assert.equal(f.controller.active,false);assert.equal(f.captures.size,0);
  assert.deepEqual(f.changes.at(-1),{x:0,y:0,active:false});
  f.emit('pointermove',{clientX:152});assert.equal(f.changes.at(-1).active,false);
});
test('cancel, lost capture, window blur, hidden page, and explicit panel reset all stop movement',t=>{
  const f=fixture(t);
  for(const stop of [()=>f.emit('pointercancel'),()=>f.emit('lostpointercapture'),()=>window.dispatchEvent(new Event('blur')),()=>window.dispatchEvent(new Event('resize')),()=>{document.hidden=true;document.dispatchEvent(new Event('visibilitychange'));document.hidden=false;},()=>f.controller.reset()]){
    f.emit('pointerdown',{clientX:152});assert.equal(f.changes.at(-1).x,1);stop();
    assert.deepEqual(f.changes.at(-1),{x:0,y:0,active:false});assert.equal(f.controller.active,false);
  }
});
test('disconnected/modal/dead input cannot start, and revoking permission cancels a held pointer',t=>{
  const f=fixture(t);f.emit('pointerdown');f.disallow();f.emit('pointermove',{clientX:152});
  assert.equal(f.controller.active,false);assert.deepEqual(f.changes.at(-1),{x:0,y:0,active:false});
  const count=f.changes.length;f.emit('pointerdown',{clientX:152});assert.equal(f.changes.length,count);
});
