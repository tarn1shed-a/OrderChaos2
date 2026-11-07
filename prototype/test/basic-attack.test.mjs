import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync,mkdtempSync,writeFileSync,readdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {matchesCombo,chooseBasicAttack,initialBasicAttack,loadGameplay} from '../game/basic-attack.mjs';
import {CharacterStore} from '../game/character-store.mjs';
import {changeEquipment} from '../game/equipment.mjs';
import {CombatRoom,syncPlayerStats} from '../game/combat.mjs';
import {RESOURCE_WORLD} from '../public/world.js';

const row=(skillId,nextSkillId,extra={})=>({id:nextSkillId,skillId,nextSkillId,reqMainWeaponType:0x30001,
  reqOffWeaponType:0xffff,isNormalAttack:1,timeOutTime:2000,timeOutSkill:84,probability:0,summonNormalSkill:0,...extra});
const profile={weapons:{staff:{word:0x30001,allowedProfessions:[2,4]}},skills:{
  84:{id:84,reqProfession:2,clip:'attack_84'},85:{id:85,reqProfession:2,clip:'attack_85'},86:{id:86,reqProfession:2,clip:'attack_86'},
  424:{id:424,reqProfession:4,clip:'attack_424'}},comboRows:[row(0,84),row(0,424),row(84,85),row(84,86)]};
const mage={profession:2,equipment:{mainHand:'staff'}};
test('native filter distinguishes profession enums, empty hands, offhand fallback and exact weapon types',()=>{
  assert(matchesCombo(row(0,84),profile.skills,0x30001,0xffff,2));
  assert(!matchesCombo(row(0,84),profile.skills,0x30001,0xffff,4));
  assert(!matchesCombo(row(0,84),profile.skills,0x60001,0xffff,2));
  assert(!matchesCombo(row(0,84,{reqMainWeaponType:0xffff}),profile.skills,0x30001,0xffff,2));
  const off=row(0,84,{reqMainWeaponType:0xffff,reqOffWeaponType:0x10000});
  assert(matchesCombo(off,profile.skills,0xffff,0x10000,2));
  assert(matchesCombo(off,profile.skills,0x30001,0x10000,2));
  assert(!matchesCombo(off,profile.skills,0x30001,0x10000,2,true));
  const any={84:{reqProfession:7}};assert(matchesCombo(row(0,84),any,0x30001,0xffff,5));
});
test('first starter, independent branch draws, source timeout and loadout reset are server decisions',()=>{
  const first=chooseBasicAttack(profile,mage,null,1000,()=>0);assert.equal(first.skill.id,84);
  assert.equal(initialBasicAttack(profile,{...mage,profession:4}).id,424);
  const values=[0,.99,0],prepared=chooseBasicAttack(profile,mage,null,1000,()=>values.shift());
  assert.equal(prepared.skill.id,84);assert.equal(prepared.slot.id,86);assert.equal(values.length,0);
  assert.equal(chooseBasicAttack(profile,mage,prepared.state,1700).skill.id,86);
  assert.equal(chooseBasicAttack(profile,mage,first.state,3000).skill.id,85);
  assert.equal(chooseBasicAttack(profile,mage,first.state,3001).skill.id,84);
  const changed=chooseBasicAttack(profile,{...mage,profession:4},first.state,1700);assert.equal(changed.skill.id,424);
  assert(chooseBasicAttack(profile,{...mage,profession:1},null,1000).error);
});
test('v4 migrates once, preserving credentials, HP, rewards, equipment and hotbar without overwriting source bytes',t=>{
  const dir=mkdtempSync(join(tmpdir(),'oc2-native-save-'));t.after(()=>rmSync(dir,{recursive:true,force:true}));
  const file=join(dir,'save.json'),store=new CharacterStore(file),id=store.resolveCharacter('保存测试');
  const raw=JSON.parse(readFileSync(file,'utf8'));raw.version=4;const c=raw.characters[0];
  delete c.profession;delete c.inventory.trainingStaff;delete c.inventory.trainingGreatsword;
  c.hp=78;c.xp=90;c.level=2;c.maxHp=120;c.gold=30;c.kills=3;c.inventory.wolfPelt=3;
  const bytes=JSON.stringify(raw);writeFileSync(file,bytes);
  const migrated=new CharacterStore(file),r=migrated.resolveCharacter('ignored',id.record.id,id.resumeToken,1).record;
  assert.equal(readFileSync(file,'utf8'),bytes);assert.equal(r.profession,2);assert.equal(r.inventory.trainingStaff,1);
  const {profession,...rest}=r;delete rest.inventory.trainingStaff;delete rest.inventory.trainingGreatsword;
  assert.deepEqual(rest,c);r.inventory.trainingStaff=1;r.inventory.trainingGreatsword=1;migrated.flush();
  assert.equal(readFileSync(join(dir,readdirSync(dir).find(n=>n.includes('v4-backup'))),'utf8'),bytes);
  assert.equal(JSON.parse(readFileSync(file,'utf8')).version,5);
  assert.equal(new CharacterStore(file).resolveCharacter('',r.id,id.resumeToken).record.profession,2);
  assert.throws(()=>new CharacterStore().resolveCharacter('invalid',undefined,undefined,7),/职业/);
});
const sourcePath=new URL('../../game-data/converted/gameplay/native.json',import.meta.url);
test('actual class/weapon rows drive confirmed combat; legacy sword is explicit and changing gear resets combo',{skip:!existsSync(sourcePath)},()=>{
  const p=loadGameplay();
  for(const [profession,item,id]of [[2,'trainingStaff',84],[4,'trainingStaff',424],[1,'trainingGreatsword',66],[5,'trainingGreatsword',66]]){
    const store=new CharacterStore(),c=store.resolveCharacter('native',undefined,undefined,profession).record;
    assert(!changeEquipment(c,{type:'equip',slot:'mainHand',itemId:item}).error);
    assert.equal(initialBasicAttack(p,c).id,id);
    const ws={character:c,player:{id:c.id,x:RESOURCE_WORLD.spawn.x+50,y:RESOURCE_WORLD.spawn.y+20,attackAt:-700}};
    syncPlayerStats(ws);const events=[],notices=[];
    const room=new CombatRoom('native',RESOURCE_WORLD,'resources',new Map([[c.id,ws]]),{gameplay:p,random:()=>0,changed(){},emit:e=>events.push(e),notice:(_,s)=>notices.push(s)});
    room.attack(ws,room.monster.id,1000);assert.equal(events[0].basicAttack.id,id);assert.equal(ws.player.basicAttack.id,id);
    const next=chooseBasicAttack(p,c,ws.basicCombo,1700,()=>0);assert(next.skill?.clip);
    assert.notEqual(next.skill.id,id);
    assert.equal(initialBasicAttack(p,{...c,equipment:{mainHand:null}}).id,4);
    assert(initialBasicAttack(p,{...c,equipment:{mainHand:'trainingSword'}}).error);
    assert.equal(notices.length,0);
  }
});
