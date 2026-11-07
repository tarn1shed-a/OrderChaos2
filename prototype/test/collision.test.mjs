import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {Vector3} from 'three';
import {createCollision,loadCollision} from '../game/collision.mjs';
import {setJumpPressed,updateJump} from '../game/jump.mjs';
import {jumpPose} from '../public/jump.js';

const world={width:100,height:100,speed:32,radius:1,obstacles:[],spawn:{x:50,y:50}};
const shape=(center,half,kind='box')=>({kind,center,halfExtents:half,yawRadians:0,flags:2048});
function fixture(shapes,instance={}){
 const profile={format:'oc2-scene-collision-v1',query:{forwardMargin:.31,stepProbeCap:.5,stepProbeMultiplier:3.5,wallNormalYThreshold:.5},sources:{test:{shapes}},instances:[{id:1,sourcePHY:'test',position:[0,0,0],quaternion:[0,0,0,1],scale:[1,1,1],...instance}]};
 const terrain={bounds:{min:[-10,0,-10],max:[10,0,10]},grid:{width:3,height:3,heights:Array(9).fill(0)}};
 return createCollision(profile,terrain,world);
}
test('original shape rays stop before a wall and allow tangential movement without tunnelling',()=>{
 const c=fixture([shape([2,2,0],[.1,2,4])]),p={x:50,y:50};c.place(p);
 const hit=c.raycast(new Vector3(0,1,0),new Vector3(5,1,0));assert(Math.abs(hit.distance-1.9)<1e-8);
 for(let i=0;i<100;i++)c.move(p,{x:1,y:0},.05,world);
 assert(Math.abs(c.point(p.x,p.y).x-1.59)<1e-7);
 const before=p.y;for(let i=0;i<8;i++)c.move(p,{x:1,y:1},.05,world);
 assert(p.y>before+2);assert(Math.abs(c.point(p.x,p.y).x-(1.9-.31/Math.sqrt(2)))<1e-6);
});
test('cylinders use analytical side/cap intersection, including transformed nonuniform instances',()=>{
 const c=fixture([shape([0,1,0],[1,1,1],'cylinder')]);
 const side=c.raycast(new Vector3(-3,1,0),new Vector3(3,1,0));assert.equal(side.distance,2);assert(side.normal.x<-.99);
 assert.equal(c.support(0,0,3),2);assert.equal(c.support(2,0,3),0);
 const ellipse=fixture([shape([0,1,0],[1,1,1],'cylinder')],{scale:[2,1,.5]});
 assert.equal(ellipse.raycast(new Vector3(-4,1,0),new Vector3(4,1,0)).distance,2);
 assert.equal(ellipse.raycast(new Vector3(0,1,-3),new Vector3(0,1,3)).distance,2.5);
});
test('finite step support, unsupported edges and ceilings participate in authoritative world motion',()=>{
 const c=fixture([shape([1,.2,0],[1,.2,2]),shape([0,2,0],[4,.1,4])]),p={x:49,y:50};c.place(p);
 for(let i=0;i<4;i++)c.move(p,{x:1,y:0},.05,world);
 assert(Math.abs(p.worldY-.4)<1e-6);
 const ceiling=c.vertical({...p,worldY:.4},2);assert(ceiling.ceiling);assert(ceiling.y<1.2);
 const edge={x:59.5,y:50,worldY:.4,grounded:true};
 for(let i=0;i<8;i++)c.move(edge,{x:1,y:0},.05,world);
 assert(edge.grounded);assert.equal(edge.worldY,0,'Short steps retain ground support');
 const ledge=fixture([shape([0,1,0],[1,1,2])]),fall={x:54.5,y:50,worldY:2,grounded:true};
 for(let i=0;i<4;i++)ledge.move(fall,{x:1,y:0},.05,world);
 assert.equal(fall.grounded,false,'Losing a tall support initiates falling rather than teleporting down');
 for(let i=0;i<30;i++)ledge.settle(fall);
 assert(fall.grounded);assert.equal(fall.worldY,0);
});
test('live jump holds locomotion when the checked stationary clip is absent; it lands on world geometry, not a fixed timer',()=>{
 const c=fixture([]),ws={scene:'resources',motion:c,world,gameplay:{jump:{stationaryAnimationAvailable:false}},input:{x:0,y:0},player:{x:50,y:50,hp:100}};
 c.place(ws.player);setJumpPressed(ws,true,1000);updateJump(ws,1300);
 assert(Math.abs(ws.player.worldY-1.494)<1e-5);assert.equal(jumpPose(ws.player.jump,1300).phase,'jump_stationary_missing');
 setJumpPressed(ws,false,1300);updateJump(ws,1700);assert.equal(ws.player.worldY,0);assert.equal(ws.player.jump,null);assert(ws.player.grounded);
 const roof=fixture([shape([0,1,0],[4,.1,4])]);ws.motion=roof;roof.place(ws.player);setJumpPressed(ws,true,2000);updateJump(ws,2200);
 assert(ws.player.worldY<.3,'Upward motion stops at the source ceiling');
 updateJump(ws,3000);assert.equal(ws.player.worldY,0);
});
test('actual preview contains original compound collision and saved spawn has finite ground support',
 {skip:!existsSync(new URL('../../game-data/converted/maps/collision.json',import.meta.url))},()=>{
 const c=loadCollision(),p={x:900,y:360};assert.equal(c.colliders.length,138);c.place(p);assert(Number.isFinite(p.worldY));assert(p.grounded);
});
