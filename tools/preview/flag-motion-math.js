// Mechanical browser interface for the pinned source flag CPU contracts.
// Source arrays stay in local asset data. This is not original engine source.
const f=Math.fround;
export const FLAG_FORMAT='oc2-source-flag-motion-v1';
export function multiply(a,b){return Array.from({length:16},(_,i)=>f(a[i%4]*b[Math.floor(i/4)*4]+a[4+i%4]*b[Math.floor(i/4)*4+1]+a[8+i%4]*b[Math.floor(i/4)*4+2]+a[12+i%4]*b[Math.floor(i/4)*4+3]));}
function compose(p,q,s){const[x,y,z,w]=q,[sx,sy,sz]=s;return[(1-2*(y*y+z*z))*sx,2*(x*y+z*w)*sx,2*(x*z-y*w)*sx,0,2*(x*y-z*w)*sy,(1-2*(x*x+z*z))*sy,2*(y*z+x*w)*sy,0,2*(x*z+y*w)*sz,2*(y*z-x*w)*sz,(1-2*(x*x+y*y))*sz,0,...p,1].map(f);}
export function sourceQuaternion(a,b,t){
 let dot=f(f(f(f(a[3]*b[3])+f(a[2]*b[2]))+f(a[0]*b[0]))+f(a[1]*b[1]));
 if(dot<0){dot=-dot;a=a.map(v=>-v);}
 if(f(1-dot)<f(.05)){
  const q=a.map((v,i)=>f(v+f(f(b[i]-v)*t))),norm=f(f(f(f(q[0]*q[0])+f(q[1]*q[1]))+f(q[2]*q[2]))+f(q[3]*q[3]));
  if(norm===0)return q;const k=f(1/f(Math.sqrt(norm)));return q.map(v=>f(v*k));
 }
 // The negative-antipode source branch is unreachable after sign correction
 // for verified finite unit flag keys. No invented fallback for bad inputs.
 if(!Number.isFinite(dot)||dot>1||dot<0)throw Error('Invalid source flag quaternion');
 const angle=f(Math.acos(dot)),div=f(Math.sin(angle)),left=f(f(Math.sin(f(f(1-t)*angle)))/div),right=f(f(Math.sin(f(angle*t)))/div);
 return a.map((v,i)=>f(f(v*left)+f(b[i]*right)));
}
export function sourceSample(ch,timeMs){
 const keys=ch.timesMs,n=ch.components,values=ch.values;let at=0;
 while(at+1<keys.length&&keys[at+1]<=timeMs)at++;
 const a=values.slice(at*n,(at+1)*n);
 if(at+1===keys.length||timeMs<=keys[at])return a;
 const t=f(f(timeMs-keys[at])/f(keys[at+1]-keys[at])),b=values.slice((at+1)*n,(at+2)*n);
 return ch.targetType===5?sourceQuaternion(a,b,t):a.map((v,i)=>f(v+f(f(b[i]-v)*t)));
}
export function paletteAt(p,timeMs){
 const nodes=p.nodes.map(n=>({position:n.position,quaternion:n.quaternion,scale:n.scale}));
 for(const c of p.channels){const value=sourceSample(c,timeMs);if(c.targetType===1)nodes[c.node].position=value;else if(c.targetType===5)nodes[c.node].quaternion=value;else if(c.targetType===10)nodes[c.node].scale=value;else throw Error('Unverified original flag property');}
 const world=[];
 for(let i=0;i<nodes.length;i++){const n=nodes[i],local=compose(n.position,n.quaternion,n.scale),parent=p.nodes[i].parent;world.push(parent<0?local:multiply(world[parent],local));}
 return p.bones.flatMap(b=>multiply(world[b.node],b.inverseBindMatrix));
}
export function createFlagClock(){let time=0;return{tick(dt){if(!Number.isFinite(dt)||dt<0)throw Error('Invalid flag clock delta');time=f(time+f(dt));if(time>4000)time=f(time%4000);return time;},value:()=>time};}
export function deform(p,positions,matrices,out=new Float32Array(positions.length)){
 for(let i=0;i<positions.length/3;i++){const x=positions[i*3],y=positions[i*3+1],z=positions[i*3+2];let v=[0,0,0];
  for(let j=0;j<2;j++){const w=p.weights[i][j];if(j&&w<=0)break;const at=p.indices[i][j]*16;
   for(let k=0;k<3;k++)v[k]+=w*(matrices[at+k]*x+matrices[at+4+k]*y+matrices[at+8+k]*z+matrices[at+12+k]);
  }out.set(v,i*3);
 }return out;
}
export function validateFlag(p){
 const finite=(a,n)=>Array.isArray(a)&&a.length===n&&a.every(Number.isFinite);
 if(p?.format!==FLAG_FORMAT||p.normalizationApplied!==false||p.additionalBindShapeApplied!==false||p.originalGPUObserved!==false||p.sourceCompatibilityBootstrap!==true||p.hostClockOrigin!==true||p.hostCPUDeformation!==true||p.range?.name!=='AUTO_Current_Range'||p.range.startMs!==0||p.range.endMs!==4000||p.clock?.loop!==true||p.clock.speed!==1||p.timeScale!==f(1000/30)||p.quaternionThreshold!==f(.05)||
 !Array.isArray(p.nodes)||!p.nodes.length||p.nodes.some((n,i)=>!Number.isInteger(n.parent)||n.parent<-1||n.parent>=i||!finite(n.position,3)||!finite(n.quaternion,4)||!finite(n.scale,3))||
 !Array.isArray(p.bones)||![7,9].includes(p.bones.length)||p.bones.some(b=>!Number.isInteger(b.node)||b.node<0||b.node>=p.nodes.length||!finite(b.inverseBindMatrix,16))||
 !Array.isArray(p.channels)||p.channels.length!==p.bones.length*3||p.channels.some(c=>![1,5,10].includes(c.targetType)||!Number.isInteger(c.node)||c.node<0||c.node>=p.nodes.length||c.components!==(c.targetType===5?4:3)||!Array.isArray(c.timesMs)||!c.timesMs.length||c.timesMs[0]!==0||c.timesMs.some((x,i)=>!Number.isInteger(x)||(i&&x<=c.timesMs[i-1]))||!finite(c.values,c.timesMs.length*c.components))||
 !Array.isArray(p.indices)||!Array.isArray(p.weights)||p.indices.length!==p.weights.length||!p.indices.length||p.weights.some((v,i)=>!finite(v,2)||v.some(x=>x<0||x>1.00001)||p.indices[i]?.length!==4||p.indices[i].some(x=>!Number.isInteger(x)||x<0)||v.some((w,j)=>w>0&&p.indices[i][j]>=p.bones.length)))throw Error('原旗帜骨骼或播放证据不完整');
 return p;
}
