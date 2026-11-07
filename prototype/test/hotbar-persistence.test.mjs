import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,readdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {once} from 'node:events';
import WebSocket from 'ws';
import {CharacterStore,characterView} from '../game/character-store.mjs';
import {createGameServer} from '../server.mjs';
import {changeEquipment} from '../game/equipment.mjs';
import {defaultHotbar,swapHotbarSlots,rebindHotbarSlot} from '../public/hotbar-settings.js';
import {encodeCharacterRecovery,decodeCharacterRecovery} from '../public/character-recovery.js';

const custom=()=>rebindHotbarSlot(swapHotbarSlots(defaultHotbar(),0,7),7,{code:'KeyQ',shift:false}).settings;
function temporary(t){const dir=mkdtempSync(join(tmpdir(),'oc2-hotbar-save-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));return dir;}
async function client(url,name,credentials={}){
  const ws=new WebSocket(url),messages=[];ws.on('message',raw=>messages.push(JSON.parse(raw)));await once(ws,'open');
  const wait=(predicate,after=0)=>{
    const old=messages.slice(after).find(predicate);if(old)return Promise.resolve(old);
    return new Promise((resolve,reject)=>{
      const read=raw=>{const value=JSON.parse(raw);if(predicate(value)){clearTimeout(timer);ws.off('message',read);resolve(value);}};
      const timer=setTimeout(()=>{ws.off('message',read);reject(new Error('Hotbar message timeout'));},3000);ws.on('message',read);
    });
  };
  const send=msg=>ws.send(JSON.stringify(msg));
  send({type:'join',name,room:'HB-SAVE',...credentials});
  return {ws,messages,wait,send,response:await wait(msg=>['welcome','error'].includes(msg.type))};
}
test('v3 migration preserves exact source bytes, look, inventory, stats and credentials; bad v4 hotbars never overwrite saves',t=>{
  const dir=temporary(t),file=join(dir,'characters.json'),old=new CharacterStore(file),identity=old.resolveCharacter('旧角色');
  changeEquipment(identity.record,{type:'equip',slot:'chest',itemId:'linenArmor'});
  identity.record.look={hair:'hair3',hairColor:'color6',skinColor:'color5'};identity.record.inventory.wolfPelt=11;
  identity.record.positions.resources={x:905,y:333};old.touch(identity.record);old.flush();
  const legacy=JSON.parse(readFileSync(file,'utf8'));legacy.version=3;delete legacy.characters[0].hotbar;delete legacy.characters[0].profession;delete legacy.characters[0].inventory.trainingStaff;delete legacy.characters[0].inventory.trainingGreatsword;
  const bytes=JSON.stringify(legacy,null,2);writeFileSync(file,bytes);
  const migrated=new CharacterStore(file),record=migrated.resolveCharacter('ignored',identity.record.id,identity.resumeToken).record;
  assert.equal(readFileSync(file,'utf8'),bytes);assert.equal(record.hotbar,null);
  const {hotbar,profession,...preserved}=record;const {trainingStaff,trainingGreatsword,...inventory}=preserved.inventory;
  assert.deepEqual({...preserved,inventory},legacy.characters[0]);assert.equal(profession,2);assert.equal(trainingStaff,1);assert.equal(trainingGreatsword,1);
  migrated.flush();assert.equal(JSON.parse(readFileSync(file,'utf8')).version,6);
  const backups=readdirSync(dir).filter(name=>name.includes('.v3-backup-'));assert.equal(backups.length,1);assert.equal(readFileSync(join(dir,backups[0]),'utf8'),bytes);
  record.hotbar=custom();migrated.touch(record);migrated.flush();
  const view=characterView(record);view.hotbar.slots[0]='forged';assert.deepEqual(record.hotbar,custom());
  assert.deepEqual(new CharacterStore(file).resolveCharacter('',identity.record.id,identity.resumeToken).record.hotbar,custom());
  for(const bad of [undefined,{...custom(),gold:999}, {...custom(),bindings:custom().bindings.map(()=>({code:'KeyW',shift:false}))}]){
    const invalid=JSON.parse(readFileSync(file,'utf8'));invalid.characters[0].hotbar=bad;
    const raw=JSON.stringify(invalid);writeFileSync(file,raw);assert.throws(()=>new CharacterStore(file),/技能栏存档无效/);assert.equal(readFileSync(file,'utf8'),raw);
  }
  assert.equal(readdirSync(dir).filter(name=>name.includes('.v3-backup-')).length,1);
});
test('private hotbars persist across a fresh client and restart; forged updates and stale browser import cannot overwrite another character',async t=>{
  const file=join(temporary(t),'characters.json');let game;
  t.after(async()=>{if(game)await game.close();});
  async function start(){game=createGameServer({saveFile:file});game.server.listen(0,'127.0.0.1');await once(game.server,'listening');return 'ws://127.0.0.1:'+game.server.address().port+'/ws';}
  const url=await start(),a=await client(url,'技能甲'),b=await client(url,'技能乙');
  assert.equal(a.response.character.hotbar,null);
  a.send({type:'hotbar',requestId:1,settings:custom(),initializeOnly:true,characterId:b.response.id,gold:999});
  const saved=await a.wait(msg=>msg.type==='hotbar-result'&&msg.requestId===1);assert(saved.ok);assert.deepEqual(saved.hotbar,custom());
  let disk=JSON.parse(readFileSync(file,'utf8'));assert.equal(disk.version,6);
  assert.deepEqual(disk.characters.find(c=>c.id===a.response.id).hotbar,custom());assert.equal(disk.characters.find(c=>c.id===b.response.id).hotbar,null);
  assert.equal(disk.characters.find(c=>c.id===a.response.id).gold,0);
  const state=await b.wait(msg=>msg.type==='state');assert(!JSON.stringify(state).includes('hotbar'));assert(!JSON.stringify(state).includes('resumeToken'));
  a.send({type:'hotbar',requestId:2,settings:defaultHotbar(),initializeOnly:true});
  assert.equal((await a.wait(msg=>msg.type==='hotbar-result'&&msg.requestId===2)).ok,false);
  a.send({type:'hotbar',requestId:3,settings:{...custom(),slots:['forged']}});
  assert.equal((await a.wait(msg=>msg.type==='hotbar-result'&&msg.requestId===3)).ok,false);
  const copied=decodeCharacterRecovery(encodeCharacterRecovery(a.response.character,a.response.resumeToken));
  await game.close();const restarted=await start();
  const fresh=await client(restarted,copied.name,{characterId:copied.characterId,resumeToken:copied.resumeToken});
  assert.equal(fresh.response.restored,true);assert.deepEqual(fresh.response.character.hotbar,custom());
  const sameName=await client(restarted,copied.name);assert.notEqual(sameName.response.id,fresh.response.id);assert.equal(sameName.response.character.hotbar,null);
  const wrong=await client(restarted,copied.name,{characterId:copied.characterId,resumeToken:'0'.repeat(64)});
  assert.equal(wrong.response.type,'error');assert(wrong.response.message.includes('不匹配'));
  fresh.send({type:'hotbar',requestId:4,settings:defaultHotbar()});assert((await fresh.wait(msg=>msg.type==='hotbar-result'&&msg.requestId===4)).ok);
  disk=JSON.parse(readFileSync(file,'utf8'));assert.deepEqual(disk.characters.find(c=>c.id===copied.characterId).hotbar,defaultHotbar());
  assert(!readFileSync(file,'utf8').includes(copied.resumeToken));
});
test('a failed hotbar disk write never sends a successful saved acknowledgement',async t=>{
  const root=temporary(t),dir=join(root,'saves'),file=join(dir,'characters.json'),game=createGameServer({saveFile:file});
  t.after(async()=>{try{await game.close();}catch{}});
  game.server.listen(0,'127.0.0.1');await once(game.server,'listening');
  const a=await client('ws://127.0.0.1:'+game.server.address().port+'/ws','失败保存测试');
  rmSync(dir,{recursive:true});writeFileSync(dir,'blocked');
  const closed=once(a.ws,'close');a.send({type:'hotbar',requestId:1,settings:custom()});await closed;
  assert(!a.messages.some(msg=>msg.type==='hotbar-result'&&msg.ok));assert.equal(readFileSync(dir,'utf8'),'blocked');
});

test('v5 adds the channel skill to an empty slot once, preserving all existing bindings, progress and exact backup bytes',t=>{
 const file=join(temporary(t),'characters.json'),s=new CharacterStore(file),identity=s.resolveCharacter('旧法师');
 const settings=custom();settings.slots[2]=null;identity.record.hotbar=settings;identity.record.hp=78;identity.record.gold=30;identity.record.positions.resources={x:912.65,y:417.16};
 s.touch(identity.record);s.flush();const old=JSON.parse(readFileSync(file,'utf8'));old.version=5;const bytes=JSON.stringify(old,null,1);writeFileSync(file,bytes);
 const upgraded=new CharacterStore(file),record=upgraded.resolveCharacter('',identity.record.id,identity.resumeToken).record;
 const expected=structuredClone(old.characters[0]);expected.hotbar.slots[0]='arcane_missile';assert.deepEqual(record,expected);assert.equal(readFileSync(file,'utf8'),bytes);
 upgraded.flush();const backups=readdirSync(join(file,'..')).filter(n=>n.includes('.v5-backup-'));assert.equal(backups.length,1);assert.equal(readFileSync(join(file,'..',backups[0]),'utf8'),bytes);
 const again=new CharacterStore(file);again.flush();assert.equal(again.resolveCharacter('',record.id,identity.resumeToken).record.hotbar.slots.filter(s=>s==='arcane_missile').length,1);
 assert.deepEqual(record.hotbar.bindings,settings.bindings);
});
