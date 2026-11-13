import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {resolve} from 'node:path';
import {brotliDecompressSync,gunzipSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import {prepare} from '../deploy/prepare_delivery.mjs';
import {installDelivery,encoding} from '../deploy/static_delivery.mjs';

let root,server,port,index;const sha=b=>createHash('sha256').update(b).digest('hex');
const body=Buffer.from(JSON.stringify({positions:Array.from({length:10000},(_,i)=>i%37)}));
async function request(path,headers={},method='GET'){
  return new Promise((ok,fail)=>{const req=http.request({hostname:'127.0.0.1',port,path,headers,method},res=>{const chunks=[];res.on('data',b=>chunks.push(b));res.on('end',()=>ok({status:res.statusCode,headers:res.headers,body:Buffer.concat(chunks)}));});req.on('error',fail);req.end();});
}
before(async()=>{
  root=await mkdtemp(resolve(tmpdir(),'oc2-delivery-'));
  const runtime=resolve(root,'analysis/raw/portable/running-preview');
  const files={
    'prototype/public/explore-map.html':Buffer.from('<html><script type="module" src="/explore-map.js?original=1"></script><body class="original">unchanged UI</body></html>'),
    'prototype/public/explore-map.js':Buffer.from("import './helper.js'; fetch('/assets/map.json');"),
    'prototype/public/helper.js':Buffer.from('export const original = true;'),
    'game-data/converted/map.json':body,
    'game-data/converted/same.json':body,
    'game-data/converted/image.png':Buffer.from([137,80,78,71,0,255,15]),
  },manifest={files:{}};
  for(const [name,bytes]of Object.entries(files)){const path=resolve(runtime,name);await mkdir(resolve(path,'..'),{recursive:true});await writeFile(path,bytes);manifest.files[name]={bytes:bytes.length,sha256:sha(bytes)};}
  await writeFile(resolve(runtime,'bundle-manifest.json'),JSON.stringify(manifest));
  await mkdir(resolve(root,'deploy/node_modules/three/build'),{recursive:true});
  for(const name of ['three.module.js','three.core.js'])await writeFile(resolve(root,'deploy/node_modules/three/build',name),'export const test = 1;');
  for(const name of ['delivery_boot.mjs','delivery_worker.mjs','retired_ui.css'])await writeFile(resolve(root,'deploy',name),'/* deployment fixture */');
  index=await prepare(root);
  server=http.createServer((req,res)=>{res.writeHead(req.url==='/health'?200:404,{'Cache-Control':'no-store'});res.end(req.url==='/health'?'original health':'missing');});
  await installDelivery(server,root);await new Promise(ok=>server.listen(0,'127.0.0.1',ok));port=server.address().port;
});
after(async()=>{if(server)await new Promise(ok=>server.close(ok));if(root)await rm(root,{recursive:true,force:true});});

test('Brotli and gzip decode to the exact original model bytes',async()=>{
  for(const name of ['br','gzip']){const response=await request('/assets/map.json',{'Accept-Encoding':name});assert.equal(response.status,200);assert.equal(response.headers['content-encoding'],name);assert.deepEqual(name==='br'?brotliDecompressSync(response.body):gunzipSync(response.body),body);assert(response.body.length<body.length*.2);assert.equal(response.headers['x-oc2-content-sha256'],sha(body));}
});
test('identity, HEAD and query URLs preserve original bytes and length',async()=>{
  const normal=await request('/assets/map.json?unchanged=1');assert.deepEqual(normal.body,body);assert.equal(normal.headers['content-encoding'],undefined);
  const head=await request('/assets/map.json',{},'HEAD');assert.equal(head.body.length,0);assert.equal(Number(head.headers['content-length']),body.length);
});
test('unchanged files revalidate with 304; stale validators get current bytes',async()=>{
  const first=await request('/assets/map.json',{'Accept-Encoding':'br'});
  const cached=await request('/assets/map.json',{'Accept-Encoding':'br','If-None-Match':'W/'+first.headers.etag});assert.equal(cached.status,304);assert.equal(cached.body.length,0);
  const stale=await request('/assets/map.json',{'If-None-Match':'"old-content"'});assert.equal(stale.status,200);assert.deepEqual(stale.body,body);assert.equal(first.headers.vary,'Accept-Encoding');
});
test('negotiation respects disabled encodings and emits 406 when none is allowed',async()=>{
  assert.equal(encoding('br;q=0,gzip;q=1',{br:{},gzip:{}}),'gzip');assert.equal(encoding('*;q=0',{}),null);
  assert.equal((await request('/assets/map.json',{'Accept-Encoding':'br;q=0,gzip;q=0,identity;q=0'})).status,406);
});
test('binary artwork is not recompressed or rewritten',async()=>{
  const response=await request('/assets/image.png',{'Accept-Encoding':'br,gzip'});assert.deepEqual(response.body,Buffer.from([137,80,78,71,0,255,15]));assert.equal(response.headers['content-encoding'],undefined);
});
test('only HTML module entry is wrapped; game module and UI remain unchanged',async()=>{
  const response=await request('/explore-map.html'),html=response.body.toString();assert.equal(response.headers['cache-control'],'no-store');assert(html.includes('class="original">unchanged UI'));assert(html.includes('/__delivery/delivery_boot.mjs?entry='));
  const code=await request('/explore-map.js');assert.equal(code.body.toString(),"import './helper.js'; fetch('/assets/map.json');");assert.equal(sha(code.body),index.files['/explore-map.js'].sha256);
});
test('retired compatibility bindings have an external hard hide stylesheet',async()=>{
  const response=await request('/__delivery/retired_ui.css');assert.equal(response.status,200);assert.equal(response.headers['content-type'],'text/css; charset=utf-8');
});
test('health and private paths bypass static cache and remain private',async()=>{
  const health=await request('/health');assert.equal(health.body.toString(),'original health');assert.equal(health.headers['cache-control'],'no-store');assert.equal(health.headers.etag,undefined);
  for(const name of ['/data/saves/characters.json','/native-inputs/library.so','/assets/../native-inputs/library.so'])assert.equal((await request(name)).status,404);
});
test('public index excludes filesystem paths, saves and native inputs',async()=>{
  const response=await request('/__delivery/index.json'),text=response.body.toString();assert(!text.includes(root));assert(!text.includes('characters.json'));const value=JSON.parse(text);assert.equal(value.files['/assets/map.json'].sha256,sha(body));assert(value.plans['/explore-map.js'].includes('/helper.js'));assert(value.plans['/explore-map.js'].includes('/assets/map.json'));
});
test('same-byte aliases safely share prepared sidecars',()=>{assert.deepEqual(index.files['/assets/map.json'].encodings,index.files['/assets/same.json'].encodings);});
test('service worker scope is granted only to the delivery worker',async()=>{
  assert.equal((await request('/__delivery/delivery_worker.mjs')).headers['service-worker-allowed'],'/');assert.equal((await request('/explore-map.js')).headers['service-worker-allowed'],undefined);
});
test('public home and old index enter the current map and retain invitation settings',async()=>{
  for(const path of ['/','/index.html']){
    const r=await request(path);assert.equal(r.status,307);
    assert.equal(r.headers.location,'/explore-map.html?room=RAILWAY-01&sourceProfile=APK_Default');
    assert.equal(r.headers['cache-control'],'no-store');assert.equal(r.body.length,0);
  }
  const r=await request('/?room=FRIENDS-02&sourceProfile=GPU_4',{},'HEAD');
  assert.equal(r.headers.location,'/explore-map.html?room=FRIENDS-02&sourceProfile=GPU_4');
});
test('retired or encoded lab page requests cannot reach the old prototype HTML',async()=>{
  for(const path of ['/explore.html?room=DYNAMIC-01&lab=collision','/explore%2Ehtml?lab=collision','/explore-map.html?room=DYNAMIC-01&lab=collision']){
    const r=await request(path);assert.equal(r.status,307);assert.equal(r.headers.location,'/explore-map.html?room=RAILWAY-01&sourceProfile=APK_Default');assert.equal(r.body.length,0);
  }
});
