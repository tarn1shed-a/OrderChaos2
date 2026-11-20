import test from'node:test';
import assert from'node:assert/strict';
import {sourceWorldBodies,SOURCE_WORLD_BODY_KEYS}from'./source_world_bodies.mjs';
test('existing opt-in retains only its reviewed HumanF body by default',()=>assert.deepEqual(sourceWorldBodies(true),['human-female']));
test('one explicit operator list drives all nine bodies without broadening its default',()=>assert.deepEqual(sourceWorldBodies(true,SOURCE_WORLD_BODY_KEYS.join(',')),SOURCE_WORLD_BODY_KEYS));
test('disabled world does not load or enable an operator body list',()=>assert.deepEqual(sourceWorldBodies(false,SOURCE_WORLD_BODY_KEYS.join(',')),[]));
test('invalid and duplicate body choices fail before a runtime or page is built',()=>{for(const value of['','*','elf-female,elf-female','human-female,unknown',{},null])assert.throws(()=>sourceWorldBodies(true,value));});
