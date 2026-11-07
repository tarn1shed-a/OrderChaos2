import { playCharacterAction, respawnCharacterAnimation, playCharacterSkill, cancelCharacterSkill } from './character-animation.js';

// This consumes confirmed server results, never the local attack button.
export function applyCombatAnimations(event, findView, now) {
  const at = Number.isFinite(event.serverTime) ? event.serverTime : now;
  const actor = findView(event.attackerId), victim = findView(event.targetId);
  if (['skill-cast','skill-stage'].includes(event.action) && actor) {
    playCharacterSkill(actor.body, event.cast, { now });
    if (victim) actor.combatFacing = Math.atan2(victim.root.position.x-actor.root.position.x, victim.root.position.z-actor.root.position.z);
  } else if (event.action === 'skill-cancel' && actor) cancelCharacterSkill(actor.body, event.castId);
  else if (['hit','player-hit','skill-hit','periodic-hit'].includes(event.action)) {
    if (actor && ['hit','player-hit'].includes(event.action)) playCharacterAction(actor.body, 'attack', { at, now, attackSeconds: actor.attackSeconds,basicAttack:event.basicAttack });
    if (victim) playCharacterAction(victim.body, event.targetHp <= 0 ? 'death' : 'hurt', { at, now });
    if (actor && victim) {
      const target = victim.target || victim.root.position;
      actor.combatFacing = Math.atan2(target.x - actor.root.position.x, target.z - actor.root.position.z);
    }
  } else if (event.action === 'kill' && victim) {
    playCharacterAction(victim.body, 'death', { at, now });
  } else if (event.action === 'respawn' && victim) {
    respawnCharacterAnimation(victim.body, { at, now });
  }
}
