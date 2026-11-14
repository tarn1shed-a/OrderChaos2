import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,rmSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createSourceAvatarStore,sourceAvatar,sourceCharacterView,SOURCE_AVATAR_FORMAT} from '../deploy/source_avatar_state.mjs';
import {stageSourceAvatarServer} from '../deploy/source_avatar_server.mjs';
import {createSourceAvatarDraft} from '../deploy/source_avatar_draft.mjs';
import {createHash} from 'node:crypto';

const chosen=()=>({format:SOURCE_AVATAR_FORMAT,key:'human-male',race:0,gender:0,sourceModelId:1,
  creationDisplayId:2053,
  sourceProfileSHA256:'1'.repeat(64),appearance:{face:0,hair:0,beard:0,skinColor:2147483647,hairColor:6710886}});

test('explicit source avatar rejects aliases, extra/private fields and missing appearance',()=>{
  const a=chosen(),v=sourceAvatar(a);a.appearance.hair=1;assert.equal(v.appearance.hair,0);
  for(const bad of [null,{}, {...chosen(),key:'elf-female'}, {...chosen(),race:2},
    {...chosen(),sourceProfileSHA256:'source'}, {...chosen(),sourceProfileSHA256:['1'.repeat(64)]}, {...chosen(),resumeToken:'private'},
    {...chosen(),appearance:{...chosen().appearance,face:1}}, {...chosen(),appearance:{...chosen().appearance,hairColor:Infinity}}])
    assert.throws(()=>sourceAvatar(bad));
});

const creationFile=resolve('analysis/raw/character-human-creation-defaults-20261115/candidate-v1/manifest.json');
test('all five original profession drafts retain their own display, hair and raw colors without equipment grants',{skip:!existsSync(creationFile)},()=>{
  const raw=readFileSync(creationFile),manifest=JSON.parse(raw),sha=createHash('sha256').update(raw).digest('hex'),choose=createSourceAvatarDraft(manifest,sha);
  for(const[index,profession]of [1,3,2,5,4].entries()){
    const source=manifest.sourceHumanCreationDraft.variants[index].draft,actual=choose({race:0,gender:0,profession});
    assert.equal(actual.creationDisplayId,source.displayId);assert.equal(actual.sourceProfileSHA256,sha);
    assert.deepEqual(actual.appearance,{face:source.face,hair:source.hair,beard:source.beard,skinColor:source.skinColorWord,hairColor:source.hairColorWord});
    assert.equal(actual.equipment,undefined);assert.equal(actual.positions,undefined);assert.equal(actual.skills,undefined);
  }
  assert.equal(choose({race:0,gender:1,profession:1}),null);
  assert.equal(choose({race:2,gender:1,profession:2}),null);
  assert.throws(()=>choose({race:0,gender:0,profession:999}));
  assert.throws(()=>createSourceAvatarDraft({},sha));
  const corrupt=structuredClone(manifest);corrupt.sourceHumanCreationDraft.variants[0].sourceEquipment={chest:100422};
  assert.throws(()=>createSourceAvatarDraft(corrupt,sha));
});

test('legacy snapshots stay identical; source snapshots contain no credentials or positions',()=>{
  const original=r=>({id:r.id,name:r.name}),r={id:'role',name:'tester',tokenHash:'secret',positions:{resources:{x:1,y:2}}};
  assert.deepEqual(sourceCharacterView(r,original),original(r));
  r.sourceAvatar=chosen();const view=sourceCharacterView(r,original);assert.deepEqual(Object.keys(view),['id','name','sourceAvatar']);
  view.sourceAvatar.appearance.hair=1;assert.equal(r.sourceAvatar.appearance.hair,0);
});

const privateRoot=resolve(process.env.OC2_REVIEWED_RUNTIME||'analysis/raw/played-species-routing-20261115/immutable-inputs/prototype');
const available=existsSync(join(privateRoot,'game/character-store.mjs'))&&existsSync(join(privateRoot,'public/items.js'));
test('real reviewed store saves the chosen avatar in its first write and restores it without migrating legacy roles',{skip:!available},async()=>{
  const {CharacterStore,characterView}=await import(pathToFileURL(join(privateRoot,'game/character-store.mjs')));
  const Store=createSourceAvatarStore(CharacterStore),folder=mkdtempSync(join(tmpdir(),'oc2-avatar-store-')),file=join(folder,'characters.json');
  try{
    const legacyStore=new CharacterStore(file),legacy=legacyStore.resolveCharacter('原角色',undefined,undefined,2),before=JSON.parse(readFileSync(file,'utf8')).characters[0];
    const originalBytes=readFileSync(file),store=new Store(file);assert.deepEqual(readFileSync(file),originalBytes);
    const expected=chosen(),role=store.resolveCharacter('人类验收',undefined,undefined,1,expected),saved=JSON.parse(readFileSync(file,'utf8'));
    assert.equal(saved.version,6);assert.deepEqual(saved.characters.find(c=>c.id===legacy.record.id),before);
    assert.deepEqual(saved.characters.find(c=>c.id===role.record.id).sourceAvatar,expected);
    assert.deepEqual(sourceCharacterView(role.record,characterView).sourceAvatar,expected);
    const disk=readFileSync(file),restored=new Store(file),again=restored.resolveCharacter('ignored',role.record.id,role.resumeToken,5);
    assert.equal(again.restored,true);assert.deepEqual(again.record.sourceAvatar,expected);assert.deepEqual(readFileSync(file),disk);
    assert.throws(()=>restored.resolveCharacter('ignored',role.record.id,role.resumeToken,5,chosen()),/cannot be replaced/);
    assert.deepEqual(readFileSync(file),disk);
    // Invalid source data is never interpreted as the old default model.
    const bad=JSON.parse(disk);bad.characters.find(c=>c.id===role.record.id).sourceAvatar.race=2;
    writeFileSync(file,JSON.stringify(bad));const badBytes=readFileSync(file);assert.throws(()=>new Store(file),/Unverified/);assert.deepEqual(readFileSync(file),badBytes);
  }finally{rmSync(folder,{recursive:true,force:true});}
});

test('guarded server overlay changes the store import and player DTO only',{skip:!existsSync(join(privateRoot,'server.mjs'))},()=>{
  const before=readFileSync(join(privateRoot,'server.mjs'),'utf8'),after=stageSourceAvatarServer(before);
  assert.match(after,/createSourceAvatarStore\(ReviewedStore\)/);assert.match(after,/ws\.player\.sourceAvatar=sourceAvatar\(ws\.character\.sourceAvatar\)/);
  for(const field of ['hp','xp','equipment','positions','profession'])assert.equal(after.includes('ws.character.'+field),before.includes('ws.character.'+field));
  assert.throws(()=>stageSourceAvatarServer(after),/anchor differs/);
});
