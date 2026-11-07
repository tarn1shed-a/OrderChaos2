import { mkdirSync, readFileSync, writeFileSync, renameSync, existsSync, openSync, fsyncSync, closeSync, unlinkSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { createHash, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { ITEMS, EQUIPMENT_SLOTS, itemById, starterInventory, emptyEquipment, equipmentStats } from '../public/items.js';
import { defaultLook, validLook } from '../public/character-look.js';
import { validHotbar, cloneHotbar } from '../public/hotbar-settings.js';
import {validProfession} from '../public/professions.js';

const hash = token => createHash('sha256').update(token).digest('hex');
const integer = value => Number.isSafeInteger(value) && value >= 0 && value <= 1_000_000_000;

export function characterView(record) {
  // Recovery credentials and saved positions are private; never spread a record into a room snapshot.
  return { id: record.id, name: record.name, profession:record.profession, level: record.level, xp: record.xp, gold: record.gold,
    kills: record.kills, hp: record.hp, maxHp: record.maxHp, inventory: { ...record.inventory },
    equipment: { ...record.equipment }, look: { ...record.look }, hotbar:record.hotbar===null?null:cloneHotbar(record.hotbar), stats: equipmentStats(record) };
}

function validate(record, legacy = false, requireLook = true, requireHotbar = true, version=5) {
  if (!record || typeof record.id !== 'string' || !/^[0-9a-f-]{36}$/.test(record.id) ||
      typeof record.name !== 'string' || !record.name.trim() || record.name.length > 16 ||
      typeof record.tokenHash !== 'string' || !/^[0-9a-f]{64}$/.test(record.tokenHash) ||
      !['xp', 'level', 'gold', 'kills', 'hp', 'maxHp'].every(k => integer(record[k])) ||
      record.level !== 1 + Math.floor(record.xp / 60) || record.hp > record.maxHp ||
      !record.inventory || !integer(record.inventory.wolfPelt) || !record.positions || typeof record.positions !== 'object' || Array.isArray(record.positions)) {
    throw new Error('角色存档结构无效');
  }
  if(requireLook && !validLook(record.look))throw new Error('角色外观存档无效');
  if(requireHotbar && record.hotbar!==null && !validHotbar(record.hotbar))throw new Error('角色技能栏存档无效');
  if(version>=5&&!validProfession(record.profession))throw new Error('角色职业存档无效');
  const itemKeys=Object.keys(ITEMS).filter(k=>version>=5||!['trainingStaff','trainingGreatsword'].includes(k));
  if (legacy) {
    if (record.maxHp !== 100 + (record.level - 1) * 20) throw new Error('旧版角色生命存档无效');
  } else {
    if (!record.equipment || Array.isArray(record.equipment) || typeof record.equipment !== 'object' ||
        Object.keys(record.inventory).length !== itemKeys.length ||
        Object.keys(record.inventory).some(key => !itemKeys.includes(key)) ||
        !itemKeys.every(key => integer(record.inventory[key])) ||
        Object.keys(record.equipment).length !== Object.keys(EQUIPMENT_SLOTS).length ||
        !Object.keys(EQUIPMENT_SLOTS).every(slot => record.equipment[slot] === null || itemById(record.equipment[slot])?.slot === slot)) throw new Error('角色物品或装备存档无效');
    for (const item of Object.values(ITEMS).filter(item => item.slot&&itemKeys.includes(item.id))) {
      if (record.inventory[item.id] + Number(record.equipment[item.slot] === item.id) !== 1) throw new Error('新手装备数量存档无效');
    }
    if (record.maxHp !== equipmentStats(record).maxHp) throw new Error('角色装备属性存档无效');
  }
  for (const [scene, p] of Object.entries(record.positions)) {
    if (!['camp', 'resources'].includes(scene) || !p || !Number.isFinite(p.x) || !Number.isFinite(p.y) || (p.groundY!==undefined&&!Number.isFinite(p.groundY))) throw new Error('角色位置存档无效');
  }
}

export class CharacterStore {
  constructor(saveFile) {
    this.saveFile = saveFile ? resolve(saveFile) : null;
    this.records = new Map(); this.dirty = false; this.savedAt = null;
    if (this.saveFile && existsSync(this.saveFile)) {
      // An unreadable/corrupt save is an error, never permission to replace it with a blank world.
      let data;
      let original;
      try { original = readFileSync(this.saveFile); data = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(original)); }
      catch (error) { throw new Error(`无法读取角色存档，原文件保留：${error.message}`); }
      if (![1, 2, 3, 4, 5].includes(data.version) || !Array.isArray(data.characters)) throw new Error('不支持的角色存档版本，原文件保留');
      for (const record of data.characters) {
        validate(record, data.version === 1, data.version >= 3, data.version >= 4, data.version);
        if (this.records.has(record.id)) throw new Error('角色存档含重复 ID');
        if (data.version === 1) {
          record.inventory = { ...starterInventory(), wolfPelt: record.inventory.wolfPelt };
          record.equipment = emptyEquipment();
        }
        if(data.version<3)record.look=defaultLook();
        if(data.version<4)record.hotbar=null;
        // Existing avatars already use mage skills. No inferred original class:
        // explicitly migrate the local prototype to Mage, preserving progress.
        if(data.version<5){record.profession=2;record.inventory.trainingStaff=1;record.inventory.trainingGreatsword=1;}
        validate(record);
        this.records.set(record.id, record);
      }
      if (data.version < 5) { this.legacySource = original; this.legacyVersion=data.version; this.dirty = true; }
      this.savedAt = data.savedAt || null;
    }
  }

  resolveCharacter(name, characterId, resumeToken, profession=2) {
    if (characterId !== undefined || resumeToken !== undefined) {
      if (typeof characterId !== 'string' || typeof resumeToken !== 'string' || !/^[0-9a-f]{64}$/.test(resumeToken)) throw new Error('角色恢复凭据无效，请使用原浏览器保存的角色');
      const record = this.records.get(characterId);
      if (!record || !timingSafeEqual(Buffer.from(record.tokenHash, 'hex'), Buffer.from(hash(resumeToken), 'hex'))) throw new Error('角色恢复凭据不匹配，未修改任何存档');
      return { record, resumeToken, restored: true };
    }
    if(!validProfession(profession))throw new Error('角色职业无效');
    const token = randomBytes(32).toString('hex');
    const record = { id: randomUUID(), name, profession, tokenHash: hash(token), createdAt: Date.now(), updatedAt: Date.now(),
      level: 1, xp: 0, gold: 0, kills: 0, hp: 100, maxHp: 100, inventory: starterInventory(), equipment: emptyEquipment(), look: defaultLook(), hotbar:null, positions: {} };
    this.records.set(record.id, record); this.touch(record); this.flush();
    return { record, resumeToken: token, restored: false };
  }

  touch(record) { record.updatedAt = Date.now(); this.dirty = true; }

  savePosition(record, scene, player) {
    const p = record.positions[scene];
    const groundY=player.grounded&&Number.isFinite(player.worldY)?player.worldY:p?.groundY;
    if (!p || p.x !== player.x || p.y !== player.y || p.groundY!==groundY) {
      record.positions[scene] = { x: player.x, y: player.y,...(Number.isFinite(groundY)?{groundY}:{}) }; this.touch(record);
    }
  }

  flush() {
    if (!this.dirty) return;
    if (!this.saveFile) { this.dirty = false; return; }
    const now = Date.now();
    const temporary = `${this.saveFile}.${randomUUID()}.tmp`;
    try {
      mkdirSync(dirname(this.saveFile), { recursive: true, mode: 0o700 });
      if (this.legacySource !== undefined) {
        const backup = `${this.saveFile}.v${this.legacyVersion}-backup-${randomUUID()}.json`;
        writeFileSync(backup, this.legacySource, { mode: 0o600, flag: 'wx' });
        const backupFd = openSync(backup, 'r');
        try { fsyncSync(backupFd); } finally { closeSync(backupFd); }
        this.legacySource = undefined;
      }
      writeFileSync(temporary, JSON.stringify({ version: 5, savedAt: now, characters: [...this.records.values()] }, null, 2), { mode: 0o600, flag: 'wx' });
      const fd = openSync(temporary, 'r');
      try { fsyncSync(fd); } finally { closeSync(fd); }
      renameSync(temporary, this.saveFile);
      this.savedAt = now; this.dirty = false;
    } catch (error) {
      try { unlinkSync(temporary); } catch {}
      throw new Error(`角色存档写入失败：${error.message}`);
    }
  }
}
