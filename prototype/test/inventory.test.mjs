import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, writeFileSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { once } from 'node:events';
import WebSocket from 'ws';
import { CharacterStore, characterView } from '../game/character-store.mjs';
import { changeEquipment } from '../game/equipment.mjs';
import { CombatRoom, syncPlayerStats } from '../game/combat.mjs';
import { bagEntries, equipmentStats } from '../public/items.js';
import { inventorySelection } from '../public/inventory-ui.js';
import { createGameServer } from '../server.mjs';
import { WORLD } from '../public/world.js';

function folder(t) {
  const path=mkdtempSync(join(tmpdir(),'oc2-equipment-'));t.after(()=>rmSync(path,{recursive:true,force:true}));return path;
}
function character() { return new CharacterStore().resolveCharacter('行囊旅人').record; }

test('equipping consumes owned items, repeated/wrong requests do not duplicate them or heal, and views are independent',()=>{
  const c=character(); c.hp=65;
  assert(changeEquipment(c,{type:'equip',slot:'mainHand',itemId:'linenArmor'}).error);
  for(const key of ['__proto__',null,{},'missing'])assert(changeEquipment(c,{type:'equip',slot:key,itemId:'trainingSword'}).error);
  assert(!changeEquipment(c,{type:'equip',slot:'chest',itemId:'linenArmor',maxHp:99999}).error);
  assert.equal(c.maxHp,120);assert.equal(c.hp,65);assert.equal(c.inventory.linenArmor,0);
  for(let i=0;i<5;i++)assert(changeEquipment(c,{type:'equip',slot:'chest',itemId:'linenArmor'}).error);
  c.hp=115;
  assert(!changeEquipment(c,{type:'unequip',slot:'chest'}).error);assert.equal(c.hp,100);assert.equal(c.maxHp,100);
  assert(changeEquipment(c,{type:'unequip',slot:'chest'}).error);assert.equal(c.inventory.linenArmor,1);
  c.hp=0;assert(changeEquipment(c,{type:'equip',slot:'mainHand',itemId:'trainingSword'}).error);
  c.hp=100;changeEquipment(c,{type:'equip',slot:'mainHand',itemId:'trainingSword'});
  const view=characterView(c);view.equipment.mainHand=null;view.inventory.trainingSword=999;
  assert.equal(c.equipment.mainHand,'trainingSword');assert.equal(c.inventory.trainingSword,0);
  assert(!JSON.stringify(characterView(c)).includes('tokenHash'));
});

test('original-model display does not decide attack/armor; the server applies gear to real combat and preserves it at level-up',()=>{
  const c=character(),events=[];
  for(const [slot,itemId] of [['mainHand','trainingSword'],['chest','linenArmor'],['feet','travelerBoots']])changeEquipment(c,{type:'equip',slot,itemId});
  const ws={character:c,player:{id:c.id,x:WORLD.spawn.x+50,y:WORLD.spawn.y+20,attackAt:-700},input:{x:0,y:0}};
  syncPlayerStats(ws);
  const room=new CombatRoom('GEAR',WORLD,'camp',new Map([[c.id,ws]]),{changed(){},emit:e=>events.push(e),notice(){}});
  room.attack(ws,room.monster.id,1000);assert.equal(room.monster.hp,36);
  room.tick(1000,0);assert.equal(c.hp,96);assert.equal(events.find(e=>e.action==='player-hit').damage,4);
  c.xp=30;room.attack(ws,room.monster.id,1800);room.attack(ws,room.monster.id,2600);
  assert.equal(c.level,2);assert.equal(c.maxHp,140);assert.equal(c.hp,140);
  assert.equal(c.inventory.wolfPelt,1);assert.equal(c.equipment.chest,'linenArmor');
  assert.deepEqual(equipmentStats(c),{attack:24,armor:2,maxHp:140});
});

test('v1 saves migrate additively once with an exact backup; credentials, position and rewards survive reload',t=>{
  const dir=folder(t),file=join(dir,'characters.json'),old=new CharacterStore(file).resolveCharacter('旧角色');
  const legacy=JSON.parse(readFileSync(file,'utf8')); legacy.version=1;
  const c=legacy.characters[0]; delete c.equipment;c.inventory={wolfPelt:37};c.gold=215;c.xp=90;c.level=2;c.hp=74;c.maxHp=120;c.positions={resources:{x:220,y:100}};
  const original=JSON.stringify(legacy,null,2);writeFileSync(file,original);
  const migrated=new CharacterStore(file);assert.equal(readFileSync(file,'utf8'),original,'Reading alone does not replace a save');
  const resumed=migrated.resolveCharacter('ignored',old.record.id,old.resumeToken).record;
  assert.equal(resumed.inventory.wolfPelt,37);assert.equal(resumed.inventory.trainingSword,1);assert.equal(resumed.hp,74);assert.equal(resumed.gold,215);
  assert.deepEqual(resumed.positions,{resources:{x:220,y:100}});migrated.flush();
  const backups=readdirSync(dir).filter(name=>name.includes('.v1-backup-'));
  assert.equal(backups.length,1);assert.equal(readFileSync(join(dir,backups[0]),'utf8'),original);
  changeEquipment(resumed,{type:'equip',slot:'mainHand',itemId:'trainingSword'});migrated.touch(resumed);migrated.flush();
  const reloaded=new CharacterStore(file).resolveCharacter('ignored',old.record.id,old.resumeToken).record;
  assert.equal(reloaded.inventory.trainingSword,0);assert.equal(reloaded.equipment.mainHand,'trainingSword');
  assert.equal(readdirSync(dir).filter(name=>name.includes('.v1-backup-')).length,1);
  assert.equal(JSON.parse(readFileSync(file,'utf8')).version,2);
});

test('invalid equipment saves fail without replacing the file or creating a migration backup',t=>{
  const dir=folder(t),file=join(dir,'characters.json');new CharacterStore(file).resolveCharacter('坏装备');
  const data=JSON.parse(readFileSync(file,'utf8'));data.characters[0].equipment.chest='trainingSword';
  const raw=JSON.stringify(data);writeFileSync(file,raw);
  assert.throws(()=>new CharacterStore(file),/装备存档无效/);assert.equal(readFileSync(file,'utf8'),raw);
  assert.equal(readdirSync(dir).length,1);
  const invalidUtf8=Buffer.from('{"version":1,"characters":[],"note":"x"}');invalidUtf8[invalidUtf8.indexOf(120)]=255;writeFileSync(file,invalidUtf8);
  assert.throws(()=>new CharacterStore(file),/无法读取/);assert.deepEqual(readFileSync(file),invalidUtf8);
  assert.equal(readdirSync(dir).length,1);
});

test('bag selections follow actual saved ownership and clear stale details after an equip',()=>{
  const c=character();c.inventory.wolfPelt=8;
  assert.equal(bagEntries(c).length,4);assert.equal(bagEntries(c).find(i=>i.id==='wolfPelt').quantity,8);
  assert.equal(inventorySelection(c,{id:'trainingSword'}).equipped,false);
  changeEquipment(c,{type:'equip',slot:'mainHand',itemId:'trainingSword'});
  assert.equal(inventorySelection(c,{id:'trainingSword'}),null);
  assert.equal(inventorySelection(c,{slot:'mainHand'}).item.id,'trainingSword');
  assert.equal(inventorySelection(c,{id:'missing'}),null);
});

async function connect(url,name,credentials={}) {
  const ws=new WebSocket(url),messages=[];ws.on('message',raw=>messages.push(JSON.parse(raw)));
  await once(ws,'open');
  const client={ws,messages,send:data=>ws.send(JSON.stringify(data)),
    wait(predicate,after=0){const existing=messages.slice(after).find(predicate);if(existing)return Promise.resolve(existing);return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{ws.off('message',read);reject(new Error('Inventory socket timeout'));},3000);
      const read=raw=>{const msg=JSON.parse(raw);if(predicate(msg)){clearTimeout(timer);ws.off('message',read);resolve(msg);}};ws.on('message',read);
    });}};
  client.send({type:'join',name,room:'GEAR-01',...credentials});client.welcome=await client.wait(m=>m.type==='welcome');return client;
}

test('two clients see authoritative gear stats, other inventories stay private, saves survive server restart and casts reject gear changes',async t=>{
  const file=join(folder(t),'characters.json');let game;
  async function start(){game=createGameServer({saveFile:file});game.server.listen(0,'127.0.0.1');await once(game.server,'listening');return `ws://127.0.0.1:${game.server.address().port}/ws`;}
  t.after(()=>game.close());
  const url=await start(),a=await connect(url,'装备甲'),b=await connect(url,'装备乙');
  let mark=a.messages.length;a.send({type:'equip',slot:'mainHand',itemId:'trainingSword',attack:9999,quantity:900});
  const changed=await a.wait(m=>m.type==='progress'&&m.character.equipment.mainHand==='trainingSword',mark);
  assert.equal(changed.character.stats.attack,24);assert.equal(changed.character.inventory.trainingSword,0);
  const observed=await b.wait(m=>m.type==='state'&&m.players.find(p=>p.id===a.welcome.id)?.stats.attack===24);
  assert.equal(observed.players.find(p=>p.id===a.welcome.id).equipment.mainHand,'trainingSword');
  assert(!JSON.stringify(observed).includes('inventory'));assert.equal(b.welcome.character.inventory.trainingSword,1);
  mark=a.messages.length;a.send({type:'equip',slot:'mainHand',itemId:'trainingSword'});await a.wait(m=>m.type==='notice'&&m.message.includes('已穿戴'),mark);
  const room=[...game.combatRooms.values()][0],live=[...game.rooms.values()][0].get(a.welcome.id);
  room.skill(live,'fireball',room.monster.id,Date.now());
  mark=a.messages.length;a.send({type:'unequip',slot:'mainHand'});await a.wait(m=>m.type==='notice'&&m.message.includes('施法时'),mark);
  assert.equal(live.character.inventory.trainingSword,0);
  await game.close();
  const resumed=await connect(await start(),'装备甲',{characterId:a.welcome.id,resumeToken:a.welcome.resumeToken});
  assert.equal(resumed.welcome.character.equipment.mainHand,'trainingSword');assert.equal(resumed.welcome.character.inventory.trainingSword,0);
  mark=resumed.messages.length;resumed.send({type:'unequip',slot:'mainHand'});
  const removed=await resumed.wait(m=>m.type==='progress'&&m.character.equipment.mainHand===null,mark);
  assert.equal(removed.character.stats.attack,20);assert.equal(removed.character.inventory.trainingSword,1);
});
