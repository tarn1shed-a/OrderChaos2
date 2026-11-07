import test from 'node:test';
import assert from 'node:assert/strict';
import {jumpTimeline,jumpPose,JUMP} from '../public/jump.js';
import {setJumpPressed,updateJump} from '../game/jump.mjs';
test('confirmed jump has bounded source animation phases and an explicit web arc',()=>{
  const j=jumpTimeline(1000);
  assert.equal(jumpPose(j,999),null);assert.equal(jumpPose(j,1000).phase,'jump_start');
  assert.equal(jumpPose(j,j.takeoffAt).phase,'jump_air');assert.equal(jumpPose(j,j.landAt).phase,'jump_land');
  assert.equal(jumpPose(j,j.endsAt),null);assert.equal(jumpPose({...j,landAt:Infinity},1200),null);
  const middle=jumpPose(j,(j.takeoffAt+j.landAt)/2);assert(Math.abs(middle.height-JUMP.height)<1e-10);
  assert.equal(jumpPose(j,j.landAt).height,0);
});
test('server rejects dead/casting/camp jumps; release cannot cancel flight or auto-repeat; death clears transient state',()=>{
  const ws={player:{hp:100,jump:null},scene:'resources'};
  assert.equal(setJumpPressed(ws,true,1000),null);const j={...ws.player.jump};
  setJumpPressed(ws,true,1100);assert.deepEqual(ws.player.jump,j);
  setJumpPressed(ws,false,1200);assert.equal(ws.jumpPressed,false);assert.deepEqual(ws.player.jump,j);
  setJumpPressed(ws,true,1300);assert.deepEqual(ws.player.jump,j);
  updateJump(ws,j.endsAt);assert.equal(ws.player.jump,null);
  setJumpPressed(ws,false,4000);assert.match(setJumpPressed(ws,true,4000,true),/施法/);assert.equal(ws.player.jump,null);
  ws.player.hp=0;setJumpPressed(ws,false,4100);assert.match(setJumpPressed(ws,true,4100),/倒地/);
  ws.player.hp=100;ws.scene='camp';setJumpPressed(ws,false,4200);assert.match(setJumpPressed(ws,true,4200),/场景/);
  ws.scene='resources';setJumpPressed(ws,false,5000);setJumpPressed(ws,true,5000);ws.player.hp=0;updateJump(ws,5100);
  assert.equal(ws.player.jump,null);assert.equal(ws.jumpPressed,false);
});
