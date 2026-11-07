// Clip lengths are recovered. This phase schedule and 0.9 world-unit arc are
// explicit local gameplay choices, not recovered native physics or collision.
export const JUMP = Object.freeze({startMs:500,airMs:2000/3,landMs:2600/3,height:.9});
export function jumpTimeline(now) {
  return {startedAt:now,takeoffAt:now+JUMP.startMs,landAt:now+JUMP.startMs+JUMP.airMs,
    endsAt:now+JUMP.startMs+JUMP.airMs+JUMP.landMs};
}
export function jumpPose(jump,now) {
  if(!jump||!Number.isFinite(now)||!['startedAt','takeoffAt','landAt','endsAt'].every(k=>Number.isFinite(jump[k])))return null;
  const {startedAt,takeoffAt,landAt,endsAt}=jump;
  if(!(startedAt<takeoffAt&&takeoffAt<landAt&&landAt<endsAt)||now<startedAt||now>=endsAt)return null;
  const phase=now<takeoffAt?'jump_start':now<landAt?'jump_air':'jump_land';
  const start=phase==='jump_start'?startedAt:phase==='jump_air'?takeoffAt:landAt;
  const end=phase==='jump_start'?takeoffAt:phase==='jump_air'?landAt:endsAt;
  const t=(now-takeoffAt)/(landAt-takeoffAt);
  return {phase,fraction:(now-start)/(end-start),height:t>0&&t<1?4*JUMP.height*t*(1-t):0,
    weight:Math.max(0,Math.min(1,(now-startedAt)/60,(endsAt-now)/80))};
}
