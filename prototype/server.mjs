import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, extname, sep } from 'node:path';
import { randomUUID } from 'node:crypto';
import { WebSocketServer, WebSocket } from 'ws';
import { WORLD, RESOURCE_WORLD, advance } from './public/world.js';

const PUBLIC = fileURLToPath(new URL('./public/', import.meta.url));
const CONVERTED = fileURLToPath(new URL('../game-data/converted/', import.meta.url));
const THREE_BUILD = fileURLToPath(new URL('./node_modules/three/build/', import.meta.url));
const COLORS = ['#80e5d1', '#ffc47c', '#b7a2f7', '#f39da9', '#90bdec', '#d4e993', '#ffdfaa', '#b4e4ed'];

export function createGameServer({ allowedOrigins = (process.env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean) } = {}) {
  const rooms = new Map();
  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://localhost');
      if (url.pathname === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ ok: true, rooms: rooms.size }));
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
        'Content-Type': ({ '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.png': 'image/png', '.glb': 'model/gltf-binary' })[extname(path)] || 'application/octet-stream',
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
        ws.player = { id: randomUUID(), name, x: world.spawn.x + index * 35, y: world.spawn.y, color: COLORS[index] };
        ws.input = { x: 0, y: 0 }; ws.inputAt = Date.now(); ws.roomId = roomKey; ws.world = world;
        room.set(ws.player.id, ws); rooms.set(roomKey, room); clearTimeout(deadline);
        send(ws, { type: 'welcome', id: ws.player.id, room: roomId, scene, world });
      } else if (msg.type === 'input' && ws.player) {
        if (typeof msg.x !== 'number' || typeof msg.y !== 'number' || !Number.isFinite(msg.x) || !Number.isFinite(msg.y) || Math.abs(msg.x) > 1 || Math.abs(msg.y) > 1) return reject(ws, '无效移动输入');
        ws.input = { x: msg.x, y: msg.y }; ws.inputAt = Date.now();
      } else if (msg.type === 'ping' && ws.player) send(ws, { type: 'pong', at: msg.at });
      else reject(ws, '无效消息');
    });
    ws.on('close', () => {
      clearTimeout(deadline);
      const room = rooms.get(ws.roomId);
      if (room) { room.delete(ws.player.id); if (!room.size) rooms.delete(ws.roomId); }
    });
  });
  let tick = 0;
  const ticker = setInterval(() => {
    tick++;
    for (const room of rooms.values()) {
      for (const ws of room.values()) {
        advance(ws.player, Date.now() - ws.inputAt > 350 ? { x: 0, y: 0 } : ws.input, 0.05, ws.world);
      }
      const snapshot = { type: 'state', tick, players: [...room.values()].map(ws => ws.player) };
      for (const ws of room.values()) send(ws, snapshot);
    }
  }, 50);
  const heartbeat = setInterval(() => {
    for (const ws of wss.clients) {
      if (!ws.alive) { ws.terminate(); continue; }
      ws.alive = false; ws.ping();
    }
  }, 15000);
  return {
    server, rooms,
    async close() {
      clearInterval(ticker); clearInterval(heartbeat);
      for (const ws of wss.clients) ws.terminate();
      await new Promise(resolve => wss.close(resolve));
      await new Promise(resolve => server.close(resolve));
    },
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const game = createGameServer();
  const port = Number(process.env.PORT || 8787);
  game.server.listen(port, process.env.HOST || '0.0.0.0', () => console.log(`营地已开启：http://localhost:${port}\n同一局域网的朋友可使用这台电脑的局域网 IP 和相同端口。`));
  const stop = async () => { await game.close(); process.exit(0); };
  process.on('SIGINT', stop); process.on('SIGTERM', stop);
}
