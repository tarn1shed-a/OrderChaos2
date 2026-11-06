import * as THREE from '/vendor/three.module.js';
import { RESOURCE_WORLD } from './world.js';
import { sampleHeight } from './heightfield.js';
import { webSocketEndpoint } from './network.js';
import { restoreCredentials, rememberCharacter, lastCharacterName, characterSessionWarning } from './character-session.js';

const $ = id => document.getElementById(id);
const viewport = $('viewport'), canvas = $('scene');
const query = new URLSearchParams(location.search);
if (query.has('room')) $('room').value = query.get('room').slice(0, 16);
$('name').value ||= lastCharacterName();
let renderer, scene, camera, terrainMeshes = [], terrainData, mapBounds, origin, heightGrid;
let assets, modelTemplate, ready = false, world = RESOURCE_WORLD, snapshot = [], selfId, socket, connected = false;
let wolfTemplate, monsterSnapshot = [], selectedMonsterId = null, character = null, nextAttackAt = 0, feedbackUntil = 0, saveAt = null;
let attackRange = 32, cooldownMs = 700, serverOffset = 0;
const monsterViews = new Map();
let target = null, keys = new Set(), avatars = new Map(), rosterSignature = '', generation = 0, retryTimer, manualExit = false;
let azimuth = .65, elevation = .58, distance = 24, previous = performance.now(), pointer = null;
const focus = new THREE.Vector3(), raycaster = new THREE.Raycaster(), pointerNDC = new THREE.Vector2(), textureCache = new Map();
const message = text => { $('message').textContent = text; };
const status = (text, online = false) => { $('status').textContent = text; $('lamp').classList.toggle('online', online); };
const send = data => { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(data)); };
async function json(url) { const r = await fetch(url); if (!r.ok) throw new Error(`读取 ${url} 失败（${r.status}）`); return r.json(); }

function logEvent(text, reward = false) {
  const li = document.createElement('li'); li.textContent = text; if (reward) li.className = 'reward';
  $('events').prepend(li); while ($('events').children.length > 6) $('events').lastElementChild.remove();
}
function flash(text) {
  $('combat-feedback').textContent = text; feedbackUntil = Date.now() + 1300;
  $('combat-feedback').classList.add('combat-flash');
}
function updateCharacter(data, savedAt = null) {
  character = data; if (!data) return;
  $('character-panel').hidden = false; $('character-title').textContent = data.name;
  $('level').textContent = `Lv. ${data.level}`; $('hp-text').textContent = `${data.hp} / ${data.maxHp}`;
  $('hp').max = data.maxHp; $('hp').value = data.hp;
  $('field-hud').hidden=false;$('field-name').textContent=`${data.name} · Lv.${data.level}`;
  $('field-hp').max=data.maxHp;$('field-hp').value=data.hp;
  $('field-stats').textContent=`生命 ${data.hp}/${data.maxHp} · 金币 ${data.gold}`;
  const xp = Number(data.xp) || 0, level = Number(data.level) || 1;
  $('xp').value = xp % 60; $('xp-text').textContent = `${xp % 60} / 60（累计 ${xp}）`;
  $('gold').textContent = data.gold; $('kills').textContent = data.kills; $('pelts').textContent = data.inventory?.wolfPelt || 0;
  if (savedAt) saveAt = savedAt;
  const warning = characterSessionWarning();
  $('save-status').textContent = warning || (saveAt ? `服务器已保存 · ${new Date(saveAt).toLocaleTimeString('zh-CN')}` : '恢复凭据已记住 · 进度由服务器保存');
  updateTarget();
}
function nearestMonster() {
  const me = snapshot.find(p => p.id === selfId); if (!me) return null;
  return monsterSnapshot.filter(m => m.alive && m.hp > 0).sort((a,b) => Math.hypot(a.x-me.x,a.y-me.y)-Math.hypot(b.x-me.x,b.y-me.y))[0] || null;
}
function chosenMonster() { return monsterSnapshot.find(m => m.id === selectedMonsterId && m.alive && m.hp > 0) || nearestMonster(); }
function updateTarget() {
  const selected = chosenMonster();
  selectedMonsterId = selected?.id || null;
  if (!connected) { $('target-name').textContent = '等待进入'; $('target-detail').textContent = '靠近野狼，按攻击开始战斗。'; $('attack').disabled = true; $('field-attack').disabled=true; return; }
  if (selected) {
    const me = snapshot.find(p => p.id === selfId);
    const distance = me ? Math.hypot(selected.x-me.x,selected.y-me.y) : Infinity;
    $('target-name').textContent = selected.name;
    $('target-detail').textContent = `${selected.hp} / ${selected.maxHp} 生命 · ${distance > attackRange ? '靠近一些再攻击' : '已进入攻击距离'}`;
    $('attack').disabled = (character?.hp ?? 0) <= 0;
  } else {
    const dead = monsterSnapshot.find(m => !m.alive);
    $('target-name').textContent = dead ? '野狼恢复中' : '等待野狼出现';
    const remaining = dead?.respawnAt ? Math.max(0,Math.ceil((dead.respawnAt-Date.now()-serverOffset)/1000)) : null;
    $('target-detail').textContent = remaining !== null ? `约 ${remaining} 秒后重新出现。` : '当前没有可以攻击的目标。';
    $('attack').disabled = true;
  }
  for (const [id, view] of monsterViews) view.label.classList.toggle('selected',id===selectedMonsterId);
  $('field-attack').disabled=$('attack').disabled;
}
function attack() {
  if (!connected || !character || character.hp <= 0 || Date.now() < nextAttackAt) return;
  const enemy = chosenMonster(); if (!enemy) return;
  selectedMonsterId = enemy.id; target = null;
  send({ type: 'attack', targetId: enemy.id });
  canvas.focus({preventScroll:true});
  // This is only button feedback. Server cooldown and range decide the hit.
  nextAttackAt = Date.now() + cooldownMs;
  $('attack').firstChild.textContent = '挥击中… ';
  setTimeout(() => { $('attack').firstChild.textContent = '攻击野狼 '; },cooldownMs);
}
function prepareFighter(body) {
  body.traverse(obj => {
    if (!obj.isMesh) return;
    obj.material=Array.isArray(obj.material)?obj.material.map(m=>m.clone()):obj.material.clone();
  });
}
function animateFighter(view, now) {
  const swing=Math.max(0,(view.swingUntil||0)-now)/250;
  const lunge=Math.sin(swing*Math.PI)*.28;
  view.body.position.x=Math.sin(view.body.rotation.y)*lunge;
  view.body.position.z=Math.cos(view.body.rotation.y)*lunge;
  view.body.traverse(obj=>{
    if(!obj.isMesh)return;
    for(const m of Array.isArray(obj.material)?obj.material:[obj.material]){
      if(m.emissive)m.emissive.setHex((view.hitUntil||0)>now?0x662719:0x000000);
    }
  });
}
function handleCombat(event) {
  const actor = avatars.get(event.attackerId) || monsterViews.get(event.attackerId);
  const victim = avatars.get(event.targetId) || monsterViews.get(event.targetId);
  if (actor) actor.swingUntil = Date.now()+250;
  if (victim) victim.hitUntil = Date.now()+220;
  if (event.action === 'hit' && event.attackerId === selfId) flash(`命中 −${event.damage}`);
  else if (event.action === 'player-hit' && event.targetId === selfId) flash(`受到 ${event.damage} 点伤害`);
  else if (event.action === 'kill') { flash('野狼已被击败'); logEvent('野狼倒下了。参与战斗者获得奖励。',true); }
  else if (event.action === 'respawn' && event.targetId === selfId) { logEvent('你已在营地恢复生命，继续出发。'); flash('生命已恢复'); }
}

function geometry(data) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(data.positions, 3));
  if (data.normals?.length) g.setAttribute('normal', new THREE.Float32BufferAttribute(data.normals, 3));
  if (data.uvs?.length) g.setAttribute('uv', new THREE.Float32BufferAttribute(data.uvs, 2));
  if (data.colors?.length) g.setAttribute('color', new THREE.Float32BufferAttribute(data.colors, 3));
  if (data.indices?.length) g.setIndex(data.indices);
  if (!data.normals?.length) g.computeVertexNormals();
  g.computeBoundingSphere(); return g;
}

async function texture(url) {
  if (!url) return null;
  if (!textureCache.has(url)) textureCache.set(url, new THREE.TextureLoader().loadAsync(url).then(t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); return t; }));
  return textureCache.get(url);
}

async function loadModel(entry) {
  const data = await json(entry.url), group = new THREE.Group();
  const materials = await Promise.all(data.materials.map(async mat => {
    const tex = await texture(assets.textures[mat.diffuse]);
    return new THREE.MeshStandardMaterial({ map: tex, color: tex ? 0xffffff : 0xa7bda1, roughness: .93, metalness: 0, side: THREE.DoubleSide, alphaTest: .35 });
  }));
  for (const mesh of data.meshes) {
    const geo = geometry(mesh);
    let material = materials[mesh.material ?? 0];
    if (mesh.groups?.length) {
      for (const g of mesh.groups) geo.addGroup(g.start, g.count, g.material ?? 0);
      material = materials;
    }
    const obj = new THREE.Mesh(geo, material); obj.castShadow = true; obj.receiveShadow = true; group.add(obj);
  }
  const box = new THREE.Box3().setFromObject(group), size = box.getSize(new THREE.Vector3()), center = box.getCenter(new THREE.Vector3());
  group.position.set(-center.x, -box.min.y, -center.z);
  const root = new THREE.Group(); root.add(group); root.userData.height = size.y;
  return root;
}

function gridFromPositions(positions) {
  const [min, max] = mapBounds;
  const width = Math.round(max[0] - min[0]) + 1, depth = Math.round(max[2] - min[2]) + 1;
  const values = new Float32Array(width * depth); values.fill(NaN);
  for (let i = 0; i < positions.length; i += 3) {
    const x = Math.round(positions[i] - min[0]), z = Math.round(positions[i + 2] - min[2]);
    if (x >= 0 && x < width && z >= 0 && z < depth) values[z * width + x] = positions[i + 1];
  }
  return { width, depth, values };
}
function heightAt(x, z) {
  const [min] = mapBounds;
  return sampleHeight(heightGrid, x - min[0], z - min[2]);
}
function localPosition(x, y) {
  const [min, max] = mapBounds;
  const xx = min[0] + x / world.width * (max[0] - min[0]);
  const zz = min[2] + y / world.height * (max[2] - min[2]);
  return new THREE.Vector3(xx - origin.x, heightAt(xx, zz) - origin.y, zz - origin.z);
}

async function init() {
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.15;
    scene = new THREE.Scene(); scene.background = new THREE.Color('#90aba6'); scene.fog = new THREE.Fog('#90aba6', 100, 310);
    camera = new THREE.PerspectiveCamera(48, 1, .1, 900);
    scene.add(new THREE.HemisphereLight('#dfecff', '#777f61', 3.1));
    const sun = new THREE.DirectionalLight('#fff1d0', 2.2); sun.position.set(50, 90, 35); sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048); sun.shadow.camera.left = -100; sun.shadow.camera.right = 100; sun.shadow.camera.top = 100; sun.shadow.camera.bottom = -100; sun.shadow.camera.far = 240; sun.shadow.normalBias = .025;
    scene.add(sun);
    assets = await json('/assets/manifest.json');
    terrainData = await json(assets.map.url);
    mapBounds = [terrainData.bounds.min, terrainData.bounds.max];
    origin = new THREE.Vector3((mapBounds[0][0] + mapBounds[1][0]) / 2, mapBounds[0][1], (mapBounds[0][2] + mapBounds[1][2]) / 2);
    heightGrid = terrainData.grid ? { width: terrainData.grid.width, depth: terrainData.grid.height, values: terrainData.grid.heights } : gridFromPositions(terrainData.positions);
    const tg = geometry(terrainData); tg.translate(-origin.x, -origin.y, -origin.z);
    const surfaceTexture = await texture(assets.map.surfaceTexture);
    if (surfaceTexture) { surfaceTexture.wrapS = surfaceTexture.wrapT = THREE.RepeatWrapping; surfaceTexture.repeat.set(36, 36); }
    const ground = new THREE.Mesh(tg, new THREE.MeshStandardMaterial({ map: surfaceTexture, vertexColors: !!terrainData.colors?.length, color: surfaceTexture || terrainData.colors?.length ? 0xffffff : 0x789565, roughness: 1, side: THREE.DoubleSide }));
    ground.receiveShadow = true; scene.add(ground); terrainMeshes.push(ground);
    modelTemplate = await loadModel(assets.player);
    // The wolf uses server state; only the bear remains a passive asset exhibit.
    for (const [i, entry] of (assets.exhibits || []).entries()) {
      const model = await loadModel(entry);
      if (entry.model?.toLowerCase().includes('wolf') || entry.url?.includes('wolf')) { wolfTemplate = model; continue; }
      const spawn = localPosition(world.spawn.x, world.spawn.y); const x = spawn.x + origin.x + 9 + i * 3, z = spawn.z + origin.z - 6;
      model.position.set(x - origin.x, heightAt(x, z) - origin.y, z - origin.z); model.rotation.y = -.8;
      scene.add(model);
    }
    if (!wolfTemplate) throw new Error('转换资源中缺少野狼模型，无法开启战斗');
    // Only explicit converted scene references are served, never raw game data.
    const staticModels = new Map();
    for (const item of assets.scenery || []) {
      if (!staticModels.has(item.model)) staticModels.set(item.model, await loadModel(item));
      for (const inst of item.instances) {
        const model = staticModels.get(item.model).clone(true);
        // Scene meshes use original local-space transforms, not the avatar centering wrapper.
        const child = model.children[0]; child.position.set(0, 0, 0);
        model.position.set(inst.position[0] - origin.x, inst.position[1] - origin.y, inst.position[2] - origin.z);
        model.quaternion.fromArray(inst.quaternion); model.scale.fromArray(inst.scale); scene.add(model);
      }
    }
    $('map-title').textContent = assets.map.label; $('scene-subtitle').textContent = assets.map.subtitle;
    $('asset-detail').textContent = assets.summary;
    $('load-note').textContent = '进入营地，靠近野狼，用空格或攻击按钮开始试炼';
    focus.copy(localPosition(world.spawn.x, world.spawn.y)).add(new THREE.Vector3(0, 1, 0));
    ready = true; $('join').disabled = false; $('join').firstElementChild.textContent = '进入试炼'; status('资源已就绪'); message('同一浏览器填写原来的名字，可恢复服务器上的角色。');
    requestAnimationFrame(draw);
  } catch (error) {
    status('载入失败'); $('load-note').textContent = `${error.message}。请先运行资源转换步骤，详见项目说明。`;
    message('资源未能就绪；刷新可重试。原营地原型仍可使用。'); console.error(error);
  }
}

function updateRoster() {
  $('count').textContent = `${snapshot.length} / 8`;
  const sig = JSON.stringify(snapshot.map(p => [p.id, p.name, p.hp, p.level])); if (sig === rosterSignature) return; rosterSignature = sig;
  $('players').replaceChildren();
  if (!snapshot.length) { const li = document.createElement('li'); li.className = 'empty'; li.textContent = '等待冒险者进入。'; $('players').append(li); }
  for (const p of snapshot) {
    const li = document.createElement('li'), icon = document.createElement('span'), text = document.createElement('span'), tag = document.createElement('small');
    icon.className = 'avatar'; icon.textContent = '◇'; icon.style.color = p.color; text.textContent = p.name; tag.textContent = `Lv.${p.level || 1} · ${p.hp ?? 100} HP${p.id === selfId ? ' · 你' : ''}`; li.append(icon, text, tag); $('players').append(li);
  }
}
function syncAvatars() {
  const ids = new Set(snapshot.map(p => p.id));
  for (const [id, a] of avatars) if (!ids.has(id)) { scene.remove(a.root); a.label.remove(); avatars.delete(id); }
  for (const p of snapshot) {
    if (!avatars.has(p.id)) {
      const root = new THREE.Group(), body = modelTemplate.clone(true);
      prepareFighter(body);
      root.add(body);
      const ring = new THREE.Mesh(new THREE.RingGeometry(.4, .49, 40), new THREE.MeshBasicMaterial({ color: p.color, side: THREE.DoubleSide, transparent: true, opacity: .8 })); ring.rotation.x = -Math.PI/2; ring.position.y = .05; root.add(ring);
      root.position.copy(localPosition(p.x, p.y)); scene.add(root);
      const label = document.createElement('div'); label.className = 'player-label' + (p.id === selfId ? ' mine' : '');
      const name = document.createElement('span'), health = document.createElement('span'); health.className = 'label-health'; name.textContent = p.name + (p.id === selfId ? ' · 你' : ''); label.append(name,health); $('labels').append(label);
      avatars.set(p.id, { root, label, health, target: localPosition(p.x, p.y), body });
    }
    const a = avatars.get(p.id); a.target.copy(localPosition(p.x, p.y));
    a.health.textContent = p.hp <= 0 ? '倒下了 · 即将恢复' : `${p.hp ?? 100} / ${p.maxHp ?? 100}`;
    a.label.classList.toggle('dead',p.hp <= 0);
    a.body.visible = p.hp > 0;
    if (p.id === selfId && character && (p.hp !== character.hp || p.maxHp !== character.maxHp)) updateCharacter({ ...character, hp:p.hp, maxHp:p.maxHp });
  }
}

function syncMonsters() {
  const ids = new Set(monsterSnapshot.map(m => m.id));
  for (const [id, view] of monsterViews) if (!ids.has(id)) { scene.remove(view.root); view.label.remove(); monsterViews.delete(id); }
  for (const m of monsterSnapshot) {
    if (!monsterViews.has(m.id)) {
      const root = new THREE.Group(), body = wolfTemplate.clone(true); root.add(body);
      prepareFighter(body);
      body.traverse(obj => { if (obj.isMesh) obj.userData.monsterId=m.id; });
      const ring = new THREE.Mesh(new THREE.RingGeometry(.65,.74,40),new THREE.MeshBasicMaterial({color:0xe1b872,side:THREE.DoubleSide,transparent:true,opacity:.8})); ring.rotation.x=-Math.PI/2; ring.position.y=.055;root.add(ring);
      root.position.copy(localPosition(m.x,m.y));scene.add(root);
      const label=document.createElement('div'),name=document.createElement('span'),bar=document.createElement('span'),fill=document.createElement('i'),health=document.createElement('span');
      label.className='monster-label';name.textContent=m.name;bar.className='monster-hp';bar.append(fill);health.className='monster-health';label.append(name,bar,health);$('labels').append(label);
      monsterViews.set(m.id,{root,body,label,fill,health,ring,target:localPosition(m.x,m.y),alive:m.alive,height:wolfTemplate.userData.height});
    }
    const view=monsterViews.get(m.id);view.target.copy(localPosition(m.x,m.y));view.alive=m.alive;view.root.visible=m.alive;view.label.hidden=!m.alive;
    view.fill.style.width=`${Math.max(0,m.hp/m.maxHp*100)}%`;view.health.textContent=`${m.hp} / ${m.maxHp}`;
  }
  updateTarget();
}

function resetConnection() {
  $('field-hud').hidden=true;$('field-attack').hidden=true;
  connected = false; snapshot = []; monsterSnapshot = []; selfId = null; keys.clear(); target = null; selectedMonsterId=null; updateRoster(); syncAvatars(); syncMonsters();
  for (const id of ['name', 'room']) $(id).disabled = false;
  $('join').disabled = !ready; $('join').firstElementChild.textContent = '进入试炼'; $('invite').disabled = $('second').disabled = true; $('leave').hidden = true;
  $('touch-controls').classList.remove('active');
}
function connect(name, room, retry = false) {
  clearTimeout(retryTimer); const gen = ++generation; socket?.close(); manualExit = false;
  status(retry ? '正在重连' : '正在加入'); for (const id of ['name', 'room', 'join']) $(id).disabled = true; $('leave').hidden = false;
  const ws = new WebSocket(webSocketEndpoint()); socket = ws; let denied = false;
  const credentials = restoreCredentials(name);
  ws.addEventListener('open', () => { if (generation === gen) send({ type: 'join', scene: 'resources', name, room, ...credentials }); });
  ws.addEventListener('message', event => {
    if (generation !== gen) return; const msg = JSON.parse(event.data);
    if (msg.type === 'welcome') {
      $('field-attack').hidden=false;
      attackRange = msg.combat?.attackRange ?? 32; cooldownMs = msg.combat?.cooldownMs ?? 700; nextAttackAt = 0;
      selfId = msg.id; world = msg.world; connected = true; status(`营地 ${msg.room}`, true);
      rememberCharacter(msg.character,msg.resumeToken); updateCharacter(msg.character,msg.savedAt);
      $('join').firstElementChild.textContent = '已进入试炼'; $('invite').disabled = $('second').disabled = false; $('touch-controls').classList.add('active');
      $('load-note').textContent = '点击野狼选中 · 空格 / F 攻击 · 进度由服务器保存';
      const restored = msg.restored ? '已恢复角色进度。' : '已创建角色，开始第一次试炼。';
      message(characterSessionWarning() || restored); logEvent(restored);
      const url = new URL(location.href); url.searchParams.set('room', msg.room); history.replaceState(null, '', url); canvas.focus({ preventScroll: true });
    } else if (msg.type === 'state') { snapshot = msg.players;monsterSnapshot=msg.monsters||[]; if(msg.serverTime)serverOffset=msg.serverTime-Date.now(); updateRoster(); syncAvatars();syncMonsters(); }
    else if (msg.type === 'progress') {
      const before=character; updateCharacter(msg.character,msg.savedAt);
      if(before&&msg.character.gold>before.gold){const gain=`获得 ${msg.character.xp-before.xp} 经验、${msg.character.gold-before.gold} 金币和狼皮`;logEvent(gain,true);flash(gain);}
      if(before&&msg.character.level>before.level){logEvent(`升级至 Lv.${msg.character.level}，生命已恢复。`,true);flash(`升级！Lv.${msg.character.level}`);}
    }
    else if (msg.type === 'notice') { message(msg.message); }
    else if (msg.type === 'combat') handleCombat(msg);
    else if (msg.type === 'error') { denied = true; message(msg.message); }
    else if (msg.type === 'pong') $('network').textContent = `${Math.max(0, Date.now() - msg.at)} ms · 角色由本地服务器保存`;
  });
  ws.addEventListener('close', () => {
    if (generation !== gen) return; resetConnection();
    if (manualExit || denied) { status('已离开'); return; }
    status('连接中断'); message('3 秒后尝试重连并恢复角色进度。'); retryTimer = setTimeout(() => connect(name, room, true), 3000);
  });
  ws.addEventListener('error', () => { if (generation === gen) message('连接失败，请确认本地服务仍在运行。'); });
}
$('join-form').addEventListener('submit', event => {
  event.preventDefault(); if (!ready) return; const name = $('name').value.trim(), room = $('room').value.trim().toUpperCase();
  if (!name || !/^[A-Z0-9-]{3,16}$/.test(room)) return message('请输入名字和 3–16 位营地编号。'); connect(name, room);
});
$('field-attack').addEventListener('click', attack);
$('leave').addEventListener('click', () => { stop(); manualExit = true; generation++; clearTimeout(retryTimer); socket?.close(); resetConnection(); status('已离开'); message('已离开。使用相同浏览器和角色名字可恢复进度。'); });
$('attack').addEventListener('click',attack);
function inviteURL() { const url = new URL(location.href); url.search = ''; url.searchParams.set('room', $('room').value.trim().toUpperCase()); return url.href; }
$('invite').addEventListener('click', async () => { const url = inviteURL(); try { await navigator.clipboard.writeText(url); message('已复制实验场邀请链接。'); } catch { message(`邀请地址：${url}`); } });
$('second').addEventListener('click', () => window.open(inviteURL(), '_blank', 'noopener'));
$('reset-view').addEventListener('click', () => { azimuth = .65; elevation = .58; distance = 12; });
function stop() { keys.clear(); target = null; if (connected) send({ type: 'input', x: 0, y: 0 }); }
window.addEventListener('blur', stop); window.addEventListener('pagehide', () => socket?.close());
document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
const codes = new Set(['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight']);
window.addEventListener('keydown', e => {
  if(!connected||['INPUT','TEXTAREA'].includes(document.activeElement?.tagName))return;
  if(e.code==='Space'||e.code==='KeyF'){e.preventDefault();if(!e.repeat)attack();return;}
  if(codes.has(e.code)){e.preventDefault();keys.add(e.code);target=null;}
});
window.addEventListener('keyup', e => keys.delete(e.code));
canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('pointerdown', e => { canvas.focus({ preventScroll: true }); pointer = { x: e.clientX, y: e.clientY, button: e.button, moved: false }; canvas.setPointerCapture(e.pointerId); });
canvas.addEventListener('pointermove', e => {
  if (!pointer) return; const dx = e.clientX - pointer.x, dy = e.clientY - pointer.y;
  if (Math.hypot(dx, dy) > 2) pointer.moved = true;
  if (pointer.button === 2 || e.pointerType === 'touch') { azimuth -= dx * .006; elevation = THREE.MathUtils.clamp(elevation + dy * .005, .18, 1.35); pointer.x = e.clientX; pointer.y = e.clientY; }
});
canvas.addEventListener('pointerup', e => {
  if (pointer && !pointer.moved && pointer.button === 0 && connected) {
    const r = canvas.getBoundingClientRect(); pointerNDC.set((e.clientX-r.left)/r.width*2-1, 1-(e.clientY-r.top)/r.height*2); raycaster.setFromCamera(pointerNDC, camera);
    const monstersHit=raycaster.intersectObjects([...monsterViews.values()].filter(v=>v.alive).map(v=>v.root),true).find(hit=>hit.object.userData.monsterId);
    if(monstersHit){selectedMonsterId=monstersHit.object.userData.monsterId;target=null;updateTarget();pointer=null;return;}
    const hit = raycaster.intersectObjects(terrainMeshes)[0];
    if (hit) {
      const [min, max] = mapBounds; target = { x: (hit.point.x+origin.x-min[0])/(max[0]-min[0])*world.width, y: (hit.point.z+origin.z-min[2])/(max[2]-min[2])*world.height };
    }
  }
  pointer = null;
});
canvas.addEventListener('pointercancel', () => { pointer = null; });
canvas.addEventListener('wheel', e => { e.preventDefault(); distance = THREE.MathUtils.clamp(distance * Math.exp(e.deltaY * .001), 4, 160); }, { passive: false });
for (const button of document.querySelectorAll('[data-key]')) {
  button.addEventListener('pointerdown', e => { e.preventDefault(); if (!connected) return; button.setPointerCapture(e.pointerId); target = null; keys.add(button.dataset.key); });
  for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(type, () => keys.delete(button.dataset.key));
}
setInterval(() => {
  if (!connected || document.hidden) return;
  const right = Number(keys.has('KeyD')||keys.has('ArrowRight')) - Number(keys.has('KeyA')||keys.has('ArrowLeft'));
  const back = Number(keys.has('KeyS')||keys.has('ArrowDown')) - Number(keys.has('KeyW')||keys.has('ArrowUp'));
  let x = right*Math.cos(azimuth)+back*Math.sin(azimuth), y = -right*Math.sin(azimuth)+back*Math.cos(azimuth);
  const me = snapshot.find(p => p.id === selfId);
  if (target && me) { const dx=target.x-me.x, dy=target.y-me.y, d=Math.hypot(dx,dy); if(d<2)target=null;else{x=dx/d;y=dy/d;} }
  const len = Math.hypot(x,y); if(len>1){x/=len;y/=len;} send({type:'input',x,y});
}, 50);
setInterval(() => { if(connected&&!document.hidden)send({type:'ping',at:Date.now()}); }, 2000);
setInterval(()=>{if(connected)updateTarget();},500);
function draw(now) {
  const dt = Math.min((now-previous)/1000,.1); previous=now;
  const w=viewport.clientWidth,h=viewport.clientHeight;
  if(canvas.width!==Math.round(w*renderer.getPixelRatio())||canvas.height!==Math.round(h*renderer.getPixelRatio())){renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();}
  for(const [id,a] of avatars){
    const delta=a.target.clone().sub(a.root.position); if(delta.length()>.01)a.body.rotation.y=Math.atan2(delta.x,delta.z);
    a.root.position.lerp(a.target,1-Math.exp(-dt*16));
    animateFighter(a,Date.now());
    if(id===selfId){const dest=a.root.position.clone().add(new THREE.Vector3(0,1,0));focus.lerp(dest,1-Math.exp(-dt*7));$('position').textContent=`${(a.root.position.x+origin.x).toFixed(1)} E / ${(a.root.position.z+origin.z).toFixed(1)} N`;}
  }
  for(const [id,a] of monsterViews){
    const delta=a.target.clone().sub(a.root.position);if(delta.length()>.005)a.body.rotation.y=Math.atan2(delta.x,delta.z);
    a.root.position.lerp(a.target,1-Math.exp(-dt*16));a.ring.visible=id===selectedMonsterId;animateFighter(a,Date.now());
  }
  camera.position.copy(focus).add(new THREE.Vector3(Math.sin(azimuth)*Math.cos(elevation)*distance,Math.sin(elevation)*distance,Math.cos(azimuth)*Math.cos(elevation)*distance));camera.lookAt(focus);
  // Keep the camera above the heightfield when orbiting hills.
  const surface=heightAt(camera.position.x+origin.x,camera.position.z+origin.z)-origin.y;
  if(camera.position.y<surface+1.5){camera.position.y=surface+1.5;camera.lookAt(focus);}
  for(const a of avatars.values()){
    const projected=a.root.position.clone().add(new THREE.Vector3(0,modelTemplate.userData.height+.4,0)).project(camera);
    a.label.hidden=projected.z>1||projected.z< -1;
    a.label.style.left=`${(projected.x*.5+.5)*w}px`;a.label.style.top=`${(-projected.y*.5+.5)*h}px`;
  }
  for(const a of monsterViews.values()){
    const projected=a.root.position.clone().add(new THREE.Vector3(0,a.height+.45,0)).project(camera);
    a.label.hidden=!a.alive||projected.z>1||projected.z< -1;
    a.label.style.left=`${(projected.x*.5+.5)*w}px`;a.label.style.top=`${(-projected.y*.5+.5)*h}px`;
  }
  if(Date.now()>feedbackUntil)$('combat-feedback').classList.remove('combat-flash');
  renderer.render(scene,camera); requestAnimationFrame(draw);
}
init();
