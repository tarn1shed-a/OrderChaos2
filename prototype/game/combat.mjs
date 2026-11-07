import { advance, walkable } from '../public/world.js';
import { skillById } from '../public/skills.js';
import { equipmentStats } from '../public/items.js';
import {chooseBasicAttack,prepareBasicAttack,updateBasicAttack} from './basic-attack.mjs';
import {SpellRuntime} from './spell-runtime.mjs';
import {DynamicScene} from './dynamic-scene.mjs';
import {BuffRuntime} from './buffs.mjs';
import {resolveDamage} from './damage.mjs';
import {MonsterAI} from './monster-ai.mjs';

export const COMBAT = Object.freeze({ playerDamage: 20, playerCooldownMs: 700, monsterHp: 60, monsterDamage: 6,
  monsterCooldownMs: 1000, monsterRespawnMs: 8000, playerRespawnMs: 4000,
  reward: Object.freeze({ xp: 30, gold: 10, wolfPelt: 1 }) });

export function syncPlayerStats(ws) {
  Object.assign(ws.player, { level: ws.character.level, hp: ws.character.hp, maxHp: ws.character.maxHp,
    profession:ws.character.profession,
    equipment: { ...ws.character.equipment }, look: { ...ws.character.look }, stats: equipmentStats(ws.character) });
}

export class CombatRoom {
  constructor(key, world, scene, clients, { changed, emit, notice, gameplay=null, motion=null, navigation=null, ai=true,casting=true,lab=false, random=Math.random }) {
    this.gameplay=scene==='resources'?gameplay:null;this.random=random;
    this.motion=scene==='resources'?(motion?.fork?.()||motion):null;
    this.world = world; this.scene = scene; this.clients = clients; this.changed = changed; this.emit = emit; this.notice = notice;
    this.range = scene === 'resources' ? 32 : 95;
    this.monsterSpeed = scene === 'resources' ? 14 : 70;
    this.monsterRange = scene === 'resources' ? 12 : 35;
    let spawn = { x: world.spawn.x + 50, y: world.spawn.y + 20 };
    if (!walkable(spawn.x, spawn.y, world)) spawn = { ...world.spawn };
    this.spawn = spawn;
    this.monster = { id: `${key}:wolf-1`, kind: 'wolf', name: '营地野狼', ...spawn, hp: COMBAT.monsterHp, maxHp: COMBAT.monsterHp,
      alive: true, respawnAt: 0, attackAt: 0, slowUntil: 0, animation: { attackAt: null, hitAt: null, deathAt: null } };
    this.contributors = new Set();
    if(this.motion)this.motion.place(this.monster);
    this.casts = new Map(); this.castSequence = 0;
    this.castProfile=casting&&scene==='resources'?gameplay?.casting:null;
    this.combatProfile=this.castProfile?gameplay?.combat:null;
    if(this.combatProfile)this.buffs=new BuffRuntime(this.combatProfile,{emit,
      valid:v=>v.target.hp>0&&this.clients.get(v.source.player.id)===v.source,
      pulse:(v,now,scheduledAt)=>{
        if(v.target!==this.monster)return;
        this.damageMonster(v.source,v.amount,now,{id:`${v.id}:tick:${v.pulsed}`,skillId:v.skillId},
          {periodic:true,auraId:this.combatProfile.auras[v.kind].id,scheduledAt});
      }});
    if(this.castProfile)this.runtime=new SpellRuntime(this.castProfile,{executions:this.casts,emit,
      check:(r,now)=>{
        if(this.clients.get(r.ws.player.id)!==r.ws||r.ws.player.hp<=0)return '施法已中断';
        if(this.blocked(r.ws.player,'skill',now))return '控制效果中断施法';
        if(!r.hit&&!this.monster.alive)return '目标已倒地';
        if(!r.hit&&this.brain?.returning)return '目标已脱战';
        if(!r.hit&&(r.channel||now>=r.cast.impactAt)&&Math.hypot(r.ws.player.x-this.monster.x,r.ws.player.y-this.monster.y)>r.skill.range)return '目标离开技能范围';
        return null;
      },hit:(r,now)=>this.damageMonster(r.ws,r.skill.damage,now,r.cast)});
    if(lab){if(!this.motion)throw new Error('碰撞验证场需要本地资源');this.dynamic=new DynamicScene(this.motion,Date.now());}
    if(ai&&scene==='resources'&&this.motion&&navigation)this.brain=new MonsterAI(this,navigation);
  }

  snapshot() { return [{ ...this.monster, ...(this.monster.ai?{ai:{...this.monster.ai}}:{}),buffs:structuredClone(this.monster.buffs||[]), animation: { ...this.monster.animation } }]; }

  blocked(target,action,now){return this.buffs?.blocked(target,action,now)||false;}
  applyStatus(target,kind,source,now,options){
    if(!this.buffs||target.hp<=0)return null;
    const value=this.buffs.apply(target,kind,source,now,options);
    if(target!==this.monster){
      const ws=this.clients.get(target.id);
      if(ws&&this.blocked(target,'move',now))ws.input={x:0,y:0};
      if(ws&&this.blocked(target,'attack',now))ws.attackPressed=false;
      if(ws&&this.blocked(target,'skill',now))for(const r of [...(this.runtime?.pending.values()||[])]){
        if(r.ws===ws)this.runtime.cancel(r,'控制效果中断施法',now);
      }
    }
    this.publishStatuses(now);return value;
  }
  publishStatuses(now){
    if(!this.buffs)return;
    for(const target of [this.monster,...[...this.clients.values()].map(ws=>ws.player)]){
      target.buffs=this.buffs.snapshot(target,now);
      target.controls=Object.fromEntries(['move','attack','skill','jump'].map(k=>[k,this.blocked(target,k,now)]));
    }
  }
  updateStatuses(now){this.buffs?.tick(now);this.publishStatuses(now);}

  skillDefinition(id) {
    const base=skillById(id),native=this.castProfile?.spells[id];
    if(id==='arcane_missile'&&!native)return null;
    return base&&native?{...base,name:native.displayName||base.name,castMs:native.chantMs,cooldownMs:native.cooldownMs,commonCD:native.commonCD,native}:base;
  }

  attack(ws, targetId, now) {
    const m = this.monster;
    if (typeof targetId !== 'string' || targetId !== m.id) return this.notice(ws, '目标不在当前营地');
    if (ws.player.hp <= 0) return this.notice(ws, '倒地后稍等片刻，会自动回到出生点');
    if(this.blocked(ws.player,'attack',now))return this.notice(ws,'控制效果中无法攻击');
    if (this.casts.has(ws.player.id)) return this.notice(ws, '正在施法，稍后再攻击');
    if (!m.alive) return this.notice(ws, '野狼已被击败，稍后会重新出现');
    if(this.brain?.returning)return this.notice(ws,'目标正在脱战返回');
    if (Math.hypot(ws.player.x - m.x, ws.player.y - m.y) > this.range) return this.notice(ws, '距离太远，先靠近野狼');
    if (now - ws.player.attackAt < COMBAT.playerCooldownMs) return this.notice(ws, '攻击尚在冷却中');
    const result=chooseBasicAttack(this.gameplay,ws.character,ws.basicCombo,now,this.random);
    if(result.error)return this.notice(ws,result.error);
    ws.basicCombo=result.state;
    ws.player.basicAttack=result.skill;
    ws.player.basicSlot=result.slot;
    ws.player.attackAt = now;
    ws.player.animation ||= { attackAt: null, hitAt: null, deathAt: null };
    ws.player.animation.attackAt = now;
    this.damageMonster(ws, equipmentStats(ws.character).attack, now);
  }

  skill(ws, skillId, targetId, now) {
    const skill=this.skillDefinition(skillId),native=skill?.native,m = this.monster;
    if (!skill) return this.notice(ws, '未知技能');
    if(native&&ws.character.profession!==2)return this.notice(ws,'当前接入的原玩家法术需要法师职业');
    if (targetId !== m.id || typeof targetId !== 'string') return this.notice(ws, '目标不在当前营地');
    if (ws.player.hp <= 0) return this.notice(ws, '倒地后无法施法');
    if(this.blocked(ws.player,'skill',now))return this.notice(ws,'控制效果中无法施法');
    if (!m.alive) return this.notice(ws, '目标已倒地，无法施法');
    if(this.brain?.returning)return this.notice(ws,'目标正在脱战返回');
    if (this.casts.has(ws.player.id)) return this.notice(ws, '正在施法，请稍候');
    if (now < (ws.player.skillReadyAt?.[skill.id] ?? 0)) return this.notice(ws, `${skill.name}还在冷却中`);
    if (native?now<(ws.player.globalReadyAt||0):now-ws.player.attackAt<COMBAT.playerCooldownMs) return this.notice(ws, '攻击尚在冷却中');
    if (Math.hypot(ws.player.x-m.x, ws.player.y-m.y) > skill.range) return this.notice(ws, `${skill.name}距离太远，先靠近野狼`);
    const cast = { id: `${ws.player.id}:${++this.castSequence}`, skillId: skill.id, targetId: m.id,
      startedAt: now, releaseAt: now + skill.castMs, impactAt: now + skill.castMs + skill.flightMs,
      origin: { x: ws.player.x, y: ws.player.y }, target: { x: m.x, y: m.y } };
    if(native?.channelMs>0){cast.channelEndsAt=cast.releaseAt+native.channelMs;cast.impactAt=cast.channelEndsAt+skill.flightMs;}
    ws.player.skillReadyAt ||= {};
    ws.player.skillReadyAt[skill.id] = now + skill.cooldownMs;
    if(native)ws.player.globalReadyAt=now+native.commonCD;
    ws.player.attackAt = now;
    ws.player.cast = cast;
    if(this.runtime){this.runtime.start(ws,skill,cast);if(this.casts.get(ws.player.id).machine.movement.stopOnEnter)ws.input={x:0,y:0};}
    else {ws.input = { x: 0, y: 0 };this.casts.set(ws.player.id, { ws, cast });}
    this.emit({ type: 'combat', action: 'skill-cast', attackerId: ws.player.id, targetId: m.id, serverTime: now, cast });
  }

  damageMonster(ws, amount, now, cast = null, {periodic=false,auraId=null,scheduledAt=null}={}) {
    const m = this.monster;
    if(!m.alive||m.hp<=0||this.brain?.returning)return;
    this.contributors.add(ws.player.id);
    const source=cast?this.combatProfile?.spells[cast.skillId]:ws.player.basicAttack;
    const bonus=!periodic&&cast?.skillId==='arcane_missile'&&this.buffs?.has(m,'burn',now)?this.combatProfile.mechanics.arcaneBurnBonus:0;
    const result=resolveDamage({base:amount,bonus,damageType:source?.damageType??null,damageAttribute:source?.damageAttribute??null},m.hp);
    const {damage}=result;m.hp=result.targetHp;
    this.brain?.hit(ws,damage);
    m.animation.hitAt = now;
    if (m.hp <= 0) m.animation.deathAt = now;
    const skill = cast && skillById(cast.skillId);
    if (m.hp > 0 && !this.combatProfile && skill?.slowMs) m.slowUntil = Math.max(m.slowUntil || 0, now + skill.slowMs);
    this.emit({ type: 'combat', action: periodic?'periodic-hit':cast ? 'skill-hit' : 'hit', attackerId: ws.player.id, targetId: m.id,
      ...result, serverTime: now, ...(periodic?{auraId,scheduledAt}:{}),...(cast ? { skillId: cast.skillId, castId: cast.id, position: { x: m.x, y: m.y } } : {basicAttack:ws.player.basicAttack}) });
    if(m.hp>0&&!periodic&&cast&&this.combatProfile){
      const p=this.combatProfile.mechanics;
      if(cast.skillId==='fireball')this.applyStatus(m,'burn',ws,now,{skillId:cast.skillId,durationMs:p.burnDurationMs,
        ticks:p.burnTicks,amount:amount*p.burnDisplayRate});
      if(cast.skillId==='frost_blast')this.applyStatus(m,'freeze',ws,now,{skillId:cast.skillId,durationMs:p.freezeDurationMs});
    }
    if (m.hp > 0) return;

    // Mark death before awarding. Further messages cannot perform a second living→dead transition.
    m.alive = false; m.respawnAt = now + COMBAT.monsterRespawnMs;
    this.buffs?.clear(m,now,'death');this.publishStatuses(now);
    this.brain?.tick(now,0);
    for (const id of this.contributors) {
      const recipient = this.clients.get(id);
      if (!recipient || recipient.player.hp <= 0) continue;
      const c = recipient.character, oldLevel = c.level;
      c.xp += COMBAT.reward.xp; c.gold += COMBAT.reward.gold; c.kills++;
      c.inventory.wolfPelt += COMBAT.reward.wolfPelt;
      c.level = 1 + Math.floor(c.xp / 60); c.maxHp = equipmentStats(c).maxHp;
      if (c.level > oldLevel) c.hp = c.maxHp;
      syncPlayerStats(recipient);
      this.changed(recipient, true);
      this.notice(recipient, `击败野狼：经验 +30，金币 +10，狼皮 +1${c.level > oldLevel ? `；升至 ${c.level} 级，生命恢复` : ''}`);
    }
    this.emit({ type: 'combat', action: 'kill', attackerId: ws.player.id, targetId: m.id, targetHp: 0, serverTime: now, rewards: { ...COMBAT.reward } });
    this.contributors.clear();
  }

  tick(now, dt) {
    this.updateStatuses(now);
    if(this.runtime)this.runtime.tick(now);
    else for (const [id, { ws, cast }] of this.casts) {
      let reason = null;
      if (this.clients.get(id) !== ws || ws.player.hp <= 0) reason = '施法已中断';
      else if (!this.monster.alive) reason = '目标已倒地';
      else if (now < cast.impactAt) continue;
      else if (Math.hypot(ws.player.x-this.monster.x, ws.player.y-this.monster.y) > skillById(cast.skillId).range) reason = '目标离开技能范围';
      this.casts.delete(id);
      if (reason) {
        this.emit({ type: 'combat', action: 'skill-cancel', attackerId: id, targetId: cast.targetId,
          skillId: cast.skillId, castId: cast.id, serverTime: now, message: reason });
      } else this.damageMonster(ws, skillById(cast.skillId).damage, now, cast);
      if (ws.player.cast?.id === cast.id) ws.player.cast = null;
    }
    for (const ws of this.clients.values()) {
      if(this.gameplay)updateBasicAttack(this.gameplay,ws,now);
      if (ws.player.hp <= 0 && ws.player.deadUntil && now >= ws.player.deadUntil) {
        this.buffs?.clear(ws.player,now,'respawn');
        ws.character.hp = ws.character.maxHp; syncPlayerStats(ws);
        ws.player.x = this.world.spawn.x; ws.player.y = this.world.spawn.y; ws.player.deadUntil = 0;
        if(this.motion)this.motion.place(ws.player);
        ws.player.animation = { attackAt: null, hitAt: null, deathAt: null };
        ws.player.cast = null; ws.player.lastCast = null;
        const basic=prepareBasicAttack(this.gameplay,ws.character,this.random);
        ws.basicCombo=basic.state;ws.player.basicSlot=basic.slot;ws.player.basicAttack=null;ws.attackPressed=false;
        ws.input = { x: 0, y: 0 }; this.changed(ws, true);
        this.emit({ type: 'combat', action: 'respawn', attackerId: null, targetId: ws.player.id, targetHp: ws.player.hp, serverTime: now });
      }
    }
    const m = this.monster;
    if (!m.alive) {
      if (now >= m.respawnAt) {
        this.buffs?.clear(m,now,'respawn');
        Object.assign(m, this.spawn, { hp: m.maxHp, alive: true, respawnAt: 0, attackAt: 0, slowUntil: 0,
          animation: { attackAt: null, hitAt: null, deathAt: null } }); this.contributors.clear();
        if(this.motion)this.motion.place(m);
        this.brain?.reset(now);
        this.emit({ type: 'combat', action: 'respawn', attackerId: null, targetId: m.id, targetHp: m.hp, serverTime: now });
      }
      return;
    }
    let target;
    if(this.brain){target=this.brain.tick(now,dt);if(!target||this.blocked(m,'attack',now))return;}
    else {
    if(this.blocked(m,'attack',now))return;
    // This first encounter is passive until attacked. Nearby contributors then share its attention.
    const targets = [...this.clients.values()].filter(ws => ws.player.hp > 0 && this.contributors.has(ws.player.id))
      .map(ws => ({ ws, distance: Math.hypot(ws.player.x - m.x, ws.player.y - m.y) }))
      .sort((a, b) => a.distance - b.distance);
    target = targets[0];
    const leash = this.scene === 'resources' ? 220 : 360;
    if (!target || target.distance > leash) {
      const dx = this.spawn.x - m.x, dy = this.spawn.y - m.y, d = Math.hypot(dx, dy);
      if (d > 1) this.moveMonster(m, { x: dx / d, y: dy / d }, dt,now);
      return;
    }
    if (target.distance > this.monsterRange) {
      this.moveMonster(m, { x: (target.ws.player.x - m.x) / target.distance, y: (target.ws.player.y - m.y) / target.distance }, dt,now);
      return;
    }
    }
    if (now - m.attackAt < COMBAT.monsterCooldownMs) return;
    m.attackAt = now;
    m.animation.attackAt = now;
    const victim = target.ws;
    const result=resolveDamage({base:COMBAT.monsterDamage,armor:equipmentStats(victim.character).armor},victim.character.hp);
    const {damage}=result;victim.character.hp=result.targetHp;syncPlayerStats(victim);
    victim.player.animation ||= { attackAt: null, hitAt: null, deathAt: null };
    victim.player.animation.hitAt = now;
    if (victim.player.hp <= 0) victim.player.animation.deathAt = now;
    if (victim.player.hp <= 0) { victim.player.deadUntil = now + COMBAT.playerRespawnMs; victim.input = { x: 0, y: 0 };this.buffs?.clear(victim.player,now,'death');this.publishStatuses(now); }
    this.changed(victim, victim.player.hp <= 0);
    this.emit({ type: 'combat', action: 'player-hit', attackerId: m.id, targetId: victim.player.id, ...result, serverTime: now });
  }

  moveMonster(monster,input,dt,now){
    if(this.blocked(monster,'move',now))return;
    const world={...this.world,speed:this.monsterSpeed*(monster.slowUntil>now ? .5 : 1)};
    if(this.motion)this.motion.move(monster,input,dt,world);else advance(monster,input,dt,world);
  }
}
