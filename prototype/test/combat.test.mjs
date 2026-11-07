import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import WebSocket from 'ws';
import { createGameServer } from '../server.mjs';
import {existsSync} from 'node:fs';
import {createCollision,loadCollision} from '../game/collision.mjs';
import {loadNavigation} from '../game/navigation.mjs';

// Every test has a fresh save directory; no test reads or modifies runtime/.
async function fixture(t,options={}) {
  const directory = await mkdtemp(join(tmpdir(), 'oc2-combat-test-'));
  const saveFile = join(directory, 'characters.json');
  let now = Date.now(), game;
  const f = {
    saveFile,
    advance(ms) { now += ms; },
    async start() {
      game = createGameServer({ saveFile, motion:null,ai:false,contextualLoot:false,casting:false,clock: () => now,...options });
      f.game=game;
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

test('quest/object states stay recipient-scoped for two peers, late join and reconnect; forged rewards are rejected',async t=>{
 const gameplay={weapons:{},skills:{},comboRows:[],quests:{format:'oc2-source-quests-v1',objects:[{id:'source-static-3064',spawnId:3064,entry:621,sourceState:0}]}};
 const f=await fixture(t,{gameplay}),a=await enter(f,'任务甲',{scene:'resources'}),b=await enter(f,'任务乙',{scene:'resources'});
 const initial=await stateAfter(a,a.mark(),s=>s.players.length===2);assert.equal(initial.questState.objects[0].state.canLoot,null);assert.deepEqual(initial.questState.active,[]);
 const room=[...f.game.combatRooms.values()][0];room.questState.applySourceState(a.id,'source-static-3064',{canLoot:false,questStatus:0,interactives:[]});
 const updated=await stateAfter(a,a.mark(),s=>s.questState.objects[0].revision===1),peer=await stateAfter(b,b.mark(),s=>s.tick===updated.tick);assert.equal(peer.questState.objects[0].revision,0);assert.equal(peer.questState.objects[0].state.canLoot,null);
 const late=await enter(f,'任务迟到',{scene:'resources'}),seen=await stateAfter(late,late.mark());assert.equal(seen.questState.objects[0].state.canLoot,null);
 const creds={characterId:a.id,resumeToken:a.welcome.resumeToken};await a.close();const resumed=await enter(f,'任务甲',{scene:'resources',...creds});assert.deepEqual((await stateAfter(resumed,resumed.mark())).questState,updated.questState);
 const mark=late.mark();late.send({type:'quest-state',questId:632,status:1,canLoot:true,rewards:{xp:11725,gold:68}});await late.wait(m=>m.type==='error',{after:mark});
 assert.equal(room.clients.get(a.id).character.xp,0);assert.equal(room.clients.get(b.id).character.gold,0);
 resumed.send({type:'save'});await resumed.wait(m=>m.type==='notice'&&m.message.includes('保存'));
 const disk=await readFile(f.saveFile,'utf8');assert(!disk.includes('questStatus'));assert(!disk.includes('source-static-3064'));assert.equal(JSON.parse(disk).version,6);
 publicStateHasNoCredentials(b,[a.welcome.resumeToken,b.welcome.resumeToken]);
});

test('contextual corpse loot is personal, authoritative, idempotent and saved across reconnect/restart',async t=>{
  const gameplay={weapons:{},skills:{},comboRows:[],interaction:{format:'oc2-source-interaction-v1'}};
  const f=await fixture(t,{gameplay,contextualLoot:true});
  const a=await enter(f,'拾取甲',{scene:'resources'}),b=await enter(f,'拾取乙',{scene:'resources'});
  await stateAfter(a,a.mark(),s=>s.players.length===2);
  const encounter=[...f.game.combatRooms.values()][0],server=id=>encounter.clients.get(id),now=Date.now();
  for(const c of [a,b])Object.assign(server(c.id).player,{x:encounter.monster.x,y:encounter.monster.y});
  encounter.damageMonster(server(a.id),20,now);encounter.damageMonster(server(b.id),40,now);
  const dead=await stateAfter(a,a.mark(),s=>s.interaction?.kind==='loot'),generation=dead.interaction.generation;
  const peer=await stateAfter(b,b.mark(),s=>s.tick===dead.tick);assert.deepEqual(wolf(dead),wolf(peer));assert(peer.interaction);
  assert.equal(server(a.id).character.gold,10);assert.equal(server(a.id).character.inventory.wolfPelt,0);
  assert.equal(server(b.id).character.inventory.wolfPelt,0);
  const late=await enter(f,'拾取迟到',{scene:'resources'});assert.equal((await stateAfter(late,late.mark())).interaction,null);
  let mark=late.mark();late.send({type:'loot',targetId:encounter.monster.id,generation,itemId:'wolfPelt',count:999});
  await late.wait(m=>m.type==='notice',{after:mark});assert.equal(server(late.id).character.inventory.wolfPelt,0);
  const claim={type:'loot',targetId:encounter.monster.id,generation,itemId:'trainingSword',count:999};
  mark=a.mark();a.send(claim);a.send(claim);
  const saved=await a.wait(m=>m.type==='progress'&&m.character.inventory.wolfPelt===1,{after:mark});
  assert.equal(saved.character.inventory.trainingSword,1);await stateAfter(a,a.mark(),s=>s.interaction===null);
  assert.equal(server(a.id).character.inventory.wolfPelt,1);assert(peer.interaction);
  const creds={characterId:b.id,resumeToken:b.welcome.resumeToken};await b.close();
  const resumed=await enter(f,'拾取乙',{scene:'resources',...creds});
  await stateAfter(resumed,resumed.mark(),s=>s.interaction?.generation===generation);
  mark=resumed.mark();resumed.send(claim);await resumed.wait(m=>m.type==='progress'&&m.character.inventory.wolfPelt===1,{after:mark});
  const disk=JSON.parse(await readFile(f.saveFile,'utf8'));assert.equal(disk.version,6);
  assert(!JSON.stringify(disk).includes(generation));assert.equal(disk.characters.find(c=>c.id===a.id).inventory.wolfPelt,1);
  // Entitlements are scoped to this room and corpse lifetime, never supplied by the client.
  const isolated=await enter(f,'拾取隔离',{scene:'resources',room:'OTHER-LOOT'});mark=isolated.mark();isolated.send(claim);
  await isolated.wait(m=>m.type==='notice',{after:mark});
  f.advance(10000);await stateAfter(a,a.mark(),s=>wolf(s).alive);
  mark=a.mark();a.send(claim);await a.wait(m=>m.type==='notice',{after:mark});assert.equal(server(a.id).character.inventory.wolfPelt,1);
  const owner={characterId:a.id,resumeToken:a.welcome.resumeToken};await f.stop();await f.start();
  const restored=await enter(f,'拾取甲',{scene:'resources',...owner});assert.equal(restored.welcome.character.inventory.wolfPelt,1);
  assert.equal((await stateAfter(restored,restored.mark())).interaction,null);
  publicStateHasNoCredentials(late,[owner.resumeToken,creds.resumeToken]);
});

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
  const initial=await stateAfter(a,a.mark(),m=>player(m,a.id)?.basicSlot?.id===84&&player(m,b.id)?.basicSlot?.id===424);
  const target=wolf(initial);await moveNear(a,target);
  let ma=a.mark(),mb=b.mark();a.send({type:'attack',targetId:target.id,skillId:424,clip:'forged',profession:4,mainWeaponType:0xffff});
  const own=await a.wait(m=>m.type==='combat'&&m.action==='hit'&&m.attackerId===a.id,{after:ma});
  const other=await b.wait(m=>m.type==='combat'&&m.action==='hit'&&m.attackerId===a.id,{after:mb});
  assert.equal(own.basicAttack.id,84);assert.deepEqual(own.basicAttack,other.basicAttack);
  assert.equal(own.basicAttack.clip,'attack_84');
  const prepared=await stateAfter(a,a.mark());
  assert.equal(player(prepared,a.id).basicAttack.id,84);
  assert([85,86].includes(player(prepared,a.id).basicSlot.id),'Execution prepares the next HUD slot before another press');
  f.advance(700);ma=a.mark();a.send({type:'attack',targetId:target.id});
  const chained=await a.wait(m=>m.type==='combat'&&m.action==='hit'&&m.attackerId===a.id,{after:ma});
  assert([85,86].includes(chained.basicAttack.id));
  a.send({type:'unequip',slot:'mainHand'});
  const empty=await stateAfter(a,a.mark(),m=>player(m,a.id)?.basicSlot?.id===4);assert.equal(player(empty,a.id).equipment.mainHand,null);
  a.send({type:'equip',slot:'mainHand',itemId:'trainingGreatsword'});
  await a.wait(m=>m.type==='notice'&&m.message.includes('职业'));
  await a.close();const resumed=await enter(f,'同一法师',{scene:'resources',profession:1,characterId:a.id,resumeToken:a.welcome.resumeToken});
  assert.equal(resumed.welcome.character.profession,2);
  const rejoined=await stateAfter(resumed,resumed.mark());assert.equal(player(rejoined,resumed.id).basicSlot.id,4);
});

test('source-shape collisions and world-space jumps are authoritative for both peers; airborne height never becomes a saved floor',async t=>{
  const profile={format:'oc2-scene-collision-v2',query:{forwardMargin:.31,stepProbeCap:.5,stepProbeMultiplier:3.5,wallNormalYThreshold:.5},
    sources:{wall:{shapes:[{kind:'box',center:[136.2,2,54],halfExtents:[.1,2,6],yawRadians:0,flags:2048}]}},
    instances:[{id:1,sourcePHY:'wall',position:[0,0,0],quaternion:[0,0,0,1],scale:[1,1,1]}]};
  const terrain={bounds:{min:[0,0,0],max:[192,0,192]},grid:{width:3,height:3,heights:Array(9).fill(0)}};
  const f=await fixture(t,{motion:createCollision(profile,terrain)}),a=await enter(f,'碰撞甲',{scene:'resources'}),b=await enter(f,'碰撞乙',{scene:'resources'});
  const before=await stateAfter(a,a.mark(),m=>m.players.length===2),start=player(before,a.id);
  assert.equal(start.worldY,0);assert(start.grounded);
  const interval=setInterval(()=>a.send({type:'input',x:1,y:0,worldY:99999}),50);
  try{await stateAfter(a,a.mark(),m=>m.tick>before.tick+12);}finally{clearInterval(interval);a.send({type:'input',x:0,y:0});}
  const blocked=await stateAfter(a,a.mark());assert(player(blocked,a.id).x>start.x);assert(player(blocked,a.id).x<start.x+6);
  const ma=a.mark(),mb=b.mark();a.send({type:'jump',pressed:true,worldY:99999,grounded:true});
  await stateAfter(a,ma,m=>player(m,a.id)?.jump);f.advance(300);
  const upA=await stateAfter(a,a.mark(),m=>player(m,a.id)?.worldY>1),upB=await stateAfter(b,mb,m=>m.tick===upA.tick);
  const airborne=player(upA,a.id);assert.deepEqual(airborne,player(upB,a.id));assert.equal(airborne.grounded,false);
  assert(Math.abs(airborne.worldY-1.494)<1e-5);
  const late=await enter(f,'碰撞旁观',{scene:'resources'});
  assert.deepEqual(player(await stateAfter(late,late.mark()),a.id),airborne);
  const saved=a.mark();a.send({type:'save'});await a.wait(m=>m.type==='notice'&&m.message.includes('保存'),{after:saved});
  const data=JSON.parse(await readFile(f.saveFile,'utf8')),record=data.characters.find(c=>c.id===a.id);
  assert.equal(record.positions.resources.groundY,0);assert(!JSON.stringify(record).includes('source-world-v1'));
  publicStateHasNoCredentials(b,[a.welcome.resumeToken,b.welcome.resumeToken]);
  const credentials={characterId:a.id,resumeToken:a.welcome.resumeToken};await f.stop();await f.start();
  const resumed=await enter(f,'碰撞甲',{scene:'resources',...credentials});
  const restored=player(await stateAfter(resumed,resumed.mark()),resumed.id);
  assert.equal(restored.worldY,0);assert(restored.grounded);assert.equal(restored.jump,null);assert.equal(restored.x,airborne.x);
});

test('normal press/release casts once per press and a lost release clears without auto attack',async t=>{
  const f=await fixture(t),a=await enter(f,'按压普攻'),target=wolf(await stateAfter(a,a.mark()));
  a.send({type:'attack-control',pressed:true,targetId:target.id});
  await stateAfter(a,a.mark(),m=>wolf(m).hp===40);
  f.advance(750);let mark=a.mark();a.send({type:'attack-control',pressed:true,targetId:target.id});
  assert.equal(wolf(await stateAfter(a,mark)).hp,40);
  a.send({type:'attack-control',pressed:false});a.send({type:'attack-control',pressed:true,targetId:target.id});
  await stateAfter(a,a.mark(),m=>wolf(m).hp===20);
  f.advance(4000);mark=a.mark();assert.equal(wolf(await stateAfter(a,mark)).hp,20);
  a.send({type:'attack-control',pressed:true,targetId:target.id});
  await stateAfter(a,a.mark(),m=>wolf(m).hp===0);
});

test('native chant/release/end and source cooldowns agree for two peers; forged stages and another player cannot cancel a cast',
 {skip:!existsSync(new URL('../../game-data/converted/gameplay/native.json',import.meta.url))},async t=>{
 const f=await fixture(t,{casting:true}),a=await enter(f,'施法状态甲',{scene:'resources'}),b=await enter(f,'施法状态乙',{scene:'resources'});
 assert.equal(a.welcome.combat.skills.fireball.castMs,1500);assert.equal(a.welcome.combat.skills.frost_blast.cooldownMs,20000);
 const target=wolf(await stateAfter(a,a.mark(),s=>s.players.length===2));await moveNear(a,target);
 let ma=a.mark(),mb=b.mark();a.send({type:'skill',skillId:'fireball',targetId:target.id,stage:2,chantTime:0,sourceSkillId:17});
 const first=await stateAfter(a,ma,s=>player(s,a.id)?.cast?.stage===1),other=await stateAfter(b,mb,s=>s.tick===first.tick);
 const c=player(first,a.id).cast;assert.equal(c.sourceSkillId,17);assert.equal(c.releaseAt-c.startedAt,1500);assert.deepEqual(player(other,a.id).cast,c);
 f.advance(1499);const waiting=await stateAfter(a,a.mark());assert.equal(player(waiting,a.id).cast.stage,1);assert.equal(wolf(waiting).hp,60);
 f.advance(1);const released=await stateAfter(a,a.mark(),s=>player(s,a.id)?.cast?.stage===2);assert.equal(player(released,a.id).cast.phaseAt,c.releaseAt);
 f.advance(350);await stateAfter(a,a.mark(),s=>wolf(s).hp===30);f.advance(250);
 const done=await stateAfter(a,a.mark(),s=>player(s,a.id)?.cast===null);assert.equal(player(done,a.id).lastCast.stage,6);
 ma=a.mark();a.send({type:'skill',skillId:'fireball',targetId:target.id});const repeat=await stateAfter(a,ma,s=>player(s,a.id)?.cast?.stage===1),active=player(repeat,a.id).cast;
 mb=b.mark();b.send({type:'cancel-skill',castId:active.id});await b.wait(m=>m.type==='notice',{after:mb});assert.equal(player(await stateAfter(a,a.mark()),a.id).cast.id,active.id);
 ma=a.mark();mb=b.mark();a.send({type:'cancel-skill',castId:active.id});
 const ca=await a.wait(m=>m.action==='skill-cancel'&&m.castId===active.id,{after:ma}),cb=await b.wait(m=>m.action==='skill-cancel'&&m.castId===active.id,{after:mb});assert.deepEqual(ca,cb);
 f.advance(333);ma=b.mark();b.send({type:'skill',skillId:'frost_blast',targetId:target.id});
 const ice=await b.wait(m=>m.action==='skill-cast'&&m.cast.skillId==='frost_blast',{after:ma});assert.equal(ice.cast.stage,2);assert.equal(ice.cast.sourceSkillId,94);assert.equal(ice.cast.releaseAt,ice.cast.startedAt);
 await stateAfter(b,b.mark(),s=>wolf(s).hp===10);f.advance(700);const back=await stateAfter(b,b.mark(),s=>player(s,b.id)?.cast===null);assert.equal(player(back,b.id).lastCast.phaseVisual.id,138);
 ma=b.mark();b.send({type:'skill',skillId:'frost_blast',targetId:target.id,cooldownMs:0});await b.wait(m=>m.type==='notice'&&m.message.includes('冷却'),{after:ma});
 publicStateHasNoCredentials(b,[a.welcome.resumeToken,b.welcome.resumeToken]);
});

test('moving source-shape gate blocks both peers, opens authoritatively, isolates rooms and keeps lab positions out of character saves',async t=>{
 const profile={format:'oc2-scene-collision-v2',query:{forwardMargin:.31,stepProbeCap:.5,stepProbeMultiplier:3.5,wallNormalYThreshold:.5},sources:{gate:{shapes:[{kind:'box',center:[0,2,0],halfExtents:[.2,2,1],yawRadians:0,flags:0}]}},instances:[],
  dynamicLab:{sourcePHY:'gate',sourceModel:'/assets/models/synthetic-gate.json',logicalPosition:[920,360],lift:9,transitionMs:800,interactDistance:4}};
 const terrain={bounds:{min:[0,0,0],max:[192,0,192]},grid:{width:3,height:3,heights:Array(9).fill(0)}};
 const f=await fixture(t,{motion:createCollision(profile,terrain)}),a=await enter(f,'门前甲',{scene:'resources',lab:'collision'}),b=await enter(f,'门后乙',{scene:'resources',lab:'collision'}),normal=await enter(f,'普通房间',{scene:'resources'});
 assert.equal((await stateAfter(normal,normal.mark())).objects.length,0);
 const start=await stateAfter(a,a.mark(),s=>s.players.length===2);assert.equal(start.objects[0].position[1],0);
 async function walkRight(until){const timer=setInterval(()=>a.send({type:'input',x:1,y:0}),50);try{return await stateAfter(a,a.mark(),until);}finally{clearInterval(timer);a.send({type:'input',x:0,y:0});}}
 const blocked=await walkRight(s=>s.tick>start.tick+18);assert(player(blocked,a.id).x<920);assert(player(blocked,a.id).x>915);
 let ma=a.mark(),mb=b.mark();a.send({type:'interact',targetId:'source-door'});await stateAfter(a,ma,s=>s.objects[0].transition);f.advance(800);
 const opened=await stateAfter(a,a.mark(),s=>s.objects[0].position[1]===9),observed=await stateAfter(b,mb,s=>s.tick===opened.tick);assert.deepEqual(opened.objects,observed.objects);
 const crossed=await walkRight(s=>player(s,a.id).x>925);assert(player(crossed,a.id).x>925);
 ma=a.mark();a.send({type:'save'});await a.wait(m=>m.type==='notice'&&m.message.includes('保存'),{after:ma});
 const data=JSON.parse(await readFile(f.saveFile,'utf8'));assert.deepEqual(data.characters.find(c=>c.id===a.id).positions,{});
 publicStateHasNoCredentials(b,[a.welcome.resumeToken,b.welcome.resumeToken]);
});

test('original player channel shares five source-timed pulses and late projectiles, enforces class/CD, and movement cancels remaining damage',
 {skip:!existsSync(new URL('../../game-data/converted/gameplay/native.json',import.meta.url))},async t=>{
 const f=await fixture(t,{casting:true}),a=await enter(f,'引导甲',{scene:'resources'}),b=await enter(f,'引导乙',{scene:'resources'});
 const target=wolf(await stateAfter(a,a.mark(),s=>s.players.length===2));await moveNear(a,target);
 let mark=a.mark();a.send({type:'skill',skillId:'arcane_missile',targetId:target.id,channelTime:0,damage:999});
 const start=await a.wait(m=>m.action==='skill-cast',{after:mark}),cast=start.cast;assert.equal(cast.sourceSkillId,90);assert.equal(cast.stage,3);assert.equal(cast.channelEndsAt-cast.startedAt,1500);
 f.advance(300);const pulse=await a.wait(m=>m.action==='skill-pulse',{after:mark}),peer=await b.wait(m=>m.action==='skill-pulse');assert.deepEqual(pulse,peer);assert.equal(pulse.cast.pulse,1);
 const late=await enter(f,'引导迟到',{scene:'resources'});const view=await stateAfter(late,late.mark(),s=>s.projectiles?.some(p=>p.cast.id===pulse.cast.id));assert.equal(player(view,a.id).cast.stage,3);
 f.advance(250);await stateAfter(a,a.mark(),s=>wolf(s).hp===52);
 f.advance(950);await stateAfter(a,a.mark(),s=>player(s,a.id).cast===null);f.advance(250);
 const done=await stateAfter(a,a.mark(),s=>wolf(s).hp===20);assert.equal(player(done,a.id).lastCast.phaseVisual.id,147);
 assert.equal(a.messages.filter(m=>m.action==='skill-pulse'&&m.cast.executionId===cast.id).length,5);
 assert.equal(a.messages.filter(m=>m.action==='skill-hit'&&m.skillId==='arcane_missile').length,5);
 mark=a.mark();a.send({type:'skill',skillId:'arcane_missile',targetId:target.id});await a.wait(m=>m.type==='notice'&&m.message.includes('冷却'),{after:mark});
 f.advance(2300);mark=a.mark();a.send({type:'skill',skillId:'arcane_missile',targetId:target.id});const next=await a.wait(m=>m.action==='skill-cast',{after:mark});
 a.send({type:'input',x:1,y:0});await a.wait(m=>m.action==='skill-cancel'&&m.castId===next.cast.id,{after:mark});a.send({type:'input',x:0,y:0});f.advance(2000);
 assert.equal(wolf(await stateAfter(a,a.mark())).hp,20);publicStateHasNoCredentials(late,[a.welcome.resumeToken]);
 // A delayed server tick may settle several outstanding impacts together.
 // Only one living-to-dead transition may award this channel's kill.
 f.advance(4000);mark=a.mark();a.send({type:'skill',skillId:'arcane_missile',targetId:target.id});await a.wait(m=>m.action==='skill-cast',{after:mark});f.advance(1750);
 await stateAfter(a,a.mark(),s=>wolf(s).hp===0);const reward=await a.wait(m=>m.type==='progress'&&m.character.kills>0,{after:mark});
 assert.equal(reward.character.gold,10);assert.equal(reward.character.xp,30);assert.equal(reward.character.kills,1);assert.equal(reward.character.inventory.wolfPelt,1);
 assert.equal(a.messages.filter(m=>m.action==='kill').length,1);
});

test('native burn/freeze and final damage agree for both peers and a late join; forged stats/buffs cannot alter authoritative results',
 {skip:!existsSync(new URL('../../game-data/converted/gameplay/native.json',import.meta.url))},async t=>{
 const f=await fixture(t,{casting:true}),a=await enter(f,'状态甲',{scene:'resources'}),b=await enter(f,'状态乙',{scene:'resources'});
 const target=wolf(await stateAfter(a,a.mark(),s=>s.players.length===2));await moveNear(a,target);
 let ma=a.mark();a.send({type:'skill',skillId:'fireball',targetId:target.id,damage:99999,buffs:[{kind:'burn',stacks:999}]});
 await a.wait(m=>m.action==='skill-cast',{after:ma});f.advance(1850);
 const burn=await stateAfter(a,a.mark(),s=>wolf(s).buffs?.some(b=>b.kind==='burn'));
 const peer=await stateAfter(b,b.mark(),s=>s.tick===burn.tick);assert.deepEqual(wolf(burn),wolf(peer));assert.equal(wolf(burn).hp,30);
 const late=await enter(f,'状态迟到',{scene:'resources'}),seen=await stateAfter(late,late.mark(),s=>wolf(s).buffs?.length===1);
 assert.deepEqual(wolf(seen).buffs,wolf(burn).buffs);assert.equal(wolf(seen).buffs[0].durationMs,7000);
 const forged=late.mark();late.send({type:'buff',kind:'freeze',targetId:target.id,durationMs:999999});await late.wait(m=>m.type==='error',{after:forged});
 ma=b.mark();b.send({type:'skill',skillId:'arcane_missile',targetId:target.id,damage:99999,bonus:9999});await b.wait(m=>m.action==='skill-cast',{after:ma});
 f.advance(550);const hit=await b.wait(m=>m.action==='skill-hit'&&m.skillId==='arcane_missile',{after:ma});
 assert.equal(hit.damage,12);assert.equal(hit.bonus,.5);assert.equal(hit.damageRule,'local-v2');assert.equal(hit.damageAttribute,16);
 const peerHit=await a.wait(m=>m.action==='skill-hit'&&m.castId===hit.castId);assert.deepEqual(hit,peerHit);
 // Stop channel, then verify one lethal hit clears the surviving burn.
 const current=player(await stateAfter(b,b.mark()),b.id).cast;b.send({type:'cancel-skill',castId:current.id});await b.wait(m=>m.action==='skill-cancel');
 ma=a.mark();a.send({type:'skill',skillId:'frost_blast',targetId:target.id});await a.wait(m=>m.action==='skill-cast',{after:ma});
 const death=await stateAfter(a,a.mark(),s=>!wolf(s).alive);assert.equal(wolf(death).hp,0);assert.deepEqual(wolf(death).buffs,[]);
 const rewards=await a.wait(m=>m.type==='progress'&&m.character.kills===1);assert.equal(rewards.character.gold,10);
 a.send({type:'save'});await a.wait(m=>m.type==='notice'&&m.message.includes('保存'));
 const disk=JSON.parse(await readFile(f.saveFile,'utf8'));assert(!JSON.stringify(disk).includes('buff:'));
 publicStateHasNoCredentials(late,[a.welcome.resumeToken,b.welcome.resumeToken]);
});

test('native freeze stops movement at both peers until expiry; server-owned overlapping player controls gate input/jump/attack/cast and clear on reconnect',
 {skip:!existsSync(new URL('../../game-data/converted/gameplay/native.json',import.meta.url))},async t=>{
 const f=await fixture(t,{casting:true}),a=await enter(f,'冻结甲',{scene:'resources'}),b=await enter(f,'冻结乙',{scene:'resources'});
 const initial=await stateAfter(a,a.mark(),s=>s.players.length===2),target=wolf(initial);
 let ma=a.mark();a.send({type:'skill',skillId:'frost_blast',targetId:target.id});
 const frozen=await stateAfter(a,ma,s=>wolf(s).buffs?.some(v=>v.kind==='freeze'));
 assert.equal(wolf(frozen).hp,40);assert.equal(wolf(frozen).buffs[0].durationMs,2000);assert.equal(wolf(frozen).slowUntil,0);
 f.advance(1999);const held=await stateAfter(a,a.mark()),peer=await stateAfter(b,b.mark(),s=>s.tick===held.tick);
 assert.deepEqual(wolf(held),wolf(peer));assert.equal(wolf(held).x,target.x);assert.equal(wolf(held).y,target.y);
 f.advance(1);const released=await stateAfter(a,a.mark(),s=>!wolf(s).buffs?.length);assert.notEqual(wolf(released).x,target.x);
 const room=[...f.game.combatRooms.values()][0],ws=[...room.clients.values()].find(ws=>ws.player.id===a.id),owner=[...room.clients.values()].find(ws=>ws.player.id===b.id);
 const now=released.serverTime;room.applyStatus(ws.player,'freeze',owner,now,{durationMs:2000});
 room.applyStatus(ws.player,'silence',owner,now,{durationMs:4000});
 const p=player(await stateAfter(a,a.mark()),a.id),jump=p.jump;
 ma=a.mark();a.send({type:'jump',pressed:true});a.send({type:'attack',targetId:target.id});a.send({type:'skill',skillId:'fireball',targetId:target.id});
 const timer=setInterval(()=>a.send({type:'input',x:1,y:0}),50);
 try {const still=await stateAfter(a,ma,s=>s.tick>released.tick+5);assert.equal(player(still,a.id).x,p.x);assert.deepEqual(player(still,a.id).jump,jump);}
 finally{clearInterval(timer);a.send({type:'input',x:0,y:0});a.send({type:'jump',pressed:false});}
 assert(a.messages.slice(ma).filter(m=>m.type==='notice'&&m.message.includes('控制')).length>=3);
 f.advance(2000);const silent=await stateAfter(a,a.mark(),s=>player(s,a.id).buffs.length===1);assert.equal(player(silent,a.id).controls.move,false);assert.equal(player(silent,a.id).controls.skill,true);
 a.send({type:'save'});await a.wait(m=>m.type==='notice'&&m.message.includes('保存'));
 const disk=JSON.parse(await readFile(f.saveFile,'utf8'));assert(!JSON.stringify(disk).includes('buff:'));
 const creds={characterId:a.id,resumeToken:a.welcome.resumeToken};await a.close();
 const resumed=await enter(f,'冻结甲',{scene:'resources',...creds});assert.deepEqual(player(await stateAfter(resumed,resumed.mark()),a.id).buffs,[]);
 publicStateHasNoCredentials(b,[creds.resumeToken]);
});

test('source-nav chase is shared by peers and late joins, then home-leash return rejects stale attacks and resets without rewards',
 {skip:!existsSync(new URL('../../game-data/converted/maps/navigation.json',import.meta.url))},async t=>{
 const f=await fixture(t,{casting:true,motion:loadCollision(),navigation:loadNavigation(),ai:true}),a=await enter(f,'导航甲',{scene:'resources'}),b=await enter(f,'导航乙',{scene:'resources'});
 await stateAfter(a,a.mark(),s=>s.players.length===2);
 const encounter=[...f.game.combatRooms.values()][0],ws=[...encounter.clients.values()].find(ws=>ws.player.id===a.id);
 assert(encounter.brain);encounter.monsterSpeed=140; // Fast test clock; production remains 14.
 Object.assign(ws.player,{x:850,y:450});encounter.motion.place(ws.player);
 const before=encounter.monster.hp;encounter.damageMonster(ws,1,Date.now());
 const chasing=await stateAfter(a,a.mark(),s=>wolf(s).ai?.state==='chasing');
 const peer=await stateAfter(b,b.mark(),s=>s.tick===chasing.tick);assert.deepEqual(wolf(peer),wolf(chasing));
 assert.equal(wolf(chasing).ai.targetId,a.id);assert.equal(wolf(chasing).ai.moveAction,2);assert(wolf(chasing).ai.routePoints>1);
 const late=await enter(f,'导航迟到',{scene:'resources'}),lateState=await stateAfter(late,late.mark(),s=>wolf(s).ai?.targetId===a.id);
 assert.equal(wolf(lateState).hp,before-1);assert.equal(wolf(lateState).ai.targetId,a.id);
 Object.assign(ws.player,{x:encounter.spawn.x+221,y:encounter.spawn.y});encounter.motion.place(ws.player);
 const returning=await stateAfter(a,a.mark(),s=>wolf(s).ai?.state==='returning');assert.equal(wolf(returning).ai.moveAction,3);
 const hp=wolf(returning).hp,mark=a.mark();a.send({type:'skill',skillId:'fireball',targetId:wolf(returning).id,ai:{state:'dead'},damage:999});
 await a.wait(m=>m.type==='notice'&&m.message.includes('脱战'),{after:mark});
 const reset=await stateAfter(a,a.mark(),s=>wolf(s).ai?.state==='idle');assert.equal(wolf(reset).hp,60);
 assert.equal(a.messages.filter(m=>m.action==='kill').length,0);assert.equal(ws.character.gold,0);assert.equal(hp,59);
 assert.equal(encounter.contributors.size,0);assert.equal(encounter.brain.threat.size,0);
 const resetPeer=await stateAfter(b,b.mark(),s=>wolf(s).ai?.state==='idle');assert.equal(wolf(resetPeer).hp,60);
 publicStateHasNoCredentials(late,[a.welcome.resumeToken,b.welcome.resumeToken]);
});
