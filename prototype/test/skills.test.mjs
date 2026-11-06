import test from 'node:test';
import assert from 'node:assert/strict';
import { CombatRoom, COMBAT } from '../game/combat.mjs';
import { WORLD } from '../public/world.js';
import { SKILLS } from '../public/skills.js';

function setup(count=1) {
  const clients=new Map(),events=[],notices=[];
  for(let i=0;i<count;i++) {
    const character={id:`p${i}`,hp:100,maxHp:100,level:1,xp:0,gold:0,kills:0,inventory:{wolfPelt:0}};
    clients.set(character.id,{character,player:{...character,x:WORLD.spawn.x+50,y:WORLD.spawn.y+20,attackAt:-700},input:{x:1,y:0}});
  }
  const room=new CombatRoom('SKILL',WORLD,'camp',clients,{changed(){},emit:e=>events.push(structuredClone(e)),notice:(ws,message)=>notices.push(message)});
  return {room,clients,events,notices,a:clients.get('p0'),b:clients.get('p1')};
}

test('unknown, foreign, distant, dead or busy skill requests cannot change combat or cooldowns',()=>{
  const {room,a,events}=setup();
  for(const id of ['unknown','__proto__',{},null])room.skill(a,id,room.monster.id,1000);
  room.skill(a,'fireball','FOREIGN:wolf',1000);
  a.player.x+=1000;room.skill(a,'fireball',room.monster.id,1000);a.player.x-=1000;
  a.player.hp=0;room.skill(a,'fireball',room.monster.id,1000);a.player.hp=100;
  room.monster.alive=false;room.skill(a,'fireball',room.monster.id,1000);room.monster.alive=true;
  assert.equal(events.length,0);assert.equal(room.monster.hp,60);assert.equal(a.player.skillReadyAt,undefined);
  room.skill(a,'fireball',room.monster.id,1000);
  room.skill(a,'frost_blast',room.monster.id,1001);room.attack(a,room.monster.id,1001);
  assert.equal(events.length,1);assert.equal(a.player.skillReadyAt.frost_blast,undefined);assert.equal(room.monster.hp,60);
});

test('fireball damage waits for authoritative impact, is applied once, and cooldown cannot be bypassed',()=>{
  const {room,a,events}=setup();
  room.skill(a,'fireball',room.monster.id,1000);
  assert.equal(events[0].action,'skill-cast');assert.equal(events[0].cast.releaseAt,1500);assert.equal(events[0].cast.impactAt,1850);
  assert.equal(a.player.skillReadyAt.fireball,4000);assert.deepEqual(a.input,{x:0,y:0});
  room.tick(1849,0);assert.equal(room.monster.hp,60);
  room.tick(1850,0);assert.equal(room.monster.hp,30);assert.equal(a.player.cast,null);
  room.tick(1850,0);assert.equal(events.filter(e=>e.action==='skill-hit').length,1);
  const hit=events.find(e=>e.action==='skill-hit');assert.equal(hit.damage,30);assert.equal(hit.serverTime,1850);assert.equal(hit.castId,events[0].cast.id);
  room.skill(a,'fireball',room.monster.id,3999);assert.equal(events.filter(e=>e.action==='skill-cast').length,1);
  room.skill(a,'fireball',room.monster.id,4000);assert.equal(events.filter(e=>e.action==='skill-cast').length,2);
});

test('death, disconnect, lost range and another player killing a target cancel pending skill damage',()=>{
  for(const reason of ['death','disconnect','range','target-death']) {
    const {room,a,b,clients,events}=setup(2);
    room.skill(a,'fireball',room.monster.id,1000);
    if(reason==='death')a.player.hp=0;
    if(reason==='disconnect')clients.delete(a.player.id);
    if(reason==='range')room.monster.x+=1000;
    if(reason==='target-death'){room.monster.hp=20;room.attack(b,room.monster.id,1100);}
    const before=room.monster.hp;
    room.tick(1900,0);
    assert.equal(room.monster.hp,before,reason);assert.equal(a.player.cast,null);
    assert.equal(events.filter(e=>e.action==='skill-hit').length,0);
    assert.equal(events.filter(e=>e.action==='skill-cancel').length,1);
    assert.equal(a.character.gold,0);
  }
});

test('frost hit slows actual movement for 2.5 seconds, expires, and resets on monster revival',()=>{
  const {room,a,events}=setup();
  room.skill(a,'frost_blast',room.monster.id,1000);room.tick(1700,0);
  assert.equal(room.monster.hp,40);assert.equal(room.monster.slowUntil,4200);
  assert.equal(events.find(e=>e.action==='skill-hit').skillId,'frost_blast');
  a.player.x=room.monster.x+100;a.player.y=room.monster.y;
  const start=room.monster.x;room.tick(1800,.05);const slowDistance=room.monster.x-start;
  const second=room.monster.x;room.tick(4200,.05);const normalDistance=room.monster.x-second;
  assert(Math.abs(normalDistance-slowDistance*2)<1e-7);
  room.monster.alive=false;room.monster.respawnAt=5000;room.tick(5000,0);
  assert.equal(room.monster.slowUntil,0);
});

test('overlapping skill and melee kills retain contributor rewards and cannot settle a kill twice',()=>{
  const {room,a,b,events}=setup(2);
  room.skill(a,'fireball',room.monster.id,1000);room.tick(1850,0); // 30 HP, a contributes
  room.skill(b,'frost_blast',room.monster.id,1900);room.tick(2600,0); // 10 HP, b contributes
  room.attack(a,room.monster.id,2700);
  for(const ws of [a,b]){assert.equal(ws.character.gold,10);assert.equal(ws.character.xp,30);assert.equal(ws.character.inventory.wolfPelt,1);}
  room.attack(b,room.monster.id,2800);room.tick(3000,0);
  assert.equal(events.filter(e=>e.action==='kill').length,1);
  assert.equal(a.character.kills,1);assert.equal(b.character.kills,1);
  assert.equal(SKILLS.fireball.damage,30);assert.equal(COMBAT.playerDamage,20);
});
