// v9 curves run at integer 30 FPS frames. Random streams are local, deterministic
// per confirmed cast; distributions/parameters come from the decoded source.
const FRAME_MS = Math.fround(1000/30), FRAME_RATE = Math.fround(.03);
export function sampleParticleCurve(curve, milliseconds) {
  const {frames,values}=curve;
  let ms=Math.max(0,Math.trunc(milliseconds));
  const last=frames.at(-1);
  if(curve.loop&&last>0)ms%=Math.trunc(Math.fround((last+1)*FRAME_MS));
  else if(ms>=Math.fround(last*FRAME_MS))return values.at(-1);
  const frame=Math.trunc(Math.fround(Math.fround(ms)*FRAME_RATE));
  if(frame<=frames[0])return values[0];
  let index=1;while(index<frames.length&&frames[index]<frame)index++;
  if(index>=frames.length)return values.at(-1);
  const amount=(frame-frames[index-1])/(frames[index]-frames[index-1]);
  const mix=(a,b)=>curve.kind==='int'?Math.trunc(a+(b-a)*amount):a+(b-a)*amount;
  return Array.isArray(values[0])?values[index-1].map((v,axis)=>mix(v,values[index][axis])):mix(values[index-1],values[index]);
}
export function particleSeed(text) {
  let seed=2166136261;for(const c of String(text)){seed^=c.charCodeAt(0);seed=Math.imul(seed,16777619);}return seed>>>0;
}
function random(seed,index) { let n=(seed+Math.imul(index+1,0x9e3779b9))>>>0;n=Math.imul(n^(n>>>16),0x21f0aaad);n=Math.imul(n^(n>>>15),0x735a2d97);return((n^(n>>>15))>>>0)/4294967296; }
const normalized=v=>{const d=Math.hypot(...v);return d>1e-9?v.map(n=>n/d):[0,1,0];};
const rotate=(v,a)=>{
  const [sx,sy,sz]=a.map(Math.sin),[cx,cy,cz]=a.map(Math.cos),[x,y,z]=v;
  const yy=y*cx-z*sx,zz=y*sx+z*cx,xx=x*cy+zz*sy,zzz=zz*cy-x*sy;
  return [xx*cz-yy*sz,xx*sz+yy*cz,zzz];
};
function percentage(percent,unit,subtract=false) {const q=Math.floor(unit*(Math.abs(percent)+1))*Math.sign(percent);return 1+(subtract?-q:q)*.01;}

export function sampleParticleSystem(definition, milliseconds, seed, {quality=0,maxParticles=256}={}) {
  const output=[];
  const effectScale=definition.particleScale??1;
  if(milliseconds<0)return output;
  const emitters=definition.emitters;
  for(let emitterIndex=0;emitterIndex<emitters.length;emitterIndex++) {
    const e=emitters[emitterIndex],p=e.particle,h=e.headerWords,c=e.curves,pc=p.curves;
    const interval=Math.max(33,Math.trunc(Math.fround(e.intervalFrames[Math.max(0,Math.min(2,quality))]*FRAME_MS)));
    const start=e.startFrame*FRAME_MS,end=e.durationFrames<0?milliseconds+1:start+e.durationFrames*FRAME_MS;
    // Only births whose longest possible lifetime reaches the requested sample.
    const longest=p.lifeFrames*FRAME_MS*(1+Math.max(0,p.lifeRandomPercent)/100);
    let birth=Math.max(0,Math.ceil((milliseconds-longest-start)/interval));
    for(;start+birth*interval<=milliseconds&&start+birth*interval<end;birth++) {
      const born=start+birth*interval,age=milliseconds-born;
      const volume=Math.max(0,Math.min(128,Math.trunc(sampleParticleCurve(c[['volumeHigh','volumeMedium','volumeLow'][quality]||'volumeHigh'],born))));
      for(let ordinal=0;ordinal<volume;ordinal++) {
        if(output.length>=maxParticles)return output;
        const rngSeed=particleSeed(`${seed}:${emitterIndex}:${birth}:${ordinal}`);
        const rnd=i=>random(rngSeed,i);
        const signed=i=>Math.floor(rnd(i)*1024)-512;
        const life=Math.trunc(Math.fround(Math.fround(p.lifeFrames*FRAME_MS)*Math.fround(percentage(p.lifeRandomPercent,rnd(0)))));
        if(age>=life)continue;
        const get=(name,time=age)=>sampleParticleCurve(pc[name],time);
        const emit=name=>sampleParticleCurve(c[name],born);
        const angles=['rotateX','rotateY','rotateZ'].map(emit),translation=['translateX','translateY','translateZ'].map(emit);
        const outer=['outerX','outerY','outerZ'].map(emit),inner=emit('innerPercent');
        let shape=[0,0,0];
        if(e.shape===1){const dir=normalized([signed(1),signed(2),signed(3)]);shape=dir.map((v,i)=>v*outer[i]*percentage(inner,rnd(30+i),true));}
        else if(e.shape===2){const count=Math.trunc(outer[1]),sequence=birth*volume+ordinal;
          const a=Math.floor(360/Math.max(1,count))*(sequence%Math.max(1,count))*Math.PI/180;
          const dir=count>1?[Math.cos(a),0,Math.sin(a)]:normalized([signed(1),0,signed(2)]);
          shape=[dir[0]*outer[0]*percentage(inner,rnd(30),true),0,dir[2]*outer[2]*percentage(inner,rnd(32),true)];}
        else if(e.shape===3)shape=outer.map((v,i)=>(rnd(i+1)*2-1)*v);
        let velocity=normalized([signed(5),signed(6),signed(7)]);
        const radial=emit('radialSpeed')*percentage(h[16],rnd(8)),directed=emit('directedSpeed')*percentage(h[17],rnd(9));
        const direction=normalized(emit('direction'));
        velocity=rotate(velocity.map((v,i)=>(v*radial+direction[i]*directed)*effectScale),angles);
        let point=rotate(shape,angles).map((v,i)=>(v+translation[i])*effectScale);
        // Native order: integrate with old velocity, then apply affectors. Fixed
        // 30 FPS steps make observers independent of requestAnimationFrame rate.
        for(let elapsed=0;elapsed<age-1e-7;) {
          const step=Math.min(1000/30,age-elapsed),dt=step/1000;
          point=point.map((v,i)=>v+velocity[i]*dt);
          for(const a of e.affectors) {
            if(a.type===0){const dir=normalized(sampleParticleCurve(a.direction,elapsed));const strength=sampleParticleCurve(a.strength,elapsed)*effectScale;velocity=velocity.map((v,i)=>v+dir[i]*strength*step*.03);}
            else if(a.type===1){const factor=1+(sampleParticleCurve(a.strength,elapsed)-1)*step*.03;velocity=velocity.map(v=>v*factor);}
            else if(a.type===2){const dir=normalized([rnd(100+Math.round(elapsed)*3)*2-1,rnd(101+Math.round(elapsed)*3)*2-1,rnd(102+Math.round(elapsed)*3)*2-1]);velocity=velocity.map((v,i)=>v+dir[i]*a.parameters[i]);}
          }
          elapsed+=step;
        }
        const sizeFactor=percentage(p.sizeRandomPercent,rnd(10),true),heightFactor=p.keepXY?sizeFactor:percentage(p.sizeRandomPercent,rnd(11),true);
        output.push({id:`${emitterIndex}:${birth}:${ordinal}`,born,age,life,texture:p.texture,material:p.material,type:p.type,
          position:point,velocity,followFlags:p.followFlags,
          size:[get('sizeX')*get('scaleX')*sizeFactor*effectScale,get('sizeY')*get('scaleY')*heightFactor*effectScale],
          angles:p.baseAngles.map((v,i)=>v*percentage(p.baseAngleRandomPercent[i],rnd(12+i),true)+get(['rotateX','rotateY','rotateZ'][i])*percentage(p.rotationRandomPercent[i],rnd(16+i),true)),
          color:['red','green','blue','alpha'].map(name=>get(name)/255),color2:['secondaryRed','secondaryGreen','secondaryBlue'].map(name=>get(name)/255),
          uv:['uvLeft','uvTop','uvRight','uvBottom'].map(name=>get(name)),pivot:p.pivot,flipH:p.flipH,flipV:p.flipV});
      }
    }
  }
  return output;
}
