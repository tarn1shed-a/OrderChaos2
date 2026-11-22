import test from 'node:test';
import assert from 'node:assert/strict';
import {PLAYER_CHOICE_BODY_DEFINITIONS,createPlayerChoiceRegistry} from './player_choice_registry.mjs';
import {buildSourceContentCatalog,readSourceContentCatalogProjection} from './source_content_catalog.mjs';

import {fixture,digest,meta} from './testdata/source_content_fixture.mjs';

const build=f=>buildSourceContentCatalog(f);

test('one original registry drives all choices, both native formats and their distinct Gather data',()=>{
  const f=fixture(),c=build(f);
  assert.deepEqual(c.bodyKeys,PLAYER_CHOICE_BODY_DEFINITIONS.map(r=>r.key));
  assert.equal(Object.keys(c.choices).length,c.registry.count);assert.equal(c.registry.count,45);
  assert.equal(Object.keys(c.definitions).length,9);
  const hf=c.definitions['human-female'];assert.equal(hf.normal.mode,'normal15');assert.equal(hf.normal.poseFormat,null);
  assert.equal(hf.gather.adapter,'frozen-normal15-gather');
  for(const d of Object.values(c.definitions).filter(d=>d.normal.mode==='own-air')){
    assert.equal(d.normal.poseFormat,'oc2-source-body-native-pose-v1');assert.equal(d.gather.adapter,'own-air-gather');
    assert.notEqual(d.gather.bindingId,d.normal.bindingId);
  }
  assert.equal(c.scope,'static-content-description');assert.equal(c.ready,undefined);assert.equal(c.prepare,undefined);
});

test('the catalog calls each lookup once, retains no mutable input records and has no execution ports',()=>{
  const f=fixture(),counts={normal:0,gather:0};
  f.normalContracts=key=>{counts.normal++;return f.normals[key]??null;};
  f.gatherContracts=key=>{counts.gather++;return f.gathers[key]??null;};
  const c=build(f);assert.deepEqual(counts,{normal:9,gather:9});
  f.normals['human-male'].sourceMotion.sha256=digest(999);f.registryProfile.bodies[0].choices[0].appearance.face=99;
  assert.notEqual(c.definitions['human-male'].normal.sourceMotion.sha256,digest(999));
  assert.equal(c.registry.draft({race:0,gender:0,profession:1}).appearance.face,1);
  assert.throws(()=>{c.definitions['human-male'].normal.bindingId=digest(999);},TypeError);
  assert.deepEqual(counts,{normal:9,gather:9});
});

test('public Python closure and frozen private support stay separate, with no handwritten file count',()=>{
  const f=fixture(),c=build(f);
  assert.deepEqual(Object.keys(c.codeClosure.publicPython),Object.keys(f.declaration.files));
  assert.deepEqual(Object.keys(c.codeClosure.privateSupport),Object.keys(f.latestPlan.explicitRootSupport));
  assert.equal(c.codeClosure.publicPython['analysis/raw/frozen/context.py'],undefined);
  assert.throws(()=>build({...f,latestPlan:{...f.latestPlan,newRootFiles:{'tools/fixture.py':meta(999)}}}),/closure differ/);
  f.latestPlan.newRootFiles['analysis/raw/not-declared.py']=meta(99);assert.throws(()=>build(f),/unlisted private/);
});

test('missing, extra, stale or mismatched normal body contracts cannot become definitions',()=>{
  for(const change of [f=>delete f.normals['elf-male'],f=>f.normals['elf-male'].policy.modelId++,
    f=>f.latestPlan.bodies['elf-male'].bindingId=digest(999),f=>f.normals['elf-male'].sourceMotion.race++,
    f=>delete f.latestPlan.bodies['elf-male'],f=>f.latestPlan.bodies.unknown={},
    f=>f.normals['elf-male'].sourcePoseFormat=null]){const f=fixture();change(f);assert.throws(()=>build(f));}
});

test('normal15 is not coerced to the eight-body adapter or given an eight-body Gather contract',()=>{
  for(const change of [f=>f.latestPlan.bodies['human-female']=structuredClone(f.latestPlan.bodies['human-male']),
    f=>f.gathers['human-female']=structuredClone(f.gathers['human-male']),
    f=>f.additionalPlans.assets.runtimeOwnBody=1]){const f=fixture();change(f);assert.throws(()=>build(f));}
});

test('normal and Gather identities cannot be interchanged, and typed source resources reject escapes',()=>{
  for(const change of [f=>f.gathers['elf-male'].normalBinding=digest(999),
    f=>f.gathers['elf-male'].sourceMotion.key='human-male',f=>f.gathers['elf-male'].valueBytes++,
    f=>f.gathers['elf-male'].normalMotion=digest(999),f=>f.gathers['elf-male'].bodyKey='human-male',
    f=>f.gathers['elf-male'].source.target='../source.json',f=>f.gathers['elf-male'].source.url='https://example.org/source.json']){
    const f=fixture();change(f);assert.throws(()=>build(f));
  }
});

test('existing delivery pins are checked; host paths are not guessed from a URL',()=>{
  const f=fixture(),c=build(f);f.publicResources=structuredClone(c.browserProjection.resources);
  assert.equal(Object.keys(build(f).choices).length,45);
  delete f.publicResources[f.declaration.content.registry.url];assert.throws(()=>build(f),/delivery resource differs/);
  const g=fixture();g.publicResources=structuredClone(build(g).browserProjection.resources);
  g.publicResources[g.declaration.content.registry.url].sha256=digest(999);assert.throws(()=>build(g),/delivery resource differs/);
  const h=fixture();h.declaration.content.browserModules[0].path='deploy/other.mjs';assert.throws(()=>build(h),/path\/URL/);
});

test('the same path or URL cannot silently acquire another hash or an unlisted loader family',()=>{
  const f=fixture();f.latestPlan.reusedBasePayloadFiles={...f.latestPlan.newPayloadFiles};
  assert.doesNotThrow(()=>build(f));const first=Object.keys(f.latestPlan.newPayloadFiles)[0];
  f.latestPlan.reusedBasePayloadFiles[first]=meta(999);assert.throws(()=>build(f),/conflicting runtime/);
  const g=fixture();g.additionalPlans.actors.files.push({...g.additionalPlans.assets.files[0],sha256:digest(999)});
  assert.throws(()=>build(g),/conflicting public/);
  const h=fixture();delete h.additionalPlans.nativeInitialization;assert.throws(()=>build(h),/original plans/);
});

function hostMigration(){
  const f=fixture(),before=meta(901),after=meta(902),url='/__delivery/player_choice_scene.mjs';
  f.additionalPlans.actors.files.push({url,...before});
  f.declaration.content.browserModules.push({url,path:'deploy/player_choice_scene.mjs',...after,replaces:before});
  return {f,url,before,after};
}

test('only an exact frozen actor host module can be explicitly superseded; original plans remain unchanged',()=>{
  const {f,url,before,after}=hostMigration(),original=structuredClone(f.additionalPlans),c=build(f),r=c.resources['public:'+url];
  assert.equal(r.sha256,after.sha256);assert.equal(r.bytes,after.bytes);
  assert.deepEqual(r.superseded,[{plan:'actors',planRef:'runtime:'+f.declaration.content.plans.actors.path,...before}]);
  assert.deepEqual(f.additionalPlans,original);
  assert.deepEqual(c.browserProjection.resources[url],{url,...after});
  assert.equal(c.browserProjection.resources[url].superseded,undefined);
  f.publicResources=structuredClone(c.browserProjection.resources);assert.doesNotThrow(()=>build(f));
  f.publicResources[url]={url,...before};assert.throws(()=>build(f),/delivery resource differs/);
});

test('wrong old pins, unrelated resource overrides and ambiguous migration sources are refused',()=>{
  for(const change of [f=>f.declaration.content.browserModules.at(-1).replaces.sha256=digest(999),
    f=>f.declaration.content.browserModules.at(-1).replaces.bytes++,
    f=>delete f.declaration.content.browserModules.at(-1).replaces,
    f=>f.additionalPlans.actors.files.push(structuredClone(f.additionalPlans.actors.files.at(-1))),
    f=>f.declaration.content.browserModules.at(-1).path='native-inputs/library.so',
    f=>{const row=f.declaration.content.browserModules.at(-1);row.url='/assets/private-model.json';f.additionalPlans.actors.files.at(-1).url=row.url;},
    f=>{const row=f.declaration.content.browserModules.at(-1);row.url='/__delivery/private.so';row.path='deploy/private.so';}]){
    const {f}=hostMigration();change(f);assert.throws(()=>build(f));
  }
});

test('the original own actor plan adds older public dependencies and keeps its independent replacement provenance',()=>{
  const {f,url,before,after}=hostMigration();f.latestPlan.browserImportPlanSHA256=digest(910);
  const extra={url:'/assets/original-own-v1/input.json',...meta(911)};
  f.actorImportPlan={files:[extra,{url,...before}]};const c=build(f),ref=c.resources['public:'+url];
  assert.deepEqual(c.browserProjection.resources[extra.url],extra);
  assert.equal(ref.sha256,after.sha256);assert.equal(ref.superseded.length,2);
  assert.deepEqual(ref.superseded[1],{plan:'ownActors',planRef:'sha256:'+f.latestPlan.browserImportPlanSHA256,...before});
  assert.equal(c.browserProjection.resources[url].superseded,undefined);
});

test('own actor resources do not waive missing plan identity or mismatched frozen host pins',()=>{
  for(const change of [f=>delete f.latestPlan.browserImportPlanSHA256,f=>f.actorImportPlan.files.at(-1).sha256=digest(999),
    f=>f.actorImportPlan.files.push({url:'/assets/../private.json',...meta(912)}),
    f=>f.actorImportPlan.files.push({path:'analysis/raw/private.json',...meta(912)})]){
    const {f,url,before}=hostMigration();f.latestPlan.browserImportPlanSHA256=digest(910);
    f.actorImportPlan={files:[{url,...before}]};change(f);assert.throws(()=>build(f));
  }
});

test('public projection round trips using the original registry, without private files or execution claims',()=>{
  const c=build(fixture()),raw=JSON.stringify(c.browserProjection),p=readSourceContentCatalogProjection(JSON.parse(raw),{registry:c.registry});
  assert.deepEqual(p,c.browserProjection);assert.equal(raw.includes('analysis/raw'),false);assert.equal(raw.includes('native-inputs/'),false);
  assert.equal(raw.includes('deploy/'),false);assert.equal(p.codeClosure,undefined);assert.equal(p.nativeReady,undefined);
  assert.throws(()=>{p.definitions['human-male'].normal.properties=1;},TypeError);
});

test('public metadata rejects injected native claims, private fields, changed definitions and extra choices',()=>{
  const original=build(fixture()).browserProjection;
  for(const change of [p=>p.nativeReady=true,p=>p.definitions['human-male'].path='/private/worker.py',
    p=>p.definitions['human-male'].normal.sourceMotion.path='/private/animation.bdae',
    p=>p.definitions['human-male'].sourceModelId=32,p=>p.choices.extra=structuredClone(Object.values(p.choices)[0]),
    p=>p.resources[Object.keys(p.resources)[0]].path='/private/source',
    p=>p.registry.privateHostPath='/private/source',
    p=>p.registry.bodies[0].nativeReady=true,
    p=>p.definitions['human-male'].normal.sourceMotion.path='/private/source',
    p=>p.definitions['human-male'].normal.sourceMotion.format='/private/source',
    p=>p.definitions['human-male'].normal.poseFormat='/private/source']){
    const p=structuredClone(original);change(p);assert.throws(()=>readSourceContentCatalogProjection(p));
  }
});

test('public projection must agree with the already selected original registry',()=>{
  const f=fixture(),c=build(f);f.registryProfile.bodies[0].choices[0].appearance.face++;
  const changed=createPlayerChoiceRegistry(f.registryProfile);
  assert.throws(()=>readSourceContentCatalogProjection(c.browserProjection,{registry:changed}),/choice does not match/);
});

test('unknown schema fields, traversal and implicit incomplete metadata are refused',()=>{
  for(const change of [f=>f.declaration.content.ready=true,f=>f.declaration.content.registry.url='/assets/%2e%2e/private',
    f=>f.declaration.content.plans.assets.path='/private/assets.json',f=>f.declaration.content.browserModules.push(f.declaration.content.browserModules[0]),
    f=>f.declaration.files['tools/../private.py']=digest(1),f=>f.declaration.files['tools/a.py']='unknown']){
    const f=fixture();change(f);assert.throws(()=>build(f));
  }
});
