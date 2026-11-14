// Consume an explicit original two-layer locomotion packet on its own model.
// This does not select a species, create a role, choose a fallback or grant gear.
export function sourceSpeciesPose(profile,packet,clips,elapsedMs=0){
 if(profile?.format!=='oc2-source-species-motion-v1'||!profile.sha256||
  !Number.isFinite(elapsedMs)||elapsedMs<0)throw Error('Explicit species profile and clock required');
 if(!packet?.available)return null;
 const stamp=packet.sourceMotion;
 if(!stamp||['format','sha256','key','race','gender','sourceModelId'].some(k=>stamp[k]!==profile[k]))
  throw Error('Animation packet belongs to another original model');
 if(packet.nativeStateCPU!==true||packet.nativeBlendCPU!==true||packet.nativeQueueCPU!==true||
  packet.nativeLayerQueueCPU!==true||packet.sourceChannels!==2||packet.layerPoseAgreement!==true||
  !Array.isArray(packet.layers)||packet.layers.length!==2||
  packet.layers.some((l,i)=>l.channel!==i)||
  ['current','previous','weights','remainingMs'].some(k=>packet.layers.some(l=>JSON.stringify(l[k])!==JSON.stringify(packet[k])))||
  !Number.isSafeInteger(packet.sequence)||packet.sequence<1||
  !Array.isArray(packet.weights)||packet.weights.length!==2||packet.weights.some(v=>!Number.isFinite(v)||v<0||v>1)||
  Math.abs(packet.weights[0]+packet.weights[1]-1)>1e-6||!packet.current||(!packet.previous&&packet.weights[1]!==0))
  throw Error('Unrecovered original species layer pose');
 const pose=[];
 for(const[slot,weight]of [[packet.current,packet.weights[0]],[packet.previous,packet.weights[1]]]){
  if(!slot)continue;
  const clip=clips.find(c=>c.name===slot.clip),range=profile.ranges[slot.clip];
  if(!clip||!range||!Number.isFinite(slot.ageMs)||slot.ageMs<0||typeof slot.loop!=='boolean'||
   clip.duration!==(range.endMs-range.startMs)/1000||
   JSON.stringify(clip.sourceRangeMs)!==JSON.stringify([range.startMs,range.endMs]))
   throw Error('Original per-model clip range is unavailable');
  const age=(slot.ageMs+elapsedMs)/1000;
  pose.push({clip:slot.clip,timeSeconds:slot.loop?age%clip.duration:Math.min(age,clip.duration),weight});
 }
 if(new Set(pose.map(p=>p.clip)).size!==pose.length)throw Error('Distinct native slots share one unverified action');
 return pose;
}

export function createSpeciesMotionBinding({profile,clips,sample,root}){
 if(typeof sample!=='function'||!root)throw Error('Explicit admitted model and sampler required');
 let packet=null,at=-Infinity,lastPose=null;
 return{
  sync(next,time){
   if(!Number.isFinite(time)||time<at)return false;
   // Validate the complete replacement before mutating the bound state.
   sourceSpeciesPose(profile,next,clips,0);packet=structuredClone(next);at=time;return true;
  },
  update(time){
   if(!Number.isFinite(time)||time<at||!packet)return false;
   const pose=sourceSpeciesPose(profile,packet,clips,time-at);
   if(!pose)return false;
   sample(root,pose);lastPose=pose;return true;
  },
  get state(){return{sourceModelId:profile.sourceModelId,profileSHA256:profile.sha256,at,lastPose:structuredClone(lastPose)};},
 };
}
