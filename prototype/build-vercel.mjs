import { cp, readFile, writeFile, mkdir, readdir, stat, mkdtemp, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';

// Static frontend only. Require an actual external game server so we never deploy
// an apparently multiplayer page whose /ws endpoint does not exist.
const check = process.argv.includes('--check');
const endpoint = process.env.GAME_WEBSOCKET_URL || (check ? 'wss://example.invalid/ws' : null);
if (!endpoint) throw new Error('请先配置 GAME_WEBSOCKET_URL=wss://你的联机服务器/ws。仅静态部署不能替代现有多人服务。');
const socket = new URL(endpoint);
if (socket.protocol !== 'wss:' || socket.username || socket.password || socket.search || socket.hash) throw new Error('GAME_WEBSOCKET_URL 必须是不含密码、查询参数或片段的 wss:// 地址。');
const here = fileURLToPath(new URL('./', import.meta.url));
const out = check ? await mkdtemp(resolve(tmpdir(), 'oc2-vercel-check-')) : resolve(here, 'dist-vercel');
const assets = resolve(here, '../game-data/converted');
await readFile(resolve(assets, 'manifest.json')); // Fail before emitting an incomplete resource build.
await mkdir(out, { recursive: true });
await cp(resolve(here, 'public'), out, { recursive: true });
await cp(assets, resolve(out, 'assets'), { recursive: true });
await mkdir(resolve(out, 'vendor'), { recursive: true });
for (const name of ['three.module.js', 'three.core.js']) await cp(resolve(here, 'node_modules/three/build', name), resolve(out, 'vendor', name));
const escaped = socket.href.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;');
for (const page of ['index.html', 'explore.html']) {
  const p = resolve(out, page);
  const html = await readFile(p, 'utf8');
  await writeFile(p, html.replace('<head>', `<head>\n  <meta name="game-websocket" content="${escaped}">`));
}
const csp = `default-src 'self'; connect-src 'self' ${socket.origin}; style-src 'self'; script-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'`;
await writeFile(resolve(out, 'vercel.json'), JSON.stringify({
  $schema: 'https://openapi.vercel.sh/vercel.json',
  headers: [{ source: '/(.*)', headers: [
    { key: 'X-Content-Type-Options', value: 'nosniff' },
    { key: 'Content-Security-Policy', value: csp },
    { key: 'Referrer-Policy', value: 'same-origin' },
  ] }],
}, null, 2));
let files = 0, bytes = 0;
async function measure(dir) { for (const e of await readdir(dir, { withFileTypes: true })) { const p = resolve(dir,e.name); if (e.isDirectory()) await measure(p); else { files++;bytes+=(await stat(p)).size; } } }
await measure(out);
console.log(JSON.stringify({ output: out, files, bytes, websocket: socket.href, note: '只包含前端和转换资源，不包含原始游戏包、数据库和分析目录。' }));
if (check) {
  const manifest = JSON.parse(await readFile(resolve(out, 'assets/manifest.json'), 'utf8'));
  for (const url of [manifest.map.url, manifest.player.url, ...Object.values(manifest.textures)]) await stat(resolve(out, '.' + url));
  if (!(await readFile(resolve(out, 'explore.html'), 'utf8')).includes('game-websocket')) throw new Error('Missing endpoint configuration');
  await rm(out, { recursive: true, force: true });
  console.log('CHECK PASSED: 临时构建和资源引用已验证，测试目录已清理；没有部署。');
}
