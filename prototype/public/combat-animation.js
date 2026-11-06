import { playCharacterAction, respawnCharacterAnimation } from './character-animation.js';

// This consumes confirmed server results, never the local attack button.
export function applyCombatAnimations(event, findView, now) {
  const at = Number.isFinite(event.serverTime) ? event.serverTime : now;
  const actor = findView(event.attackerId), victim = findView(event.targetId);
  if (event.action === 'hit' || event.action === 'player-hit') {
    if (actor) playCharacterAction(actor.body, 'attack', { at, now, attackSeconds: actor.attackSeconds });
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
