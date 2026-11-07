// Client execution states recovered from 5b8a9c/5b9ed0 and 5d1b20..5d3dec.
// Advancing a chant/channel requires an authoritative signal, not a local timer.
export const CAST_STAGE=Object.freeze({prepare:0,chant:1,release:2,channel:3,end:6,cancelled:-2});
export class CastMachine {
  constructor(spec,now,{watchdogMs=5000}={}){
    this.spec=spec;this.watchdogMs=watchdogMs;this.stage=0;this.phaseAt=now;this.revision=0;this.reason=null;
    this.enter(spec.chantMs>0?1:spec.channelMs>0?3:2,now);
  }
  enter(stage,now){
    this.stage=stage;this.phaseAt=now;this.revision++;
    const visual=this.spec.visuals[String(stage)]||{};
    this.visual=visual;
    this.watchdogAt=[1,3].includes(stage)?now+(stage===1?this.spec.chantMs:this.spec.channelMs)+this.watchdogMs:null;
    // Release end is supplied by the recovered animation duration; the server's
    // projectile/hit schedule is separate from this visual execution timer.
    this.endsAt=stage===2?now+(visual.pre?.durationMs||0):stage===6?now+(visual.pre?.durationMs||0):null;
  }
  signal(stage,now){
    if(!Number.isFinite(now)||now<this.phaseAt||this.stage===6||this.stage===-2)return false;
    if(this.stage===1&&[2,3].includes(stage)){this.enter(stage,now);return true;}
    if(this.stage===3&&stage===6){this.enter(6,now);return true;}
    return false;
  }
  tick(now){
    if(this.watchdogAt!==null&&now>=this.watchdogAt)return this.cancel('等待施法确认超时',now);
    if(this.stage===2&&now>=this.endsAt){this.enter(6,this.endsAt);return true;}
    return false;
  }
  cancel(reason,now){if([6,-2].includes(this.stage))return false;this.stage=-2;this.phaseAt=now;this.revision++;this.reason=reason;this.watchdogAt=null;return true;}
  get done(){return this.stage===6||this.stage===-2;}
  get movement(){return this.visual?.movement||{stopOnEnter:false,interruptOnMove:false};}
  snapshot(){return {stage:this.stage,phaseAt:this.phaseAt,revision:this.revision,watchdogAt:this.watchdogAt,
    phaseEndsAt:this.endsAt,phaseVisual:this.visual,sourceSkillId:this.spec.sourceSkillId,...(this.reason?{cancelReason:this.reason}:{})};}
}
