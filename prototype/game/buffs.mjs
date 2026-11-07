// Server-owned transient effects. Durations/descriptions are source evidence;
// scheduling, refresh scope and control arbitration are bounded web policies.
export const CONTROL_POLICY=Object.freeze({
  freeze:Object.freeze(['move','jump','attack','skill']),
  stun:Object.freeze(['move','jump','attack','skill']),
  silence:Object.freeze(['skill']),
  burn:Object.freeze([]),
});
export class BuffRuntime {
  constructor(profile,{emit,pulse,valid=()=>true}){
    this.profile=profile;this.emit=emit;this.pulse=pulse;this.valid=valid;this.targets=new Map();this.sequence=0;
  }
  apply(target,kind,source,now,{durationMs,ticks=0,amount=0,skillId=null}={}){
    const def=this.profile.auras[kind];
    if(!Object.hasOwn(CONTROL_POLICY,kind)||!def||def.maxStack!==1||!Number.isFinite(now)||
      !Number.isFinite(durationMs)||durationMs<=0||durationMs>3600000||!Number.isSafeInteger(ticks)||ticks<0||ticks>100||
      !Number.isFinite(amount)||amount<0||!target?.id||!source?.player?.id)throw new Error('无效服务器状态');
    let bank=this.targets.get(target.id);if(!bank){bank=new Map();this.targets.set(target.id,bank);}
    const old=bank.get(kind);
    const value={id:`buff:${++this.sequence}`,target,kind,source,skillId,amount,ticks,pulsed:0,
      startedAt:now,expiresAt:now+durationMs,interval:ticks?durationMs/ticks:0};
    // One aura per kind per target; replacement invalidates old periodic work.
    bank.set(kind,value);
    this.event(old?'buff-update':'buff-add',value,now);return this.view(value);
  }
  active(target,now){return [...(this.targets.get(target.id)?.values()||[])].filter(v=>v.startedAt<=now&&now<v.expiresAt);}
  has(target,kind,now){return this.active(target,now).some(v=>v.kind===kind);}
  blocked(target,action,now){return this.active(target,now).some(v=>CONTROL_POLICY[v.kind].includes(action));}
  view(v){const d=this.profile.auras[v.kind];return {id:v.id,kind:v.kind,auraId:d.id,runeId:d.runeId,
    casterId:v.source.player.id,skillId:v.skillId,name:d.name,icon:d.icon.url,stacks:1,
    startedAt:v.startedAt,expiresAt:v.expiresAt,durationMs:v.expiresAt-v.startedAt};}
  snapshot(target,now){return this.active(target,now).map(v=>this.view(v));}
  event(action,v,now,reason){this.emit({type:'combat',action,targetId:v.target.id,attackerId:v.source.player.id,
    buff:this.view(v),serverTime:now,...(reason?{reason}:{})});}
  remove(v,now,reason){const bank=this.targets.get(v.target.id);if(bank?.get(v.kind)!==v)return;
    bank.delete(v.kind);if(!bank.size)this.targets.delete(v.target.id);this.event('buff-remove',v,now,reason);}
  clear(target,now,reason='clear'){for(const v of [...(this.targets.get(target.id)?.values()||[])])this.remove(v,now,reason);}
  tick(now){
    for(const bank of [...this.targets.values()])for(const v of [...bank.values()]){
      if(!this.valid(v)){this.remove(v,now,'invalid-owner');continue;}
      while(v.pulsed<v.ticks&&v.startedAt+(v.pulsed+1)*v.interval<=Math.min(now,v.expiresAt)){
        // Increment before callbacks; a lethal pulse may clear the whole bank.
        const scheduledAt=v.startedAt+(++v.pulsed)*v.interval;
        this.pulse(v,now,scheduledAt);
        if(this.targets.get(v.target.id)?.get(v.kind)!==v)break;
      }
      if(now>=v.expiresAt)this.remove(v,now,'expired');
    }
  }
}
