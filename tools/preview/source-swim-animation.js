// Existing skeleton/controller identity is retained for portraits/equipment.
// Original swim tracks play over that rig. Original blend/dispatch is still missing.
import * as base from './character-animation.js';
export * from './character-animation.js';
const swimmers=new WeakMap();
export function createCharacterFactory(THREE,data,materials){
  const factory=base.createCharacterFactory(THREE,data,materials);
  return()=>{
    const root=factory(),bones=base.characterAnimationState(root).bones,mixer=new THREE.AnimationMixer(root),actions={};
    for(const clip of data.clips.filter(c=>c.name==='swim_idle'||c.name==='swim_forward')){
      const tracks=clip.tracks.map(track=>{
        const type=track.type==='quaternion'?THREE.QuaternionKeyframeTrack:THREE.VectorKeyframeTrack;
        return new type(`${bones[track.node].name}.${track.type}`,track.times,track.values);
      });
      actions[clip.name]=mixer.clipAction(new THREE.AnimationClip(clip.name,clip.duration,tracks)).setLoop(THREE.LoopRepeat,Infinity);
    }
    swimmers.set(root,{mixer,actions,swimming:false,active:false,phase:'idle'});return root;
  };
}
export function syncCharacterCombat(root,snapshot,serverTime,attackSeconds){
  base.syncCharacterCombat(root,snapshot,serverTime,attackSeconds);
  const c=swimmers.get(root);if(c)c.swimming=snapshot.swimming===true;
}
export function updateCharacterAnimation(root,seconds,motion,serverTime){
  const c=swimmers.get(root),state=base.characterAnimationState(root),active=Boolean(c?.swimming&&!state?.dead&&c.actions.swim_idle&&c.actions.swim_forward);
  if(c?.active&&!active){c.mixer.stopAllAction();c.active=false;}
  if(!active){base.updateCharacterAnimation(root,seconds,motion,serverTime);return;}
  if(!c.active){for(const a of Object.values(c.actions))a.reset().play();c.active=true;}
  c.phase=motion?.moving?'swim_forward':'swim_idle';
  for(const[name,a]of Object.entries(c.actions))a.setEffectiveWeight(name===c.phase?1:0);
  c.mixer.update(Math.max(0,Math.min(seconds,.1)));
}
export function characterAnimationState(root){
  const state=base.characterAnimationState(root),c=swimmers.get(root);
  return state&&c?.active?{...state,phase:c.phase,jumpHeight:0,swimming:true}:state;
}
export function disposeCharacterAnimation(root){
  const c=swimmers.get(root);if(c){c.mixer.stopAllAction();c.mixer.uncacheRoot(root);swimmers.delete(root);}
  base.disposeCharacterAnimation(root);
}
