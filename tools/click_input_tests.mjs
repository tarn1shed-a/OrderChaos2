import {test} from 'node:test';
import assert from 'node:assert/strict';
import {clickTarget,clickMovement} from '../deploy/click_input.mjs';

test('normal approach retains the old direction and arrival radius',()=>{
  const target=clickTarget({x:10,y:5},{x:0,y:0});
  for(const p of [{x:0,y:0},{x:5,y:2.5},{x:8,y:4}]){
    const d=Math.hypot(10-p.x,5-p.y);
    assert.deepEqual(clickMovement(target,p),{x:(10-p.x)/d,y:(5-p.y)/d});
  }
  assert.equal(clickMovement(target,{x:9,y:5}),null);
});
test('late samples that skip the arrival circle cannot reverse pursuit',()=>{
  const target=clickTarget({x:9.45,y:0},{x:0,y:0});
  assert(clickMovement(target,{x:6.4,y:0}));
  assert.equal(clickMovement(target,{x:12.8,y:0}),null);
  // The old radius-only branch would send a full-speed reverse here.
  assert(Math.hypot(9.45-12.8,0)>2);
  assert.equal(clickMovement(target,{x:19.2,y:.2}),null);
});
test('diagonal and negative-coordinate targets use the same crossing test',()=>{
  const start={x:1053.333333,y:-1280},goal={x:1051.9199,y:-1287.3474};
  const target=clickTarget(goal,start),dx=goal.x-start.x,dy=goal.y-start.y;
  assert(clickMovement(target,{x:start.x+dx*.5,y:start.y+dy*.5}));
  assert.equal(clickMovement(target,{x:start.x+dx*2,y:start.y+dy*2}),null);
  assert.equal(clickMovement(target,goal),null);
});
test('sideways obstruction does not pretend to find a route or move the actor',()=>{
  const target=clickTarget({x:10,y:0},{x:0,y:0}),position={x:2,y:8};
  const movement=clickMovement(target,position);
  assert(Math.abs(movement.x-Math.SQRT1_2)<1e-15);
  assert(Math.abs(movement.y+Math.SQRT1_2)<1e-15);
  assert.deepEqual(position,{x:2,y:8});
});
test('missing, identical or invalid points cannot emit nonfinite movement',()=>{
  assert.equal(clickTarget({x:1,y:2},null),null);
  assert.equal(clickTarget({x:NaN,y:2},{x:1,y:2}),null);
  assert.equal(clickMovement(clickTarget({x:1,y:2},{x:1,y:2}),{x:1,y:2}),null);
  assert.equal(clickMovement({x:1,y:2},{x:0,y:0}),null);
});
