// AttributePage.SetAttributeValueHp / scrollUp_ac / scrollDown_ac.
export function sourceHPFrame(current,maximum){
  let ratio=maximum===0||current>maximum?1:current/maximum;
  ratio=Math.max(.02,Math.min(1,ratio));return Math.max(1,Math.trunc(ratio*60));
}
export function sourceScrollRatio(ratio,direction){
  if(direction===0)return ratio;
  return direction<0?ratio-(ratio>.1?.1:ratio):ratio+(ratio<.9?.1:1-ratio);
}
export function attributeRoleValues(character,xp){
  const number=value=>Number.isFinite(value)?value.toLocaleString('en-US'):'';
  const values={name:character.name,level:number(character.level),hp:`${number(character.hp)} / ${number(character.maxHp)}`,armor:number(character.stats?.armor)};
  if(Number.isFinite(xp?.value)&&xp.max>0)values.xp=`${number(xp.value)} / ${number(xp.max)}`;
  return values;
}
//31f178 defaults and9d4c48 low-byte-red consumption. The current trial role
//selects an existing table entry; this does not choose an original new-role look.
export function previewColors(profile,look){
 const result={hair:[1,1,1],skin:[1,1,1],eye:[0,0,0]};
 if(!look)return result;
 for(const [kind,key]of [['hair','hairColor'],['skin','skinColor']]){
  const row=profile.colors?.[kind]?.[look[key]],value=row?.sourcePair?.[0];
  if(!row||!Number.isInteger(value)||value<0||value>0xffffff)throw Error('原人物颜色引用不完整');
  result[kind]=[0,8,16].map(shift=>Math.fround((value>>>shift&255)*Math.fround(1/255)));
 }
 return result;
}
