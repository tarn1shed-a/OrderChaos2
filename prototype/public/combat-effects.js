import { skillById } from './skills.js';
import { resolveSkillAttachment } from './skill-attachments.js';
import { createParticleRenderer } from './particle-renderer.js';

export function createCombatEffects(THREE,{scene,data,textures,findView,position,camera}) {
  if(data?.format!=='oc2-combat-effects-v4'||!data.attachments?.slots||!['fireCast','fireMissile','fireHit','frostHit'].every(key=>data.effects?.[key]?.verification?.completePayload))throw new Error('原始粒子与挂点参数版本不匹配，请重新构建本地资源');
  const bindings=data.playerSpells?.bindings||{fireball:{cast:'fireCast',missile:'fireMissile',hit:'fireHit'},frost_blast:{hit:'frostHit'}};
  const active=new Map(),seen=new Map(),particles=createParticleRenderer(THREE,{data,textures,camera});
  const statusGeometry=new THREE.RingGeometry(.72,.79,32);
  let disposed=false;
  function attachment(slotName,actorId,targetId,fallback) {
    const slot=data.attachments.slots[slotName],view=findView(slot.owner==='caster'?actorId:targetId);
    return resolveSkillAttachment(THREE,slot,view,position(fallback.x,fallback.y));
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
  function system(entry,key,slot=''){const id=`${key}:${slot}`;if(!entry.systems.has(id)){const root=new THREE.Group();entry.group.add(root);entry.systems.set(id,particles.create(key,`${entry.id}:${id}`,root));}return entry.systems.get(id);}
  function cast(event,now){
    const c=event.cast,skill=skillById(c?.skillId);
    if(!skill||!c?.id||![c.startedAt,c.releaseAt,c.impactAt,c.origin?.x,c.origin?.y,c.target?.x,c.target?.y].every(Number.isFinite)||c.startedAt>now+1000||c.impactAt<=now)return;
    const channel=Boolean(c.channelEndsAt&&!c.executionId);
    add(`cast:${c.id}`,channel?'channel':'cast',c.startedAt,channel?c.channelEndsAt:c.impactAt,{...c,attackerId:event.attackerId});
  }
  function handle(event,now){
    if(event.action==='skill-cast'||event.action==='skill-pulse')cast(event,now);
    if(event.action==='skill-cancel'||event.action==='respawn')for(const [id,e]of active)if(['cast','channel'].includes(e.type)&&(event.castId===e.payload.id||event.castId===e.payload.executionId||event.targetId===e.payload.attackerId)){destroy(e);active.delete(id);}
    if(event.action==='skill-hit'&&skillById(event.skillId)&&event.position&&Number.isFinite(event.serverTime)){
      const type=bindings[event.skillId]?.hit;if(!type)return;const duration=data.effects[type].durationMs;
      if(now>=event.serverTime-1000&&now<event.serverTime+duration)add(`hit:${event.castId}`,type,event.serverTime,event.serverTime+duration,event);
    }
    if((event.action==='player-hit'&&event.targetHp<=0)||event.action==='kill')for(const [id,e]of active)if(['cast','channel'].includes(e.type)&&(e.payload.attackerId===event.targetId||e.payload.targetId===event.targetId)){destroy(e);active.delete(id);}
  }
  function sync(players,monsters,now,projectiles=[]){
    for(const player of players)if(player.hp>0&&player.cast)cast({cast:player.cast,attackerId:player.id},now);
    for(const pending of projectiles)cast(pending,now);
    for(const m of monsters)if(m.alive&&m.slowUntil>now)add(`slow:${m.id}:${m.slowUntil}`,'slow',m.slowUntil-2500,m.slowUntil,{id:m.id,x:m.x,y:m.y});
  }
  function update(now){
    for(const [id,end]of seen)if(end<now)seen.delete(id);
    for(const [id,e]of active){
      if(now>=e.end){destroy(e);active.delete(id);continue;}
      e.group.visible=now>=e.start;if(!e.group.visible)continue;
      const p=e.payload;e.count=0;
      if(e.type==='channel'){
        const key=bindings[p.skillId]?.cast;if(!key)continue;
        for(const slot of data.attachments.effects[key].slots){const at=attachment(slot,p.attackerId,p.targetId,p.origin);if(at)e.count+=system(e,key,slot).update(now-e.start,at,at);}
      }else if(e.type==='cast'){
        // Only the fire cast/missile has a recovered source effect. Frost's source
        // bundle is an impact effect; do not invent a pre-cast particle layer.
        const binding=bindings[p.skillId];if(!binding?.missile)continue;
        e.birthPoses ||= {};
        if(now<p.releaseAt){for(const slot of data.attachments.effects[binding.cast].slots){
          const at=attachment(slot,p.attackerId,p.targetId,p.origin);if(!at)continue;
          e.birthPoses[slot] ||= {position:at.position.clone(),quaternion:at.quaternion.clone(),scale:at.scale.clone()};
          e.count+=system(e,binding.cast,slot).update(now-e.start,at,e.birthPoses[slot]);
        }}
        else{
          for(const[id,value]of e.systems)if(id.startsWith(binding.cast+':')){value.dispose();e.systems.delete(id);}
          const start=attachment('casterRHand',p.attackerId,p.targetId,p.origin),end=attachment('targetChest',p.attackerId,p.targetId,p.target);
          if(!start||!end)continue;e.releasePose ||= start;
          const from=e.releasePose.position,to=end.position,t=Math.max(0,Math.min(1,(now-p.releaseAt)/(p.impactAt-p.releaseAt)));
          const q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(1,0,0),to.clone().sub(from).normalize());
          const at={position:p.skillId==='arcane_missile'?start.position:from.clone().lerp(to,t),quaternion:q,scale:new THREE.Vector3(1,1,1),target:to};
          e.count=system(e,binding.missile,data.attachments.effects[binding.missile].slot).update(now-p.releaseAt,at,at);
        }
      }else if(e.type==='slow'){
        const view=findView(p.id);if(!view?.alive){destroy(e);active.delete(id);continue;}
        e.group.position.copy(view.root.position);e.marker.material.opacity=.3*Math.min(1,(e.end-now)/300);
      }else{
        e.hitPose ||= attachment(data.attachments.effects[e.type].slot,p.attackerId,p.targetId,p.position);
        if(e.hitPose)e.count=system(e,e.type,data.attachments.effects[e.type].slot).update(now-e.start,e.hitPose);
      }
    }
  }
  function clear(){for(const e of active.values())destroy(e);active.clear();seen.clear();}
  return {handle,sync,update,clear,state:()=>({active:active.size,types:[...active.values()].map(e=>e.type),seen:seen.size}),
    attachmentState:()=>[...active.values()].flatMap(e=>[...e.systems.keys()]).join(','),
    particleCount:()=>[...active.values()].reduce((n,e)=>n+e.count,0),
    dispose(){clear();particles.dispose();statusGeometry.dispose();disposed=true;}};
}
