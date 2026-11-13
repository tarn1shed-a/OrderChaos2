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
