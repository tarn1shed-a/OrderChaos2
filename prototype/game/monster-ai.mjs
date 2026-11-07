import {RouteFollower} from './navigation.mjs';

// Original source enums/data are evidence. These server decisions are local:
// passive aggro, damage threat, home leash and safe return/reset are not a
// reconstruction of the missing npc*_ai server scripts.
export const AI_RULES=Object.freeze({leash:220,unreachableMs:3000,returnTolerance:.8});
export class MonsterAI {
  constructor(room,navigation){this.room=room;this.routes=new RouteFollower(navigation,room.motion);this.threat=new Map();this.state='idle';this.targetId=null;this.revision=0;this.publish(0);}
  publish(now,reason=null){
    const map=this.room.gameplay?.npc?.moveActions||{stand:0,chase:2,goBack:3,pause:5,freeze:6};
    const action=this.state==='returning'?map.goBack:this.state==='chasing'?map.chase:this.state==='frozen'?map.freeze:this.state==='blocked'?map.pause:map.stand;
    this.room.monster.ai={state:this.state,targetId:this.targetId,moveAction:action,revision:this.revision,changedAt:now,
      ...(reason?{reason}:{}),routePoints:this.routes.remaining};
  }
  set(state,targetId,now,reason=null){
    if(this.state!==state||this.targetId!==targetId){this.state=state;this.targetId=targetId;this.revision++;this.publish(now,reason);
      this.room.emit({type:'combat',action:'monster-ai',targetId:this.room.monster.id,serverTime:now,ai:{...this.room.monster.ai}});
    }else if(this.room.monster.ai)this.room.monster.ai.routePoints=this.routes.remaining;
  }
  get returning(){return this.state==='returning';}
  hit(ws,amount){if(amount>0)this.threat.set(ws.player.id,(this.threat.get(ws.player.id)||0)+amount);}
  reset(now){this.threat.clear();this.routes.reset();this.set('idle',null,now);}
  evade(now,reason){
    this.routes.reset();this.threat.clear();this.room.contributors.clear();this.room.buffs?.clear(this.room.monster,now,'evade');this.room.publishStatuses(now);
    this.set('returning',null,now,reason);
  }
  tick(now,dt){
    const room=this.room,m=room.monster,home=room.spawn;
    if(!m.alive){this.threat.clear();this.routes.reset();this.set('dead',null,now);return null;}
    if(this.returning){
      const r=this.routes.follow(m,home,now,dt,{...room.world,speed:room.monsterSpeed});
      this.room.monster.ai.routePoints=this.routes.remaining;
      if(r.arrived||Math.hypot(m.x-home.x,m.y-home.y)<=AI_RULES.returnTolerance&&Math.abs(this.routes.world(m)[1]-this.routes.world(home)[1])<2){
        m.hp=m.maxHp;m.slowUntil=0;this.reset(now);
        room.emit({type:'combat',action:'evade-reset',targetId:m.id,targetHp:m.hp,serverTime:now});
      }
      return null;
    }
    if(room.blocked(m,'move',now)){this.set('frozen',this.targetId,now);return null;}
    const candidates=[];
    for(const [id,threat]of this.threat){const ws=room.clients.get(id);if(!ws||ws.player.hp<=0){this.threat.delete(id);continue;}
      candidates.push({ws,threat,distance:Math.hypot(ws.player.x-m.x,ws.player.y-m.y)});}
    candidates.sort((a,b)=>b.threat-a.threat||a.distance-b.distance||a.ws.player.id.localeCompare(b.ws.player.id));
    const target=candidates[0];
    if(!target){if(this.state!=='idle'){this.evade(now,'no-target');return this.tick(now,dt);}return null;}
    const p=target.ws.player;
    if(Math.hypot(m.x-home.x,m.y-home.y)>AI_RULES.leash||Math.hypot(p.x-home.x,p.y-home.y)>AI_RULES.leash||target.distance>AI_RULES.leash){this.evade(now,'home-leash');return this.tick(now,dt);}
    if(target.distance<=room.monsterRange&&Math.abs((m.worldY||0)-(p.worldY||0))<2&&this.routes.clear(this.routes.world(m),this.routes.world(p))){
      this.routes.reset();this.set('attacking',p.id,now);return target;
    }
    const r=this.routes.follow(m,p,now,dt,{...room.world,speed:room.monsterSpeed});
    if(r.stalledMs>=AI_RULES.unreachableMs){this.evade(now,'unreachable');return this.tick(now,dt);}
    this.set(r.blocked?'blocked':'chasing',p.id,now);return null;
  }
}
