import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, extname, sep } from 'node:path';
import { WebSocketServer, WebSocket } from 'ws';
import { WORLD, RESOURCE_WORLD, advance, walkable } from './public/world.js';
import { CharacterStore, characterView } from './game/character-store.mjs';
import { CombatRoom, COMBAT, syncPlayerStats } from './game/combat.mjs';
import { SKILLS } from './public/skills.js';
import { changeEquipment } from './game/equipment.mjs';
import { validLook } from './public/character-look.js';
import { validHotbar, cloneHotbar } from './public/hotbar-settings.js';
import { setJumpPressed, updateJump } from './game/jump.mjs';
import {loadGameplay,prepareBasicAttack} from './game/basic-attack.mjs';
import {loadCollision} from './game/collision.mjs';

const PUBLIC = fileURLToPath(new URL('./public/', import.meta.url));
const CONVERTED = fileURLToPath(new URL('../game-data/converted/', import.meta.url));
const THREE_BUILD = fileURLToPath(new URL('./node_modules/three/build/', import.meta.url));
const COLORS = ['#80e5d1', '#ffc47c', '#b7a2f7', '#f39da9', '#90bdec', '#d4e993', '#ffdfaa', '#b4e4ed'];

export function createGameServer({ saveFile, clock = Date.now, gameplay=loadGameplay(), motion=loadCollision(), allowedOrigins = (process.env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean) } = {}) {
  if (saveFile && [PUBLIC, CONVERTED].some(root => resolve(saveFile).startsWith(root.endsWith(sep) ? root : root + sep))) throw new Error('角色存档必须放在静态资源目录之外');
  const store = new CharacterStore(saveFile);
  const rooms = new Map();
  const combatRooms = new Map();
  const activeCharacters = new Map();
  let storageError = null;
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      if (url.pathname === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ ok: !storageError, rooms: rooms.size, persistence: store.saveFile ? 'file' : 'memory' }));
      }
      const pathname = decodeURIComponent(url.pathname);
      const isAsset = pathname.startsWith('/assets/');
      const isVendor = ['/vendor/three.module.js', '/vendor/three.core.js'].includes(pathname);
      const root = isAsset ? CONVERTED : isVendor ? THREE_BUILD : PUBLIC;
      const relative = isAsset ? pathname.slice('/assets'.length) : isVendor ? pathname.slice('/vendor'.length) : pathname;
      const path = resolve(root, '.' + (relative === '/' ? '/index.html' : relative));
      if (!path.startsWith(root.endsWith(sep) ? root : root + sep)) {
        res.writeHead(403); return res.end();
      }
      const data = await readFile(path);
      res.writeHead(200, {
        'Content-Type': ({ '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.woff': 'font/woff', '.glb': 'model/gltf-binary' })[extname(path)] || 'application/octet-stream',
        'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-cache',
        'Content-Security-Policy': "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'",
      });
      res.end(data);
    } catch { res.writeHead(404); res.end('Not found'); }
  });
  const wss = new WebSocketServer({ noServer: true, maxPayload: 2048 });
  server.on('upgrade', (req, socket, head) => {
    // Browser connections must originate from this host. Non-browser test clients may omit Origin.
    let allowed = !req.headers.origin;
    try { if (req.headers.origin) allowed = new URL(req.headers.origin).host === req.headers.host || allowedOrigins.includes(req.headers.origin); } catch {}
    if (req.url !== '/ws' || !allowed || wss.clients.size >= 128) return socket.destroy();
    wss.handleUpgrade(req, socket, head, ws => wss.emit('connection', ws));
  });
  const send = (ws, data) => {
    if (ws.readyState === WebSocket.OPEN && ws.bufferedAmount < 65536) ws.send(JSON.stringify(data));
  };
  const reject = (ws, message) => { send(ws, { type: 'error', message }); ws.close(1008, message); };
  const notice = (ws, message) => send(ws, { type: 'notice', message });
  const emit = (room, data) => { for (const ws of room.values()) send(ws, data); };
  const progress = ws => send(ws, { type: 'progress', character: characterView(ws.character), savedAt: store.savedAt });
  const changed = (ws, immediate = false) => {
    store.touch(ws.character); store.savePosition(ws.character, ws.scene, ws.player);
    if (immediate) store.flush();
    progress(ws);
  };
  const storageFailure = error => {
    if (!storageError) console.error(error.message);
    storageError = error;
    for (const ws of activeCharacters.values()) notice(ws, '角色存档写入失败，游戏已暂停；请检查服务器终端');
  };
  wss.on('connection', ws => {
    ws.alive = true;
    ws.on('error', () => {});
    ws.on('pong', () => { ws.alive = true; });
    const deadline = setTimeout(() => { if (!ws.player) ws.close(1008, 'Join timeout'); }, 5000);
    let budget = 0, windowAt = Date.now();
    ws.on('message', (buffer, binary) => {
      if (binary) return reject(ws, '仅支持 JSON 消息');
      if (Date.now() - windowAt >= 1000) { budget = 0; windowAt = Date.now(); }
      if (++budget > 90) return reject(ws, '消息过于频繁');
      let msg;
      try { msg = JSON.parse(buffer.toString()); } catch { return reject(ws, '消息格式错误'); }
      if (!msg || typeof msg !== 'object') return reject(ws, '消息格式错误');
      if (storageError) return reject(ws, '存档当前不可用，请检查服务器后重试');
      try {
      if (msg.type === 'join' && !ws.player) {
        const scene = msg.scene || 'camp';
        if (!['camp', 'resources'].includes(scene)) return reject(ws, '未知场景');
        const world = scene === 'resources' ? RESOURCE_WORLD : WORLD;
        const roomId = typeof msg.room === 'string' ? msg.room.trim().toUpperCase() : '';
        const name = typeof msg.name === 'string' ? msg.name.trim().slice(0, 16) : '';
        if (!/^[A-Z0-9-]{3,16}$/.test(roomId) || !name) return reject(ws, '请输入名字和 3–16 位英文或数字房间号');
        const roomKey = scene === 'camp' ? roomId : `resources:${roomId}`;
        if (!rooms.has(roomKey) && rooms.size >= 32) return reject(ws, '房间已满，请稍后重试');
        const room = rooms.get(roomKey) || new Map();
        if (room.size >= 8) return reject(ws, '这个房间已满（最多 8 人）');
        const used = new Set([...room.values()].map(s => s.player.color));
        const index = COLORS.findIndex(c => !used.has(c));
        let identity;
        try { identity = store.resolveCharacter(name, msg.characterId, msg.resumeToken, msg.profession); }
        catch (error) {
          if (/存档写入失败/.test(error.message)) throw error;
          return reject(ws, error.message);
        }
        if (activeCharacters.has(identity.record.id)) return reject(ws, '这个角色已在另一个窗口在线，请先退出原窗口');
        ws.character = identity.record; ws.scene = scene;
        ws.motion=scene==='resources'?motion:null;ws.gameplay=gameplay;
        const position = ws.character.positions[scene];
        const restorePosition = position && walkable(position.x, position.y, world) && ws.character.hp > 0;
        ws.player = { id: ws.character.id, name: ws.character.name,
          x: restorePosition ? position.x : world.spawn.x + index * 35,
          y: restorePosition ? position.y : world.spawn.y,
          color: COLORS[index], deadUntil: 0, attackAt: -COMBAT.playerCooldownMs,
          animation: { attackAt: null, hitAt: null, deathAt: null }, cast: null, jump:null, skillReadyAt: {} };
        if (ws.character.hp <= 0) ws.character.hp = ws.character.maxHp;
        syncPlayerStats(ws);
        if(ws.motion){
          ws.motion.place(ws.player);
          if(restorePosition&&Number.isFinite(position.groundY)){
            const p=ws.motion.point(ws.player.x,ws.player.y);ws.player.worldY=ws.motion.support(p.x,p.z,position.groundY+ws.motion.step);
          }
        }
        ws.input = { x: 0, y: 0 }; ws.inputAt = Date.now(); ws.roomId = roomKey; ws.world = world;
        activeCharacters.set(ws.player.id, ws);
        room.set(ws.player.id, ws); rooms.set(roomKey, room); clearTimeout(deadline);
        if (!combatRooms.has(roomKey)) combatRooms.set(roomKey, new CombatRoom(roomKey, world, scene, room, { changed, emit: data => emit(room, data), notice,gameplay,motion }));
        const basic=prepareBasicAttack(scene==='resources'?gameplay:null,ws.character);ws.basicCombo=basic.state;
        ws.player.basicSlot=basic.slot;ws.player.basicAttack=null;
        store.savePosition(ws.character, scene, ws.player); store.touch(ws.character); store.flush();
        send(ws, { type: 'welcome', id: ws.player.id, room: roomId, scene, world,
          character: characterView(ws.character), resumeToken: identity.resumeToken, restored: identity.restored,
          savedAt: store.savedAt, combat: { attackRange: combatRooms.get(roomKey).range, cooldownMs: COMBAT.playerCooldownMs, monsterCooldownMs: COMBAT.monsterCooldownMs, skills: SKILLS } });
      } else if (msg.type === 'input' && ws.player) {
        if (typeof msg.x !== 'number' || typeof msg.y !== 'number' || !Number.isFinite(msg.x) || !Number.isFinite(msg.y) || Math.abs(msg.x) > 1 || Math.abs(msg.y) > 1) return reject(ws, '无效移动输入');
        ws.input = { x: msg.x, y: msg.y }; ws.inputAt = Date.now();
      } else if (msg.type === 'jump' && ws.player) {
        if(typeof msg.pressed!=='boolean')return reject(ws,'无效跳跃输入');
        const result=setJumpPressed(ws,msg.pressed,clock(),combatRooms.get(ws.roomId).casts.has(ws.player.id));
        if(result)notice(ws,result);
      } else if (msg.type === 'attack-control' && ws.player) {
        if(typeof msg.pressed!=='boolean')return reject(ws,'无效普攻输入');
        if(!msg.pressed){ws.attackPressed=false;return;}
        if(ws.attackPressed)return;
        ws.attackPressed=true;ws.attackInputAt=clock();
        if(ws.player.jump&&clock()<ws.player.jump.endsAt)return notice(ws,'跳跃结束后再攻击');
        combatRooms.get(ws.roomId).attack(ws,msg.targetId,clock());
      } else if (msg.type === 'attack' && ws.player) {
        if(ws.player.jump&&clock()<ws.player.jump.endsAt)return notice(ws,'跳跃结束后再攻击');
        combatRooms.get(ws.roomId).attack(ws, msg.targetId, clock());
      } else if (msg.type === 'skill' && ws.player) {
        if(ws.player.jump&&clock()<ws.player.jump.endsAt)return notice(ws,'跳跃结束后再施法');
        combatRooms.get(ws.roomId).skill(ws, msg.skillId, msg.targetId, clock());
      } else if (['equip', 'unequip'].includes(msg.type) && ws.player) {
        if (combatRooms.get(ws.roomId).casts.has(ws.player.id)) return notice(ws, '施法时无法更换装备');
        const result = changeEquipment(ws.character, msg);
        if (result.error) return notice(ws, result.error);
        syncPlayerStats(ws); changed(ws, true); notice(ws, result.message);
        const basic=prepareBasicAttack(ws.scene==='resources'?gameplay:null,ws.character);ws.basicCombo=basic.state;ws.player.basicSlot=basic.slot;
      } else if (msg.type === 'hotbar' && ws.player) {
        if(!Number.isSafeInteger(msg.requestId)||msg.requestId<1||msg.requestId>1_000_000_000)return notice(ws,'技能栏请求编号无效');
        const result=(ok,message)=>send(ws,{type:'hotbar-result',requestId:msg.requestId,ok,message,
          hotbar:ws.character.hotbar===null?null:cloneHotbar(ws.character.hotbar),savedAt:store.savedAt});
        if(!validHotbar(msg.settings)||(msg.initializeOnly!==undefined&&typeof msg.initializeOnly!=='boolean'))return result(false,'技能栏设置无效，未修改角色存档');
        if(msg.initializeOnly&&ws.character.hotbar!==null)return result(false,'已恢复服务器技能栏，未使用旧版本机设置');
        ws.character.hotbar=cloneHotbar(msg.settings);changed(ws,true);
        result(true,'技能栏已保存到服务器');
      } else if (msg.type === 'look' && ws.player) {
        if (!validLook(msg.look)) return notice(ws, '外观选项无效');
        if (ws.player.hp<=0 || combatRooms.get(ws.roomId).casts.has(ws.player.id)) return notice(ws, '倒地或施法时暂不能更换外观');
        ws.character.look={...msg.look};syncPlayerStats(ws);changed(ws,true);notice(ws,'角色外观已保存');
      } else if (msg.type === 'save' && ws.player) {
        changed(ws, true); notice(ws, '角色进度已保存');
      } else if (msg.type === 'ping' && ws.player) send(ws, { type: 'pong', at: msg.at });
      else reject(ws, '无效消息');
      } catch (error) { storageFailure(error); reject(ws, '存档写入失败，请检查服务器后重试'); }
    });
    ws.on('close', () => {
      clearTimeout(deadline);
      const room = rooms.get(ws.roomId);
      if (ws.character && activeCharacters.get(ws.character.id) === ws) {
        store.savePosition(ws.character, ws.scene, ws.player);
        if (!closing) { try { store.flush(); } catch (error) { storageFailure(error); } }
        activeCharacters.delete(ws.character.id);
      }
      if (room) {
        room.delete(ws.player.id);
        if (!room.size) { rooms.delete(ws.roomId); combatRooms.delete(ws.roomId); }
      }
    });
  });
  let tick = 0;
  const ticker = setInterval(() => {
    tick++;
    if (storageError) return;
    try {
    for (const [roomKey, room] of rooms) {
      for (const ws of room.values()) {
        // A lost pointer release must not latch the control forever; recovery
        // clears input only and never schedules an automatic second attack.
        if(ws.attackPressed&&clock()-ws.attackInputAt>3000)ws.attackPressed=false;
        if (ws.player.hp > 0 && !combatRooms.get(roomKey).casts.has(ws.player.id)) {
          const input=Date.now()-ws.inputAt>350?{x:0,y:0}:ws.input;
          if(ws.motion)ws.motion.move(ws.player,input,.05,ws.world);else advance(ws.player,input,.05,ws.world);
        }
        store.savePosition(ws.character, ws.scene, ws.player);
      }
      const encounter = combatRooms.get(roomKey);
      encounter.tick(clock(), 0.05);
      if(encounter.motion&&encounter.monster.alive)encounter.motion.settle(encounter.monster);
      for(const ws of room.values())updateJump(ws,clock());
      const snapshot = { type: 'state', tick, serverTime: clock(), players: [...room.values()].map(ws => ({ ...ws.player, animation: { ...ws.player.animation },
        skillReadyAt: { ...ws.player.skillReadyAt }, cast: ws.player.cast ? structuredClone(ws.player.cast) : null })), monsters: encounter.snapshot() };
      for (const ws of room.values()) send(ws, snapshot);
    }
    } catch (error) { storageFailure(error); }
  }, 50);
  const saveTimer = setInterval(() => {
    if (storageError || !store.dirty) return;
    try { store.flush(); for (const ws of activeCharacters.values()) progress(ws); }
    catch (error) { storageFailure(error); }
  }, 5000);
  const heartbeat = setInterval(() => {
    for (const ws of wss.clients) {
      if (!ws.alive) { ws.terminate(); continue; }
      ws.alive = false; ws.ping();
    }
  }, 15000);
  let closing;
  return {
    server, rooms, combatRooms,
    close() {
      if (closing) return closing;
      closing = (async () => {
        clearInterval(ticker); clearInterval(heartbeat); clearInterval(saveTimer);
        try {
          for (const ws of activeCharacters.values()) store.savePosition(ws.character, ws.scene, ws.player);
          store.flush();
        } finally {
          // Even a full/unwritable disk must not leave the game listening or sockets alive.
          for (const ws of wss.clients) ws.terminate();
          await new Promise(resolve => wss.close(resolve));
          await new Promise(resolve => server.close(resolve));
        }
      })();
      return closing;
    },
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const repositoryRoot = fileURLToPath(new URL('../', import.meta.url));
  const saveFile = resolve(repositoryRoot, process.env.SAVE_FILE || 'runtime/characters.json');
  const game = createGameServer({ saveFile });
  const port = Number(process.env.PORT || 8787);
  game.server.listen(port, process.env.HOST || '0.0.0.0', () => console.log(`营地已开启：http://localhost:${port}\n角色存档：${saveFile}\n同一局域网的朋友可使用这台电脑的局域网 IP 和相同端口。`));
  let stopping = false;
  const stop = async () => {
    if (stopping) return; stopping = true;
    try { await game.close(); process.exit(0); }
    catch (error) { console.error(`服务器已关闭，但最终存档失败：${error.message}`); process.exit(1); }
  };
  process.on('SIGINT', stop); process.on('SIGTERM', stop);
}
