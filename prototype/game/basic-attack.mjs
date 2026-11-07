import {readFileSync,existsSync} from 'node:fs';
const EMPTY=0xffff;
export function loadGameplay(path=new URL('../../game-data/converted/gameplay/native.json',import.meta.url)) {
  if(!existsSync(path))return null;
  const profile=JSON.parse(readFileSync(path,'utf8'));
  if(profile.format!=='oc2-native-gameplay-v6'||!Array.isArray(profile.comboRows)||
    !profile.skills||!profile.weapons||profile.comboRows.some(r=>r.isNormalAttack!==1||
      !['id','skillId','nextSkillId','reqMainWeaponType','reqOffWeaponType','timeOutTime','timeOutSkill','probability','summonNormalSkill'].every(k=>Number.isSafeInteger(r[k])&&r[k]>=0)))throw new Error('原版普攻数据无效，请重新构建本地资源');
  if(profile.casting?.format!=='oc2-native-cast-v2'||!profile.casting.spells?.fireball||!profile.casting.spells?.frost_blast||!profile.casting.spells?.arcane_missile)throw new Error('原版施法资源缺失，请整体重建本地资源');
  if(profile.combat?.format!=='oc2-native-combat-v1'||!profile.combat.auras?.burn||!profile.combat.auras?.freeze||
    profile.combat.mechanics?.burnDurationMs!==7000||profile.combat.mechanics?.freezeDurationMs!==2000||profile.combat.mechanics?.burnTicks!==5||profile.combat.mechanics?.arcaneBurnBonus!==.5)throw new Error('原版战斗资料缺失，请整体重建本地资源');
  if(profile.npc?.format!=='oc2-npc-evidence-v1'||profile.npc.navigation?.format!=='oc2-source-navigation-v1')throw new Error('原版NPC与导航资料缺失，请整体重建本地资源');
  return profile;
}
// Direct reconstruction of filter 0x5bf5d0. 0xffff means empty, not any weapon.
export function matchesCombo(row,skills,main,off,profession,flag=false) {
  const proto=skills[row.skillId||row.nextSkillId];
  if(proto&&![0,7,profession].includes(proto.reqProfession))return false;
  if(main===row.reqMainWeaponType&&off===row.reqOffWeaponType)return true;
  if(((main&off)&0xffff)===EMPTY&&(row.reqMainWeaponType&0xffff)===EMPTY&&(row.reqOffWeaponType&0xffff)===EMPTY)return true;
  if(!flag&&(off&0xffff)!==EMPTY&&(row.reqMainWeaponType&0xffff)===EMPTY)return off===row.reqOffWeaponType;
  return (main&0xffff)!==EMPTY&&(row.reqOffWeaponType&0xffff)===EMPTY&&main===row.reqMainWeaponType;
}
function context(profile,character) {
  const item=character.equipment?.mainHand,weapon=item?profile.weapons[item]:null;
  if(item&&(!weapon||weapon.legacy))return {error:'这把旧版单手剑没有已核实的普通攻击入口，请卸下或换用法杖、大剑'};
  if(weapon&&!weapon.allowedProfessions.includes(character.profession))return {error:'当前职业不能使用这件武器'};
  return {main:weapon?.word??EMPTY,off:EMPTY,profession:character.profession??2,key:`${character.profession??2}:${item||''}`};
}
function candidates(profile,ctx,id) {
  return profile.comboRows.filter(r=>r.skillId===id&&r.nextSkillId!==0&&r.summonNormalSkill!==1&&
    matchesCombo(r,profile.skills,ctx.main,ctx.off,ctx.profession));
}
function pick(rows,random){
  if(!rows.length)return null;
  const sum=rows.reduce((s,r)=>s+(r.probability||50),0);
  return rows.find(r=>Math.floor(random()*(sum+1))<(r.probability||50))||rows[0];
}
export function prepareBasicAttack(profile,character,random=Math.random){
  if(!profile)return {state:null,slot:null};
  const ctx=context(profile,character);if(ctx.error)return {state:null,slot:ctx};
  // Live equipment path 0x5c11bc uses the weighted group selector, including
  // the initial group. The previously traced first-match helper is unused here.
  const starter=pick(candidates(profile,ctx,0),random),skill=starter&&profile.skills[starter.nextSkillId];
  if(!skill?.clip)return {state:null,slot:{error:'这个职业与武器的普攻动作尚未恢复'}};
  return {state:{key:ctx.key,starter,currentRow:starter,expiresAt:Infinity},slot:{...skill}};
}
export function initialBasicAttack(profile,character) {
  return prepareBasicAttack(profile,character).slot;
}
export function chooseBasicAttack(profile,character,previous,now,random=Math.random) {
  if(!profile)return {skill:null,state:null,slot:null}; // Explicit source-free prototype mode.
  const ctx=context(profile,character);if(ctx.error)return ctx;
  let state=previous?.key===ctx.key&&previous.currentRow?previous:prepareBasicAttack(profile,character,random).state;
  if(!state)return {error:'这个职业与武器的普攻动作尚未恢复'};
  // 0x5bf9b4 uses strict > and restores the stored starter, not timeOutSkill
  // (that field belongs to the separate bank-2/3 temporary-slot path).
  const row=now>state.expiresAt?state.starter:state.currentRow;
  const skill=profile.skills[row.nextSkillId];
  if(!skill?.clip)return {error:'这段原版普攻动作尚未恢复'};
  const currentRow=pick(candidates(profile,ctx,skill.id),random)||state.starter;
  const duration=Math.max(0,skill.durationMs||0),timeout=currentRow.timeOutTime;
  state={...state,currentRow,id:skill.id,at:now,expiresAt:timeout>0?now+duration+timeout:Infinity};
  return {skill,state,slot:{...profile.skills[currentRow.nextSkillId]}};
}
export function updateBasicAttack(profile,ws,now){
  const state=ws.basicCombo;
  if(state&&now>state.expiresAt){
    state.currentRow=state.starter;state.expiresAt=Infinity;
    ws.player.basicSlot={...profile.skills[state.starter.nextSkillId]};
  }
}
