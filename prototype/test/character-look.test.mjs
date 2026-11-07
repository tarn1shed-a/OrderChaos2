import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync,readFileSync,writeFileSync,readdirSync,rmSync } from 'node:fs';
import { join } from 'node:path';import {tmpdir}from'node:os';import{once}from'node:events';import WebSocket from 'ws';
import {defaultLook,validLook}from'../public/character-look.js';
import {CharacterStore}from'../game/character-store.mjs';
import {createGameServer}from'../server.mjs';
import {changeEquipment}from'../game/equipment.mjs';
import {existsSync}from'node:fs';
import * as THREE from 'three';
import {createCharacterMaterial}from'../public/character-materials.js';
import {createCharacterFactory,setCharacterLook,characterEquipmentState,disposeCharacterAnimation}from'../public/character-animation.js';

test('look validation rejects unknown styles, disabled zero skin pair and forged fields',()=>{
  assert(validLook(defaultLook()));
  for(const look of [null,[],{...defaultLook(),hair:'__proto__'},{...defaultLook(),skinColor:'color6'},{...defaultLook(),gold:999},{...defaultLook(),hairColor:{}}])assert.equal(validLook(look),false);
});
test('v2 migration backs up exact bytes once and preserves equipped items without issuing starter items again',t=>{
  const dir=mkdtempSync(join(tmpdir(),'oc2-look-migrate-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));
  const file=join(dir,'characters.json'),store=new CharacterStore(file),identity=store.resolveCharacter('原角色');
  changeEquipment(identity.record,{type:'equip',slot:'chest',itemId:'linenArmor'});identity.record.inventory.wolfPelt=14;store.touch(identity.record);store.flush();
  const old=JSON.parse(readFileSync(file,'utf8'));old.version=2;delete old.characters[0].look;const bytes=JSON.stringify(old,null,2);writeFileSync(file,bytes);
  const migrated=new CharacterStore(file),c=migrated.resolveCharacter('ignored',identity.record.id,identity.resumeToken).record;
  assert.deepEqual(c.look,defaultLook());assert.equal(c.inventory.linenArmor,0);assert.equal(c.equipment.chest,'linenArmor');assert.equal(c.inventory.wolfPelt,14);assert.equal(c.hp,100);assert.equal(c.maxHp,120);
  migrated.flush();const backups=readdirSync(dir).filter(name=>name.includes('.v2-backup-'));assert.equal(backups.length,1);assert.equal(readFileSync(join(dir,backups[0]),'utf8'),bytes);
  c.look={hair:'hair3',hairColor:'color6',skinColor:'color5'};migrated.touch(c);migrated.flush();
  assert.deepEqual(new CharacterStore(file).resolveCharacter('ignored',identity.record.id,identity.resumeToken).record.look,c.look);
  const bad=JSON.parse(readFileSync(file,'utf8'));bad.characters[0].look.skinColor='color6';const invalid=JSON.stringify(bad);writeFileSync(file,invalid);
  assert.throws(()=>new CharacterStore(file),/外观存档无效/);assert.equal(readFileSync(file,'utf8'),invalid);
});
async function enter(url,name,credentials={}){
  const ws=new WebSocket(url),messages=[];ws.on('message',raw=>messages.push(JSON.parse(raw)));await once(ws,'open');
  const wait=(predicate,after=0)=>{const old=messages.slice(after).find(predicate);if(old)return Promise.resolve(old);return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{ws.off('message',read);reject(new Error('Look message timeout'));},3000);const read=raw=>{const msg=JSON.parse(raw);if(predicate(msg)){clearTimeout(timer);ws.off('message',read);resolve(msg);}};ws.on('message',read);
  });};
  const send=data=>ws.send(JSON.stringify(data));send({type:'join',room:'LOOK-NEW',name,...credentials});return{ws,send,wait,messages,welcome:await wait(m=>m.type==='welcome')};
}
test('two clients and a late observer see saved look changes; rejected choices do not change gold, equipment, or persistence',async t=>{
  const dir=mkdtempSync(join(tmpdir(),'oc2-look-server-'));let game;
  t.after(async()=>{await game.close();rmSync(dir,{recursive:true,force:true});});
  async function start(){game=createGameServer({saveFile:join(dir,'characters.json')});game.server.listen(0,'127.0.0.1');await once(game.server,'listening');return`ws://127.0.0.1:${game.server.address().port}/ws`;}
  const url=await start(),a=await enter(url,'发型甲'),b=await enter(url,'发型乙'),look={hair:'hair3',hairColor:'color6',skinColor:'color5'};
  a.send({type:'look',look,gold:99999});const updated=await a.wait(m=>m.type==='progress'&&m.character.look.hair==='hair3');assert.equal(updated.character.gold,0);assert.equal(updated.character.inventory.trainingSword,1);
  const observed=await b.wait(m=>m.type==='state'&&m.players.find(p=>p.id===a.welcome.id)?.look.hair==='hair3');assert.deepEqual(observed.players.find(p=>p.id===a.welcome.id).look,look);assert(!JSON.stringify(observed).includes('inventory'));
  const late=await enter(url,'迟加入');assert.deepEqual((await late.wait(m=>m.type==='state')).players.find(p=>p.id===a.welcome.id).look,look);
  let mark=a.messages.length;a.send({type:'look',look:{...look,skinColor:'color6'}});await a.wait(m=>m.type==='notice'&&m.message.includes('无效'),mark);
  await game.close();const resumed=await enter(await start(),'发型甲',{characterId:a.welcome.id,resumeToken:a.welcome.resumeToken});assert.deepEqual(resumed.welcome.character.look,look);assert.equal(resumed.welcome.character.gold,0);
});

const original=new URL('../../game-data/converted/models/elf-female.json',import.meta.url);
test('original hair switches one style on shared bones while two characters own independent color uniforms',{skip:!existsSync(original)},()=>{
  const data=JSON.parse(readFileSync(original,'utf8'));assert.equal(data.appearance.hair.format,'oc2-character-hair-v1');
  const profile=data.characterMaterials,textures=new Map(profile.materials.flatMap(entry=>Object.values(entry.samplers)).map(url=>[url,new THREE.Texture()]));
  const materials=profile.materials.map(entry=>createCharacterMaterial(THREE,entry,textures,profile.colors));
  const create=createCharacterFactory(THREE,data,materials),a=create(),b=create();
  setCharacterLook(a,{hair:'hair3',hairColor:'color6',skinColor:'color5'});
  for(const [root,key]of [[a,'hair3'],[b,'hair1']]){
    const visible=new Set(characterEquipmentState(root).visibleMeshIndices),all=data.appearance.hair.allMeshIndices;
    assert.deepEqual(all.filter(index=>visible.has(index)),data.appearance.hair.styles[key].meshIndices);
  }
  const findBody=root=>{let material;root.traverse(object=>{if(object.userData.sourceMeshIndex===0)material=Array.isArray(object.material)?object.material[0]:object.material;});return material;};
  const compile=material=>{const shader={uniforms:{},vertexShader:THREE.ShaderLib.standard.vertexShader,fragmentShader:THREE.ShaderLib.standard.fragmentShader};material.onBeforeCompile(shader);return shader;};
  const first=compile(findBody(a)),second=compile(findBody(b));assert.notEqual(first.uniforms.nativeHair.value,second.uniforms.nativeHair.value);
  assert.deepEqual(first.uniforms.nativeHair.value.toArray(),profile.colors.hair.color6.primaryRGB);assert.deepEqual(second.uniforms.nativeHair.value.toArray(),profile.colors.hair.color1.primaryRGB);
  assert(data.meshes.every(mesh=>mesh.sourceTangents.length===mesh.positions.length&&mesh.sourceBinormals.length===mesh.positions.length));
  disposeCharacterAnimation(a);disposeCharacterAnimation(b);
});
