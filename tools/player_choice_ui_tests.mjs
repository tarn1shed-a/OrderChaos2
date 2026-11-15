// Read-only entry-QA preflight. This never creates an avatar through an API.
// The 45 actual creation proofs must come from later original-UI clicks.
import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {createHash} from 'node:crypto';
import {savedEntryIdentities} from '../deploy/entry_ui.mjs';

const ROOT=resolve('.'),file=resolve(process.env.OC2_ENTRY_UI_QA_PROFILE||'analysis/raw/player-choice-ui-20261115/session-v1/qa-profile.json');
const available=process.env.OC2_ENTRY_UI_PUBLIC_ONLY!=='1'&&existsSync(file),hash=b=>createHash('sha256').update(b).digest('hex');
let profile;
test('existing local identity adapter keeps the 32 limit and filters invalid credentials without changing storage',()=>{
 const value={characters:Object.fromEntries(Array.from({length:40},(_,i)=>['fixture'+i,{id:'00000000-0000-0000-0000-'+String(i).padStart(12,'0'),token:'a'.repeat(64)}]))};
 const raw=JSON.stringify(value),storage={getItem:key=>{assert.equal(key,'oc2.character-slots.v1');return raw;},setItem(){throw Error('Read-only check cannot write storage');}};
 assert.equal(savedEntryIdentities(storage).length,32);assert.equal(raw,JSON.stringify(value));
 assert.deepEqual(savedEntryIdentities({getItem:()=>'{broken'}),[]);
 assert.deepEqual(savedEntryIdentities({getItem:()=>JSON.stringify({characters:{bad:{id:'role',token:'private'}}})}),[]);
});
test('nine fresh QA origins cover exact original45 choices with unchanged UI and source IDs',{skip:!available},()=>{
 profile=JSON.parse(readFileSync(file));assert.equal(profile.combinationCount,45);assert.equal(profile.origins.length,9);
 assert.equal(new Set(profile.origins.map(x=>x.origin)).size,9);assert.equal(new Set(profile.origins.map(x=>x.key)).size,9);
 assert.equal(profile.physicsWorkers,0);assert.equal(profile.WebSocketServers,0);assert.equal(profile.original3DPreviewEnabled,false);assert.equal(profile.StartEnabled,false);assert.equal(profile.savedIdentityLimitUnchanged,32);
 assert.equal(hash(readFileSync(profile.sourceEntryProfile.path)),profile.sourceEntryProfile.sha256);
 assert.equal(hash(readFileSync(profile.originalMatrix.path)),profile.originalMatrix.sha256);
 for(const[path,sha]of Object.entries(profile.sourceModules))assert.equal(hash(readFileSync(join(ROOT,path))),sha,path);
 const matrix=JSON.parse(readFileSync(profile.originalMatrix.path));
 for(const [i,o]of profile.origins.entries()){
  assert.match(o.origin,/^http:\/\/127\.0\.0\.1:[0-9]+$/);assert.equal(o.choices.length,5);
  const source=matrix.bodyChoices[i];assert.equal(o.uiRace,source.uiRace);assert.equal(o.gender,source.gender);assert.equal(o.sourceModelId,source.sourceModel.ID);
  assert.deepEqual(o.choices.map(c=>c.profession),[1,3,2,5,4]);
  for(const [j,c]of o.choices.entries()){assert.equal(c.creationDisplayId,source.choices[j].creationDisplayId);assert.equal(c.expectedAvatar.sourceModelId,source.sourceModel.ID);assert.equal(c.expectedAvatar.race,source.internalRace);}
 }
});
test('all nine HTTP hosts serve unchanged original UI/assets and have zero created roles before UI clicks',{skip:!available||process.env.OC2_ENTRY_UI_LIVE_PREFLIGHT!=='1'},async()=>{
 const results=await Promise.all(profile.origins.map(async o=>{
  const status=await(await fetch(o.origin+'/__entry_qa_status.json')).json();assert.equal(status.records,0);assert.equal(status.noPhysicsWorkers,true);assert.equal(status.no3D,true);assert.equal(status.noStart,true);assert.equal(status.body.key,o.key);
  const ui=await(await fetch(o.origin+'/__delivery/entry_ui.mjs')).text();assert.equal(hash(ui),profile.sourceModules['deploy/entry_ui.mjs']);
  const art=await(await fetch(o.origin+'/assets/source-entry/entry.json')).arrayBuffer();assert.equal(hash(Buffer.from(art)),profile.sourceEntryProfile.sha256);
  const host=await(await fetch(o.origin+'/__entry_qa_host.mjs')).text();assert.match(host,/previewURL:null/);assert.doesNotMatch(host,/entry\.ready\(/);
  assert.equal((await fetch(o.origin+'/ws')).status,404);assert.equal((await fetch(o.origin+'/vendor/three.module.js')).status,404);
  for(const font of ['chineseText','chineseDisplay','leagueGothic'])assert.equal((await fetch(o.origin+'/assets/ui/'+font+'.woff')).status,200);
  return o.key;
 }));assert.equal(results.length,9);assert.equal(existsSync(profile.storeFile),false);
});
