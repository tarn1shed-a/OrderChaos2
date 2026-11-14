// Read-only inputs for the source-drawn panel. No progression calculations.
const finite=v=>typeof v==='number'&&Number.isFinite(v);
function matchedSource(roleId,profession,source){
  if(!source||source.roleId!==roleId)return null;
  const originalProfession=source.attributes?.[127];
  if(originalProfession!==undefined&&originalProfession!==profession)return null;
  return source;
}
export function sourcePanelValues(role,source=null,trialXP=null){
  const input=matchedSource(role.id,role.profession,source),a=input?.attributes;
  const level=finite(a?.[77])?a[77]:role.level,values={name:role.name,level,hp:role.hp,maxHp:role.maxHp,armor:role.stats?.armor,profession:role.profession,
    xp:null,upgradeXp:null,xpOrigin:null,skillPoints:finite(a?.[145])?a[145]:null};
  if(finite(a?.[77])&&finite(a?.[138])&&finite(a?.[139])){values.xp=a[77]===55?a[139]:a[138];values.upgradeXp=a[139];values.xpOrigin='original-message';}
  else if(finite(trialXP?.value)&&finite(trialXP?.max)){values.xp=trialXP.value;values.upgradeXp=trialXP.max;values.xpOrigin='existing-trial-progress';}
  return values;
}
export function sourceProfessionSkills(profile,profession,source=null,roleId=null){
  const rows=profile.catalogs?.[String(profession)];if(!Array.isArray(rows)||![1,2,3,4,5].includes(profession))return [];
  const incoming=matchedSource(roleId,profession,source),records=incoming?.learning;
  const known=Array.isArray(records),learned=new Map();
  if(known)for(const pair of records){if(!Array.isArray(pair)||pair.length!==2||!Number.isInteger(pair[0])||!Number.isInteger(pair[1])||pair[1]<0||pair[1]>3)throw Error('原学习记录无效');if(!learned.has(pair[0]))learned.set(pair[0],new Set());learned.get(pair[0]).add(pair[1]);}
  const level=incoming?.attributes?.[77];
  return rows.map(row=>({...row,runes:row.runes.map(r=>({...r,
    learned:known?Boolean(learned.get(row.skillId)?.has(r.index)):null,
    locked:finite(level)?level<r.requirement.needlevel:null}))}));
}
export function sourceXPFrame(ratio,totalFrames){
  if(!finite(ratio)||!Number.isInteger(totalFrames)||totalFrames<1)throw Error('原经验绘图输入无效');
  const p=Math.min(1,Math.max(.02,ratio));return{frame:Math.max(1,Math.trunc(totalFrames*p)),scale:p};
}
