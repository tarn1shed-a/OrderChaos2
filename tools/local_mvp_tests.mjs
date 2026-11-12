import assert from 'node:assert/strict';
import {test} from 'node:test';
import {inspectRuntime,startLocalMvp,ROOT} from './local_mvp.mjs';
import {resolve} from 'node:path';

test('MVP refuses runtime outside ignored research directory',()=>{
 assert.throws(()=>inspectRuntime(ROOT),/忽略目录/);
});
test('Missing private runtime fails explicitly without starting a replacement',()=>{
 assert.throws(()=>inspectRuntime(resolve(ROOT,'analysis/raw/nonexistent-mvp-inputs')),/缺失或有未核对改动/);
});
test('Invalid port fails before runtime or save access',async()=>{
 for(const port of [-1,65536,3.2,NaN])await assert.rejects(startLocalMvp({port}),/端口/);
});
test('Capacity is configurable without a two-player minimum',async()=>{
 for(const maxPlayers of [0,33,1.5,NaN])await assert.rejects(startLocalMvp({maxPlayers}),/人数上限/);
});
test('Existing main and historical save directories cannot be selected',async()=>{
 for(const dataDir of [resolve(ROOT,'runtime'),resolve(ROOT,'game-data'),ROOT])
  await assert.rejects(startLocalMvp({dataDir}),/独立 runtime/);
});
