import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync,symlinkSync,renameSync,statSync,utimesSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {createPinnedResourceReader} from './source_resource_reader.mjs';

const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
function fixture(t){
  const base=mkdtempSync(join(tmpdir(),'oc2-resource-reader-')),root=join(base,'root');mkdirSync(root);
  t.after(()=>rmSync(base,{recursive:true,force:true}));
  const reader=createPinnedResourceReader({roots:[root]});
  function file(name,bytes){const path=join(root,name);writeFileSync(path,bytes);return{path,bytes:Buffer.byteLength(bytes),sha256:digest(bytes)};}
  return{base,root,reader,file};
}

test('streamed SHA equals original whole-file check across many chunks and caches only receipts',t=>{
  const{reader,file}=fixture(t),data=Buffer.alloc(65536*4+73);for(let i=0;i<data.length;i++)data[i]=i%251;
  const pin=file('many.bin',data),old=readFileSync(pin.path);assert.equal(digest(old),pin.sha256);
  const a=reader.verify(pin),b=reader.verify({...pin});assert.equal(a,b);assert.ok(Object.isFrozen(a));
  assert.deepEqual(reader.inspect(),{entries:1,filesHashed:1,bytesHashed:data.length,cacheHits:1,scratchBytes:65536,rawBytesCached:false,parsedJSONCached:false});
});
test('zero-byte file follows the same exact SHA contract',t=>{const{reader,file}=fixture(t);reader.verify(file('empty',''));assert.equal(reader.inspect().bytesHashed,0);});
test('wrong byte count/SHA rejects despite an earlier successful receipt',t=>{
  const{reader,file}=fixture(t),pin=file('one','original');reader.verify(pin);
  assert.throws(()=>reader.verify({...pin,bytes:pin.bytes+1}),/size/);
  assert.throws(()=>reader.verify({...pin,sha256:'0'.repeat(64)}),/SHA/);assert.equal(reader.inspect().entries,1);
});
test('same length changed contents invalidate cached receipt even if mtime restored',t=>{
  const{reader,file}=fixture(t),pin=file('mutated','first-value'),old=statSync(pin.path);reader.verify(pin);
  writeFileSync(pin.path,'other-value');utimesSync(pin.path,old.atime,old.mtime);
  assert.throws(()=>reader.verify(pin),/SHA/);assert.equal(reader.inspect().cacheHits,0);
});
test('file replacement with same name/size rejects old pin and accepts only new exact bytes',t=>{
  const{reader,file}=fixture(t),old=file('replaced','before'),newer=file('new','after!');reader.verify(old);renameSync(newer.path,old.path);
  assert.throws(()=>reader.verify(old),/SHA/);reader.verify({...newer,path:old.path});
});
test('two real paths sharing a SHA are independently verified',t=>{
  const{reader,file}=fixture(t),a=file('a','identical'),b=file('b','identical');reader.verify(a);reader.verify(b);
  assert.equal(reader.inspect().filesHashed,2);assert.equal(reader.inspect().entries,2);
});
test('canonical same-root symlink alias shares receipt without weakening target-root guard',t=>{
  const{reader,file,root}=fixture(t),pin=file('real','pinned');symlinkSync(pin.path,join(root,'alias'));
  assert.equal(reader.verify(pin),reader.verify({...pin,path:join(root,'alias')}));assert.equal(reader.inspect().cacheHits,1);
});
test('outside path, sibling-prefix root and escaping symlink reject',t=>{
  const{reader,base,root,file}=fixture(t),pin=file('safe','safe');const outside=join(base,'root-other');mkdirSync(outside);const path=join(outside,'same');writeFileSync(path,'safe');
  assert.throws(()=>reader.verify({...pin,path}),/outside/);
  assert.throws(()=>reader.verify({...pin,path:resolve(root,'../root-other/same')}),/outside/);
  symlinkSync(path,join(root,'escape'));assert.throws(()=>reader.verify({...pin,path:join(root,'escape')}),/outside/);
});
test('invalid pin/missing file/directory do not become verified entries',t=>{
  const{reader,root,file}=fixture(t),pin=file('safe','safe');
  for(const wrong of [{...pin,path:'relative'},{...pin,bytes:-1},{...pin,bytes:1.5},{...pin,sha256:'xyz'}])assert.throws(()=>reader.verify(wrong),/pin/);
  assert.throws(()=>reader.verify({...pin,path:join(root,'missing')}),/ENOENT/);
  assert.throws(()=>reader.verify({...pin,path:root}));assert.equal(reader.inspect().entries,0);
});
test('readBytes returns plain Uint8Array with copying slice and no cached backing bytes',t=>{
  const{reader,file}=fixture(t),pin=file('data','original'),a=reader.readBytes(pin);assert.ok(a instanceof Uint8Array);assert.equal(Buffer.isBuffer(a),false);
  const copy=a.slice();a.fill(0);assert.equal(new TextDecoder().decode(copy),'original');
  const b=reader.readBytes(pin);assert.equal(new TextDecoder().decode(b),'original');assert.notEqual(a,b);reader.verify(pin);assert.equal(reader.inspect().rawBytesCached,false);
});
test('small readBytes files own the complete exact-sized ArrayBuffer without slab offsets',t=>{
  const{reader,file}=fixture(t);
  for(const size of[1,7,255,4095]){
    const raw=Buffer.alloc(size,37),bytes=reader.readBytes(file('small-'+size,raw));
    assert.equal(Object.getPrototypeOf(bytes),Uint8Array.prototype);assert.equal(bytes.byteOffset,0);
    assert.equal(bytes.buffer.byteLength,size);assert.equal(bytes.byteLength,size);assert.equal(digest(new Uint8Array(bytes.buffer)),digest(raw));
  }
});
test('empty readBytes has its own zero-byte ArrayBuffer and remains a plain Uint8Array',t=>{
  const{reader,file}=fixture(t),pin=file('zero',''),a=reader.readBytes(pin),b=reader.readBytes(pin);
  assert.equal(Object.getPrototypeOf(a),Uint8Array.prototype);assert.equal(a.byteOffset,0);assert.equal(a.buffer.byteLength,0);assert.equal(a.byteLength,0);assert.notEqual(a.buffer,b.buffer);
});
test('large multi-read readBytes has exact owned storage and preserves every original byte',t=>{
  const{reader,file}=fixture(t),raw=Buffer.alloc(65536*3+31);for(let i=0;i<raw.length;i++)raw[i]=i%251;
  const pin=file('large',raw),bytes=reader.readBytes(pin);
  assert.equal(Object.getPrototypeOf(bytes),Uint8Array.prototype);assert.equal(bytes.byteOffset,0);
  assert.equal(bytes.buffer.byteLength,pin.bytes);assert.equal(bytes.byteLength,pin.bytes);assert.equal(digest(new Uint8Array(bytes.buffer)),pin.sha256);
  assert.deepEqual(Array.from(bytes),Array.from(raw));
});
test('readJSON returns actual independently owned data and rejects wrong source digest',t=>{
  const{reader,file}=fixture(t),pin=file('metadata.json','{"values":[1,2],"ok":true}');const a=reader.readJSON(pin);a.values[0]=99;
  assert.deepEqual(reader.readJSON(pin),{values:[1,2],ok:true});assert.throws(()=>reader.readJSON({...pin,sha256:'f'.repeat(64)}),/SHA/);
});
test('clearing metadata cache forces rehash and neither closes a file nor creates ready capability',t=>{
  const{reader,file}=fixture(t),pin=file('a','one');reader.verify(pin);reader.clear();reader.verify(pin);
  assert.equal(reader.inspect().filesHashed,2);assert.equal(reader.inspect().cacheHits,0);assert.deepEqual(Object.keys(reader.verify(pin)).sort(),['bytes','path','sha256']);
});
