import test from 'node:test';
import assert from 'node:assert/strict';
import { once } from 'node:events';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import WebSocket from 'ws';
import { CharacterStore } from '../game/character-store.mjs';
import { createGameServer } from '../server.mjs';

function message(ws, predicate) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { ws.off('message', read); reject(new Error('Message timeout')); }, 3000);
    const read = raw => {
      const msg = JSON.parse(raw);
      if (predicate(msg)) { clearTimeout(timer); ws.off('message', read); resolve(msg); }
    };
    ws.on('message', read);
  });
}

test('store keeps opaque credentials hashed and preserves corrupt saves', t => {
  const dir = mkdtempSync(join(tmpdir(), 'oc2-store-integrity-')); t.after(() => rmSync(dir, { recursive: true, force: true }));
  const file = join(dir, 'characters.json');
  const identity = new CharacterStore(file).resolveCharacter('旅人');
  assert(!readFileSync(file, 'utf8').includes(identity.resumeToken));
  const resumed = new CharacterStore(file).resolveCharacter('改名不能篡改存档', identity.record.id, identity.resumeToken);
  assert.equal(resumed.record.name, '旅人'); assert.equal(resumed.restored, true);
  assert.throws(() => new CharacterStore(file).resolveCharacter('旅人', identity.record.id, '0'.repeat(64)), /不匹配/);
  writeFileSync(file, 'broken save');
  assert.throws(() => new CharacterStore(file), /无法读取/);
  assert.equal(readFileSync(file, 'utf8'), 'broken save');
});

test('failed final save still closes sockets/server and repeated close is idempotent', async t => {
  const dir = mkdtempSync(join(tmpdir(), 'oc2-shutdown-failure-')); t.after(() => rmSync(dir, { recursive: true, force: true }));
  const saveDir = join(dir, 'saves'), saveFile = join(saveDir, 'characters.json');
  const game = createGameServer({ saveFile });
  // Failures before our explicit close must still clean up the listener.
  t.after(async () => { try { await game.close(); } catch {} });
  game.server.listen(0, '127.0.0.1'); await once(game.server, 'listening');
  const ws = new WebSocket(`ws://127.0.0.1:${game.server.address().port}/ws`);
  await once(ws, 'open');
  const joined = message(ws, m => m.type === 'welcome');
  ws.send(JSON.stringify({ type: 'join', name: '关机存档测试', room: 'SAVE-01' })); await joined;
  const moved = message(ws, m => m.type === 'state' && m.players[0].x > 640);
  ws.send(JSON.stringify({ type: 'input', x: 1, y: 0 })); await moved;
  // Replacing a directory with a regular file deterministically blocks atomic writes even as root.
  rmSync(saveDir, { recursive: true }); writeFileSync(saveDir, 'blocked');
  const disconnected = once(ws, 'close');
  const closing = game.close();
  assert.equal(game.close(), closing);
  await assert.rejects(closing, /存档写入失败|EEXIST|ENOTDIR/);
  await disconnected;
  assert.equal(game.server.listening, false);
  await assert.rejects(game.close(), /存档写入失败|EEXIST|ENOTDIR/);
});
