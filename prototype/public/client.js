import { WORLD } from './world.js';
import { webSocketEndpoint } from './network.js';

const $ = id => document.getElementById(id);
const canvas = $('world'), ctx = canvas.getContext('2d');
const query = new URLSearchParams(location.search);
if (query.has('room')) $('room').value = query.get('room').slice(0, 16);
let socket, selfId, roomId, connected = false, generation = 0;
let players = [], display = new Map(), keys = new Set(), target = null, view = { scale: 1, ox: 0, oy: 0 };
let lastList = '', reconnect = null, intentional = false, lastFrame = performance.now(), dimensions = { w: 0, h: 0 };
let roomName = '', playerName = '';
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

function status(text, online = false) { $('status').textContent = text; $('lamp').classList.toggle('online', online); }
function message(text) { $('message').textContent = text; }
function send(data) { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(data)); }
function stop() { keys.clear(); target = null; if (connected) send({ type: 'input', x: 0, y: 0 }); }
function reset() {
  connected = false; players = []; display.clear(); lastList = ''; selfId = null;
  for (const id of ['name', 'room', 'join']) $(id).disabled = false;
  $('invite').disabled = $('second').disabled = true; $('leave').hidden = true;
  $('join').firstElementChild.textContent = '进入营地';
  $('touch-controls').classList.remove('active');
  $('map-hint').classList.remove('joined'); $('map-hint').textContent = '在右侧输入名字，与朋友相约同一个营地';
  $('coords').textContent = '等待冒险者进入'; $('latency').textContent = ''; renderRoster();
}

function connect(name, room, retry = false) {
  const epoch = ++generation;
  clearTimeout(reconnect); intentional = false;
  socket?.close();
  status(retry ? '正在重新连接' : '正在进入营地');
  for (const id of ['name', 'room', 'join']) $(id).disabled = true;
  $('leave').hidden = false;
  const ws = new WebSocket(webSocketEndpoint());
  socket = ws;
  let denied = false;
  ws.addEventListener('open', () => { if (epoch === generation) send({ type: 'join', name, room }); });
  ws.addEventListener('message', event => {
    if (epoch !== generation) return;
    const msg = JSON.parse(event.data);
    if (msg.type === 'welcome') {
      selfId = msg.id; roomId = msg.room; connected = true;
      $('invite').disabled = $('second').disabled = false;
      $('join').firstElementChild.textContent = '已进入营地';
      $('touch-controls').classList.add('active');
      $('map-hint').classList.add('joined'); $('map-hint').textContent = 'WASD / 方向键移动 · 点击地面前进';
      status(`营地 ${roomId}`, true); message(retry ? '已重新连接，以新角色身份返回出生点。' : '你已到达。复制邀请链接，等朋友一起出发。');
      const url = new URL(location.href); url.searchParams.set('room', roomId); history.replaceState(null, '', url);
      canvas.focus({ preventScroll: true });
    } else if (msg.type === 'state') {
      players = msg.players;
      const ids = new Set(players.map(p => p.id));
      for (const id of display.keys()) if (!ids.has(id)) display.delete(id);
      for (const p of players) if (!display.has(p.id)) display.set(p.id, { x: p.x, y: p.y });
      renderRoster();
    } else if (msg.type === 'error') { denied = true; message(msg.message); }
    else if (msg.type === 'pong') $('latency').textContent = ` · ${Math.max(0, Date.now() - msg.at)} ms`;
  });
  ws.addEventListener('close', () => {
    if (epoch !== generation) return;
    stop(); reset();
    if (denied || intentional) { status('已离开营地'); return; }
    status('连接中断'); message('连接中断，3 秒后尝试重连。重连后会回到出生点。');
    reconnect = setTimeout(() => connect(name, room, true), 3000);
  });
  ws.addEventListener('error', () => { if (epoch === generation) message('暂时无法连接营地，请确认服务器仍在运行。'); });
}

$('join-form').addEventListener('submit', event => {
  event.preventDefault(); playerName = $('name').value.trim(); roomName = $('room').value.trim().toUpperCase();
  if (!playerName || !/^[A-Z0-9-]{3,16}$/.test(roomName)) return message('请输入名字和有效的营地编号。');
  connect(playerName, roomName);
});
$('leave').addEventListener('click', () => {
  intentional = true; clearTimeout(reconnect); stop(); generation++; socket?.close(); reset(); status('已离开营地'); message('营地仍在这里，随时可以回来。');
});
function inviteURL() { const url = new URL(location.href); url.search = ''; url.searchParams.set('room', roomId); return url.href; }
$('invite').addEventListener('click', async () => {
  const url = inviteURL();
  try { await navigator.clipboard.writeText(url); message('邀请链接已复制。朋友打开后填写名字即可加入。'); }
  catch { message(`复制这个地址邀请朋友：${url}`); }
});
$('second').addEventListener('click', () => { window.open(inviteURL(), '_blank', 'noopener'); });

function renderRoster() {
  $('count').textContent = `${players.length} / 8`;
  const signature = JSON.stringify(players.map(p => [p.id, p.name, p.color]));
  if (signature === lastList) return;
  lastList = signature; $('players').replaceChildren();
  if (!players.length) {
    const li = document.createElement('li'); li.className = 'empty'; li.textContent = '营火已亮，等待你的到来。'; $('players').append(li);
  }
  for (const p of players) {
    const li = document.createElement('li'), icon = document.createElement('span'), name = document.createElement('span'), tag = document.createElement('small');
    icon.className = 'avatar'; icon.textContent = '◇'; icon.style.color = p.color;
    name.textContent = p.name; tag.textContent = p.id === selfId ? '你 · 冒险者' : '同行者';
    li.append(icon, name, tag); $('players').append(li);
  }
}

const movement = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowLeft', 'ArrowDown', 'ArrowRight']);
window.addEventListener('keydown', event => {
  if (!connected || !movement.has(event.code) || ['INPUT', 'TEXTAREA', 'BUTTON'].includes(document.activeElement?.tagName)) return;
  event.preventDefault(); keys.add(event.code); target = null;
});
window.addEventListener('keyup', event => { keys.delete(event.code); });
window.addEventListener('blur', stop);
document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
window.addEventListener('pagehide', () => socket?.close());
canvas.addEventListener('pointerdown', event => {
  if (!connected) return;
  canvas.focus({ preventScroll: true });
  const rect = canvas.getBoundingClientRect();
  target = { x: (event.clientX - rect.left - view.ox) / view.scale, y: (event.clientY - rect.top - view.oy) / view.scale };
});
for (const button of document.querySelectorAll('[data-key]')) {
  button.addEventListener('pointerdown', event => {
    event.preventDefault(); if (!connected) return;
    button.setPointerCapture(event.pointerId); target = null; keys.add(button.dataset.key);
  });
  for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(type, () => keys.delete(button.dataset.key));
}
setInterval(() => {
  if (!connected || document.hidden) return;
  let x = Number(keys.has('KeyD') || keys.has('ArrowRight')) - Number(keys.has('KeyA') || keys.has('ArrowLeft'));
  let y = Number(keys.has('KeyS') || keys.has('ArrowDown')) - Number(keys.has('KeyW') || keys.has('ArrowUp'));
  const me = players.find(p => p.id === selfId);
  if (target && me) {
    const dx = target.x - me.x, dy = target.y - me.y, d = Math.hypot(dx, dy);
    if (d < 12) target = null;
    else { x = dx / d; y = dy / d; }
  }
  send({ type: 'input', x, y });
}, 50);
setInterval(() => { if (connected && !document.hidden) send({ type: 'ping', at: Date.now() }); }, 2000);

// Deterministic, original Canvas scenery. No original game assets or external images.
let seed = 17;
function rand() { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }
const grasses = Array.from({ length: 1500 }, () => ({ x: rand() * WORLD.width, y: rand() * WORLD.height, a: rand(), size: 1 + rand() * 3 }));
function ellipse(x, y, rx, ry, color) { ctx.fillStyle = color; ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2); ctx.fill(); }
function line(points, color, width) { ctx.strokeStyle = color; ctx.lineWidth = width; ctx.beginPath(); points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.stroke(); }
function tree(o) {
  const { x, y, r } = o;
  ellipse(x + 12, y + 14, r * 1.4, r * .62, '#071b2160');
  ctx.fillStyle = '#554e36'; ctx.fillRect(x - 5, y - 30, 10, 42);
  for (let level = 0; level < 3; level++) {
    const yy = y - level * r * .55, ww = r * (1.12 - level * .2);
    ctx.fillStyle = ['#213e39', '#2a4c41', '#38594a'][level];
    ctx.beginPath(); ctx.moveTo(x, yy - r * 1.45); ctx.lineTo(x + ww, yy); ctx.lineTo(x + 8, yy - 6); ctx.lineTo(x, yy + 4); ctx.lineTo(x - ww, yy); ctx.closePath(); ctx.fill();
    line([[x, yy-r*1.45], [x-ww, yy]], '#66806a40', 1.5);
  }
}
function rock(o) {
  ellipse(o.x + 6, o.y + 7, o.r * 1.1, o.r * .6, '#071b2160');
  ctx.fillStyle = '#596960'; ctx.beginPath(); ctx.moveTo(o.x-o.r,o.y);ctx.lineTo(o.x-o.r*.5,o.y-o.r);ctx.lineTo(o.x+o.r*.5,o.y-o.r*.8);ctx.lineTo(o.x+o.r,o.y);ctx.lineTo(o.x+o.r*.4,o.y+o.r*.3);ctx.closePath();ctx.fill();
  line([[o.x-o.r*.5,o.y-o.r],[o.x,o.y-o.r*.3],[o.x+o.r*.5,o.y-o.r*.8]], '#85917b70', 2);
}
function gate(o, time) {
  const { x, y } = o;
  ellipse(x, y + 10, 95, 40, '#0b201c70');
  ellipse(x, y + 5, 72, 31, '#607467'); ellipse(x, y, 66, 26, '#354e45');
  ctx.strokeStyle = '#95b69a60';ctx.lineWidth=2;ctx.beginPath();ctx.ellipse(x,y,58,21,0,0,Math.PI*2);ctx.stroke();
  const glow = ctx.createRadialGradient(x, y - 43, 2, x, y - 43, 85); glow.addColorStop(0, '#8dffe72f'); glow.addColorStop(1, '#8dffe700');ctx.fillStyle=glow;ctx.fillRect(x-90,y-133,180,180);
  for (const dx of [-42, 31]) {
    ctx.fillStyle='#697f70';ctx.fillRect(x+dx,y-105,12,101);ctx.fillStyle='#43594e';ctx.fillRect(x+dx+9,y-105,7,101);
    line([[x+dx+2,y-93],[x+dx+6,y-82],[x+dx+2,y-70]], '#c2d5a780', 2);
  }
  ctx.fillStyle='#778d76';ctx.beginPath();ctx.moveTo(x-43,y-105);ctx.lineTo(x-24,y-127);ctx.lineTo(x+28,y-125);ctx.lineTo(x+47,y-105);ctx.closePath();ctx.fill();
  ctx.fillStyle='#344e43';ctx.fillRect(x-23,y-113,51,9);
  const pulse=reduceMotion ? 1 : 0.8+Math.sin(time*.0014)*.2;
  ctx.globalAlpha=pulse;line([[x,y-89],[x+10,y-73],[x,y-57],[x-10,y-73],[x,y-89]],'#a6ecd3',2);ctx.globalAlpha=1;
}
function avatar(p, position, time) {
  const {x,y}=position;
  const mine=p.id===selfId;
  ellipse(x+3,y+8,16,7,'#07151e80');
  if(mine){ctx.strokeStyle=p.color+'90';ctx.lineWidth=1.3;ctx.beginPath();ctx.ellipse(x,y+6,20,9,0,0,Math.PI*2);ctx.stroke();}
  ctx.fillStyle='#243234';ctx.fillRect(x-8,y-6,6,14);ctx.fillRect(x+2,y-6,6,14);
  ctx.fillStyle=p.color;ctx.beginPath();ctx.moveTo(x,y-31);ctx.lineTo(x+13,y+2);ctx.lineTo(x,y-2);ctx.lineTo(x-13,y+2);ctx.closePath();ctx.fill();
  ellipse(x,y-30,7,8,'#dac8a4');
  ctx.fillStyle='#303b35';ctx.beginPath();ctx.arc(x,y-34,7,Math.PI,0);ctx.fill();
  line([[x+12,y-24],[x+17,y+6]],'#c4ae80',2.5);ellipse(x+12,y-25,3,4,'#c3ead0');
  ctx.font='12px "PingFang SC", sans-serif';ctx.textAlign='center';
  const label=p.name+(mine?' · 你':'');const width=ctx.measureText(label).width;
  ctx.fillStyle='#112722d9';ctx.fillRect(x-width/2-8,y-63,width+16,22);
  ctx.fillStyle=mine?'#c8f0d3':'#e9debe';ctx.fillText(label,x,y-48);
}
function frame(now) {
  const rect=canvas.getBoundingClientRect(), dpr=Math.min(devicePixelRatio||1,2), w=rect.width, h=rect.height;
  if (dimensions.w!==w || dimensions.h!==h || canvas.width!==Math.round(w*dpr)) {
    canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);dimensions={w,h};
  }
  const dt=Math.min((now-lastFrame)/1000,.1); lastFrame=now;
  ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);ctx.fillStyle='#172d2b';ctx.fillRect(0,0,w,h);
  const scale=Math.min(w/WORLD.width,h/WORLD.height)*.96;view={scale,ox:(w-WORLD.width*scale)/2,oy:(h-WORLD.height*scale)/2+20};
  ctx.save();ctx.translate(view.ox,view.oy);ctx.scale(scale,scale);
  const ground=ctx.createRadialGradient(640,440,60,640,440,740);ground.addColorStop(0,'#45604a');ground.addColorStop(.65,'#2b473b');ground.addColorStop(1,'#172e2b');ctx.fillStyle=ground;ctx.fillRect(0,0,WORLD.width,WORLD.height);
  // Small clearings and worn paths lead towards the ancient gate.
  ctx.lineCap='round';ctx.lineJoin='round';
  const path=[[590,880],[620,690],[640,550],[640,430],[750,360],[900,390],[1050,450],[1280,480]];
  line(path,'#7a806137',75);line(path,'#b4ad7f16',45);
  line([[0,470],[200,490],[400,550],[640,550]],'#7a80612b',60);
  for(const g of grasses){
    const onPath=Math.abs(g.x-640)<48&&g.y>430;
    ctx.fillStyle=g.a>.85?'#b0b58a37':g.a>.5?'#66856835':'#152e2a40';
    if(!onPath)ctx.fillRect(g.x,g.y,g.size,g.size*.6);
    if(g.a>.95&&!onPath)line([[g.x,g.y],[g.x-2,g.y-5],[g.x+2,g.y-2]],'#8a9d6b3f',1);
  }
  ctx.strokeStyle='#9fae7830';ctx.lineWidth=2;ctx.setLineDash([5,12]);ctx.strokeRect(14,14,WORLD.width-28,WORLD.height-28);ctx.setLineDash([]);
  // Decorative forest outside the traversable center.
  for(let i=0;i<12;i++){tree({x:55+i*107,y:90+(i%3)*20,r:32+(i%3)*6}); if(i<4||i>8)tree({x:50+i*107,y:820+(i%2)*14,r:34});}
  if(target&&connected){ctx.strokeStyle='#d2d9ab80';ctx.lineWidth=1.5;ctx.beginPath();ctx.ellipse(target.x,target.y,13,7,0,0,Math.PI*2);ctx.stroke();line([[target.x-5,target.y],[target.x+5,target.y]],'#d2d9ab',1);}
  const objects=WORLD.obstacles.map(o=>({y:o.y,draw:()=>o.kind==='tree'?tree(o):o.kind==='gate'?gate(o,now):rock(o)}));
  for(const p of players){const pos=display.get(p.id);if(!pos)continue;const t=reduceMotion?1:1-Math.exp(-dt*18);pos.x+=(p.x-pos.x)*t;pos.y+=(p.y-pos.y)*t;objects.push({y:pos.y,draw:()=>avatar(p,pos,now)});}
  objects.sort((a,b)=>a.y-b.y);for(const o of objects)o.draw();
  // A quiet campfire, rendered below the spawn area.
  ellipse(560,650,24,10,'#102c24a0');line([[546,650],[573,643]],'#887b58',5);line([[550,642],[570,652]],'#887b58',5);
  const flame=ctx.createRadialGradient(560,638,0,560,638,40);flame.addColorStop(0,'#ffcf6a35');flame.addColorStop(1,'#ffcf6a00');ctx.fillStyle=flame;ctx.fillRect(520,598,80,80);
  ctx.fillStyle='#eabf76';ctx.beginPath();ctx.moveTo(552,646);ctx.quadraticCurveTo(549,635,561,621);ctx.quadraticCurveTo(558,635,567,637);ctx.quadraticCurveTo(576,648,552,646);ctx.fill();
  if(!reduceMotion)for(let i=0;i<14;i++){const x=350+(i*139)%650+Math.sin(now*.0003+i)*12,y=260+(i*97)%430+Math.cos(now*.0004+i)*10;ellipse(x,y,1.4,1.4,`rgba(211,228,159,${.25+.2*Math.sin(now*.001+i)})`);}
  ctx.restore();
  const vignette=ctx.createRadialGradient(w/2,h/2,Math.min(w,h)*.2,w/2,h/2,Math.max(w,h)*.72);vignette.addColorStop(0,'#07191c00');vignette.addColorStop(1,'#07191c95');ctx.fillStyle=vignette;ctx.fillRect(0,0,w,h);
  const me=players.find(p=>p.id===selfId);if(me)$('coords').textContent=`${Math.round(me.x)} E / ${Math.round(me.y)} N`;
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
