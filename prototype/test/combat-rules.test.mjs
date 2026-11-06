import test from 'node:test';
import assert from 'node:assert/strict';
import { CombatRoom, COMBAT } from '../game/combat.mjs';
import { WORLD } from '../public/world.js';

function adventurer(id, { hp = 100 } = {}) {
  return {
    character: { id, name: id, hp, maxHp: 100, level: 1, xp: 0, gold: 0, kills: 0, inventory: { wolfPelt: 0 } },
    player: { id, name: id, hp, maxHp: 100, level: 1, x: WORLD.spawn.x + 50, y: WORLD.spawn.y + 20,
      attackAt: -COMBAT.playerCooldownMs, deadUntil: 0 },
    input: { x: 1, y: 1 },
  };
}

function encounter(clients) {
  const changes = [], events = [], notices = [];
  const room = new CombatRoom('RULES', WORLD, 'camp', clients, {
    changed(ws, immediate) {
      // Capture the state passed to the server's persistence/progress callback.
      changes.push({ id: ws.player.id, immediate, hp: ws.character.hp, x: ws.player.x, y: ws.player.y,
        input: { ...ws.input }, monsterAlive: room.monster.alive });
    },
    emit(event) { events.push(event); },
    notice(ws, message) { notices.push({ id: ws.player.id, message }); },
  });
  return { room, changes, events, notices };
}

test('a lethal monster hit stops input; the player revives after exactly four seconds and requests saved progress', () => {
  const victim = adventurer('victim', { hp: COMBAT.monsterDamage });
  const { room, changes, events, notices } = encounter(new Map([[victim.player.id, victim]]));
  const hitAt = 1000;
  room.attack(victim, room.monster.id, hitAt); // Start the encounter through a valid player attack.
  room.tick(hitAt, .05);

  assert.equal(victim.character.hp, 0);
  assert.equal(victim.player.hp, 0);
  assert.equal(victim.player.deadUntil, hitAt + 4000);
  assert.deepEqual(victim.input, { x: 0, y: 0 });
  assert.equal(changes.length, 1);
  assert.equal(changes[0].hp, 0);
  assert.equal(changes[0].immediate, true, 'Death requests immediate persistence and progress delivery');
  assert.equal(events.filter(e => e.action === 'player-hit' && e.targetId === victim.player.id).length, 1);

  const remainingMonsterHp = room.monster.hp;
  room.attack(victim, room.monster.id, hitAt + 750);
  assert.equal(room.monster.hp, remainingMonsterHp, 'A dead character cannot keep attacking');
  assert.equal(notices.length, 1);

  const deathPosition = { x: victim.player.x, y: victim.player.y };
  victim.input = { x: 1, y: 0 }; // Stale/new input must not survive revival.
  room.tick(hitAt + 3999, .05);
  assert.equal(victim.player.hp, 0);
  assert.deepEqual({ x: victim.player.x, y: victim.player.y }, deathPosition);
  assert.equal(events.filter(e => e.action === 'respawn' && e.targetId === victim.player.id).length, 0);

  room.tick(hitAt + 4000, .05);
  assert.equal(victim.character.hp, victim.character.maxHp);
  assert.equal(victim.player.hp, victim.character.maxHp);
  assert.deepEqual({ x: victim.player.x, y: victim.player.y }, WORLD.spawn);
  assert.equal(victim.player.deadUntil, 0);
  assert.deepEqual(victim.input, { x: 0, y: 0 });
  assert.equal(changes.length, 2);
  assert.deepEqual(changes[1], {
    id: victim.player.id, immediate: true, hp: 100, ...WORLD.spawn,
    input: { x: 0, y: 0 }, monsterAlive: true,
  }, 'Revival supplies restored HP/position to the persistence/progress callback');
  assert.equal(events.filter(e => e.action === 'respawn' && e.targetId === victim.player.id).length, 1);

  room.tick(hitAt + 4001, .05);
  assert.equal(events.filter(e => e.action === 'respawn' && e.targetId === victim.player.id).length, 1);
  assert.equal(changes.length, 2, 'Revival cannot be persisted or emitted twice');
});

test('dead, disconnected and nonparticipating characters do not receive a kill reward', () => {
  const winner = adventurer('winner'), dead = adventurer('dead-contributor');
  const disconnected = adventurer('disconnected-contributor'), spectator = adventurer('spectator');
  const clients = new Map([winner, dead, disconnected, spectator].map(ws => [ws.player.id, ws]));
  const { room, changes, events } = encounter(clients);
  const now = 1000;

  room.attack(dead, room.monster.id, now);
  room.attack(disconnected, room.monster.id, now);
  assert.equal(room.monster.hp, 20);
  assert(room.contributors.has(dead.player.id));
  assert(room.contributors.has(disconnected.player.id));
  dead.character.hp = dead.player.hp = 0;
  clients.delete(disconnected.player.id);
  room.attack(winner, room.monster.id, now);

  assert.equal(room.monster.alive, false);
  assert.equal(room.monster.hp, 0);
  assert.equal(winner.character.xp, 30);
  assert.equal(winner.character.gold, 10);
  assert.equal(winner.character.kills, 1);
  assert.equal(winner.character.inventory.wolfPelt, 1);
  for (const ws of [dead, disconnected, spectator]) {
    assert.equal(ws.character.xp, 0, ws.player.id);
    assert.equal(ws.character.gold, 0, ws.player.id);
    assert.equal(ws.character.kills, 0, ws.player.id);
    assert.equal(ws.character.inventory.wolfPelt, 0, ws.player.id);
  }
  assert.deepEqual(changes.map(c => c.id), [winner.player.id]);
  assert.equal(changes[0].immediate, true);
  assert.equal(changes[0].monsterAlive, false, 'Death is established before reward persistence');
  assert.equal(events.filter(e => e.action === 'kill').length, 1);
  assert.equal(room.contributors.size, 0);

  clients.set(disconnected.player.id, disconnected);
  room.attack(winner, room.monster.id, now + 750);
  room.attack(disconnected, room.monster.id, now + 750);
  assert.equal(changes.length, 1, 'A stale attack or returning contributor cannot settle the same kill again');
  assert.equal(events.filter(e => e.action === 'kill').length, 1);
  assert.equal(disconnected.character.gold, 0);
  assert.equal(winner.character.gold, 10);
});

test('only accepted server results publish animation clocks, fatal HP and fresh life metadata', () => {
  const a=adventurer('attacker'),b=adventurer('fragile',{hp:6});
  const {room,events}=encounter(new Map([[a.player.id,a],[b.player.id,b]]));
  room.attack(a,room.monster.id,1000);
  assert.equal(a.player.animation.attackAt,1000);
  assert.equal(room.monster.animation.hitAt,1000);
  assert.equal(events.at(-1).targetHp,40);assert.equal(events.at(-1).serverTime,1000);
  room.attack(a,room.monster.id,1001);
  assert.equal(a.player.animation.attackAt,1000,'Rejected cooldown attempts do not restart the animation');
  const oldSnapshot=room.snapshot()[0];
  room.attack(b,room.monster.id,1750);
  assert.equal(oldSnapshot.animation.hitAt,1000,'A captured public snapshot cannot be mutated by later hits');
  a.player.x=room.monster.x+200;
  room.tick(2000,.05);
  const fatal=events.find(event=>event.action==='player-hit'&&event.targetId===b.player.id);
  assert.equal(fatal.targetHp,0);assert.equal(fatal.serverTime,2000);assert.equal(b.player.animation.deathAt,2000);
  a.player.x=room.monster.x;a.player.y=room.monster.y;
  room.attack(a,room.monster.id,2500);
  assert.equal(room.monster.animation.deathAt,2500);
  assert.equal(events.find(event=>event.action==='kill').serverTime,2500);
  room.tick(6000,.05);
  assert.deepEqual(b.player.animation,{attackAt:null,hitAt:null,deathAt:null});
  room.tick(10500,.05);
  assert.deepEqual(room.monster.animation,{attackAt:null,hitAt:null,deathAt:null});
});
