import {readFileSync,existsSync} from 'node:fs';
const EMPTY=0xffff;
export function loadGameplay(path=new URL('../../game-data/converted/gameplay/native.json',import.meta.url)) {
  if(!existsSync(path))return null;
  const profile=JSON.parse(readFileSync(path,'utf8'));
  if(profile.format!=='oc2-native-gameplay-v1'||!Array.isArray(profile.comboRows)||
    !profile.skills||!profile.weapons||profile.comboRows.some(r=>r.isNormalAttack!==1||
      !['id','skillId','nextSkillId','reqMainWeaponType','reqOffWeaponType','timeOutTime','timeOutSkill','probability','summonNormalSkill'].every(k=>Number.isSafeInteger(r[k])&&r[k]>=0)))throw new Error('原版普攻数据无效，请重新构建本地资源');
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
export function initialBasicAttack(profile,character) {
  if(!profile)return null;
  const ctx=context(profile,character);if(ctx.error)return ctx;
  const row=candidates(profile,ctx,0)[0],skill=row&&profile.skills[row.nextSkillId];
  return skill?.clip?{...skill,contextKey:ctx.key}: {error:'这个职业与武器的普攻动作尚未恢复'};
}
export function chooseBasicAttack(profile,character,previous,now,random=Math.random) {
  if(!profile)return {skill:null,state:null}; // Explicit source-free prototype mode.
  const ctx=context(profile,character);if(ctx.error)return ctx;
  let rows=previous?.key===ctx.key?candidates(profile,ctx,previous.id):[];
  const timeout=rows[0];
  let row;
  if(timeout&&timeout.timeOutTime>0&&now-previous.at>=timeout.timeOutTime) {
    // Timer orchestration is a web adaptation, not a proven native timer caller.
    const skill=profile.skills[timeout.timeOutSkill];
    if(skill?.clip)return {skill,state:{id:skill.id,at:now,key:ctx.key}};
    rows=[];
  }
  if(!rows.length)row=candidates(profile,ctx,0)[0];
  else {
    // 0x5bef40 draws once per candidate and falls back to the first. It is not
    // cumulative weighted selection. Native RNG(min,max) excludes max.
    const sum=rows.reduce((s,r)=>s+(r.probability||50),0);
    row=rows.find(r=>Math.floor(random()*(sum+1))<(r.probability||50))||rows[0];
  }
  const skill=row&&profile.skills[row.nextSkillId];
  if(!skill?.clip)return {error:'这段原版普攻动作尚未恢复'};
  return {skill,state:{id:skill.id,at:now,key:ctx.key}};
}
