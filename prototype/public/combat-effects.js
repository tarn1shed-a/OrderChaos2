import { skillById } from './skills.js';
import { characterAttachment } from './character-animation.js';
import { createParticleRenderer } from './particle-renderer.js';

export function createCombatEffects(THREE,{scene,data,textures,findView,position,camera}) {
  if(data?.format!=='oc2-combat-effects-v2'||!['fireCast','fireMissile','fireHit','frostHit'].every(key=>data.effects?.[key]?.verification?.completePayload))throw new Error('原始粒子参数版本不匹配，请重新构建本地资源');
  const active=new Map(),seen=new Map(),particles=createParticleRenderer(THREE,{data,textures,camera});
  const statusGeometry=new THREE.RingGeometry(.72,.79,32);
  let disposed=false;
  const pose=point=>({position:point,quaternion:new THREE.Quaternion()});
  function anchor(id,fallback,hand=false) {
    const view=findView(id);
    if(view){
      if(hand){view.root.updateMatrixWorld(true);const at=characterAttachment(view.body,'Bip01_R_Hand',new THREE.Vector3());if(at)return at;}
      return view.root.position.clone().add(new THREE.Vector3(0,hand?1.1:(view.height||.9)*.6,0));
    }
    return position(fallback.x,fallback.y).add(new THREE.Vector3(0,hand?1.1:.6,0));
  }
  function destroy(entry){for(const system of entry.systems.values())system.dispose();entry.marker?.material.dispose();scene.remove(entry.group);}
  function add(id,type,start,end,payload) {
    if(disposed||seen.has(id)||active.has(id))return null;
    while(active.size>=48){const [key,entry]=active.entries().next().value;destroy(entry);active.delete(key);}
    const group=new THREE.Group();group.name=`combat-effect:${type}`;scene.add(group);
    const entry={id,type,start,end,payload,group,systems:new Map(),count:0};active.set(id,entry);seen.set(id,end+10000);
    if(type==='slow'){
      entry.marker=new THREE.Mesh(statusGeometry,new THREE.MeshBasicMaterial({color:0x79cced,side:THREE.DoubleSide,transparent:true,opacity:.3,depthWrite:false}));
      entry.marker.rotation.x=-Math.PI/2;entry.marker.position.y=.06;group.add(entry.marker);
    }
    return entry;
  }
  function system(entry,key){if(!entry.systems.has(key)){const root=new THREE.Group();entry.group.add(root);entry.systems.set(key,particles.create(key,`${entry.id}:${key}`,root));}return entry.systems.get(key);}
  function cast(event,now){
    const c=event.cast,skill=skillById(c?.skillId);
    if(!skill||!c?.id||![c.startedAt,c.releaseAt,c.impactAt,c.origin?.x,c.origin?.y,c.target?.x,c.target?.y].every(Number.isFinite)||c.startedAt>now+1000||c.impactAt<=now)return;
    add(`cast:${c.id}`,'cast',c.startedAt,c.impactAt,{...c,attackerId:event.attackerId});
  }
  function handle(event,now){
    if(event.action==='skill-cast')cast(event,now);
    if(event.action==='skill-cancel'||event.action==='respawn')for(const [id,e]of active)if(e.type==='cast'&&(event.castId===e.payload.id||event.targetId===e.payload.attackerId)){destroy(e);active.delete(id);}
    if(event.action==='skill-hit'&&skillById(event.skillId)&&event.position&&Number.isFinite(event.serverTime)){
      const type=event.skillId==='fireball'?'fireHit':'frostHit',duration=data.effects[type].durationMs;
      if(now>=event.serverTime-1000&&now<event.serverTime+duration)add(`hit:${event.castId}`,type,event.serverTime,event.serverTime+duration,event);
    }
    if((event.action==='player-hit'&&event.targetHp<=0)||event.action==='kill')for(const [id,e]of active)if(e.type==='cast'&&(e.payload.attackerId===event.targetId||e.payload.targetId===event.targetId)){destroy(e);active.delete(id);}
  }
  function sync(players,monsters,now){
    for(const player of players)if(player.hp>0&&player.cast)cast({cast:player.cast,attackerId:player.id},now);
    for(const m of monsters)if(m.alive&&m.slowUntil>now)add(`slow:${m.id}:${m.slowUntil}`,'slow',m.slowUntil-2500,m.slowUntil,{id:m.id,x:m.x,y:m.y});
  }
  function update(now){
    for(const [id,end]of seen)if(end<now)seen.delete(id);
    for(const [id,e]of active){
      if(now>=e.end){destroy(e);active.delete(id);continue;}
      e.group.visible=now>=e.start;if(!e.group.visible)continue;
      const p=e.payload;e.count=0;
      if(e.type==='cast'){
        // Only the fire cast/missile has a recovered source effect. Frost's source
        // bundle is an impact effect; do not invent a pre-cast particle layer.
        if(p.skillId!=='fireball')continue;
        const from=anchor(p.attackerId,p.origin,true);
        e.birthPose ||= pose(from.clone());
        if(now<p.releaseAt){e.count=system(e,'fireCast').update(now-e.start,pose(from),e.birthPose);}
        else{
          if(e.systems.has('fireCast')){e.systems.get('fireCast').dispose();e.systems.delete('fireCast');}
          const to=anchor(p.targetId,p.target),t=Math.max(0,Math.min(1,(now-p.releaseAt)/(p.impactAt-p.releaseAt)));
          const q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1,0,0),to.clone().sub(from).normalize());
          e.count=system(e,'fireMissile').update(now-p.releaseAt,{position:from.clone().lerp(to,t),quaternion:q},e.birthPose);
        }
      }else if(e.type==='slow'){
        const view=findView(p.id);if(!view?.alive){destroy(e);active.delete(id);continue;}
        e.group.position.copy(view.root.position);e.marker.material.opacity=.3*Math.min(1,(e.end-now)/300);
      }else{
        const origin=position(p.position.x,p.position.y);
        if(e.type==='fireHit')origin.y+=(findView(p.targetId)?.height||.9)*.6;
        else origin.y+=.02;
        e.count=system(e,e.type).update(now-e.start,pose(origin));
      }
    }
  }
  function clear(){for(const e of active.values())destroy(e);active.clear();seen.clear();}
  return {handle,sync,update,clear,state:()=>({active:active.size,types:[...active.values()].map(e=>e.type),seen:seen.size}),
    particleCount:()=>[...active.values()].reduce((n,e)=>n+e.count,0),
    dispose(){clear();particles.dispose();statusGeometry.dispose();disposed=true;}};
}
