import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync,symlinkSync} from 'node:fs';
import {resolve,join,dirname} from 'node:path';
import {tmpdir} from 'node:os';
import {createHash,randomUUID} from 'node:crypto';
import {fixture} from './testdata/source_content_fixture.mjs';
import {buildSourceContentCatalog} from './source_content_catalog.mjs';
import {createPinnedResourceReader} from './source_resource_reader.mjs';
import {loadSourceContentCatalog,readSourceContentDeclaration} from './source_content_runtime.mjs';

const digest=b=>createHash('sha256').update(b).digest('hex');
const pin=b=>({sha256:digest(b),bytes:b.length});
const encode=x=>Buffer.from(JSON.stringify(x));
const CONTRACT='prototype/game/world-admission-latest-v1/contracts.mjs';
const OWN_ACTORS='native-inputs/world-latest-v1/browser-import-plan.json';

// Only tiny JSON and a data-only contract module are materialized. The full
// model/animation/Native input tree is neither copied nor read by these tests.
function tree(t){
  const root=mkdtempSync(join(tmpdir(),'oc2-content-runtime-'));
  t.after(()=>rmSync(root,{recursive:true,force:true}));
  const runtime=resolve(root,'runtime'),delivery=resolve(root,'delivery'),deploy=resolve(root,'deploy');
  for(const p of [runtime,delivery,deploy,resolve(root,'tools')])mkdirSync(p,{recursive:true});
  const f=fixture();
  const put=(path,b)=>{mkdirSync(dirname(path),{recursive:true});writeFileSync(path,b);return pin(b);};
  const writeDeclaration=()=>put(resolve(root,'tools/source_world_python.json'),encode(f.declaration));
  const writeLatest=()=>{Object.assign(f.declaration.plans.latestWorld,
    put(resolve(runtime,f.declaration.plans.latestWorld.path),encode(f.latestPlan)));writeDeclaration();};
  f.additionalPlans.assets.format='synthetic-原始资料-🧪';
  for(const [name,p]of Object.entries(f.additionalPlans))Object.assign(f.declaration.content.plans[name],
    put(resolve(runtime,f.declaration.content.plans[name].path),encode(p)));
  const registryPath=resolve(runtime,'fixture-registry.json');
  Object.assign(f.declaration.content.registry,put(registryPath,encode(f.registryProfile)));
  for(const row of f.declaration.content.browserModules)Object.assign(row,
    put(resolve(root,row.path),Buffer.from('// 仅测试浏览器模块，无导入或执行入口\n')));
  const contractPath=resolve(runtime,CONTRACT);
  const contractSource=(prefix='')=>prefix+'const n='+JSON.stringify(f.normals)+';const g='+JSON.stringify(f.gathers)+';\n'+
    'export function getNormalContract(k){return n[k]??null;}\nexport function getGatherContract(k){return g[k]??null;}\n';
  f.latestPlan.newPayloadFiles[CONTRACT]=put(contractPath,Buffer.from(contractSource()));
  f.actorImportPlan={files:[{url:'/assets/original-own-v1-only.json',sha256:'9'.repeat(64),bytes:17}]};
  const ownPin=put(resolve(runtime,OWN_ACTORS),encode(f.actorImportPlan));
  f.latestPlan.browserImportPlanSHA256=ownPin.sha256;
  put(resolve(runtime,'bundle-manifest.json'),encode({files:{[OWN_ACTORS]:ownPin}}));
  writeLatest();
  const c=buildSourceContentCatalog(f);
  const files=Object.fromEntries(Object.entries(c.browserProjection.resources).map(([url,row])=>[url,{...row,path:resolve(runtime,'not-read',url.slice(1))}]));
  files[f.declaration.content.registry.url].path=registryPath;
  for(const row of f.declaration.content.browserModules)files[row.url].path=resolve(root,row.path);
  const args={root,runtime,delivery,files};
  return {root,runtime,delivery,deploy,f,args,put,writeDeclaration,writeLatest,registryPath,contractPath,contractSource};
}

function observedReader(s){
  const reader=createPinnedResourceReader({roots:[s.runtime,s.delivery,s.deploy]}),reads=[],verified=[];
  return {reads,verified,port:{...reader,
    readBytes(p){reads.push(p.path);const b=reader.readBytes(p);assert.equal(b.constructor,Uint8Array);return b;},
    verify(p){verified.push(p.path);return reader.verify(p);}}};
}

test('real pinned Uint8Array reads use fatal UTF-8 JSON decoding; repeated catalogs have the same public identity',async t=>{
  const s=tree(t),reader=observedReader(s);
  const a=await loadSourceContentCatalog({...s.args,reader:reader.port});
  const b=await loadSourceContentCatalog({...s.args,reader:reader.port});
  assert.equal(a.plans.assets.format,'synthetic-原始资料-🧪');
  assert.deepEqual(a.projectionBytes,b.projectionBytes);assert.deepEqual(a.projectionPin,b.projectionPin);
  assert.equal(a.projectionPin.sha256,digest(a.projectionBytes));assert.equal(a.projectionPin.bytes,a.projectionBytes.length);
  assert.equal(a.catalog.registry.count,45);assert.equal(Object.keys(a.catalog.definitions).length,9);
  assert.equal(a.catalog.ready,undefined);assert.equal(a.catalog.prepare,undefined);assert.equal(a.catalog.tick,undefined);
  assert.equal(a.reader,reader.port);assert.equal(reader.verified.length,2);
  assert(reader.reads.every(p=>!p.endsWith('.bdae')&&!p.endsWith('.so')&&!p.endsWith('.py')));
  assert.equal(a.projectionBytes.toString().includes(s.root),false);
  assert.equal(a.catalog.resources['public:/assets/original-own-v1-only.json'].sha256,'9'.repeat(64));
});

test('invalid UTF-8 is rejected even when the file has the explicitly expected SHA',async t=>{
  const s=tree(t),row=s.f.declaration.content.plans.assets;
  Object.assign(row,s.put(resolve(s.runtime,row.path),Buffer.from([0x7b,0x22,0x61,0x22,0x3a,0x22,0xff,0x22,0x7d])));
  s.writeDeclaration();await assert.rejects(loadSourceContentCatalog(s.args),/encoded data|UTF-8|encoding/i);
});

test('a changed private plan fails byte/SHA verification before JSON or contract import',async t=>{
  const s=tree(t),reader=observedReader(s),path=resolve(s.runtime,s.f.declaration.content.plans.assets.path),raw=readFileSync(path);
  raw[raw.indexOf(Buffer.from('synthetic'))]=0x78;writeFileSync(path,raw);
  await assert.rejects(loadSourceContentCatalog({...s.args,reader:reader.port}),/Resource SHA differs/);
  assert.equal(reader.verified.length,0);
});

test('the bundle byte descriptor and latest own actor SHA must agree before the import plan is read',async t=>{
  const s=tree(t),reader=observedReader(s),path=resolve(s.runtime,'bundle-manifest.json');
  const bundle=JSON.parse(readFileSync(path));bundle.files[OWN_ACTORS].sha256='0'.repeat(64);s.put(path,encode(bundle));
  await assert.rejects(loadSourceContentCatalog({...s.args,reader:reader.port}));
  assert.equal(reader.reads.includes(resolve(s.runtime,OWN_ACTORS)),false);
  const missing=tree(t);missing.put(resolve(missing.runtime,'bundle-manifest.json'),encode({files:{}}));
  await assert.rejects(loadSourceContentCatalog(missing.args));
});

test('own actor-plan bytes and strict UTF-8 are checked, not just registered as metadata',async t=>{
  const s=tree(t),path=resolve(s.runtime,OWN_ACTORS),raw=readFileSync(path);raw[raw.indexOf(Buffer.from('files'))]=0x78;s.put(path,raw);
  await assert.rejects(loadSourceContentCatalog(s.args),/Resource SHA differs/);
  const invalid=tree(t),bad=Buffer.from([0x7b,0x22,0x61,0x22,0x3a,0x22,0xff,0x22,0x7d]);
  const p=invalid.put(resolve(invalid.runtime,OWN_ACTORS),bad);
  invalid.f.latestPlan.browserImportPlanSHA256=p.sha256;
  invalid.put(resolve(invalid.runtime,'bundle-manifest.json'),encode({files:{[OWN_ACTORS]:p}}));invalid.writeLatest();
  await assert.rejects(loadSourceContentCatalog(invalid.args),/encoded data|UTF-8|encoding/i);
});

test('public delivery metadata cannot replace the declared registry identity',async t=>{
  const s=tree(t);s.args.files[s.f.declaration.content.registry.url].sha256='0'.repeat(64);
  await assert.rejects(loadSourceContentCatalog(s.args),/Content delivery identity differs/);
});

test('matching delivery metadata still cannot hide changed registry bytes',async t=>{
  const s=tree(t),raw=readFileSync(s.registryPath);raw[raw.indexOf(Buffer.from('format'))]=0x78;writeFileSync(s.registryPath,raw);
  await assert.rejects(loadSourceContentCatalog(s.args),/Resource SHA differs/);
});

test('a changed host browser module or contract file is not silently reused',async t=>{
  const a=tree(t),row=a.f.declaration.content.browserModules[0],path=resolve(a.root,row.path),bytes=readFileSync(path);
  bytes[0]=0x78;writeFileSync(path,bytes);await assert.rejects(loadSourceContentCatalog(a.args),/Resource SHA differs/);
  const b=tree(t),raw=readFileSync(b.contractPath);raw[0]=0x78;writeFileSync(b.contractPath,raw);
  await assert.rejects(loadSourceContentCatalog(b.args),/Resource SHA differs/);
});

test('a delivery path outside the permitted roots, including a symlink, is rejected',async t=>{
  const s=tree(t),outside=mkdtempSync(join(tmpdir(),'oc2-content-outside-'));t.after(()=>rmSync(outside,{recursive:true,force:true}));
  const path=resolve(outside,'registry.json');writeFileSync(path,readFileSync(s.registryPath));
  const url=s.f.declaration.content.registry.url;s.args.files[url].path=path;
  await assert.rejects(loadSourceContentCatalog(s.args),/outside allowed roots/);
  const link=resolve(s.runtime,'outside-link.json');symlinkSync(path,link);s.args.files[url].path=link;
  await assert.rejects(loadSourceContentCatalog(s.args),/outside allowed roots/);
});

test('a private-plan traversal into another permitted root is rejected before the read',async t=>{
  const s=tree(t),path=resolve(s.deploy,'escaped-plan.json'),reader=observedReader(s);
  const row=s.f.declaration.content.plans.assets;Object.assign(row,s.put(path,encode(s.f.additionalPlans.assets)));row.path='../deploy/escaped-plan.json';
  s.writeDeclaration();await assert.rejects(loadSourceContentCatalog({...s.args,reader:reader.port}));
  assert.equal(reader.reads.includes(path),false,'private plans must stay in the runtime root before I/O');
});

test('absolute private-plan paths are not accepted merely because another reader root contains the file',async t=>{
  const s=tree(t),path=resolve(s.deploy,'absolute-plan.json'),reader=observedReader(s);
  const row=s.f.declaration.content.plans.assets;Object.assign(row,s.put(path,encode(s.f.additionalPlans.assets)));row.path=path;
  s.writeDeclaration();await assert.rejects(loadSourceContentCatalog({...s.args,reader:reader.port}));
  assert.equal(reader.reads.includes(path),false);
});

test('an extra contract pin path cannot redirect verification while the fixed module is imported',async t=>{
  const s=tree(t),marker='__oc2UnverifiedContract_'+randomUUID().replaceAll('-','');t.after(()=>delete globalThis[marker]);
  writeFileSync(s.contractPath,Buffer.from(s.contractSource('globalThis['+JSON.stringify(marker)+']=true;\n')));
  const decoy=resolve(s.runtime,'checked-decoy.json'),row=s.put(decoy,Buffer.from('{}'));
  s.f.latestPlan.newPayloadFiles[CONTRACT]={...row,path:decoy};s.writeLatest();
  await assert.rejects(loadSourceContentCatalog(s.args));assert.equal(globalThis[marker],undefined,'unverified module must not execute');
});

test('missing content declarations fail before any runtime adapter can be loaded',t=>{
  const s=tree(t);delete s.f.declaration.content;s.writeDeclaration();
  assert.throws(()=>readSourceContentDeclaration(s.root),/Reviewed source content declaration required/);
});
