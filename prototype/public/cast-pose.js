export function castPose(cast,now){
  if(!cast?.phaseVisual||!Number.isFinite(cast.phaseAt)||now<cast.phaseAt||cast.stage===-2)return null;
  const age=now-cast.phaseAt,{pre,loop}=cast.phaseVisual;
  if(cast.stage===6&&now>=cast.phaseEndsAt)return null;
  if(pre&&age<pre.durationMs)return {clip:pre.clip,time:age/1000};
  if(loop&&[1,3].includes(cast.stage))return {clip:loop.clip,time:((age-(pre?.durationMs||0))%loop.durationMs)/1000};
  if(pre&&cast.stage===2&&age<=pre.durationMs)return {clip:pre.clip,time:age/1000};
  return null;
}
export const castActive=cast=>Boolean(cast&&(cast.stage===undefined||![6,-2].includes(cast.stage)));
export const castStageName=stage=>({0:'准备',1:'吟唱',2:'释放',3:'引导',6:'收招'})[stage]||'';
