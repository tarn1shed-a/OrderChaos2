import assert from 'node:assert/strict';
import test from 'node:test';
import {createSourceFramePresentation} from './preview/source-frame-presentation.js';
const actor = (t,id='a') => ({id,x:t*.01,y:4,worldY:10+t*.001,
  sourceCamera:{nativeCPU:true,yaw:t*.1,position:[t*.01,15+t*.001,10],target:[t*.01,12+t*.001,0]}});

test('20 Hz paired frames retain actor/camera separation at 30, 60 and 144 Hz',()=>{
  for(const hz of [30,60,144]){
    const p=createSourceFramePresentation();let next=0;
    for(let now=0;now<2000;now+=1000/hz){
      while(next<=now){p.push([actor(next)],10000+next,next);next+=50;}
      const a=p.sample(now).get('a');
      assert(Math.abs(a.sourceCamera.position[0]-a.x)<1e-12);
      assert(Math.abs(a.sourceCamera.position[1]-a.worldY-5)<1e-12);
      if(now>=100)assert(Math.abs(a.x-(now-100)*.01)<1e-9);
    }
  }
});

test('stop, missing packets and late packets cannot extrapolate through a wall',()=>{
  const p=createSourceFramePresentation();p.push([actor(0)],1000,0);p.push([actor(50)],1050,50);
  assert.equal(p.push([actor(40)],1040,60),false);
  assert.equal(p.sample(1000).get('a').x,.5);
  p.push([actor(50)],2050,1050);
  assert.equal(p.sample(1100).get('a').x,.5);
});

test('height and camera endpoints remain exact and inputs stay immutable',()=>{
  const p=createSourceFramePresentation({delayMs:0}),a=actor(0),b=actor(50),saved=structuredClone([a,b]);
  p.push([a],1000,0);p.push([b],1050,50);
  assert.equal(p.sample(25).get('a').worldY,10.025);
  assert.deepEqual(p.sample(50).get('a').sourceCamera,b.sourceCamera);
  assert.deepEqual([a,b],saved);
});

test('removed actors, reconnect and unsupported frame data are handled explicitly',()=>{
  const p=createSourceFramePresentation();p.push([actor(0),actor(0,'b')],1000,0);p.push([actor(50)],1050,50);
  assert.equal(p.sample(70).has('b'),false);p.reset();assert.equal(p.sample(100).size,0);
  p.push([actor(0)],1,100);assert.equal(p.sample(101).get('a').x,0);
  assert.throws(()=>p.push([{...actor(0),worldY:NaN}],2,101));
  assert.throws(()=>createSourceFramePresentation({delayMs:-1}));
});
