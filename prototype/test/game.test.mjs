import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import WebSocket from 'ws';
import { createGameServer } from '../server.mjs';
import { WORLD, advance, walkable } from '../public/world.js';
import { sampleHeight } from '../public/heightfield.js';

function next(ws, predicate) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { ws.off('message', onMessage); reject(new Error('Timed out waiting for game message')); }, 3000);
    function onMessage(raw) {
      const data = JSON.parse(raw);
      if (predicate(data)) { clearTimeout(timer); ws.off('message', onMessage); resolve(data); }
    }
    ws.on('message', onMessage);
  });
}
const send = (ws, msg) => ws.send(JSON.stringify(msg));

test('two real sockets share authoritative movement, isolate rooms, and clean up departures', async t => {
  const game = createGameServer();
  game.server.listen(0, '127.0.0.1'); await once(game.server, 'listening');
  t.after(() => game.close());
  const address = `ws://127.0.0.1:${game.server.address().port}/ws`;
  async function join(name, room = 'CAMP-01') {
    const ws = new WebSocket(address); await once(ws, 'open');
    const welcome = next(ws, m => m.type === 'welcome'); send(ws, { type: 'join', name, room });
    return { ws, id: (await welcome).id };
  }
  const a = await join('旅人甲'), b = await join('旅人乙'), c = await join('隔壁营地', 'OTHER-01');
  const initial = await next(b.ws, m => m.type === 'state' && m.players.length === 2);
  const x0 = initial.players.find(p => p.id === a.id).x;
  assert.equal((await next(c.ws, m => m.type === 'state')).players.length, 1);
  const moving = next(b.ws, m => m.type === 'state' && m.players.find(p => p.id === a.id)?.x > x0 + 25);
  const input = setInterval(() => send(a.ws, { type: 'input', x: 1, y: 0 }), 50);
  send(a.ws, { type: 'input', x: 1, y: 0 });
  const observed = await moving; clearInterval(input);
  assert(observed.players.find(p => p.id === a.id).x <= x0 + WORLD.speed * .4);
  send(a.ws, { type: 'input', x: 0, y: 0 });
  const frameA = await next(a.ws, m => m.type === 'state');
  const frameB = await next(b.ws, m => m.type === 'state' && m.tick > frameA.tick);
  assert.deepEqual(frameA.players, frameB.players);
  const departure = next(a.ws, m => m.type === 'state' && m.players.length === 1);
  b.ws.close(); await departure;
  const rejected = next(a.ws, m => m.type === 'error');
  send(a.ws, { type: 'input', x: 999, y: 0 });
  assert.match((await rejected).message, /无效/);
  c.ws.close();
});

test('movement is speed limited diagonally, stops at geometry, and stays inside map', () => {
  const p = { x: 640, y: 560 };
  advance(p, { x: 1, y: 1 }, .05);
  assert(Math.abs(Math.hypot(p.x - 640, p.y - 560) - WORLD.speed * .05) < 1e-9);
  const wall = { x: 640, y: 560 };
  for (let i = 0; i < 100; i++) advance(wall, { x: 0, y: -1 }, .05);
  assert(wall.y >= 405 + 52 + WORLD.radius); assert(walkable(wall.x, wall.y));
  const edge = { x: 100, y: 500 };
  for (let i = 0; i < 500; i++) advance(edge, { x: -1, y: 0 }, .05);
  assert(edge.x >= WORLD.radius);
});

test('server ignores stalled input after lease expires', async t => {
  const game = createGameServer(); game.server.listen(0, '127.0.0.1'); await once(game.server, 'listening'); t.after(() => game.close());
  const ws = new WebSocket(`ws://127.0.0.1:${game.server.address().port}/ws`); await once(ws, 'open');
  const welcome = next(ws, m => m.type === 'welcome'); send(ws, { type: 'join', name: '断线测试', room: 'CAMP-02' }); await welcome;
  const start = await next(ws, m => m.type === 'state');
  send(ws, { type: 'input', x: -1, y: 0 });
  const after = await next(ws, m => m.type === 'state' && m.tick >= start.tick + 12);
  const later = await next(ws, m => m.type === 'state' && m.tick >= after.tick + 5);
  assert(after.players[0].x < start.players[0].x);
  assert.equal(later.players[0].x, after.players[0].x);
});

test('room capacity rejects ninth player, malformed messages are contained, assets serve', async t => {
  const game = createGameServer(); game.server.listen(0, '127.0.0.1'); await once(game.server, 'listening'); t.after(() => game.close());
  const port = game.server.address().port;
  assert.equal((await fetch(`http://127.0.0.1:${port}/`)).status, 200);
  assert.equal((await fetch(`http://127.0.0.1:${port}/client.js`)).status, 200);
  for (let i = 0; i < 8; i++) {
    const ws = new WebSocket(`ws://127.0.0.1:${port}/ws`); await once(ws, 'open');
    const welcome = next(ws, m => m.type === 'welcome'); send(ws, { type: 'join', name: `玩家${i}`, room: 'FULL-01' }); await welcome;
  }
  const ninth = new WebSocket(`ws://127.0.0.1:${port}/ws`); await once(ninth, 'open');
  const full = next(ninth, m => m.type === 'error'); send(ninth, { type: 'join', name: '第九位', room: 'FULL-01' }); assert.match((await full).message, /已满/);
  const invalid = new WebSocket(`ws://127.0.0.1:${port}/ws`); await once(invalid, 'open');
  const error = next(invalid, m => m.type === 'error'); invalid.send('{bad'); assert.match((await error).message, /格式/);
});

test('resource scene shares movement but is isolated from camp even with the same room code', async t => {
  const game = createGameServer(); game.server.listen(0, '127.0.0.1'); await once(game.server, 'listening'); t.after(() => game.close());
  const url = `ws://127.0.0.1:${game.server.address().port}/ws`;
  async function join(name, scene) {
    const ws = new WebSocket(url); await once(ws, 'open'); const welcome = next(ws, m => m.type === 'welcome');
    send(ws, { type: 'join', name, room: 'SAME-01', scene }); return { ws, welcome: await welcome };
  }
  const a = await join('三维甲', 'resources'), b = await join('三维乙', 'resources'), camp = await join('营地', 'camp');
  assert.equal(a.welcome.scene, 'resources'); assert.equal(a.welcome.world.obstacles.length, 0);
  assert.equal((await next(camp.ws, m => m.type === 'state')).players.length, 1);
  const initial = await next(b.ws, m => m.type === 'state' && m.players.length === 2);
  const x = initial.players.find(p => p.id === a.welcome.id).x;
  const movement = next(b.ws, m => m.type === 'state' && m.players.some(p => p.id === a.welcome.id && p.x > x));
  send(a.ws, { type: 'input', x: 1, y: 0 }); await movement;
  const departure = next(b.ws, m => m.type === 'state' && m.players.length === 1);
  a.ws.close(); await departure;
  await join('新加入', 'resources');
  const rejoined = await next(b.ws, m => m.type === 'state' && m.players.length === 2);
  assert.notEqual(rejoined.players[0].x, rejoined.players[1].x, 'Reused spawn slots must not overlap remaining players');
});

test('height follows the exported terrain triangles rather than a bilinear surface', () => {
  const grid = { width: 2, depth: 2, values: [0, 0, 0, 10] };
  assert.equal(sampleHeight(grid, .25, .25), 0);
  assert.equal(sampleHeight(grid, .75, .75), 5);
  assert.equal(sampleHeight(grid, 1, 0), 0);
});
