// Read-only validation of every served source file and lossless compressed sidecar.
import {readFile} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {Writable} from 'node:stream';
import {pipeline} from 'node:stream/promises';
import {createBrotliDecompress,createGunzip} from 'node:zlib';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url)),index=JSON.parse(await readFile(resolve(root,'analysis/raw/delivery/index.json'),'utf8'));
async function verify(path,expected,encoding){
  const hash=createHash('sha256');let bytes=0;
  const sink=new Writable({write(chunk,_,done){hash.update(chunk);bytes+=chunk.length;done();}});
  const streams=[createReadStream(path)];if(encoding)streams.push(encoding==='br'?createBrotliDecompress():createGunzip());streams.push(sink);await pipeline(...streams);
  if(bytes!==expected.bytes||hash.digest('hex')!==expected.sha256)throw Error('Delivery bytes differ: '+path);
}
let sources=0,sidecars=0;const checked=new Set();
for(const meta of Object.values(index.files)){
  await verify(meta.path,meta);sources++;
  for(const [encoding,variant]of Object.entries(meta.encodings||{}))if(!checked.has(variant.path)){await verify(variant.path,meta,encoding);checked.add(variant.path);sidecars++;}
}
console.log(JSON.stringify({sourceFiles:sources,losslessSidecars:sidecars,allContentHashesMatch:true,revision:index.revision}));
