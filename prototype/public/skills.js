// Original clip/effect identities, with intentionally local prototype combat rules.
const BASE_SKILLS = Object.freeze({
  fireball: Object.freeze({ id: 'fireball', name: '火球术', key: 'Digit1', hotkey: '1', clip: 'skill_fireball',
    damage: 30, range: 90, cooldownMs: 3000, castMs: 500, flightMs: 350, effect: 'fireball' }),
  arcane_missile: Object.freeze({id:'arcane_missile',name:'奥术飞弹',key:'Digit3',hotkey:'3',clip:'skill_arcane_missile',damage:8,range:90,cooldownMs:4000,castMs:0,flightMs:250,effect:'arcane_missile'}),
  frost_blast: Object.freeze({ id: 'frost_blast', name: '冰霜爆破', key: 'Digit2', hotkey: '2', clip: 'skill_frost_blast',
    damage: 20, range: 60, cooldownMs: 5000, castMs: 700, flightMs: 0, slowMs: 2500, slowFactor: .5, effect: 'frost_blast' }),
});
export let SKILLS=BASE_SKILLS;
// Browser presentation follows the same recovered stage/cooldown table as its
// server. Source-free camp tests keep the explicit prototype definitions.
export function configureSkills(casting){
  SKILLS=Object.freeze(Object.fromEntries(Object.entries(BASE_SKILLS).map(([id,base])=>{
    const source=casting?.spells[id];return [id,source?Object.freeze({...base,castMs:source.chantMs,cooldownMs:source.cooldownMs,commonCD:source.commonCD,clip:source.visuals[source.channelMs>0?'3':'2']?.pre?.clip||base.clip,name:source.displayName||base.name}):base];
  })));
}
export function skillById(id) { return typeof id === 'string' && Object.hasOwn(SKILLS, id) ? SKILLS[id] : null; }
