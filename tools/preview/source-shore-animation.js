// Original tracks, original decision; Three.js playback remains a host binding.
import * as base from './character-animation-swimming.js';
import {sourceRun} from './source-shore-motion.js';
export * from './character-animation-swimming.js';
const runners=new WeakMap();
export function createCharacterFactory(THREE,data,materials){
  const factory=base.createCharacterFactory(THREE,data,materials),clip=data.clips.find(c=>c.name==='run_normal');
  if(!clip)return factory; // Other source models keep their existing controller.
  return()=>{
    const root=factory(),bones=base.characterAnimationState(root).bones,mixer=new THREE.AnimationMixer(root);
    const tracks=clip.tracks.map(t=>new( t.type==='quaternion'?THREE.QuaternionKeyframeTrack:THREE.VectorKeyframeTrack)(`${bones[t.node].name}.${t.type}`,t.times,t.values));
    const action=mixer.clipAction(new THREE.AnimationClip(clip.name,clip.duration,tracks)).setLoop(THREE.LoopRepeat,Infinity);
    runners.set(root,{mixer,action,run:false,active:false});return root;
  };
}
export function syncCharacterCombat(root,snapshot,time,attackSeconds){
  base.syncCharacterCombat(root,snapshot,time,attackSeconds);
  const c=runners.get(root);if(c)c.run=sourceRun(snapshot);
}
export function updateCharacterAnimation(root,seconds,motion,time){
  const c=runners.get(root);
  if(c?.active&&!c.run){c.mixer.stopAllAction();c.active=false;}
  base.updateCharacterAnimation(root,seconds,motion,time);
  const state=base.characterAnimationState(root),active=c?.run&&!state?.dead&&['idle','walk'].includes(state?.phase);
  if(c?.active&&!active){c.mixer.stopAllAction();c.active=false;base.updateCharacterAnimation(root,0,motion,time);}
  if(!active)return;
  if(!c.active){c.action.reset().play();c.active=true;}
  c.mixer.update(Math.max(0,Math.min(seconds,.1)));
}
export function characterAnimationState(root){
  const state=base.characterAnimationState(root),c=runners.get(root);
  return state&&c?.active?{...state,phase:'run_normal',jumpHeight:0}:state;
}
export function disposeCharacterAnimation(root){
  const c=runners.get(root);if(c){c.mixer.stopAllAction();c.mixer.uncacheRoot(root);runners.delete(root);}
  base.disposeCharacterAnimation(root);
}
