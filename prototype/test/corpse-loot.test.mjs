import test from 'node:test';
import assert from 'node:assert/strict';
import {CorpseLoot} from '../game/corpse-loot.mjs';
function fixture(){
  const ws={player:{id:'a',hp:100,x:0,y:0,worldY:10,grounded:true},character:{inventory:{wolfPelt:0}}};
  const events=[],room={monster:{id:'wolf',alive:false,x:0,y:0,worldY:10},casts:new Map(),blocked:()=>false,
    changed(){events.push('saved');},notice(){},emit:v=>events.push(v)};
  const loot=new CorpseLoot(room);loot.begin(100,8100);loot.grant('a');
  return {ws,room,loot,events,pick:()=>loot.pick(ws,'wolf',loot.current?.generation,100)};
}
test('corpse eligibility checks life, range, floor, sight, control and casting; exact boundary is usable',()=>{
  const f=fixture(),p=f.ws.player;assert(f.loot.context(f.ws,100));
  for(const changes of [{hp:0},{x:24.01},{worldY:12.01},{grounded:false},{jump:{endsAt:101}}]){
    const before={...p};Object.assign(p,changes);assert.equal(f.loot.context(f.ws,100),null);Object.assign(p,before);delete p.jump;
  }
  p.x=24;p.worldY=12;assert(f.loot.context(f.ws,100));p.x=0;p.worldY=10;
  f.room.casts.set('a',{});assert.equal(f.loot.context(f.ws,100),null);f.room.casts.clear();
  f.room.blocked=()=>true;assert.equal(f.loot.context(f.ws,100),null);f.room.blocked=()=>false;
  f.room.motion={point:()=>({x:0,y:0,z:0}),raycast:()=>({normal:{y:0}})};assert.equal(f.loot.context(f.ws,100),null);
  f.room.motion.raycast=()=>null;assert(f.loot.context(f.ws,100));
  f.room.monster.alive=true;assert.equal(f.loot.context(f.ws,100),null);
});
test('forged, stale and duplicate claims never award; expiry and another life get independent generation',()=>{
  const f=fixture(),generation=f.loot.current.generation;
  f.loot.pick(f.ws,'other',generation,100);f.loot.pick(f.ws,'wolf',{},100);f.loot.pick(f.ws,'wolf','stale',100);
  assert.equal(f.ws.character.inventory.wolfPelt,0);f.pick();f.loot.pick(f.ws,'wolf',generation,100);
  assert.equal(f.ws.character.inventory.wolfPelt,1);assert.equal(f.events.filter(v=>v==='saved').length,1);
  f.loot.begin(200,8200);f.loot.grant('a');assert.notEqual(f.loot.current.generation,generation);
  f.loot.pick(f.ws,'wolf',generation,200);assert.equal(f.ws.character.inventory.wolfPelt,1);
  assert.equal(f.loot.context(f.ws,8200),null);f.loot.tick(8200);assert.equal(f.loot.view(),null);
});
