import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {createNavigation,loadNavigation,RouteFollower} from '../game/navigation.mjs';
import {createCollision,loadCollision} from '../game/collision.mjs';
import {CombatRoom} from '../game/combat.mjs';
import {RESOURCE_WORLD} from '../public/world.js';
import {monsterStateText} from '../public/monster-state.js';

function rectangle(x0,z0,x1,z1,y=0){return [[x0,y,z0],[x1,y,z0],[x1,y,z1],[x0,y,z1]];}
function navFixture(){
  const nodes=[rectangle(0,0,4,10),rectangle(4,8,6,10),rectangle(6,0,10,10),rectangle(0,0,10,10,20)].map(vertices=>({vertices,
    center:[vertices.reduce((s,v)=>s+v[0],0)/4,vertices[0][1],vertices.reduce((s,v)=>s+v[2],0)/4],edges:[],flags:1,area:0}));
  for(const [a,b,p]of [[0,1,[[4,0,8],[4,0,10]]],[1,2,[[6,0,8],[6,0,10]]]]){
    nodes[a].edges.push({to:b,portal:p});nodes[b].edges.push({to:a,portal:p});
  }
  return createNavigation({format:'oc2-source-navigation-v1',nodes});
}
const world={...RESOURCE_WORLD,width:1000,height:1000,radius:.1,spawn:{x:2,y:2},speed:2};
function motionFixture(){
  return createCollision({format:'oc2-scene-collision-v2',query:{forwardMargin:.31,stepProbeCap:.5,stepProbeMultiplier:3.5,wallNormalYThreshold:.5},
    sources:{wall:{shapes:[{kind:'box',center:[5,1,4],halfExtents:[1,1,4],yawRadians:0,flags:0}]},door:{shapes:[{kind:'box',center:[0,1,0],halfExtents:[1,1,.2],yawRadians:0,flags:0}]}},
    instances:[{id:'wall',sourcePHY:'wall',position:[0,0,0],quaternion:[0,0,0,1],scale:[1,1,1]}]},
    {bounds:{min:[0,0,0],max:[1000,0,1000]},grid:{width:2,height:2,heights:[0,0,0,0]}},world);
}
function roomFixture(){
  const clients=new Map(),events=[],notices=[];
  for(const id of ['a','b']){const character={id,name:id,hp:100,maxHp:100,level:1,xp:0,gold:0,kills:0,inventory:{wolfPelt:0}};
    clients.set(id,{character,player:{...character,x:8,y:2,worldY:0,grounded:true},input:{x:0,y:0}});}
  const room=new CombatRoom('AI',world,'resources',clients,{motion:motionFixture(),navigation:navFixture(),changed(){},emit:e=>events.push(structuredClone(e)),notice:(ws,t)=>notices.push(t)});
  room.spawn={x:2,y:2};Object.assign(room.monster,{x:2,y:2,worldY:0,grounded:true});room.monsterSpeed=2;room.monsterRange=.4;
  return {room,events,notices,a:clients.get('a'),b:clients.get('b'),clients};
}
test('ground route goes around the missing corridor, honours explicit edges and distinguishes overlapping roof polygons',()=>{
  const nav=navFixture(),path=nav.path([2,0,2],[8,0,2]);assert.deepEqual(path.polygons,[0,1,2]);
  assert(path.points.slice(0,-1).every(p=>p[2]===9));assert.equal(nav.nearest([2,19.9,2]).index,3);
  assert.equal(nav.path([2,0,2],[8,20,2]),null);assert.equal(nav.nearest([40,0,40]),null);
  assert.equal(nav.path([2,0,2],[8,0,2],{clear:(a,b)=>a[0]<6&&b[0]<6}),null);
  assert.throws(()=>createNavigation({format:'oc2-source-navigation-v1',nodes:[{vertices:rectangle(0,0,1,1),center:[0,NaN,0],edges:[]}]}));
});
test('route follower uses collision for every step, never cuts the wall and reaches its target through portals',()=>{
  const motion=motionFixture(),route=new RouteFollower(navFixture(),motion),p={id:'wolf',x:2,y:2},goal={x:8,y:2};motion.place(p);motion.place(goal);
  let result,highest=0;
  for(let t=0;t<30000;t+=50){const before={x:p.x,y:p.y};result=route.follow(p,goal,t,.05,{...world,speed:2});
    assert(Math.hypot(p.x-before.x,p.y-before.y)<=.100001);assert(!(p.x>4&&p.x<6&&p.y<8));highest=Math.max(highest,p.y);if(result.arrived)break;}
  assert(result.arrived);assert(highest>=8.8);assert(Math.hypot(p.x-8,p.y-2)<.13);
});
test('a registered closed door blocks the route and replanning recovers after it opens without teleporting',()=>{
  const motion=motionFixture(),route=new RouteFollower(navFixture(),motion),p={id:'wolf',x:2,y:9},goal={x:8,y:9};motion.place(p);motion.place(goal);
  const door={id:'door',sourcePHY:'door',position:[5,0,9],quaternion:[0,0,0,1],scale:[1,1,1]};motion.updateDynamic(door);
  assert.equal(route.follow(p,goal,0,.05,{...world,speed:2}).blocked,true);assert.equal(p.x,2);
  assert(route.follow(p,goal,3000,.05,{...world,speed:2}).stalledMs>=3000);
  motion.updateDynamic({...door,position:[5,5,9]});let r;
  for(let t=3500;t<10000;t+=50){r=route.follow(p,goal,t,.05,{...world,speed:2});if(r.arrived)break;}
  assert(r.arrived);assert(p.x>7.8);
});
test('damage threat beats proximity, freeze pauses routing, and target death/disconnect starts a safe return',()=>{
  const {room,a,b,clients}=roomFixture();b.player.x=2;b.player.y=3;
  room.damageMonster(a,5,0);room.damageMonster(b,1,1);room.tick(10,.05);
  assert.equal(room.monster.ai.targetId,'a');assert.equal(room.monster.ai.state,'chasing');
  const old={x:room.monster.x,y:room.monster.y};room.blocked=()=>true;room.tick(100,.05);
  assert.equal(room.monster.ai.state,'frozen');assert.deepEqual({x:room.monster.x,y:room.monster.y},old);room.blocked=()=>false;
  a.player.hp=0;room.tick(200,.05);assert.equal(room.monster.ai.targetId,'b');
  clients.delete('b');room.tick(250,.05);assert(['returning','idle'].includes(room.monster.ai.state));assert.equal(room.contributors.size,0);
});
test('leash is anchored at home, returning monsters reject stale damage, and arrival resets HP without awarding loot',()=>{
  const {room,a,events}=roomFixture();room.damageMonster(a,5,0);
  Object.assign(room.monster,{x:8,y:5});a.player.x=230;room.tick(100,.05);
  assert.equal(room.monster.ai.state,'returning');assert.equal(room.monster.ai.moveAction,3);
  assert(room.monster.ai.routePoints>0);
  const hp=room.monster.hp;room.damageMonster(a,999,200,{id:'stale',skillId:'fireball'});assert.equal(room.monster.hp,hp);
  for(let t=150;t<30000&&room.brain.returning;t+=50)room.tick(t,.05);
  assert.equal(room.monster.ai.state,'idle');assert.equal(room.monster.hp,60);assert.equal(room.contributors.size,0);
  assert.equal(events.filter(e=>e.action==='kill').length,0);assert.equal(a.character.gold,0);
  assert.equal(events.filter(e=>e.action==='evade-reset').length,1);
});
test('unreachable height layer times out and clears aggro without rewards',()=>{
  const {room,a,events}=roomFixture();room.damageMonster(a,5,0);Object.assign(room.monster,{x:3,y:9});
  a.player.worldY=20;room.tick(0,.05);assert.equal(room.monster.ai.state,'blocked');room.tick(3000,.05);
  assert.equal(room.contributors.size,0);assert(events.some(e=>e.ai?.state==='returning'&&e.ai?.reason==='unreachable'));
  const state=room.snapshot()[0];if(state.ai){state.ai.state='forged';assert.notEqual(room.monster.ai.state,'forged');}
  assert.equal(monsterStateText({ai:{state:'returning'}}),'脱战返回');
});
test('blocked return does not teleport or heal through a door, then finishes when the same registered door opens',()=>{
  const {room,a}=roomFixture();room.damageMonster(a,5,0);Object.assign(room.monster,{x:8,y:9});a.player.x=230;
  const door={id:'door',sourcePHY:'door',position:[5,0,9],quaternion:[0,0,0,1],scale:[1,1,1]};room.motion.updateDynamic(door);
  room.tick(100,.05);const blocked={x:room.monster.x,y:room.monster.y};room.tick(10000,.05);
  assert.equal(room.monster.ai.state,'returning');assert.equal(room.monster.hp,55);assert.deepEqual({x:room.monster.x,y:room.monster.y},blocked);
  room.motion.updateDynamic({...door,position:[5,5,9]});for(let t=10500;t<40000&&room.brain.returning;t+=50)room.tick(t,.05);
  assert.equal(room.monster.ai.state,'idle');assert.equal(room.monster.hp,60);
});
test('actual source navigation traverses multiple original polygons and keeps roof and ground separate',
 {skip:!existsSync(new URL('../../game-data/converted/maps/navigation.json',import.meta.url))},()=>{
  const motion=loadCollision(),nav=loadNavigation(),route=new RouteFollower(nav,motion),p={id:'wolf',x:950,y:380},goal={x:850,y:450};motion.place(p);motion.place(goal);
  const path=nav.path(route.world(p),route.world(goal),{clear:(a,b)=>route.clear(a,b)});assert(path.polygons.length>=8);
  let result;for(let t=0;t<40000;t+=50){result=route.follow(p,goal,t,.05,{...RESOURCE_WORLD,speed:14});motion.settle(p);assert(Number.isFinite(p.worldY));if(result.arrived)break;}
  assert(result.arrived);assert(Math.hypot(p.x-goal.x,p.y-goal.y)<1);assert(p.worldY<140);
  assert.equal(nav.path(route.world(p),[...route.world(goal).slice(0,1),172,route.world(goal)[2]]),null);
});
