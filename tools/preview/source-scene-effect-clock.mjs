// Only the recovered default fire/smoke clock; no wall-clock phase or restart.
export function createSourceSceneEffectClock(){
 let first=true,ms=0;
 return {advance(delta,{visible=true,paused=false}={}){
  if(!Number.isFinite(delta)||delta<0)throw Error('场景特效帧时钟无效');
  if(!visible||paused)return ms;
  // e8ed28: float step * root+23c (source default 1), fcvtzu,
  // steps >=2001 become33. First38a keeps the initial clock at0;
  // e907a4 clears it after the first point-spawn decision.
  // FCVTZU W saturates huge positive input. Compare before any JS uint32
  // conversion; otherwise a >=2^32 long frame could wrap below the clamp.
  let step=Math.trunc(Math.fround(Math.fround(delta)*Math.fround(1)));
  if(step>=2001)step=33;
  if(first){first=false;ms=0;}else ms=(ms+step)>>>0;
  return ms;
 },inspect(){return{milliseconds:ms,first,automaticRestart:false};}};
}
