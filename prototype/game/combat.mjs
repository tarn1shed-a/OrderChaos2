import { advance, walkable } from '../public/world.js';

export const COMBAT = Object.freeze({ playerDamage: 20, playerCooldownMs: 700, monsterHp: 60, monsterDamage: 6,
  monsterCooldownMs: 1000, monsterRespawnMs: 8000, playerRespawnMs: 4000,
  reward: Object.freeze({ xp: 30, gold: 10, wolfPelt: 1 }) });

export function syncPlayerStats(ws) {
  Object.assign(ws.player, { level: ws.character.level, hp: ws.character.hp, maxHp: ws.character.maxHp });
}

export class CombatRoom {
  constructor(key, world, scene, clients, { changed, emit, notice }) {
    this.world = world; this.scene = scene; this.clients = clients; this.changed = changed; this.emit = emit; this.notice = notice;
    this.range = scene === 'resources' ? 32 : 95;
    this.monsterSpeed = scene === 'resources' ? 14 : 70;
    this.monsterRange = scene === 'resources' ? 12 : 35;
    let spawn = { x: world.spawn.x + 50, y: world.spawn.y + 20 };
    if (!walkable(spawn.x, spawn.y, world)) spawn = { ...world.spawn };
    this.spawn = spawn;
    this.monster = { id: `${key}:wolf-1`, kind: 'wolf', name: '营地野狼', ...spawn, hp: COMBAT.monsterHp, maxHp: COMBAT.monsterHp,
      alive: true, respawnAt: 0, attackAt: 0, animation: { attackAt: null, hitAt: null, deathAt: null } };
    this.contributors = new Set();
  }

  snapshot() { return [{ ...this.monster, animation: { ...this.monster.animation } }]; }

  attack(ws, targetId, now) {
    const m = this.monster;
    if (typeof targetId !== 'string' || targetId !== m.id) return this.notice(ws, '目标不在当前营地');
    if (ws.player.hp <= 0) return this.notice(ws, '倒地后稍等片刻，会自动回到出生点');
    if (!m.alive) return this.notice(ws, '野狼已被击败，稍后会重新出现');
    if (Math.hypot(ws.player.x - m.x, ws.player.y - m.y) > this.range) return this.notice(ws, '距离太远，先靠近野狼');
    if (now - ws.player.attackAt < COMBAT.playerCooldownMs) return this.notice(ws, '攻击尚在冷却中');
    ws.player.attackAt = now;
    ws.player.animation ||= { attackAt: null, hitAt: null, deathAt: null };
    ws.player.animation.attackAt = now;
    this.contributors.add(ws.player.id);
    const damage = Math.min(COMBAT.playerDamage, m.hp); m.hp -= damage;
    m.animation.hitAt = now;
    if (m.hp <= 0) m.animation.deathAt = now;
    this.emit({ type: 'combat', action: 'hit', attackerId: ws.player.id, targetId: m.id, damage, targetHp: m.hp, serverTime: now });
    if (m.hp > 0) return;

    // Mark death before awarding. Further messages cannot perform a second living→dead transition.
    m.alive = false; m.respawnAt = now + COMBAT.monsterRespawnMs;
    for (const id of this.contributors) {
      const recipient = this.clients.get(id);
      if (!recipient || recipient.player.hp <= 0) continue;
      const c = recipient.character, oldLevel = c.level;
      c.xp += COMBAT.reward.xp; c.gold += COMBAT.reward.gold; c.kills++;
      c.inventory.wolfPelt += COMBAT.reward.wolfPelt;
      c.level = 1 + Math.floor(c.xp / 60); c.maxHp = 100 + (c.level - 1) * 20;
      if (c.level > oldLevel) c.hp = c.maxHp;
      syncPlayerStats(recipient);
      this.changed(recipient, true);
      this.notice(recipient, `击败野狼：经验 +30，金币 +10，狼皮 +1${c.level > oldLevel ? `；升至 ${c.level} 级，生命恢复` : ''}`);
    }
    this.emit({ type: 'combat', action: 'kill', attackerId: ws.player.id, targetId: m.id, targetHp: 0, serverTime: now, rewards: { ...COMBAT.reward } });
    this.contributors.clear();
  }

  tick(now, dt) {
    for (const ws of this.clients.values()) {
      if (ws.player.hp <= 0 && ws.player.deadUntil && now >= ws.player.deadUntil) {
        ws.character.hp = ws.character.maxHp; syncPlayerStats(ws);
        ws.player.x = this.world.spawn.x; ws.player.y = this.world.spawn.y; ws.player.deadUntil = 0;
        ws.player.animation = { attackAt: null, hitAt: null, deathAt: null };
        ws.input = { x: 0, y: 0 }; this.changed(ws, true);
        this.emit({ type: 'combat', action: 'respawn', attackerId: null, targetId: ws.player.id, targetHp: ws.player.hp, serverTime: now });
      }
    }
    const m = this.monster;
    if (!m.alive) {
      if (now >= m.respawnAt) {
        Object.assign(m, this.spawn, { hp: m.maxHp, alive: true, respawnAt: 0, attackAt: 0,
          animation: { attackAt: null, hitAt: null, deathAt: null } }); this.contributors.clear();
        this.emit({ type: 'combat', action: 'respawn', attackerId: null, targetId: m.id, targetHp: m.hp, serverTime: now });
      }
      return;
    }
    // This first encounter is passive until attacked. Nearby contributors then share its attention.
    const targets = [...this.clients.values()].filter(ws => ws.player.hp > 0 && this.contributors.has(ws.player.id))
      .map(ws => ({ ws, distance: Math.hypot(ws.player.x - m.x, ws.player.y - m.y) }))
      .sort((a, b) => a.distance - b.distance);
    const target = targets[0];
    const leash = this.scene === 'resources' ? 220 : 360;
    if (!target || target.distance > leash) {
      const dx = this.spawn.x - m.x, dy = this.spawn.y - m.y, d = Math.hypot(dx, dy);
      if (d > 1) advance(m, { x: dx / d, y: dy / d }, dt, { ...this.world, speed: this.monsterSpeed });
      return;
    }
    if (target.distance > this.monsterRange) {
      advance(m, { x: (target.ws.player.x - m.x) / target.distance, y: (target.ws.player.y - m.y) / target.distance }, dt, { ...this.world, speed: this.monsterSpeed });
      return;
    }
    if (now - m.attackAt < COMBAT.monsterCooldownMs) return;
    m.attackAt = now;
    m.animation.attackAt = now;
    const victim = target.ws;
    const damage = Math.min(victim.character.hp, COMBAT.monsterDamage);
    victim.character.hp -= damage; syncPlayerStats(victim);
    victim.player.animation ||= { attackAt: null, hitAt: null, deathAt: null };
    victim.player.animation.hitAt = now;
    if (victim.player.hp <= 0) victim.player.animation.deathAt = now;
    if (victim.player.hp <= 0) { victim.player.deadUntil = now + COMBAT.playerRespawnMs; victim.input = { x: 0, y: 0 }; }
    this.changed(victim, victim.player.hp <= 0);
    this.emit({ type: 'combat', action: 'player-hit', attackerId: m.id, targetId: victim.player.id, damage, targetHp: victim.player.hp, serverTime: now });
  }
}
