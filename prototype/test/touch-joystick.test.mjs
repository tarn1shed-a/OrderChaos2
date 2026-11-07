import test from 'node:test';
import assert from 'node:assert/strict';
import {joystickFrame,joystickCanStart,createTouchJoystick} from '../public/touch-joystick.js';
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
const profile={diameter:48,radius:24,baseFollowFraction:.1,activationMaxXFraction:.25,activationMinYFraction:.5,moveEventGate:3};
test('source radius/angle/floating base and native rejection replace the previous analog ramp',()=>{
  assert.equal(joystickFrame(24,0,profile).accepted,false);
  assert.equal(joystickFrame(24.001,0,profile).accepted,true);
  assert.equal(joystickFrame(0,0,profile).accepted,false);
  assert.equal(joystickFrame(NaN,0,profile).accepted,false);
  for(const [x,y,angle] of [[30,0,0],[0,-30,90],[-30,0,180],[0,30,270]]){
    const frame=joystickFrame(x,y,profile);near(frame.angle,angle);near(Math.hypot(frame.x,frame.y),1);
    near(Math.hypot(x-frame.baseX,y-frame.baseY),2.4);
  }
  near(joystickFrame(40,40,profile).angle,315);
  assert.deepEqual(joystickFrame(1,0,profile).baseX,0);
});
test('source StartMove guard uses strict left quarter / bottom half boundaries',()=>{
  assert(joystickCanStart(0,321,1136,640,profile));
  assert(joystickCanStart(283,640,1136,640,profile));
  for(const [x,y] of [[284,400],[10,320],[-1,400],[10,641],[NaN,400]])assert(!joystickCanStart(x,y,1136,640,profile));
});
function fixture(t){
  const oldWindow=globalThis.window,oldDocument=globalThis.document;
  globalThis.window=new EventTarget();globalThis.document=new EventTarget();document.hidden=false;
  t.after(()=>{globalThis.window=oldWindow;globalThis.document=oldDocument;});
  const element=new EventTarget(),knob={style:{}},base={style:{}},hit={style:{}},classes=new Set(),captures=new Set(),changes=[];
  element.dataset={};element.querySelector=s=>s==='.joystick-knob'?knob:s==='.joystick-base'?base:hit;
  element.classList={add:v=>classes.add(v),remove:v=>classes.delete(v)};
  const stage={getBoundingClientRect:()=>({left:100,top:200,width:568,height:320})};
  element.hasPointerCapture=id=>captures.has(id);element.setPointerCapture=id=>captures.add(id);
  element.releasePointerCapture=id=>{captures.delete(id);emit('lostpointercapture',{pointerId:id});};
  function emit(type,fields={}){const e=new Event(type,{cancelable:true});Object.assign(e,{pointerId:1,button:0,clientX:132,clientY:432,...fields});element.dispatchEvent(e);}
  let allowed=true;
  const controller=createTouchJoystick(element,{stage,profile,scale:()=>.5,enabled:()=>allowed,change:v=>changes.push(v)});
  function drag(){emit('pointerdown');for(let i=0;i<4;i++)emit('pointermove',{clientX:152});}
  return {emit,drag,controller,element,knob,base,changes,classes,captures,disallow:()=>{allowed=false;}};
}
test('three move events show floating art; fourth valid move accepts direction, with independent finger ownership',t=>{
  const f=fixture(t);f.emit('pointerdown');
  for(let i=0;i<2;i++)f.emit('pointermove',{clientX:152});
  assert(!f.classes.has('active'));assert.equal(f.changes.at(-1).x,0);
  f.emit('pointermove',{clientX:152});assert(f.classes.has('active'));assert.equal(f.knob.style.width,'24px');
  f.emit('pointermove',{clientX:152});near(f.changes.at(-1).x,1);assert.equal(f.knob.style.left,'40px');
  // A nonfinite source speed argument inside the radius must not alter the last accepted movement.
  f.emit('pointermove',{clientX:132});assert.equal(f.changes.at(-1).x,1);
  f.emit('pointerdown',{pointerId:2});f.emit('pointerup',{pointerId:2});assert(f.controller.active);
  f.emit('pointerup');assert(!f.controller.active);assert(!f.classes.has('active'));assert.equal(f.captures.size,0);
  assert.deepEqual(f.changes.at(-1),{x:0,y:0,active:false});
});
test('cancel, lost capture, blur, visibility, resize and panel reset stop and hide the joystick',t=>{
  const f=fixture(t);
  for(const stop of [()=>f.emit('pointercancel'),()=>f.emit('lostpointercapture'),()=>window.dispatchEvent(new Event('blur')),()=>window.dispatchEvent(new Event('resize')),()=>{document.hidden=true;document.dispatchEvent(new Event('visibilitychange'));document.hidden=false;},()=>f.controller.reset()]){
    f.drag();assert.equal(f.changes.at(-1).x,1);stop();
    assert.deepEqual(f.changes.at(-1),{x:0,y:0,active:false});assert(!f.controller.active);assert(!f.classes.has('active'));
  }
});
test('modal/dead/disconnected controls reject starting and cancel a held pointer',t=>{
  const f=fixture(t);f.emit('pointerdown');f.disallow();f.emit('pointermove',{clientX:152});
  assert(!f.controller.active);assert.deepEqual(f.changes.at(-1),{x:0,y:0,active:false});
  const count=f.changes.length;f.emit('pointerdown');assert.equal(f.changes.length,count);
});
