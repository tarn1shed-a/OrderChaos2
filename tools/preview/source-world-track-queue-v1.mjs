const F=Math.fround,copy=x=>x?structuredClone(x):null;
const same=(a,b)=>a&&b&&['name','flags','speed','begin','blend'].every(k=>a[k]===b[k]);
/** Original loaded-track queue subset 32d58c/32cd44/32cef0/32ee00/330d0c.
 * Only speed1/begin0, absent marker/provider, two loaded channels. */
export function createWorldTrackQueue(ranges){
 const clean=p=>p?{clip:p.clip,ageMs:p.ageMs,loop:p.loop}:null;
 const channels=Array.from({length:2},()=>({record:null,defaultRecord:null,pending:[],needSelect:false,completed:false,current:null,previous:null,sequence:0,remainingMs:0,durationMs:0,completionCount:0}));
 function decide(q,r){
  let allow=false,update=false;
  if(!q.completed){if(q.record?.name===r.name)update=!!(r.flags&4);else allow=!!(r.flags&2);}
  else if(q.record?.flags&32)allow=!!(r.flags&2);else allow=true;
  if(!q.needSelect&&!(r.flags&1)){
   if(same(q.record,q.defaultRecord))allow=true;
   else if(!(r.flags&64)||!(q.record?.flags&16))return{allow,update};
  }
  return{allow:true,update};
 }
 function synchronized(q,input){
  const r=copy(input),channel=channels.indexOf(q);
  if(r.flags&0x300)for(let i=0;i<2;i++)if(i!==channel&&(r.flags&(i===0?0x100:0x200))&&((r.flags&0x400)||channels[i].record?.name===r.name)){const other=channels[i];r.flags=(r.flags&~0xb0)|(other.record.flags&0x30);r.speed=other.record.speed;r.begin=other.current.ageMs;break;}
  return r;
 }
 function update(q,input){const r=synchronized(q,input);
  if(!q.record||q.record.name!==r.name)throw Error('Original same-name update target missing');
  // Original 32d0c8 begin0 leaves current age. 32d2d0 changes loop in-place.
  q.record.flags=(q.record.flags&~(32|0x7fff800))|(r.flags&(32|0x7fff800));
  q.record.speed=r.speed;q.current._clockLoop=!!(r.flags&16);
 }
 function select(q){
  q.needSelect=false;const input=q.pending.length?q.pending.shift():q.defaultRecord;
  if(!input||same(q.record,input))return;const r=synchronized(q,input);
  const range=ranges[r.name];if(!range)throw Error('Unadmitted source track');
  q.previous=q.current;q.current={clip:r.name,ageMs:r.begin,loop:!!(r.flags&16),_clockLoop:!!(r.flags&16)};q.record=copy(r);q.completed=false;q.sequence++;
  q.durationMs=r.blend<0?150:Math.trunc(r.blend);q.remainingMs=q.previous?q.durationMs:0;
 }
 function enqueueOne(q,r){
  if(!(r.flags&8))q.pending=[];
  const d=(!(r.flags&8)||q.pending.length<1)?decide(q,r):{allow:false,update:false};
  if(d.update){if(q.needSelect&&q.pending.length<1)q.needSelect=false;update(q,r);}
  else{if(q.pending.length>=6)throw Error('Original bounded queue capacity exceeded');q.pending.push(copy(r));q.needSelect=d.allow;}
 }
 function request(r){
  if(!r||!['play','default'].includes(r.kind)||!Object.hasOwn(ranges,r.name)||r.speed!==1||r.begin!==0||!Number.isFinite(r.blend)||!Number.isInteger(r.flags)||![0,1,0xffffffff].includes(r.channel))throw Error('Covered original loaded request required');
  const target=r.channel===0xffffffff?[0,1]:[r.channel];
  for(const c of target){const q=channels[c],v={name:r.name,flags:r.flags|(r.kind==='play'?0x44:0),speed:r.speed,begin:r.begin,blend:r.blend};
   if(r.kind==='play')enqueueOne(q,v);
   else if(!same(q.defaultRecord,v)){const old=q.defaultRecord,wasDefault=same(q.record,old);q.defaultRecord=copy(v);if(!q.pending.length&&wasDefault)enqueueOne(q,v);}
  }
 }
 function clock(p,dt){if(!p)return;const d=ranges[p.clip].endMs-ranges[p.clip].startMs,absolute=F(F(ranges[p.clip].startMs+p.ageMs)+dt),end=ranges[p.clip].endMs;
  p.ageMs=absolute>end?(p._clockLoop?F((absolute-end)%d):d):F(absolute-ranges[p.clip].startMs);
 }
 return Object.freeze({
  request,
  clearPending(){for(const q of channels)q.pending=[];},
  forceSelect(channel=0xffffffff){for(const [i,q]of channels.entries())if(channel===0xffffffff||channel===i)q.needSelect=true;},
  clearDefault(){for(const q of channels)q.defaultRecord=null;},
  inspect(){return copy(channels);},
  tick(dt){if(!Number.isInteger(dt)||dt<0||dt>1000)throw Error('Bounded source milliseconds required');
   const result=[];
   for(const[c,q]of channels.entries()){
    if(q.needSelect||!q.current)select(q);
    let guard=0;while(q.pending.length){if(++guard>6)throw Error('Queue selection guard');const d=decide(q,q.pending[0]);if(d.update)update(q,q.pending.shift());else if(d.allow)select(q);else break;}
    if(q.completed&&!same(q.record,q.defaultRecord)&&!(q.record.flags&0x30))select(q);
   }
   for(const[c,q]of channels.entries()){
    const before=q.completed;clock(q.current,dt);clock(q.previous,dt);
    if(q.current&&!q.current._clockLoop&&q.current.ageMs===ranges[q.current.clip].endMs-ranges[q.current.clip].startMs&&dt>0){q.completed=true;if(!before)q.completionCount++;}
    q.remainingMs=Math.max(0,q.remainingMs-dt);const old=q.remainingMs===0?0:Math.min(Math.fround(.99),F(q.remainingMs/q.durationMs)),weights=[F(1-old),old];
    if(!q.current)throw Error('No original current loaded track');result.push({channel:c,current:clean(q.current),previous:clean(q.previous),sequence:q.sequence,weights,remainingMs:q.remainingMs,completionCount:q.completionCount});
   }return result;
  }
 });
}
