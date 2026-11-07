import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import WebSocket from 'ws';
import { createGameServer } from '../server.mjs';
import {existsSync} from 'node:fs';

// Every test has a fresh save directory; no test reads or modifies runtime/.
async function fixture(t) {
  const directory = await mkdtemp(join(tmpdir(), 'oc2-combat-test-'));
  const saveFile = join(directory, 'characters.json');
  let now = Date.now(), game;
  const f = {
    saveFile,
    advance(ms) { now += ms; },
    async start() {
      game = createGameServer({ saveFile, clock: () => now });
      await new Promise(resolve => game.server.listen(0, '127.0.0.1', resolve));
      f.url = `ws://127.0.0.1:${game.server.address().port}/ws`;
      return f;
    },
    async stop() { if (game) { const previous = game; game = null; await previous.close(); } },
  };
  t.after(async () => { await f.stop(); await rm(directory, { recursive: true, force: true }); });
  return f.start();
}

async function client(url) {
  const ws = new WebSocket(url);
  const messages = [];
  ws.on('error', () => {});
  ws.on('message', raw => messages.push(JSON.parse(raw.toString())));
  const c = {
    ws, messages,
    send(data) { ws.send(JSON.stringify(data)); },
    mark() { return messages.length; },
    wait(predicate, { after = 0, timeout = 4000 } = {}) {
      const existing = messages.slice(after).find(predicate);
      if (existing) return Promise.resolve(existing);
      return new Promise((resolve, reject) => {
        const finish = (error, data) => {
          clearTimeout(timer); ws.off('message', receive); ws.off('close', closed);
          if (error) reject(error); else resolve(data);
        };
        const receive = raw => { const data = JSON.parse(raw.toString()); if (predicate(data)) finish(null, data); };
        const closed = () => finish(new Error(`Socket closed while waiting; last messages: ${JSON.stringify(messages.slice(-3))}`));
        const timer = setTimeout(() => finish(new Error(`Timed out; last messages: ${JSON.stringify(messages.slice(-3))}`)), timeout);
        ws.on('message', receive); ws.on('close', closed);
      });
    },
    async close() {
      if (ws.readyState === WebSocket.CLOSED) return;
      const closed = once(ws, 'close'); ws.close(); await closed;
    },
  };
  await once(ws, 'open');
  return c;
}

async function enter(f, name, { scene = 'camp', room = 'PLAY-01', ...credentials } = {}) {
  const c = await client(f.url);
  c.send({ type: 'join', name, room, scene, ...credentials });
  c.welcome = await c.wait(m => m.type === 'welcome');
  c.id = c.welcome.id;
  return c;
}

const stateAfter = (c, after, predicate = () => true) => c.wait(m => m.type === 'state' && predicate(m), { after });
const player = (state, id) => state.players.find(p => p.id === id);
const wolf = state => state.monsters.find(m => m.kind === 'wolf');
const monster = (state, id) => state.monsters.find(m => m.id === id);

function publicStateHasNoCredentials(c, tokens) {
  for (const message of c.messages.filter(m => m.type === 'state')) {
    const text = JSON.stringify(message);
    for (const token of tokens) if (token) assert(!text.includes(token), 'Recovery credentials must not be broadcast');
    assert(!/"(?:resumeToken|tokenHash|recoveryToken|password)"\s*:/.test(text));
  }
}

async function moveNear(c, target, distance = 22) {
  let latest = await stateAfter(c, c.mark());
  const input = () => {
    const own = player(latest, c.id), dx = target.x - own.x, dy = target.y - own.y;
    const d = Math.hypot(dx, dy);
    c.send({ type: 'input', x: dx / Math.max(d, 1), y: dy / Math.max(d, 1) });
  };
  const update = raw => { const m = JSON.parse(raw.toString()); if (m.type === 'state') latest = m; };
  c.ws.on('message', update);
  const after = c.mark();
  input();
  const timer = setInterval(input, 50);
  try {
    await stateAfter(c, after, m => {
      const p = player(m, c.id);
      return Math.hypot(p.x - target.x, p.y - target.y) <= distance;
    });
  } finally {
    clearInterval(timer); c.ws.off('message', update);
    if (c.ws.readyState === WebSocket.OPEN) c.send({ type: 'input', x: 0, y: 0 });
  }
  return stateAfter(c, c.mark());
}

async function attackUntilDead(c, f, targetId) {
  for (const remaining of [40, 20, 0]) {
    f.advance(750);
    const after = c.mark(); c.send({ type: 'attack', targetId });
    await stateAfter(c, after, m => monster(m, targetId)?.hp === remaining);
  }
  return c.wait(m => m.type === 'progress' && m.character.kills === 1);
}

test('server enforces melee range and cooldown, ignores forged stats, and awards a dead monster once', async t => {
  const f = await fixture(t), c = await enter(f, '近战测试', { scene: 'resources' });
  const initial = await stateAfter(c, c.mark()), target = wolf(initial);
  assert(target && target.alive && target.hp === 60);
  const own = player(initial, c.id);
  assert(Math.hypot(own.x - target.x, own.y - target.y) > 32);

  let after = c.mark();
  c.send({ type: 'attack', targetId: target.id, damage: 99999, gold: 99999, xp: 99999, x: target.x, y: target.y });
  await c.wait(m => m.type === 'notice', { after });
  const tooFar = await stateAfter(c, after);
  assert.equal(monster(tooFar, target.id).hp, 60);
  assert.equal(player(tooFar, c.id).x, own.x, 'Attack frames cannot teleport the character');
  assert.equal(c.ws.readyState, WebSocket.OPEN, 'Invalid combat attempts should be nonfatal');

  await moveNear(c, target);
  after = c.mark(); c.send({ type: 'attack', targetId: target.id, damage: 99999, gold: 99999, xp: 99999 });
  const hit = await stateAfter(c, after, m => monster(m, target.id).hp === 40);
  assert.equal(monster(hit, target.id).hp, 40, 'Only server damage is applied');
  after = c.mark(); c.send({ type: 'attack', targetId: target.id });
  await c.wait(m => m.type === 'notice', { after });
  assert.equal(monster(await stateAfter(c, after), target.id).hp, 40);

  for (const remaining of [20, 0]) {
    f.advance(750); after = c.mark(); c.send({ type: 'attack', targetId: target.id });
    await stateAfter(c, after, m => monster(m, target.id).hp === remaining);
  }
  const progress = await c.wait(m => m.type === 'progress' && m.character.kills === 1);
  assert.equal(progress.character.xp, 30); assert.equal(progress.character.gold, 10);
  assert.equal(progress.character.inventory.wolfPelt, 1);
  assert.equal(c.messages.filter(m => m.type === 'combat' && m.action === 'kill').length, 1);

  f.advance(750); after = c.mark(); c.send({ type: 'attack', targetId: target.id, reward: 99999 });
  await c.wait(m => m.type === 'notice', { after });
  assert.equal(monster(await stateAfter(c, after), target.id).alive, false);
  assert.equal(c.messages.filter(m => m.type === 'progress' && m.character.kills > 1).length, 0);
  f.advance(8001);
  const respawned = await stateAfter(c, c.mark(), m => monster(m, target.id)?.alive);
  assert.equal(monster(respawned, target.id).hp, 60);
  assert.equal(c.messages.filter(m => m.type === 'combat' && m.action === 'kill').length, 1);
  for (const remaining of [40, 20, 0]) {
    f.advance(750); after = c.mark(); c.send({ type: 'attack', targetId: target.id });
    await stateAfter(c, after, m => monster(m, target.id).hp === remaining);
  }
  const leveled = (await c.wait(m => m.type === 'progress' && m.character.kills === 2)).character;
  assert.equal(leveled.xp, 60); assert.equal(leveled.gold, 20); assert.equal(leveled.inventory.wolfPelt, 2);
  assert.equal(leveled.level, 2); assert.equal(leveled.maxHp, 120); assert.equal(leveled.hp, 120);
  publicStateHasNoCredentials(c, [c.welcome.resumeToken]);
});

test('two players observe the same kill and each living contributor receives exactly one reward', async t => {
  const f = await fixture(t), a = await enter(f, '同行甲'), b = await enter(f, '同行乙');
  const initial = await stateAfter(a, a.mark(), m => m.players.length === 2), target = wolf(initial);
  let markA = a.mark(), markB = b.mark();
  a.send({ type: 'attack', targetId: target.id }); b.send({ type: 'attack', targetId: target.id });
  const [hitA, hitB] = await Promise.all([
    stateAfter(a, markA, m => monster(m, target.id).hp === 20),
    stateAfter(b, markB, m => monster(m, target.id).hp === 20),
  ]);
  assert.deepEqual(monster(hitA, target.id), monster(hitB, target.id));

  f.advance(750); markA = a.mark(); markB = b.mark();
  a.send({ type: 'attack', targetId: target.id }); b.send({ type: 'attack', targetId: target.id });
  const [deadA, deadB] = await Promise.all([
    stateAfter(a, markA, m => monster(m, target.id).hp === 0),
    stateAfter(b, markB, m => monster(m, target.id).hp === 0),
  ]);
  assert.equal(monster(deadA, target.id).alive, false);
  assert.deepEqual(monster(deadA, target.id), monster(deadB, target.id));
  for (const c of [a, b]) {
    const result = (await c.wait(m => m.type === 'progress' && m.character.kills === 1)).character;
    assert.equal(result.xp, 30); assert.equal(result.gold, 10); assert.equal(result.inventory.wolfPelt, 1);
    assert.equal(c.messages.filter(m => m.type === 'combat' && m.action === 'kill').length, 1);
    publicStateHasNoCredentials(c, [a.welcome.resumeToken, b.welcome.resumeToken]);
  }
});

test('credentials restore rewards and per-scene positions after a server restart', async t => {
  const f = await fixture(t), original = await enter(f, '存档旅人', { scene: 'resources' });
  const target = wolf(await stateAfter(original, original.mark()));
  await moveNear(original, target);
  const progress = await attackUntilDead(original, f, target.id);
  const before = await stateAfter(original, original.mark());
  const savedPosition = { x: player(before, original.id).x, y: player(before, original.id).y };
  const credentials = { characterId: original.welcome.character.id, resumeToken: original.welcome.resumeToken };
  assert(credentials.characterId && credentials.resumeToken);
  await original.close(); await f.stop();
  const stored = await readFile(f.saveFile, 'utf8');
  assert(stored.length > 0);
  assert(!stored.includes(credentials.resumeToken), 'Recovery secrets must be stored as hashes, not plaintext');
  await f.start();

  const restored = await enter(f, '存档旅人', { scene: 'resources', ...credentials });
  assert.equal(restored.welcome.restored, true);
  assert.equal(restored.id, original.id);
  for (const key of ['level', 'xp', 'gold', 'kills', 'inventory']) assert.deepEqual(restored.welcome.character[key], progress.character[key]);
  const resumed = await stateAfter(restored, restored.mark());
  assert.equal(player(resumed, restored.id).x, savedPosition.x);
  assert.equal(player(resumed, restored.id).y, savedPosition.y);
  await restored.close();

  const camp = await enter(f, '存档旅人', { scene: 'camp', ...credentials });
  const campState = await stateAfter(camp, camp.mark());
  assert.equal(player(campState, camp.id).x, camp.welcome.world.spawn.x);
  assert.equal(player(campState, camp.id).y, camp.welcome.world.spawn.y);
  await camp.close();
  const back = await enter(f, '存档旅人', { scene: 'resources', ...credentials });
  const returned = await stateAfter(back, back.mark());
  assert.equal(player(returned, back.id).x, savedPosition.x);
  assert.equal(player(returned, back.id).y, savedPosition.y);
  assert.equal(back.welcome.character.inventory.wolfPelt, 1);
  publicStateHasNoCredentials(back, [credentials.resumeToken]);
});

test('wrong credentials and duplicate sessions cannot claim another active character', async t => {
  const f = await fixture(t), owner = await enter(f, '原角色');
  const credentials = { characterId: owner.welcome.character.id, resumeToken: owner.welcome.resumeToken };
  for (const resumeToken of ['0'.repeat(64), credentials.resumeToken]) {
    const candidate = await client(f.url);
    candidate.send({ type: 'join', name: '原角色', room: 'PLAY-01', scene: 'camp', characterId: credentials.characterId, resumeToken });
    await candidate.wait(m => m.type === 'error');
    assert.equal(candidate.messages.filter(m => m.type === 'welcome').length, 0);
    await candidate.close();
  }
  const state = await stateAfter(owner, owner.mark());
  assert.equal(state.players.length, 1); assert.equal(owner.ws.readyState, WebSocket.OPEN);
  publicStateHasNoCredentials(owner, [credentials.resumeToken]);
});

test('a corrupt existing save fails visibly and is not overwritten', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'oc2-corrupt-save-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const saveFile = join(directory, 'characters.json'), damaged = '{broken save content';
  await writeFile(saveFile, damaged);
  assert.throws(() => createGameServer({ saveFile }));
  assert.equal(await readFile(saveFile, 'utf8'), damaged);
});

test('two clients and a late observer receive the same server skill, impact and cooldown without trusting forged data', async t => {
  const f=await fixture(t),a=await enter(f,'技能联机甲',{scene:'resources'}),b=await enter(f,'技能联机乙',{scene:'resources'});
  const initial=await stateAfter(a,a.mark(),m=>m.players.length===2),target=wolf(initial);
  const before=player(initial,a.id),markA=a.mark(),markB=b.mark();
  a.send({type:'skill',skillId:'fireball',targetId:target.id,damage:999999,cooldownMs:0,castMs:0,x:target.x});
  const [castA,castB]=await Promise.all([a.wait(m=>m.action==='skill-cast',{after:markA}),b.wait(m=>m.action==='skill-cast',{after:markB})]);
  assert.deepEqual(castA,castB);assert.equal(castA.cast.impactAt-castA.serverTime,850);
  a.send({type:'input',x:1,y:0});
  const during=await stateAfter(a,a.mark(),m=>player(m,a.id)?.cast);
  assert.equal(wolf(during).hp,60);assert.equal(player(during,a.id).x,before.x,'Cast lock is enforced on server movement');
  const observer=await enter(f,'技能旁观',{scene:'resources'});
  const late=await stateAfter(observer,observer.mark());
  assert.equal(player(late,a.id).cast.id,castA.cast.id,'Late observer gets the original pending cast and timeline');
  assert.equal(player(late,a.id).skillReadyAt.fireball,castA.serverTime+3000);
  f.advance(850);
  const impactA=await a.wait(m=>m.action==='skill-hit'),impactB=await b.wait(m=>m.action==='skill-hit');
  assert.deepEqual(impactA,impactB);assert.equal(impactA.damage,30);assert.equal(impactA.targetHp,30);
  const cooldownMark=a.mark();a.send({type:'skill',skillId:'fireball',targetId:target.id});
  await a.wait(m=>m.type==='notice'&&m.message.includes('冷却'),{after:cooldownMark});
  b.send({type:'skill',skillId:'frost_blast',targetId:target.id});await b.wait(m=>m.action==='skill-cast'&&m.cast.skillId==='frost_blast');
  f.advance(700);
  await stateAfter(a,a.mark(),m=>wolf(m).hp===10&&wolf(m).slowUntil>m.serverTime);
  await moveNear(a,target,22);
  a.send({type:'attack',targetId:target.id});
  for(const c of [a,b]){
    const progress=await c.wait(m=>m.type==='progress'&&m.character.kills===1);assert.equal(progress.character.gold,10);
    publicStateHasNoCredentials(c,[a.welcome.resumeToken,b.welcome.resumeToken,observer.welcome.resumeToken]);
  }
  assert.equal(observer.messages.filter(m=>m.type==='progress'&&m.character.kills>0).length,0);
});

test('jump is server timed, shared with late observers, transient across reconnect, and ignores forged height/timing',async t=>{
  const f=await fixture(t),a=await enter(f,'跳跃甲',{scene:'resources'}),b=await enter(f,'跳跃乙',{scene:'resources'});
  const markA=a.mark(),markB=b.mark();
  a.send({type:'jump',pressed:true,startedAt:0,height:999999,endsAt:Infinity});
  const first=await stateAfter(a,markA,m=>player(m,a.id)?.jump),second=await stateAfter(b,markB,m=>player(m,a.id)?.jump);
  const jump=player(first,a.id).jump;assert.deepEqual(player(second,a.id).jump,jump);
  assert.equal(jump.startedAt,first.serverTime);assert.equal(jump.takeoffAt-jump.startedAt,0);assert(!('height' in jump));
  const late=await enter(f,'跳跃旁观',{scene:'resources'});
  const observed=await stateAfter(late,late.mark());assert.deepEqual(player(observed,a.id).jump,jump);
  a.send({type:'jump',pressed:false});a.send({type:'jump',pressed:true});
  const again=await stateAfter(a,a.mark());assert.deepEqual(player(again,a.id).jump,jump);
  const target=wolf(again),mark=a.mark();a.send({type:'skill',skillId:'fireball',targetId:target.id});
  await a.wait(m=>m.type==='notice'&&m.message.includes('跳跃'),{after:mark});
  f.advance(2500);const landed=await stateAfter(a,a.mark(),m=>player(m,a.id)?.jump===null);assert.equal(player(landed,a.id).jump,null);
  a.send({type:'save'});await a.wait(m=>m.type==='notice'&&m.message.includes('保存'));
  const raw=JSON.parse(await readFile(f.saveFile,'utf8'));assert(!JSON.stringify(raw).includes('takeoffAt'));
  publicStateHasNoCredentials(b,[a.welcome.resumeToken,b.welcome.resumeToken,late.welcome.resumeToken]);
  await a.close();
  const restored=await enter(f,'跳跃甲',{scene:'resources',characterId:a.id,resumeToken:a.welcome.resumeToken});
  const state=await stateAfter(restored,restored.mark());assert.equal(player(state,a.id).jump,null);
  const bad=restored.mark();restored.send({type:'jump',pressed:1});await restored.wait(m=>m.type==='error'&&m.message.includes('跳跃'),{after:bad});
});

test('original staff attack is chosen on the server and both peers receive its skill; weapon changes and reconnect reset it',
  {skip:!existsSync(new URL('../../game-data/converted/gameplay/native.json',import.meta.url))},async t=>{
  const f=await fixture(t),a=await enter(f,'法师普攻',{scene:'resources',profession:2}),b=await enter(f,'武僧普攻',{scene:'resources',profession:4});
  for(const c of [a,b]){
    const mark=c.mark();c.send({type:'equip',slot:'mainHand',itemId:'trainingStaff'});
    await c.wait(m=>m.type==='progress'&&m.character.equipment.mainHand==='trainingStaff',{after:mark});
  }
  const initial=await stateAfter(a,a.mark(),m=>player(m,a.id)?.basicAttack?.id===84&&player(m,b.id)?.basicAttack?.id===424);
  const target=wolf(initial);await moveNear(a,target);
  let ma=a.mark(),mb=b.mark();a.send({type:'attack',targetId:target.id,skillId:424,clip:'forged',profession:4,mainWeaponType:0xffff});
  const own=await a.wait(m=>m.type==='combat'&&m.action==='hit'&&m.attackerId===a.id,{after:ma});
  const other=await b.wait(m=>m.type==='combat'&&m.action==='hit'&&m.attackerId===a.id,{after:mb});
  assert.equal(own.basicAttack.id,84);assert.deepEqual(own.basicAttack,other.basicAttack);
  assert.equal(own.basicAttack.clip,'attack_84');
  f.advance(700);ma=a.mark();a.send({type:'attack',targetId:target.id});
  const chained=await a.wait(m=>m.type==='combat'&&m.action==='hit'&&m.attackerId===a.id,{after:ma});
  assert([85,86].includes(chained.basicAttack.id));
  a.send({type:'unequip',slot:'mainHand'});
  const empty=await stateAfter(a,a.mark(),m=>player(m,a.id)?.basicAttack?.id===4);assert.equal(player(empty,a.id).equipment.mainHand,null);
  a.send({type:'equip',slot:'mainHand',itemId:'trainingGreatsword'});
  await a.wait(m=>m.type==='notice'&&m.message.includes('职业'));
  await a.close();const resumed=await enter(f,'同一法师',{scene:'resources',profession:1,characterId:a.id,resumeToken:a.welcome.resumeToken});
  assert.equal(resumed.welcome.character.profession,2);
  const rejoined=await stateAfter(resumed,resumed.mark());assert.equal(player(rejoined,resumed.id).basicAttack.id,4);
});
