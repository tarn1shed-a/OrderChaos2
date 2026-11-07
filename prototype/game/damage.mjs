// Explicit local resolver. The original client's damage-display coefficients
// do not establish a server armor/critical/resistance formula.
export function resolveDamage({base,armor=0,bonus=0,damageType=null,damageAttribute=null},hp){
  if(![base,armor,bonus,hp].every(Number.isFinite)||base<0||armor<0||bonus<0||hp<0)throw new Error('无效伤害属性');
  const raw=Math.round(Math.max(0,base-armor)*(1+bonus));
  const damage=Math.min(hp,base>0?Math.max(1,raw):0);
  return {damage,targetHp:hp-damage,damageType,damageAttribute,bonus,damageRule:'local-v2'};
}
