// Weights and state decisions come from original CPU execution. Three.js track
// sampling/quaternion composition and network frame cadence are host bindings.
import * as base from './character-animation-shore.js';
export * from './character-animation-shore.js';
const controllers=new WeakMap();
export function checkedBlend(packet){
  if(!packet?.available)return null;
  if(packet.nativeStateCPU!==true||packet.nativeBlendCPU!==true||!Array.isArray(packet.weights)||packet.weights.length!==2||
     packet.weights.some(w=>!Number.isFinite(w)||w<0||w>1)||Math.abs(packet.weights[0]+packet.weights[1]-1)>1e-6||
     !Number.isInteger(packet.sequence)||packet.sequence<1||!Number.isFinite(packet.current?.ageMs)||packet.current.ageMs<0||
     (!packet.previous&&packet.weights[1]!==0)||
     (packet.previous&&(!Number.isFinite(packet.previous.ageMs)||packet.previous.ageMs<0)))throw Error('Invalid original locomotion blend packet');
  return packet;
}
export function createCharacterFactory(THREE,data,materials){
  const factory=base.createCharacterFactory(THREE,data,materials);
  if(!data.sourceBlendBinding)return factory;
  return()=>{
    const root=factory(),bones=base.characterAnimationState(root).bones,mixer=new THREE.AnimationMixer(root),actions={};
    for(const clip of data.clips.filter(c=>['idle','walk_forward','swim_idle','swim_forward','run_normal_front','run_idle'].includes(c.name))){
      const tracks=clip.tracks.map(t=>new(t.type==='quaternion'?THREE.QuaternionKeyframeTrack:THREE.VectorKeyframeTrack)(`${bones[t.node].name}.${t.type}`,t.times,t.values));
      const action=mixer.clipAction(new THREE.AnimationClip(clip.name,clip.duration,tracks)).setLoop(THREE.LoopRepeat,Infinity);
      actions[clip.name]=action;
    }
    controllers.set(root,{mixer,actions,packet:null,at:-Infinity,active:false});return root;
  };
}
export function syncCharacterCombat(root,snapshot,time,attackSeconds){
  base.syncCharacterCombat(root,snapshot,time,attackSeconds);
  const c=controllers.get(root);if(!c||time<c.at)return;
  const packet=checkedBlend(snapshot.sourceAnimation);
  if(packet&&(!c.actions[packet.current.clip]||(packet.previous&&!c.actions[packet.previous.clip])))throw Error('Unrecovered original locomotion track');
  c.packet=snapshot.jump?null:packet;c.at=time;
}
export function updateCharacterAnimation(root,seconds,motion,time){
  const c=controllers.get(root);
  if(c?.active&&!c.packet){c.mixer.stopAllAction();c.active=false;}
  base.updateCharacterAnimation(root,seconds,motion,time);
  const state=base.characterAnimationState(root),active=c?.packet&&!state?.dead&&['idle','walk','run_normal','swim_idle','swim_forward'].includes(state?.phase);
  if(c?.active&&!active){c.mixer.stopAllAction();c.active=false;base.updateCharacterAnimation(root,0,motion,time);}
  if(!active)return;
  if(!c.active){for(const a of Object.values(c.actions)){a.reset().play();a.paused=true;}c.active=true;}
  for(const a of Object.values(c.actions))a.setEffectiveWeight(0);
  const p=c.packet,elapsed=Number.isFinite(time)?Math.max(0,time-c.at):0;
  for(const [slot,weight]of [[p.current,p.weights[0]],[p.previous,p.weights[1]]])if(slot){
    const a=c.actions[slot.clip],duration=a.getClip().duration,age=(slot.ageMs+elapsed)/1000;
    a.time=slot.loop===false?Math.min(age,duration):age%duration;a.setEffectiveWeight(weight);
  }
  c.mixer.update(0);
}
export function characterAnimationState(root){
  const state=base.characterAnimationState(root),c=controllers.get(root),p=c?.packet;
  return state&&c?.active?{...state,phase:p.current.clip,jumpHeight:0,sourceBlend:{from:p.previous?.clip||null,to:p.current.clip,weights:p.weights,remainingMs:p.remainingMs,posture:p.posture,movement:p.movement,sequence:p.sequence,nativeCPU:true,...(p.nativeQueueCPU?{nativeQueueCPU:true,completionCount:p.completionCount,ageMs:p.current.ageMs,loop:p.current.loop}: {})}}:state;
}
export function disposeCharacterAnimation(root){
  const c=controllers.get(root);if(c){c.mixer.stopAllAction();c.mixer.uncacheRoot(root);controllers.delete(root);}
  base.disposeCharacterAnimation(root);
}
