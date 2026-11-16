// Shared original property math; callers retain their own identity/range gates.
const F=Math.fround;
const MS_PER_FRAME=F(33.33333206176758),FRAMES_PER_MS=F(.030000001192092896),QUAT_EPSILON=F(.05000000074505806);
function frameMs(frame){const scaled=F(frame*MS_PER_FRAME);return Math.trunc(F(scaled+(scaled>0?.5:-.5)));}

// Original11dd664, including the original sign and near-angle branches.
function quaternion(a,b,weight){
 let dot=F(F(a[0]*b[0])+F(a[1]*b[1]));dot=F(F(a[2]*b[2])+dot);dot=F(F(a[3]*b[3])+dot);
 if(dot<0){a=a.map(v=>-v);dot=-dot;}
 if(F(1+dot)<=QUAT_EPSILON)throw Error('Uncovered original antipodal quaternion branch');
 if(F(1-dot)<QUAT_EPSILON){
  const out=a.map((x,i)=>F(x+F(F(b[i]-x)*weight)));
  let norm=F(F(out[0]*out[0])+F(out[1]*out[1]));norm=F(norm+F(out[2]*out[2]));norm=F(norm+F(out[3]*out[3]));
  if(norm===0)return out;const inverse=F(1/F(Math.sqrt(norm)));return out.map(v=>F(v*inverse));
 }
 const angle=F(Math.acos(dot)),inverse=F(1/F(Math.sin(angle)));
 const left=F(F(Math.sin(F(F(1-weight)*angle)))*inverse),right=F(inverse*F(Math.sin(F(angle*weight))));
 return a.map((x,i)=>F(F(x*left)+F(b[i]*right)));
}
function sampleTrack(track,absolute){
 const clock=track.nativeClock,frames=clock.frames,width=clock.components,values=clock.values,frame=F(absolute*FRAMES_PER_MS);
 let low=0,high=frames.length;
 while(low<high){const middle=(low+high)>>>1;if(frames[middle]<=frame)low=middle+1;else high=middle;}
 const at=Math.max(0,Math.min(frames.length-1,low-1)),left=frameMs(frames[at]),a=values.slice(at*width,(at+1)*width);
 if(at===frames.length-1||Math.trunc(absolute)===left)return a;
 const right=frameMs(frames[at+1]);if(right<=left)throw Error('Original key interval must increase');
 const weight=Math.max(0,Math.min(1,F(F(absolute-left)/F(right-left)))),b=values.slice((at+1)*width,(at+2)*width);
 if(weight===0)return a;if(weight===1)return b;
 return track.type==='quaternion'?quaternion(a,b,weight):a.map((x,i)=>F(x+F(weight*F(b[i]-x))));
}
function mixProperty(type,current,previous,weights){
 if(type===5)return quaternion(current,previous,F(weights[1]/F(weights[0]+weights[1])));
 // Original1160988/11679fc accumulates child0, then child1, in float32.
 return current.map((v,i)=>F(F(F(0+F(v*weights[0])))+F(previous[i]*weights[1])));
}

export {frameMs,quaternion,sampleTrack,mixProperty};

// Original 11dd3e0 column-major rotation matrix, without input renormalization.
export function rotationMatrix(q){
 const [x,y,z,w]=q,x2=F(x+x),y2=F(y+y),z2=F(z+z),zz=F(z*z2),base=F(1-F(y*y2));
 return [F(base-zz),F(F(x2*y)+F(z2*w)),F(F(x2*z)-F(y2*w)),0,
  F(F(x2*y)-F(z2*w)),F(F(1-F(x*x2))-zz),F(F(y2*z)+F(x2*w)),0,
  F(F(x2*z)+F(y2*w)),F(F(y2*z)-F(x2*w)),F(base-F(x*x2)),0,0,0,0,1];
}
// Original 3732ac affine multiply. Each original multiply/add rounds to f32.
export function affineMultiply(a,b){
 const o=Array(16).fill(0);o[15]=1;
 for(let c=0;c<3;c++)for(let r=0;r<3;r++)o[c*4+r]=F(F(F(a[r]*b[c*4])+F(a[r+4]*b[c*4+1]))+F(a[r+8]*b[c*4+2]));
 for(let r=0;r<3;r++)o[12+r]=F(F(F(a[r+12]+F(a[r]*b[12]))+F(a[r+4]*b[13]))+F(a[r+8]*b[14]));
 return o;
}
// Original 3d60bc full multiply, used after original 3734f4 inverse.
export function matrixMultiply(a,b){
 const o=Array(16);for(let c=0;c<4;c++)for(let r=0;r<4;r++)o[c*4+r]=F(F(F(F(a[r]*b[c*4])+F(a[r+4]*b[c*4+1]))+F(a[r+8]*b[c*4+2]))+F(a[r+12]*b[c*4+3]));return o;
}
// Original 11dd47c includes conjugation and normalization after trace branch.
export function matrixQuaternion(m){
 const a=m[0],b=m[5],c=m[10],trace=F(F(a+b)+c);let x,y,z,w,s,t;
 if(trace>0){s=F(Math.sqrt(F(trace+1)));t=F(.5/s);x=F(t*F(m[9]-m[6]));y=F(t*F(m[2]-m[8]));z=F(t*F(m[4]-m[1]));w=F(s*.5);}
 else if(a>b&&a>c){s=F(Math.sqrt(F(F(F(a+1)-b)-c)));t=F(.5/s);x=F(s*.5);y=F(t*F(m[1]+m[4]));z=F(t*F(m[8]+m[2]));w=F(t*F(m[9]-m[6]));}
 else if(b>c){s=F(Math.sqrt(F(F(F(b+1)-a)-c)));t=F(.5/s);x=F(t*F(m[1]+m[4]));y=F(s*.5);z=F(t*F(m[6]+m[9]));w=F(t*F(m[2]-m[8]));}
 else{s=F(Math.sqrt(F(F(F(c+1)-a)-b)));t=F(.5/s);x=F(t*F(m[2]+m[8]));y=F(t*F(m[6]+m[9]));z=F(s*.5);w=F(t*F(m[4]-m[1]));}
 const norm=F(F(F(F(w*w)+F(z*z))+F(x*x))+F(y*y));
 if(norm===0)return[-x,-y,-z,w];const k=F(1/F(Math.sqrt(norm)));return[F(-x*k),F(-y*k),F(-z*k),F(w*k)];
}
// Original 3734f4: cofactors in float32, determinant/inverse in float64.
export function matrixInverse(a){
 const mul=(x,y)=>F(x*y),add=(x,y)=>F(x+y),sub=(x,y)=>F(x-y);
 const v18=sub(mul(a[10],a[15]),mul(a[11],a[14])),v13=sub(mul(a[15],a[6]),mul(a[14],a[7])),v2=sub(mul(a[5],a[0]),mul(a[4],a[1])),v3=sub(mul(a[9],a[0]),mul(a[8],a[1])),v12=sub(mul(a[11],a[6]),mul(a[10],a[7])),v17=sub(mul(a[13],a[0]),mul(a[12],a[1])),v23=sub(mul(a[15],a[2]),mul(a[14],a[3])),v6=sub(mul(a[9],a[4]),mul(a[8],a[5])),v11=sub(mul(a[11],a[2]),mul(a[10],a[3])),v5=sub(mul(a[13],a[4]),mul(a[12],a[5])),v9=sub(mul(a[7],a[2]),mul(a[6],a[3])),v7=sub(mul(a[8],a[13]),mul(a[9],a[12]));
 const det=v9*v7+((v23*v6+v12*v17+(v18*v2-v13*v3))-v11*v5);
 if(!(Math.abs(det)>-1.7976931348623157e298))throw Error('Original matrix inverse comparison failed');
 const o=[add(mul(v12,a[13]),sub(mul(v18,a[5]),mul(v13,a[9]))),sub(sub(mul(v23,a[9]),mul(v18,a[1])),mul(v11,a[13])),add(sub(mul(v13,a[1]),mul(v23,a[5])),mul(v9,a[13])),sub(sub(mul(v11,a[5]),mul(v12,a[1])),mul(v9,a[9])),sub(sub(mul(v13,a[8]),mul(v18,a[4])),mul(v12,a[12])),add(sub(mul(v18,a[0]),mul(v23,a[8])),mul(v11,a[12])),sub(sub(mul(v23,a[4]),mul(v13,a[0])),mul(v9,a[12])),add(sub(mul(v12,a[0]),mul(v11,a[4])),mul(v9,a[8])),add(sub(mul(v7,a[7]),mul(v5,a[11])),mul(v6,a[15])),sub(sub(mul(v17,a[11]),mul(v7,a[3])),mul(v3,a[15])),add(sub(mul(v5,a[3]),mul(v17,a[7])),mul(v2,a[15])),sub(sub(mul(v3,a[7]),mul(v6,a[3])),mul(v2,a[11])),sub(sub(mul(v5,a[10]),mul(v7,a[6])),mul(v6,a[14])),add(sub(mul(v7,a[2]),mul(v17,a[10])),mul(v3,a[14])),sub(sub(mul(v17,a[6]),mul(v5,a[2])),mul(v2,a[14])),add(sub(mul(v6,a[2]),mul(v3,a[6])),mul(v2,a[10]))].map(x=>F(x*(1/det)));
 if(o.some(x=>!Number.isFinite(x)))throw Error('Nonfinite original inverse result is outside admitted pose domain');return o;
}
