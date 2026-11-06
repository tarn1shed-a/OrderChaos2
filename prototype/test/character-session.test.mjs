import test from 'node:test';
import assert from 'node:assert/strict';
import { restoreCredentials, rememberCharacter, lastCharacterName, characterSessionWarning } from '../public/character-session.js';

function storage(initial = null) {
  let raw = initial;
  return { getItem: () => raw, setItem: (key,value) => { raw=value; }, value: () => raw };
}

test('distinct named character slots restore distinct server credentials', () => {
  const local = storage();globalThis.localStorage=local;
  assert.deepEqual(restoreCredentials('新角色'),{});
  assert.equal(rememberCharacter({id:'id-a',name:'旅人甲'},'token-a'),true);
  assert.equal(rememberCharacter({id:'id-b',name:'旅人乙'},'token-b'),true);
  assert.deepEqual(restoreCredentials('旅人甲'),{characterId:'id-a',resumeToken:'token-a'});
  assert.deepEqual(restoreCredentials(' 旅人乙 '),{characterId:'id-b',resumeToken:'token-b'});
  assert.equal(lastCharacterName(),'旅人乙');
  assert.equal(local.value().includes('http'),false);
  assert.equal(characterSessionWarning(),'');
});

test('prototype-shaped names behave as ordinary character slot names', () => {
  globalThis.localStorage=storage();
  for(const name of ['__proto__','constructor','toString']){
    assert.equal(rememberCharacter({id:'id-'+name,name},'token-'+name),true);
    assert.deepEqual(restoreCredentials(name),{characterId:'id-'+name,resumeToken:'token-'+name});
  }
  assert.equal(Object.prototype.id,undefined);
});

test('malformed local storage never crashes or silently overwrites recovery data', () => {
  for(const raw of ['{broken','null','{"characters":null}','{"characters":[]}']){
    const local=storage(raw);globalThis.localStorage=local;
    assert.deepEqual(restoreCredentials('旅人'),{});
    assert.equal(lastCharacterName(),'');
    assert.equal(rememberCharacter({id:'id',name:'旅人'},'token'),false);
    assert.equal(local.value(),raw);
    assert.notEqual(characterSessionWarning(),'');
  }
});

test('unavailable storage reports recovery limitation while leaving the game usable', () => {
  globalThis.localStorage={getItem(){throw new Error('Storage denied');},setItem(){throw new Error('Storage denied');}};
  assert.deepEqual(restoreCredentials('旅人'),{});
  assert.equal(rememberCharacter({id:'id',name:'旅人'},'token'),false);
  assert.notEqual(characterSessionWarning(),'');
  delete globalThis.localStorage;
});
