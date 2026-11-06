// Original clip/effect identities, with intentionally local prototype combat rules.
export const SKILLS = Object.freeze({
  fireball: Object.freeze({ id: 'fireball', name: '火球术', key: 'Digit1', hotkey: '1', clip: 'skill_fireball',
    damage: 30, range: 90, cooldownMs: 3000, castMs: 500, flightMs: 350, effect: 'fireball' }),
  frost_blast: Object.freeze({ id: 'frost_blast', name: '冰霜爆破', key: 'Digit2', hotkey: '2', clip: 'skill_frost_blast',
    damage: 20, range: 60, cooldownMs: 5000, castMs: 700, flightMs: 0, slowMs: 2500, slowFactor: .5, effect: 'frost_blast' }),
});
export function skillById(id) { return typeof id === 'string' && Object.hasOwn(SKILLS, id) ? SKILLS[id] : null; }
