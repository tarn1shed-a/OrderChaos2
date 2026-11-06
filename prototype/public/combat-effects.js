import { skillById } from './skills.js';
import { characterAttachment } from './character-animation.js';

// Recovered BEFF texture dependencies/lifetimes. Choreography is a web adaptation;
// opaque source emitters, shaders and their attachment transforms are not executed.
export function createCombatEffects(THREE, { scene, data, textures, findView, position }) {
  if (data?.format !== 'oc2-combat-effects-v1' || !['fireCast','fireMissile','fireHit','frostHit'].every(key => data.effects?.[key])) throw new Error('技能特效资源版本不匹配，请重新构建本地资源');
  const active = new Map(), seen = new Map();
  const plane = new THREE.PlaneGeometry(1,1);
  let disposed = false;
  function map(effect, basename) {
    const definition = data.effects[effect];
    const path = definition.textures.find(name => name.split('/').at(-1) === basename);
    const texture = textures.get(definition.textureURLs[path]);
    if (!texture) throw new Error(`缺少技能贴图：${basename}`);
    return texture;
  }
  const maps = {
    charge: map('fireCast','fire_015.tga'), flare: map('fireCast','fx_sun.tga'),
    missile: map('fireMissile','jpg_s_fire012e.tga'), glow: map('fireMissile','blur_a.tga'),
    fire: map('fireHit','fire03_xulie4x4.tga'), streak: map('fireHit','fx_stick.tga'),
    ring: map('frostHit','quan_02.tga'), rays: map('frostHit','ray045.tga'),
    ice: map('frostHit','fx_iceblock01.tga'), shards: map('frostHit','ice06.tga'),
  };
  function sprite(group, texture, size, color=0xffffff, atlas=false) {
    const image = atlas ? texture.clone() : texture;
    if (atlas) { image.repeat.set(.25,.25); image.needsUpdate=true; }
    const material = new THREE.SpriteMaterial({ map: image, color, blending: THREE.AdditiveBlending,
      depthWrite: false, transparent: true, toneMapped: false });
    const node = new THREE.Sprite(material); node.scale.set(size,size,1); node.renderOrder=3;
    node.userData.baseSize=size; node.userData.ownsMap=atlas;
    group.add(node); return node;
  }
  function ring(group, size, opacity=1) {
    const material = new THREE.MeshBasicMaterial({ map: maps.ring, color: 0x7ddcff, side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity, toneMapped: false });
    const node = new THREE.Mesh(plane,material); node.rotation.x=-Math.PI/2;node.scale.setScalar(size);node.position.y=.08;
    group.add(node);return node;
  }
  function destroy(entry) {
    scene.remove(entry.group);
    entry.group.traverse(node => { if(node.material){ if(node.userData.ownsMap)node.material.map.dispose(); node.material.dispose(); } });
  }
  function add(id,type,start,end,payload) {
    if (disposed || seen.has(id) || active.has(id)) return null;
    // Bound both GPU use and replay bookkeeping, including extended multiplayer sessions.
    while (active.size>=48) { const [key,entry]=active.entries().next().value;destroy(entry);active.delete(key); }
    const group=new THREE.Group();group.name=`combat-effect:${type}`;scene.add(group);
    const entry={id,type,start,end,payload,group,nodes:[]};active.set(id,entry);seen.set(id,end+10000);
    if(type==='cast') {
      if(payload.skillId==='fireball') {
        entry.nodes=[sprite(group,maps.charge,1.7),sprite(group,maps.flare,1.05,0xff9a50),sprite(group,maps.missile,1.8)];
        entry.trail=Array.from({length:5},()=>sprite(group,maps.glow,.8,0xff721c));
      } else entry.nodes=[ring(group,2.6,.55),sprite(group,maps.rays,2.2,0x82ccff)];
    } else if(type==='fireHit') {
      entry.nodes=[sprite(group,maps.fire,3.1,0xffffff,true),sprite(group,maps.streak,3.2,0xffbc73)];
    } else if(type==='frostHit') {
      entry.nodes=[ring(group,2),sprite(group,maps.rays,4,0x65bfff),sprite(group,maps.shards,3.4,0xa4eaff)];
      entry.particles=Array.from({length:10},()=>sprite(group,maps.ice,.5,0x90dfff));
    } else entry.nodes=[ring(group,2.4,.23)];
    return entry;
  }
  function anchor(id,fallback,hand=false) {
    const view=findView(id);
    if(view) {
      if(hand) {
        view.root.updateMatrixWorld(true);
        const at=characterAttachment(view.body,'Bip01_R_Hand',new THREE.Vector3());
        if(at)return at;
      }
      return view.root.position.clone().add(new THREE.Vector3(0,hand?1.1:.65,0));
    }
    return position(fallback.x,fallback.y).add(new THREE.Vector3(0,hand?1.1:.65,0));
  }
  function cast(event,now) {
    const c=event.cast, skill=skillById(c?.skillId);
    if(!skill||!c?.id||![c.startedAt,c.releaseAt,c.impactAt,c.origin?.x,c.origin?.y,c.target?.x,c.target?.y].every(Number.isFinite)||c.startedAt>now+1000||c.impactAt<=now)return;
    add(`cast:${c.id}`,'cast',c.startedAt,c.impactAt,{...c,attackerId:event.attackerId});
  }
  function handle(event,now) {
    if(event.action==='skill-cast')cast(event,now);
    if(event.action==='skill-cancel'||event.action==='respawn') {
      for(const [id,e] of active)if(e.type==='cast'&&(event.castId===e.payload.id||event.targetId===e.payload.attackerId)) {destroy(e);active.delete(id);}
    }
    if(event.action==='skill-hit'&&skillById(event.skillId)&&event.position&&Number.isFinite(event.serverTime)) {
      const type=event.skillId==='fireball'?'fireHit':'frostHit',duration=data.effects[type].durationMs;
      if(now>=event.serverTime-1000&&now<event.serverTime+duration)add(`hit:${event.castId}`,type,event.serverTime,event.serverTime+duration,event);
    }
    if((event.action==='player-hit'&&event.targetHp<=0)||event.action==='kill') {
      for(const [id,e] of active)if(e.type==='cast'&&(e.payload.attackerId===event.targetId||e.payload.targetId===event.targetId)) {destroy(e);active.delete(id);}
    }
  }
  function sync(players,monsters,now) {
    for(const player of players)if(player.hp>0&&player.cast)cast({cast:player.cast,attackerId:player.id},now);
    for(const monster of monsters)if(monster.alive&&monster.slowUntil>now) {
      const id=`slow:${monster.id}:${monster.slowUntil}`;
      const entry=add(id,'slow',monster.slowUntil-2500,monster.slowUntil,{id:monster.id,x:monster.x,y:monster.y});
      if(entry)entry.group.position.copy(position(monster.x,monster.y));
    }
  }
  function update(now) {
    for(const [key,expiry] of seen)if(expiry<now)seen.delete(key);
    for(const [id,e] of active) {
      if(now>=e.end) {destroy(e);active.delete(id);continue;}
      e.group.visible=now>=e.start;if(!e.group.visible)continue;
      const t=(now-e.start)/(e.end-e.start),fade=Math.min(1,(1-t)*4),p=e.payload;
      if(e.type==='cast') {
        const from=anchor(p.attackerId,p.origin,true),to=anchor(p.targetId,p.target);
        if(p.skillId==='fireball') {
          const released=now>=p.releaseAt;
          e.nodes[0].visible=e.nodes[1].visible=!released;e.nodes[2].visible=released;
          e.nodes[0].position.copy(from);e.nodes[1].position.copy(from);
          e.nodes[0].material.rotation=(now-e.start)*.004;
          const progress=Math.max(0,Math.min(1,(now-p.releaseAt)/(p.impactAt-p.releaseAt)));
          e.nodes[2].position.copy(from).lerp(to,progress);e.nodes[2].material.rotation=(now-e.start)*.008;
          e.trail.forEach((node,index)=>{node.visible=released;node.position.copy(from).lerp(to,Math.max(0,progress-index*.09));node.material.opacity=(1-index/6)*.65;});
        } else {
          const view=findView(p.attackerId);
          e.group.position.copy(view?.root.position||position(p.origin.x,p.origin.y));
          e.nodes[0].scale.setScalar(1.2+t*1.7);e.nodes[0].material.opacity=.35+t*.3;
          e.nodes[1].position.y=.9;e.nodes[1].material.opacity=.25+t*.5;e.nodes[1].material.rotation=t*2;
        }
      } else if(e.type==='slow') {
        const view=findView(p.id);
        if(!view||!view.alive){destroy(e);active.delete(id);continue;}
        e.group.position.copy(view.root.position);e.nodes[0].material.opacity=.2*fade;
      } else {
        e.group.position.copy(position(p.position.x,p.position.y));
        if(e.type==='fireHit') {
          e.nodes[0].position.y=.8;e.nodes[1].position.y=.8;
          const frame=Math.min(15,Math.floor(t*16));e.nodes[0].material.map.offset.set((frame%4)/4,(3-Math.floor(frame/4))/4);
          e.nodes[0].material.opacity=fade;e.nodes[1].material.opacity=(1-t)*.65;
          e.nodes[1].material.rotation=t*2;
        } else {
          e.nodes[0].scale.setScalar(2+t*5);e.nodes[0].material.opacity=fade*.9;
          e.nodes[1].position.y=.7;e.nodes[1].material.opacity=(1-t)*.8;e.nodes[1].material.rotation=t;
          e.nodes[2].position.y=.8;e.nodes[2].material.opacity=fade;
          e.particles.forEach((node,index)=>{
            const angle=index*Math.PI*2/10+.3,radius=.3+t*(1.5+(index%3)*.35);
            node.position.set(Math.cos(angle)*radius,.3+Math.sin(t*Math.PI)*1.3+(index%3)*.15,Math.sin(angle)*radius);
            node.material.opacity=fade;node.material.rotation=t*4+index;
          });
        }
      }
    }
  }
  function clear() { for(const e of active.values())destroy(e);active.clear();seen.clear(); }
  return { handle, sync, update, clear,
    state:()=>({active:active.size,types:[...active.values()].map(e=>e.type),seen:seen.size}),
    dispose(){clear();plane.dispose();disposed=true;} };
}
