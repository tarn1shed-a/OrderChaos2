// Original rounded-ms key clocks, appended without changing frozen species APIs.
import * as male from './character_human_world_avatar.mjs';
import * as female from './character_human_female_world_avatar.mjs';
const owners=new WeakMap(),FORMAT='oc2-character-source-native-clock-v2';
const apiFor=gender=>gender===0?male:gender===1?female:null;
const member=(api,gender,name)=>api[gender===0?`humanWorld${name}`:`humanFemaleWorld${name}`];
const F=Math.fround,MS_PER_FRAME=F(33.33333206176758),FRAMES_PER_MS=F(.030000001192092896),QUAT_EPSILON=F(.05000000074505806);
const frameMs=frame=>{const value=F(frame*MS_PER_FRAME);return Math.trunc(F(value+(value>0?.5:-.5)));};

export function sourceHumanQuaternionSample(a,b,weight){
 let dot=F(F(a[0]*b[0])+F(a[1]*b[1]));dot=F(F(a[2]*b[2])+dot);dot=F(F(a[3]*b[3])+dot);
 if(dot<0){a=a.map(v=>-v);dot=-dot;}
 if(F(1+dot)<=QUAT_EPSILON)throw Error('Uncovered original antipodal quaternion branch');
 if(F(1-dot)<QUAT_EPSILON){
  const values=a.map((x,i)=>F(x+F(F(b[i]-x)*weight)));
  let norm=F(F(values[0]*values[0])+F(values[1]*values[1]));norm=F(norm+F(values[2]*values[2]));norm=F(norm+F(values[3]*values[3]));
  if(norm===0)return values;const inverse=F(1/F(Math.sqrt(norm)));return values.map(v=>F(v*inverse));
 }
 const angle=F(Math.acos(dot)),inverse=F(1/F(Math.sin(angle))),left=F(F(Math.sin(F(F(1-weight)*angle)))*inverse),right=F(inverse*F(Math.sin(F(angle*weight))));
 return a.map((x,i)=>F(F(x*left)+F(b[i]*right)));
}

export function sourceHumanTrackSample(track,beginMs,timeSeconds){
 const native=track.nativeClock,frames=native.frames,width=native.components,values=native.values;
 const absolute=F(beginMs+timeSeconds*1000),frame=F(absolute*FRAMES_PER_MS);
 let low=0,high=frames.length;
 while(low<high){const middle=(low+high)>>>1;if(frames[middle]<=frame)low=middle+1;else high=middle;}
 const at=Math.max(0,Math.min(frames.length-1,low-1)),left=frameMs(frames[at]),a=values.slice(at*width,(at+1)*width);
 if(at===frames.length-1||Math.trunc(absolute)===left)return a;
 const right=frameMs(frames[at+1]),weight=Math.max(0,Math.min(1,F(F(absolute-left)/F(right-left)))),b=values.slice((at+1)*width,(at+2)*width);
 if(weight===0)return a;if(weight===1)return b;
 return track.type==='quaternion'?sourceHumanQuaternionSample(a,b,weight):a.map((x,i)=>F(x+F(weight*F(b[i]-x))));
}

export function sourceHumanMotionAppearanceGate(input={}){
  const api=apiFor(input.gender),equipment=input.equipment;
  if(!api||input.race!==0||!equipment||typeof equipment!=='object'||Array.isArray(equipment))return{supported:false,reason:'Explicit original human species, appearance and empty equipment required'};
  return member(api,input.gender,'AppearanceGate')(input);
}

export function checkedSourceHumanMotion(manifest,data){
  const clock=manifest?.sourceMotionClock,source=data?.sourceHumanWorld;
  if(clock?.format!==FORMAT||clock.constantBits!=='0x42055555'||clock.framesPerMsBits!=='0x3cf5c290'||clock.quaternionEpsilonBits!=='0x3d4ccccd'||clock.nativeKeySelection!==true||clock.tolerance!==.002||clock.sourceValuesChanged!==false||
     JSON.stringify(source?.motionClock)!==JSON.stringify(clock)||!apiFor(manifest.gender)||manifest.race!==0||
     !Array.isArray(manifest.actions)||!data.clips?.length||manifest.actions.length!==data.clips.length||
     new Set(manifest.actions).size!==manifest.actions.length||new Set(data.clips.map(c=>c.name)).size!==data.clips.length||
     data.clips.some(c=>!manifest.actions.includes(c.name)||c.sourceClock?.startsWith('uint16 absolute frame')!==true||
       c.duration!==(c.sourceRangeMs[1]-c.sourceRangeMs[0])/1000||c.tracks.some(t=>t.times[0]!==0||Math.abs(t.times.at(-1)-c.duration)>1e-9||
        t.nativeClock?.timeType!==3||t.nativeClock.msPerFrameBits!=='0x42055555'||t.nativeClock.framesPerMsBits!=='0x3cf5c290'||
        !t.nativeClock.frames.length||t.nativeClock.values.length!==t.nativeClock.frames.length*t.nativeClock.components))||
     [...(manifest.unadmittedActions||[]),...(manifest.absentActions||[])].some(name=>manifest.actions.includes(name)))throw Error('Original rounded-ms motion descriptor unresolved');
  return{race:0,gender:manifest.gender,sourceModelId:source.sourceModelId,sourceClock:FORMAT};
}

export function createSourceHumanMotionFactory({THREE,manifest,data,materials,createCharacterFactory}){
  const scope=checkedSourceHumanMotion(manifest,data),api=apiFor(scope.gender);
  const make=scope.gender===0?male.createHumanWorldFactory:female.createHumanFemaleWorldFactory;
  const factory=make({THREE,manifest,data,materials,createCharacterFactory});
  const clips=data.clips.map(clip=>new THREE.AnimationClip(clip.name,clip.duration,clip.tracks.map(track=>{
   const value=new(track.type==='quaternion'?THREE.QuaternionKeyframeTrack:THREE.VectorKeyframeTrack)(`node_${track.node}.${track.type}`,track.times,track.values);
   value.createInterpolant=result=>new(class extends THREE.Interpolant{
    constructor(){super(value.times,value.values,track.nativeClock.components,result);}
    evaluate(time){const sampled=sourceHumanTrackSample(track,clip.sourceRangeMs[0],time);for(let i=0;i<sampled.length;i++)this.resultBuffer[i]=sampled[i];return this.resultBuffer;}
   })();
   return value;
  })));
  return()=>{const root=factory(),mixer=new THREE.AnimationMixer(root),actions=new Map();
   for(const clip of clips){const action=mixer.clipAction(clip).setLoop(THREE.LoopOnce,1);action.clampWhenFinished=true;actions.set(clip.name,action);}
   owners.set(root,{api,scope,mixer,actions,lastPose:[]});sampleSourceHumanMotion(root,[{clip:'idle',timeSeconds:0,weight:1}]);return root;};
}

export function sampleSourceHumanMotion(root,pose){
  const entry=owners.get(root);if(!entry)throw Error('Original human motion instance required');
  if(!Array.isArray(pose)||!pose.length||pose.length>2||Math.abs(pose.reduce((s,p)=>s+p.weight,0)-1)>1e-6||
    pose.some(p=>!entry.actions.has(p.clip)||!Number.isFinite(p.timeSeconds)||p.timeSeconds<0||p.timeSeconds>entry.actions.get(p.clip).getClip().duration||!Number.isFinite(p.weight)||p.weight<0||p.weight>1)||
    new Set(pose.map(p=>p.clip)).size!==pose.length)throw Error('Unsupported original human pose/clock/weights');
  entry.mixer.stopAllAction();for(const p of pose){const a=entry.actions.get(p.clip);a.reset().play();a.time=p.timeSeconds;a.paused=true;a.setEffectiveWeight(p.weight);}
  entry.mixer.update(0);root.updateMatrixWorld(true);entry.lastPose=pose.map(p=>({...p}));return true;
}

export function sourceHumanMotionState(root){
  const entry=owners.get(root);if(!entry)return null;
  return{...entry.scope,emptyEquipmentOnly:true,createsRole:false,writesCharacter:false,grantsEquipment:false,height:root.userData.height,pose:entry.lastPose.map(p=>({...p}))};
}

export function disposeSourceHumanMotion(root){
  const entry=owners.get(root);if(!entry)return;
  entry.mixer.stopAllAction();entry.mixer.uncacheRoot(root);
  (entry.scope.gender===0?male.disposeHumanWorldPose:female.disposeHumanFemaleWorldPose)(root);owners.delete(root);
}

export function sourceHumanMotionWrap(THREE,value){
  if(value===0)return THREE.RepeatWrapping;if(value===1||value===2)return THREE.ClampToEdgeWrapping;
  throw Error('Unverified original sampler address');
}
