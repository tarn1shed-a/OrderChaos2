// Normal, unmounted native motion (ARM64 build 77f449f2…). See native_gameplay.py.
// Fixed 50 ms web steps differ from the original render-frame timing.
const f = Math.fround;
export const JUMP = Object.freeze({velocity:10, gravity:f(-41.6), riseSlowGravity:-20,
  fallGravity:-75, fastFallGravity:f(-6.7), slowThreshold:3.5, fastThreshold:f(13.1),
  maxVelocityStepMs:100, stepMs:50, startMs:500, landMs:300});
export function jumpAcceleration(velocity) {
  return velocity<=-JUMP.fastThreshold?JUMP.fastFallGravity:velocity<=-JUMP.slowThreshold?JUMP.fallGravity:
    velocity<=JUMP.slowThreshold?JUMP.riseSlowGravity:JUMP.gravity;
}
export function nativeJumpStep({height,velocity,acceleration},milliseconds) {
  if(![height,velocity,acceleration,milliseconds].every(Number.isFinite)||milliseconds<0)throw new Error('Invalid motion step');
  // Position first (0x9e171c). Only the velocity integrator caps dt (0x9e3fbc).
  const nextHeight=f(f(height)+f(f(f(velocity)*f(milliseconds))*f(.001)));
  const nextVelocity=f(f(velocity)+f(f(f(Math.min(milliseconds,100))*f(acceleration))*f(.001)));
  return {height:nextHeight,velocity:nextVelocity,acceleration:jumpAcceleration(nextVelocity)};
}
const samples=[{time:0,height:0,velocity:JUMP.velocity,acceleration:JUMP.gravity}];
while(samples.at(-1).time<5000) {
  const last=samples.at(-1),next=nativeJumpStep(last,JUMP.stepMs);
  if(next.height<=0) {
    // Relative-ground crossing. Original triangle/capsule collision is pending.
    samples.push({...next,height:0,time:last.time+JUMP.stepMs*last.height/(last.height-next.height)});break;
  }
  samples.push({...next,time:last.time+JUMP.stepMs});
}
export const JUMP_SAMPLES=Object.freeze(samples.map(Object.freeze));
export const FLIGHT_MS=samples.at(-1).time;
export function jumpTimeline(now,moving=false) {
  return {startedAt:now,takeoffAt:now,landAt:now+FLIGHT_MS,endsAt:now+FLIGHT_MS+JUMP.landMs,moving:Boolean(moving)};
}
export function jumpPose(jump,now) {
  if(!jump||!Number.isFinite(now)||!['startedAt','takeoffAt','landAt','endsAt'].every(k=>Number.isFinite(jump[k])))return null;
  const {startedAt,takeoffAt,landAt,endsAt}=jump;
  if(!(startedAt===takeoffAt&&takeoffAt<landAt&&landAt<endsAt)||now<startedAt||now>=endsAt)return null;
  const age=now-startedAt;
  const phase=now>=landAt?'jumplandrun':age<JUMP.startMs?'jump_start':'jump_air';
  const start=phase==='jump_start'?startedAt:phase==='jump_air'?startedAt+JUMP.startMs:landAt;
  const duration=phase==='jump_start'?JUMP.startMs:phase==='jump_air'?2000/3:JUMP.landMs;
  let height=0;
  if(now<landAt) {
    const right=samples.findIndex(s=>s.time>=age),a=samples[Math.max(0,right-1)],b=samples[Math.max(0,right)];
    height=a===b?a.height:a.height+(b.height-a.height)*(age-a.time)/(b.time-a.time);
  }
  return {phase,fraction:Math.min(1,(now-start)/duration),height:Math.max(0,height),
    weight:Math.max(0,Math.min(1,(age+16)/60,(endsAt-now)/80))};
}
