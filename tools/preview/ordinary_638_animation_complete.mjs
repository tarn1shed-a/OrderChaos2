// Mechanical 638-only source clock/key consumers. No byte codec or actor state.
const F=Math.fround,MS=F(33.33333206176758),FPS=F(.030000001192092896),EPS=F(.05000000074505806);
const frameMs=n=>{const v=F(n*MS);return Math.trunc(F(v+(v>0?.5:-.5)));};
const ranges={idle:[34993,36600],walk_forward:[-7,1333]};

function checkedClip(clip){
 const expected=ranges[clip?.name];
 if(!expected||clip.startMs!==expected[0]||clip.endMs!==expected[1]||clip.duration!==(expected[1]-expected[0])/1000)
  throw Error('Original638 idle/walk source range required');
 return clip;
}

function quaternion(a,b,w){
 let dot=F(F(a[0]*b[0])+F(a[1]*b[1]));dot=F(F(a[2]*b[2])+dot);dot=F(F(a[3]*b[3])+dot);
 if(dot<0){a=a.map(v=>-v);dot=-dot;}
 if(F(1+dot)<=EPS)throw Error('Uncovered original quaternion branch');
 if(F(1-dot)<EPS){
  const out=a.map((v,i)=>F(v+F(F(b[i]-v)*w)));
  let norm=F(F(out[0]*out[0])+F(out[1]*out[1]));norm=F(norm+F(out[2]*out[2]));norm=F(norm+F(out[3]*out[3]));
  if(norm===0)return out;const inverse=F(1/F(Math.sqrt(norm)));return out.map(v=>F(v*inverse));
 }
 const angle=F(Math.acos(dot)),inverse=F(1/F(Math.sin(angle))),left=F(F(Math.sin(F(F(1-w)*angle)))*inverse),right=F(inverse*F(Math.sin(F(angle*w))));
 return a.map((v,i)=>F(F(v*left)+F(b[i]*right)));
}

function cacheTick(clip,ms){
 // Actual118a6a8 FCVTZU, then118a6c8..6e8 signed CMP/LT source range clamp.
 let tick=Math.max(0,Math.trunc(ms))>>>0;
 tick=Math.max(tick,clip.startMs);return Math.min(tick,clip.endMs);
}

export function sampleSource638Track(track,absoluteMs,state,clip){
 const ms=F(absoluteMs),tick=cacheTick(clip,ms);
 let segment=track.nativeSegments[0];
 for(const value of track.nativeSegments)if(value.startMs<=tick)segment=value;
 const frames=segment.frames,values=segment.values,width=track.nativeClock.components,last=frames.length-1;
 const frame=F(ms*FPS);let at=Math.min(last,Math.max(0,state.get(segment.index)??0));
 if(frame<frames[at]&&at>=1)at--;
 else if(at<last&&frame>=frames[at+1]){
  if(at+1>=last)at++;
  else if(frames[at+2]>frame)at++;
  else at+=2;
 }
 if(at<last&&!(frames[at]<=frame&&frame<=frames[at+1])){
  let low=0,high=frames.length;
  while(low<high){const middle=(low+high)>>>1;if(frames[middle]<=frame)low=middle+1;else high=middle;}
  at=Math.max(0,low-1);
 }
 const left=frameMs(frames[at]);let weight=null;
 if(at!==last&&Math.trunc(ms)!==left){
  const right=frameMs(frames[at+1]);
  if(right!==left){
   weight=Math.max(0,Math.min(1,F(F(ms-left)/F(right-left))));
   if(weight===1){at++;weight=null;}else if(weight===0)weight=null;
  }
 }
 state.set(segment.index,at);
 const a=values.slice(at*width,(at+1)*width);if(weight===null)return a;
 const b=values.slice((at+1)*width,(at+2)*width);
 if(track.type==='quaternion')return quaternion(a,b,weight);
 if(track.nativeInterpolationTarget==='0x116243c')return a.map((v,i)=>F(F(F(1-weight)*v)+F(weight*b[i])));
 return a.map((v,i)=>F(v+F(weight*F(b[i]-v))));
}

export function create638ClipSampler(animation,name){
 if(animation?.format!=='oc2-original638-idle-walk-native-keys-v1'||animation.compressedValueCodecInvented!==false||
    animation.valuesFromOriginalCopyVirtual60!==true||animation.allOriginal44PropertiesRetained!==true||
    animation.repeatedSourceKeysAndSegmentOrderRetained!==true||
    animation.sourceSHA256!=='613cbe7a7fe3aaa5ece10e00f8b18280ac20da77f6cdd67ae9a450bc44d21f9b'||
    animation.nativeSHA256!=='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4')
  throw Error('Original638 native key export required');
 const matches=animation.clips.filter(c=>c.name===name);
 if(matches.length!==1)throw Error('Single original638 action required');
 const clip=structuredClone(checkedClip(matches[0]));
 if(!Array.isArray(clip.tracks)||clip.tracks.length!==44||new Set(clip.tracks.map(t=>`${t.node}/${t.type}`)).size!==44)
  throw Error('All44 original638 tracks required');
 for(const track of clip.tracks){
  const clock=track.nativeClock,width=track.type==='position'?3:track.type==='quaternion'?4:0;
  const expectedInterpolation=track.node==='Camera01-node'?(width===3?'0x116243c':'0x115c894'):(width===3?'0x1160c70':'0x115d0c8');
  if(!width||clock?.timeType!==3||clock.components!==width||clock.msPerFrameBits!=='0x42055555'||clock.framesPerMsBits!=='0x3cf5c290'||
     track.nativeInterpolationTarget!==expectedInterpolation||
     !Array.isArray(track.nativeSegments)||track.nativeSegments.length!==clip.sourceSegments.length||
     track.nativeSegments.some((s,i)=>s.index!==clip.sourceSegments[i]||!s.frames.length||s.values.length!==s.frames.length*width||
      !s.frames.every((v,k)=>Number.isInteger(v)&&v>=0&&v<=65535&&(k===0||s.frames[k-1]<=v))||!s.values.every(Number.isFinite)))
   throw Error('Original638 ordered source keys required');
 }
 const camera=clip.tracks.filter(t=>t.node==='Camera01-node');
 if(camera.length!==2||new Set(camera.map(t=>t.type)).size!==2)throw Error('Original638 camera tracks required');
 const states=clip.tracks.map(()=>new Map());
 return{
  sampleAbsolute(ms){
   if(!Number.isFinite(ms)||F(ms)<clip.startMs||F(ms)>clip.endMs)throw Error('Original638 source time outside action');
   return{sourceMs:F(ms),samples:clip.tracks.map((track,i)=>({node:track.node,type:track.type,
    value:sampleSource638Track(track,ms,states[i],clip)}))};
  },
  reset(){for(const state of states)state.clear();},
  inspect(){return{name:clip.name,startMs:clip.startMs,endMs:clip.endMs,tracks:44,compressedCodecInvented:false};}
 };
}

export function create638FreshClock(sourceClip){
 // Only original fresh1195f3c/1196824 clock: speed1, loop1, no callbacks.
 const clip={...checkedClip(sourceClip)},duration=F(clip.endMs-clip.startMs);let current=clip.startMs;
 return{
  tick(dtMs){
   if(!Number.isFinite(dtMs)||!Number.isFinite(F(dtMs))||dtMs<0)throw Error('Finite nonnegative source clock delta required');
   const next=F(F(current)+F(dtMs));if(!Number.isFinite(next))throw Error('Source clock float overflow');let crossedEnd=false;
   if(next<=clip.endMs)current=next;
   else{
    crossedEnd=true;
    const remainder=duration===0?0:F(F(next-clip.endMs)%duration);
    current=remainder>0?F(clip.startMs+remainder):clip.startMs;
   }
   return{absoluteMs:current,crossedEnd};
  },
  read(){return{absoluteMs:current};}
 };
}
