// Presentation only: this module never decides damage, drops or saved progress.
export function createCampCombat({ send, getSelfId, getPlayers, connected, canvas }) {
  const $ = id => document.getElementById(id);
  let monsters = [], selectedId, lastAttack = 0, serverOffset = 0;
  const creatureDisplay = new Map();
  function log(text) {
    const li = document.createElement('li'); li.textContent = text;
    $('combat-log').prepend(li);
    while ($('combat-log').children.length > 5) $('combat-log').lastElementChild.remove();
  }
  function progress(c, savedAt) {
    $('hero-name').textContent = c.name;
    $('hero-level').textContent = `Lv.${c.level}`;
    $('hero-hp').value = c.hp; $('hero-hp').max = c.maxHp;
    $('hero-health').textContent = `${c.hp} / ${c.maxHp}`;
    $('hero-xp').textContent = `经验 ${c.xp} · 金币 ${c.gold}`;
    $('hero-loot').textContent = `击败 ${c.kills} · 狼皮 ${c.inventory?.wolfPelt || 0}`;
    $('field-name').textContent=`${c.name} · Lv.${c.level}`;$('field-hp').max=c.maxHp;$('field-hp').value=c.hp;$('field-stats').textContent=`生命 ${c.hp}/${c.maxHp} · 金币 ${c.gold}`;
    if (savedAt) $('save-state').textContent = '角色进度已保存到本机服务器';
  }
  function targetInfo() {
    const wolf = monsters.find(m => m.id === selectedId) || monsters[0];
    if (!wolf) { $('enemy-info').textContent = '进入营地后可挑战野狼'; return; }
    if (!wolf.alive) {
      const left = Math.max(0, Math.ceil((wolf.respawnAt - Date.now() - serverOffset) / 1000));
      $('enemy-info').textContent = `野狼已击败 · 约 ${left} 秒后重新出现`;
    } else $('enemy-info').textContent = `${wolf.name} · ${wolf.hp} / ${wolf.maxHp} 生命`;
  }
  function attack() {
    if (!connected()) return;
    const me = getPlayers().find(p => p.id === getSelfId());
    const candidates = monsters.filter(m => m.alive).sort((a, b) => Math.hypot(a.x-(me?.x||0),a.y-(me?.y||0))-Math.hypot(b.x-(me?.x||0),b.y-(me?.y||0)));
    const target = candidates.find(m => m.id === selectedId) || candidates[0];
    if (!target) return log('野狼尚未重新出现。');
    selectedId = target.id;
    send({ type: 'attack', targetId: target.id });
    canvas.focus({ preventScroll: true });
  }
  $('attack').addEventListener('click', attack);
  $('field-attack').addEventListener('click', attack);
  window.addEventListener('keydown', event => {
    if (!['Space', 'KeyF'].includes(event.code) || ['INPUT','TEXTAREA','BUTTON'].includes(document.activeElement?.tagName)) return;
    if (connected()) { event.preventDefault(); if (!event.repeat) attack(); }
  });
  const timer = setInterval(targetInfo, 500);
  window.addEventListener('pagehide', () => clearInterval(timer), { once:true });
  return {
    log, progress,
    enable(active) { $('attack').disabled = $('field-attack').disabled = !active; $('hero-card').hidden = $('field-hud').hidden = $('field-attack').hidden = !active; if (!active) { monsters=[];creatureDisplay.clear();targetInfo(); } },
    state(msg) { monsters=msg.monsters||[]; if(msg.serverTime)serverOffset=msg.serverTime-Date.now();targetInfo(); },
    event(msg) {
      if (msg.action === 'hit' && msg.attackerId === getSelfId()) { lastAttack=performance.now();log(`命中野狼，造成 ${msg.damage} 点伤害。`); }
      if (msg.action === 'player-hit' && msg.targetId === getSelfId()) log(`受到 ${msg.damage} 点伤害。`);
      if (msg.action === 'respawn' && msg.targetId === getSelfId()) log('你已在营地复活，奖励和进度保留。');
      if (msg.action === 'kill') log('野狼倒下了，参与战斗的冒险者获得奖励。');
    },
    pick(x,y) { const wolf=monsters.find(m=>m.alive&&Math.hypot(m.x-x,m.y-y)<35);if(!wolf)return false;selectedId=wolf.id;targetInfo();log('已选中野狼，靠近后按空格或攻击按钮。');return true; },
    draw(ctx, dt, now) {
      for (const m of monsters) {
        if (!m.alive) continue;
        if(!creatureDisplay.has(m.id))creatureDisplay.set(m.id,{x:m.x,y:m.y});
        const pos=creatureDisplay.get(m.id), t=1-Math.exp(-dt*18);pos.x+=(m.x-pos.x)*t;pos.y+=(m.y-pos.y)*t;
        const {x,y}=pos;
        ctx.save();ctx.translate(x,y);
        ctx.fillStyle='#081b21aa';ctx.beginPath();ctx.ellipse(2,10,27,10,0,0,Math.PI*2);ctx.fill();
        ctx.fillStyle=m.id===selectedId?'#c89b8a':'#a9b8b3';
        ctx.beginPath();ctx.ellipse(0,-2,25,13,0,0,Math.PI*2);ctx.fill();
        ctx.fillRect(-17,4,5,14);ctx.fillRect(12,4,5,14);
        ctx.beginPath();ctx.moveTo(-22,-5);ctx.lineTo(-39,-11);ctx.lineTo(-26,1);ctx.closePath();ctx.fill();
        ctx.beginPath();ctx.moveTo(18,-6);ctx.lineTo(19,-25);ctx.lineTo(27,-16);ctx.lineTo(35,-7);ctx.lineTo(38,1);ctx.lineTo(24,5);ctx.closePath();ctx.fill();
        ctx.fillStyle='#c8e8b6';ctx.fillRect(28,-9,3,3);
        ctx.fillStyle='#112421';ctx.fillRect(-38,-49,76,7);ctx.fillStyle='#d18c79';ctx.fillRect(-38,-49,76*m.hp/m.maxHp,7);
        ctx.font='11px "PingFang SC",sans-serif';ctx.fillStyle='#e8d7b5';ctx.textAlign='center';ctx.fillText(`${m.name} ${m.hp}/${m.maxHp}`,0,-59);
        ctx.restore();
      }
      const me=getPlayers().find(p=>p.id===getSelfId());
      if(me&&now-lastAttack<250){ctx.strokeStyle='#ffe2a8';ctx.lineWidth=4;ctx.beginPath();ctx.arc(me.x,me.y-10,42,-1.5,1.2);ctx.stroke();}
    },
  };
}
