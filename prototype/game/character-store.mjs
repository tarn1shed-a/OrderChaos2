import { mkdirSync, readFileSync, writeFileSync, renameSync, existsSync, openSync, fsyncSync, closeSync, unlinkSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { createHash, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';

const hash = token => createHash('sha256').update(token).digest('hex');
const integer = value => Number.isSafeInteger(value) && value >= 0 && value <= 1_000_000_000;

export function characterView(record) {
  // Recovery credentials and saved positions are private; never spread a record into a room snapshot.
  return { id: record.id, name: record.name, level: record.level, xp: record.xp, gold: record.gold,
    kills: record.kills, hp: record.hp, maxHp: record.maxHp, inventory: { ...record.inventory } };
}

function validate(record) {
  if (!record || typeof record.id !== 'string' || !/^[0-9a-f-]{36}$/.test(record.id) ||
      typeof record.name !== 'string' || !record.name.trim() || record.name.length > 16 ||
      typeof record.tokenHash !== 'string' || !/^[0-9a-f]{64}$/.test(record.tokenHash) ||
      !['xp', 'level', 'gold', 'kills', 'hp', 'maxHp'].every(k => integer(record[k])) ||
      record.level !== 1 + Math.floor(record.xp / 60) || record.maxHp !== 100 + (record.level - 1) * 20 || record.hp > record.maxHp ||
      !record.inventory || !integer(record.inventory.wolfPelt) || !record.positions || typeof record.positions !== 'object' || Array.isArray(record.positions)) {
    throw new Error('角色存档结构无效');
  }
  for (const [scene, p] of Object.entries(record.positions)) {
    if (!['camp', 'resources'].includes(scene) || !p || !Number.isFinite(p.x) || !Number.isFinite(p.y)) throw new Error('角色位置存档无效');
  }
}

export class CharacterStore {
  constructor(saveFile) {
    this.saveFile = saveFile ? resolve(saveFile) : null;
    this.records = new Map(); this.dirty = false; this.savedAt = null;
    if (this.saveFile && existsSync(this.saveFile)) {
      // An unreadable/corrupt save is an error, never permission to replace it with a blank world.
      let data;
      try { data = JSON.parse(readFileSync(this.saveFile, 'utf8')); }
      catch (error) { throw new Error(`无法读取角色存档，原文件保留：${error.message}`); }
      if (data.version !== 1 || !Array.isArray(data.characters)) throw new Error('不支持的角色存档版本，原文件保留');
      for (const record of data.characters) {
        validate(record);
        if (this.records.has(record.id)) throw new Error('角色存档含重复 ID');
        this.records.set(record.id, record);
      }
      this.savedAt = data.savedAt || null;
    }
  }

  resolveCharacter(name, characterId, resumeToken) {
    if (characterId !== undefined || resumeToken !== undefined) {
      if (typeof characterId !== 'string' || typeof resumeToken !== 'string' || !/^[0-9a-f]{64}$/.test(resumeToken)) throw new Error('角色恢复凭据无效，请使用原浏览器保存的角色');
      const record = this.records.get(characterId);
      if (!record || !timingSafeEqual(Buffer.from(record.tokenHash, 'hex'), Buffer.from(hash(resumeToken), 'hex'))) throw new Error('角色恢复凭据不匹配，未修改任何存档');
      return { record, resumeToken, restored: true };
    }
    const token = randomBytes(32).toString('hex');
    const record = { id: randomUUID(), name, tokenHash: hash(token), createdAt: Date.now(), updatedAt: Date.now(),
      level: 1, xp: 0, gold: 0, kills: 0, hp: 100, maxHp: 100, inventory: { wolfPelt: 0 }, positions: {} };
    this.records.set(record.id, record); this.touch(record); this.flush();
    return { record, resumeToken: token, restored: false };
  }

  touch(record) { record.updatedAt = Date.now(); this.dirty = true; }

  savePosition(record, scene, player) {
    const p = record.positions[scene];
    if (!p || p.x !== player.x || p.y !== player.y) {
      record.positions[scene] = { x: player.x, y: player.y }; this.touch(record);
    }
  }

  flush() {
    if (!this.dirty) return;
    if (!this.saveFile) { this.dirty = false; return; }
    const now = Date.now();
    const temporary = `${this.saveFile}.${randomUUID()}.tmp`;
    try {
      mkdirSync(dirname(this.saveFile), { recursive: true, mode: 0o700 });
      writeFileSync(temporary, JSON.stringify({ version: 1, savedAt: now, characters: [...this.records.values()] }, null, 2), { mode: 0o600, flag: 'wx' });
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
