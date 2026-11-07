import test from 'node:test';
import assert from 'node:assert/strict';
import {encodeCharacterRecovery,decodeCharacterRecovery} from '../public/character-recovery.js';
test('recovery codes round-trip existing credentials with a Unicode name without using URLs',()=>{
  const character={id:'12345678-1234-1234-1234-123456789abc',name:'林间旅人'},token='a'.repeat(64);
  const code=encodeCharacterRecovery(character,token),restored=decodeCharacterRecovery('  '+code+'  ');
  assert(code.startsWith('OC2-'));assert(!code.includes('http'));
  assert.deepEqual(restored,{version:1,name:character.name,characterId:character.id,resumeToken:token});
});
test('truncated, oversized and malformed recovery codes fail without changing a browser slot',()=>{
  for(const code of ['',null,'OC2-!', 'OC2-'+ 'a'.repeat(1100), 'OC2-'+btoa('{"version":1}'),'https://example.com/#token']){
    assert.throws(()=>decodeCharacterRecovery(code),/恢复码无效/);
  }
  assert.throws(()=>encodeCharacterRecovery({id:'bad',name:'旅人'},'bad'),/凭据不可用/);
});
