import test from 'node:test';
import assert from 'node:assert/strict';
import {BuffRuntime} from '../game/buffs.mjs';
import {resolveDamage} from '../game/damage.mjs';
import {CombatRoom} from '../game/combat.mjs';
import {WORLD} from '../public/world.js';
import {activeBuffs,buffText} from '../public/buff-presentation.js';

// Synthetic fixtures exercise mechanics without distributing original tables.
const combat={format:'oc2-native-combat-v1',auras:Object.fromEntries(['burn','freeze','stun','silence'].map((kind,i)=>[kind,
  {id:i+1,runeId:(i+1)*4,name:kind,maxStack:1,icon:{url:`/assets/ui/buff-${kind}.png`}}])),
  mechanics:{burnDurationMs:7000,burnTicks:5,burnDisplayRate:.1,freezeDurationMs:2000,arcaneBurnBonus:.5},
  spells:{fireball:{damageType:2,damageAttribute:1},frost_blast:{damageType:2,damageAttribute:2},arcane_missile:{damageType:2,damageAttribute:16}}};
const visuals=Object.fromEntries(['-1','1','2','3','6'].map(k=>[k,{movement:{stopOnEnter:false,interruptOnMove:false}}]));
const gameplay={combat,comboRows:[],skills:{},weapons:{},casting:{serverWaitExtraMs:5000,spells:{
  fireball:{sourceSkillId:17,chantMs:1500,channelMs:0,cooldownMs:0,commonCD:600,visuals},
  frost_blast:{sourceSkillId:94,chantMs:0,channelMs:0,cooldownMs:20000,commonCD:700,visuals},
  arcane_missile:{sourceSkillId:90,chantMs:0,channelMs:1500,channelIntervalMs:300,cooldownMs:4000,commonCD:0,visuals}}}};
function fixture(){
  const events=[],notices=[],clients=new Map();
  for(const id of ['a','b']){const character={id,name:id,profession:2,hp:100,maxHp:100,level:1,xp:0,gold:0,kills:0,inventory:{wolfPelt:0}};
    clients.set(id,{character,player:{...character,x:WORLD.spawn.x+50,y:WORLD.spawn.y+20,attackAt:-700},input:{x:1,y:0}});}
  const room=new CombatRoom('BUFF',WORLD,'resources',clients,{gameplay,emit:e=>events.push(structuredClone(e)),changed(){},notice:(ws,message)=>notices.push(message)});
  return {room,a:clients.get('a'),b:clients.get('b'),clients,events,notices};
}

test('local damage resolver validates stats, caps overkill and carries source channels without inventing resistance',()=>{
  assert.deepEqual(resolveDamage({base:8,bonus:.5,damageType:2,damageAttribute:16},60),
    {damage:12,targetHp:48,damageType:2,damageAttribute:16,bonus:.5,damageRule:'local-v2'});
  assert.equal(resolveDamage({base:6,armor:2},100).damage,4);
  assert.equal(resolveDamage({base:6,armor:999},100).damage,1);
  assert.equal(resolveDamage({base:100},3).damage,3);
  assert.equal(resolveDamage({base:0},100).damage,0);
  for(const args of [{base:NaN},{base:Infinity},{base:-1},{base:5,bonus:-1},{base:5,armor:NaN}])assert.throws(()=>resolveDamage(args,60));
});

test('periodic status catches up exactly five times, includes its final boundary and expires once',()=>{
  const pulses=[],events=[],target={id:'target',hp:100},source={player:{id:'caster'}};
  const r=new BuffRuntime(combat,{emit:e=>events.push(e),pulse:(v,now,at)=>pulses.push(at)});
  r.apply(target,'burn',source,100,{durationMs:7000,ticks:5,amount:3});
  r.tick(1499);assert.equal(pulses.length,0);r.tick(1500);assert.deepEqual(pulses,[1500]);
  r.tick(7100);assert.deepEqual(pulses,[1500,2900,4300,5700,7100]);
  r.tick(7100);r.tick(10000);assert.equal(pulses.length,5);assert.equal(events.filter(e=>e.action==='buff-remove').length,1);
  assert.deepEqual(r.snapshot(target,7100),[]);
});

test('refresh and cross-caster replacement invalidate the old schedule and snapshots never share mutable state',()=>{
  const hits=[],target={id:'target',hp:100},a={player:{id:'a'}},b={player:{id:'b'}};
  const r=new BuffRuntime(combat,{emit(){},pulse:v=>hits.push(v.source.player.id)});
  r.apply(target,'burn',a,0,{durationMs:7000,ticks:5});r.tick(1400);
  r.apply(target,'burn',b,1500,{durationMs:7000,ticks:5});r.tick(2800);assert.deepEqual(hits,['a']);
  const snap=r.snapshot(target,2800);snap[0].expiresAt=0;r.tick(2900);assert.deepEqual(hits,['a','b']);
  assert.equal(r.snapshot(target,2900)[0].expiresAt,8500);assert.equal(r.snapshot(target,2900).length,1);
  assert.equal(activeBuffs(target,2900).length,0);
  assert.match(buffText({buffs:r.snapshot(target,2900)},2900),/burn · 5.6s/);
  assert.equal(buffText({buffs:r.snapshot(target,2900)},8500),'');
  assert.throws(()=>r.apply(target,'__proto__',a,0,{durationMs:2}));
  assert.throws(()=>r.apply(target,'burn',a,0,{durationMs:Infinity}));
});

test('source-profile frost freezes real movement and melee for 2000ms, then resumes with no local slow fallback',()=>{
  const {room,a}=fixture();room.skill(a,'frost_blast',room.monster.id,1000);room.tick(1000,.05);
  assert.equal(room.monster.hp,40);assert.equal(room.monster.slowUntil,0);
  const frozen={x:room.monster.x,y:room.monster.y,hp:a.player.hp};
  for(const now of [1001,2000,2999])room.tick(now,.05);
  assert.deepEqual({x:room.monster.x,y:room.monster.y,hp:a.player.hp},frozen);
  a.player.x+=100;room.tick(3000,.05);assert(room.monster.x>frozen.x);
  assert.deepEqual(room.monster.buffs,[]);
});

test('burning target grants arcane 50% at impact, periodic damage does not refresh itself or replay a spell hit',()=>{
  const {room,a,b,events}=fixture();room.monster.hp=room.monster.maxHp=500;
  room.damageMonster(a,30,1000,{id:'fire',skillId:'fireball'});
  const burn=room.monster.buffs[0];assert.equal(burn.expiresAt,8000);
  room.damageMonster(b,8,1100,{id:'arcane',skillId:'arcane_missile'});
  assert.equal(events.find(e=>e.castId==='arcane').damage,12);
  assert.equal(events.find(e=>e.castId==='arcane').damageAttribute,16);
  room.tick(2400,0);assert.equal(events.filter(e=>e.action==='periodic-hit').length,1);
  assert.equal(events.find(e=>e.action==='periodic-hit').damage,3);
  assert.equal(room.monster.buffs[0].id,burn.id);assert.equal(room.monster.buffs[0].expiresAt,8000);
  room.tick(8000,0);room.damageMonster(b,8,8000,{id:'plain',skillId:'arcane_missile'});
  assert.equal(events.find(e=>e.castId==='plain').damage,8);
  assert.equal(events.filter(e=>e.action==='periodic-hit').length,5);
});

test('server control cancels outstanding channel once, rejects attacks/spells, and uses independent overlapping lifetimes',()=>{
  const {room,a,b,events,notices}=fixture();room.skill(a,'arcane_missile',room.monster.id,1000);
  room.applyStatus(a.player,'freeze',b,1100,{durationMs:2000});
  room.applyStatus(a.player,'silence',b,1200,{durationMs:4000});
  assert.deepEqual(a.input,{x:0,y:0});assert.equal(room.runtime.pending.size,0);
  room.attack(a,room.monster.id,1200);room.skill(a,'fireball',room.monster.id,1200);
  assert.equal(notices.length,2);assert.equal(room.monster.hp,60);
  room.tick(3100,0);assert(!room.blocked(a.player,'move',3100));assert(room.blocked(a.player,'skill',3100));
  assert(!room.blocked(a.player,'attack',3100));assert(!room.blocked(a.player,'jump',3100));
  room.tick(5200,0);assert(!room.blocked(a.player,'skill',5200));
  assert.equal(events.filter(e=>e.action==='skill-cancel').length,1);
  assert.equal(events.filter(e=>e.action==='skill-hit').length,0);
});

test('lethal periodic catch-up awards one kill, clears all statuses, and cannot damage a respawn',()=>{
  const {room,a,events}=fixture();room.monster.hp=35;
  room.damageMonster(a,30,1000,{id:'fire',skillId:'fireball'});room.tick(8000,0);room.tick(8000,0);
  assert.equal(room.monster.hp,0);assert.equal(a.character.kills,1);assert.equal(a.character.gold,10);
  assert.equal(events.filter(e=>e.action==='periodic-hit').length,2);
  assert.equal(events.filter(e=>e.action==='kill').length,1);assert.equal(room.buffs.targets.size,0);
  room.tick(16000,0);room.tick(20000,0);assert.equal(room.monster.hp,60);assert.deepEqual(room.monster.buffs,[]);
});

test('dead targets and disconnected casters lose transient effects without leaking another room or granting stale rewards',()=>{
  const {room,a,clients,events}=fixture();room.damageMonster(a,30,1000,{id:'fire',skillId:'fireball'});
  clients.delete(a.player.id);room.tick(9000,0);assert.equal(room.monster.hp,30);
  assert.equal(events.filter(e=>e.action==='periodic-hit').length,0);assert.equal(a.character.kills,0);
  const other=fixture();assert.equal(other.room.buffs.targets.size,0);
  other.room.applyStatus(other.a.player,'stun',other.b,0,{durationMs:5000});
  other.a.player.hp=0;other.room.tick(1,0);assert.deepEqual(other.a.player.buffs,[]);
});
