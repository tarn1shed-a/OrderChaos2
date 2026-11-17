// Host file integrity only. A receipt never means native/body/library ready.
// Cache metadata, not resource bytes or parsed model/animation documents.
import {constants,openSync,closeSync,fstatSync,readSync,realpathSync} from 'node:fs';
import {isAbsolute,relative,resolve,sep} from 'node:path';
import {createHash} from 'node:crypto';

const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const inside=(root,path)=>{const value=relative(root,path);return value!==''&&!isAbsolute(value)&&value!=='..'&&!value.startsWith('..'+sep);};
const stamp=stat=>[stat.dev,stat.ino,stat.mode,stat.size,stat.mtimeNs,stat.ctimeNs].join(':');

export function createPinnedResourceReader({roots}){
  if(!Array.isArray(roots)||!roots.length||roots.some(root=>typeof root!=='string'||!isAbsolute(root)))throw Error('Explicit absolute resource roots required');
  const declared=roots.map(root=>resolve(root));
  const allowed=[...new Set(declared.map(root=>realpathSync(root)))],cache=new Map();
  const scratch=Buffer.allocUnsafe(65536);
  let filesHashed=0,bytesHashed=0,cacheHits=0;
  function opened(pin){
    if(!pin||typeof pin.path!=='string'||!isAbsolute(pin.path)||!Number.isSafeInteger(pin.bytes)||pin.bytes<0||! /^[a-f0-9]{64}$/.test(pin.sha256))throw Error('Exact resource path/byte/SHA pin required');
    const lexical=resolve(pin.path);
    if(![...declared,...allowed].some(root=>inside(root,lexical)))throw Error('Resource path outside allowed roots');
    const path=realpathSync(lexical);
    if(!allowed.some(root=>inside(root,path)))throw Error('Resource target outside allowed roots');
    const fd=openSync(path,constants.O_RDONLY|(constants.O_NOFOLLOW||0));
    try{
      const stat=fstatSync(fd,{bigint:true});
      if(!stat.isFile()||stat.size!==BigInt(pin.bytes))throw Error('Resource byte size differs');
      return {fd,path,before:stamp(stat),key:JSON.stringify([path,pin.bytes,pin.sha256])};
    }catch(error){closeSync(fd);throw error;}
  }
  function unchanged(file){if(stamp(fstatSync(file.fd,{bigint:true}))!==file.before)throw Error('Resource changed during verification');}
  function remember(file,pin){
    unchanged(file);
    const receipt=Object.freeze({path:file.path,bytes:pin.bytes,sha256:pin.sha256});
    cache.set(file.key,{stamp:file.before,receipt});return receipt;
  }
  function verify(pin){
    const file=opened(pin);
    try{
      const old=cache.get(file.key);
      if(old?.stamp===file.before){unchanged(file);cacheHits++;return old.receipt;}
      const sha=createHash('sha256');let count=0,length;
      while((length=readSync(file.fd,scratch,0,scratch.length,null))!==0){sha.update(scratch.subarray(0,length));count+=length;}
      filesHashed++;bytesHashed+=count;
      if(count!==pin.bytes||sha.digest('hex')!==pin.sha256)throw Error('Resource SHA differs');
      return remember(file,pin);
    }finally{closeSync(file.fd);}
  }
  function readBytes(pin){
    const file=opened(pin);
    try{
      // Match the old plain Uint8Array's complete ownership contract, including
      // offset zero and an exact-sized ArrayBuffer, without a Buffer/slab copy.
      const bytes=new Uint8Array(pin.bytes);let offset=0;
      while(offset<bytes.length){
        const count=readSync(file.fd,bytes,offset,Math.min(scratch.length,bytes.length-offset),null);
        if(count===0)throw Error('Resource ended before pinned byte size');offset+=count;
      }
      filesHashed++;bytesHashed+=offset;
      if(hash(bytes)!==pin.sha256)throw Error('Resource SHA differs');
      remember(file,pin);return bytes;
    }finally{closeSync(file.fd);}
  }
  return Object.freeze({verify,readBytes,
    readJSON(pin){const b=readBytes(pin);return JSON.parse(Buffer.from(b.buffer,b.byteOffset,b.byteLength).toString('utf8'));},
    clear(){cache.clear();},
    inspect:()=>Object.freeze({entries:cache.size,filesHashed,bytesHashed,cacheHits,scratchBytes:scratch.length,rawBytesCached:false,parsedJSONCached:false}),
  });
}
