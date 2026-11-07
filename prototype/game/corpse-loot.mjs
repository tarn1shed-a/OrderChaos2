import {randomUUID} from 'node:crypto';

// Local encounter policy; original loot tables/ownership scripts are unknown.
export class CorpseLoot {
  constructor(room){this.room=room;this.current=null;}
  begin(now,expiresAt){this.current={generation:randomUUID(),createdAt:now,expiresAt,available:new Set()};}
  grant(id){this.current?.available.add(id);}
  clear(){this.current=null;}
  tick(now){if(this.current&&now>=this.current.expiresAt)this.clear();}
  view(){const c=this.current;return c?{generation:c.generation,expiresAt:c.expiresAt,availableFor:[...c.available]}:null;}
  context(ws,now){
    const c=this.current,r=this.room,m=r.monster,p=ws.player;
    if(!c||now>=c.expiresAt||m.alive||p.hp<=0||!c.available.has(p.id)||r.casts.has(p.id)||p.grounded===false||
      p.jump&&now<p.jump.endsAt||r.blocked(p,'move',now))return null;
    if(Math.hypot(p.x-m.x,p.y-m.y)>24)return null;
    if(Number.isFinite(p.worldY)&&Number.isFinite(m.worldY)&&Math.abs(p.worldY-m.worldY)>2)return null;
    if(r.motion){const from=r.motion.point(p.x,p.y),to=r.motion.point(m.x,m.y);from.y=p.worldY+.5;to.y=m.worldY+.5;
      const hit=r.motion.raycast(from,to);if(hit&&Math.abs(hit.normal.y)<.5)return null;}
    return {kind:'loot',targetId:m.id,generation:c.generation,label:'拾取狼皮',expiresAt:c.expiresAt};
  }
  pick(ws,targetId,generation,now){
    const context=this.context(ws,now);
    if(!context||context.targetId!==targetId||typeof generation!=='string'||generation!==context.generation)
      return this.room.notice(ws,'没有可拾取的掉落，或距离太远');
    // Consume entitlement before persistence/events. Duplicate messages cannot
    // award twice; this room's unclaimed drops are intentionally transient.
    this.current.available.delete(ws.player.id);ws.character.inventory.wolfPelt++;
    this.room.changed(ws,true);this.room.notice(ws,'拾取狼皮 ×1，已保存到背包');
    this.room.emit({type:'combat',action:'loot-picked',attackerId:ws.player.id,targetId:this.room.monster.id,
      generation,serverTime:now,itemId:'wolfPelt',count:1});
  }
}
