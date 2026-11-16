// Original composed Model2 properties on the exact released legacy world rig.
// Transport/ownership adapter only: no animation selection or interpolation.
const DATA='9dd178a38bd82b1a45d70a13c57a20a41909a606c7bec0e39b90e84d01766e5b';
const BINDING='c03c5f0cd41117b7f88b32f41d6a9a299f5bf0e802a6ea307de22e92ad37a473';
const MASK='021eb8db3a38df2ae7fb4a369b802fc2ee1930e2b2fcbcddbd154fbea12da371';
const MOTION='936993bc8a1c357b6641120fe7cbc43b31cd67135f3001eab359aea415ea422a';
const owners=new WeakMap();
const digest=async text=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text)))].map(v=>v.toString(16).padStart(2,'0')).join('');

export async function createGatherPoseTarget({body,characterAnimationState,dataText,bindingText,actorKey}){
 if(!crypto?.subtle||typeof dataText!=='string'||typeof bindingText!=='string'||typeof characterAnimationState!=='function'||typeof actorKey!=='string'||!actorKey||!body?.updateMatrixWorld)throw Error('Exact current world rig, actor and source text required');
 if(await digest(dataText)!==DATA)throw Error('Released Model2 player data differs');
 const data=JSON.parse(dataText),b=JSON.parse(bindingText),bones=characterAnimationState(body)?.bones;
 if(b?.format!=='oc2-source-own-body-pose-binding-v1'||b.bindingId!==BINDING||b.sourceMaskSHA256!==MASK||b.sourceMotion?.sha256!==MOTION||b.sourceMotion.key!=='elf-female'||b.sourceMotion.sourceModelId!==2||b.sourceMotion.race!==1||b.sourceMotion.gender!==1||b.properties!==110||b.valueBytes!==1536||b.propertyOrder?.length!==110||
  !Array.isArray(bones)||bones.length!==124||new Set(bones).size!==124||owners.has(body)||bones.some((n,i)=>!n.isBone||n.name!==`node_${i}`||data.rig.nodes[i].parent>=0&&n.parent!==bones[data.rig.nodes[i].parent]))throw Error('Own released Model2 bone targets/binding required');
 const desc=[b.nativeSHA256,b.sourceBodyDataSHA256,MASK,MOTION,...b.propertyOrder.map((r,i)=>`${i}|${r.node}|${r.sourceNode}|${r.sourceType}|${r.originalPropertyWeight===0?'00000000':r.originalPropertyWeight===.5?'0000003f':'0000803f'}`)].join('\n');
 if(await digest(desc)!==BINDING)throw Error('Original Gather property binding digest differs');
 const keys=new Set();
 for(const [i,r]of b.propertyOrder.entries()){
  const n=data.rig.nodes[r.node],key=r.node+':'+r.sourceType;
  if(r.sourcePropertyIndex!==i||!n||![n.name,...(n.aliases||[])].includes(r.sourceNode)||![1,5,10].includes(r.sourceType)||![0,.5,1].includes(r.originalPropertyWeight)||keys.has(key))throw Error('Original property target differs');keys.add(key);
 }
 if(owners.has(body))throw Error('Current world body already owns another source target');
 const owner={};owners.set(body,owner);let disposed=false,last=null;
 return{apply(p){
  if(disposed||owners.get(body)!==owner||p?.format!=='oc2-source-body-native-pose-v1'||p.key!=='elf-female'||p.actorKey!==actorKey||p.bindingId!==BINDING||p.valueBytes!==1536||p.valueEncoding!=='float32-le-base64'||typeof p.values!=='string'||!/^[A-Za-z0-9+/]+={0,2}$/.test(p.values))throw Error('Current actor complete original Gather pose required');
  const raw=atob(p.values);if(raw.length!==1536||btoa(raw)!==p.values)throw Error('Original Gather span differs');
  const bytes=Uint8Array.from(raw,c=>c.charCodeAt(0)),v=new DataView(bytes.buffer),pending=[];let at=0;
  for(const t of b.propertyOrder){const values=[];for(let i=0;i<(t.sourceType===5?4:3);i++){const x=v.getFloat32(at,true);at+=4;if(!Number.isFinite(x))throw Error('Nonfinite original Gather property');values.push(x);}pending.push({node:bones[t.node],type:t.sourceType,values});}
  if(at!==1536)throw Error('Complete original property widths required');
  for(const r of pending)(r.type===5?r.node.quaternion:r.type===10?r.node.scale:r.node.position).fromArray(r.values);
  body.updateMatrixWorld(true);for(const s of characterAnimationState(body)?.skeletons||[])s.update();last={actorKey,bindingId:BINDING,properties:110,valueBytes:1536};return true;
 },inspect:()=>last?{...last}:null,dispose(){if(disposed)return;disposed=true;if(owners.get(body)===owner)owners.delete(body);last=null;}};
}

// The host retains the authenticated task request and calls finish only for
// that actual current response. This object never submits/grants a task/item.
export function createGatherPresentationBridge({readHost,makeProducer,makeTarget,onError=()=>{}}){
 if(![readHost,makeProducer,makeTarget,onError].every(v=>typeof v==='function'))throw Error('Owned host/producer/target interfaces required');
 let active=null,serial=0;const records=new WeakMap();
 function host(){const h=readHost();if(!h?.connected||!h.displayed||!h.body||typeof h.characterId!=='string'||typeof h.actorKey!=='string'||!Number.isInteger(h.epoch)||h.sourceAvatar||h.appearance?.race!==2||h.appearance?.gender!==1||![1,2,3,4,5].includes(h.profession)||!(h.hp>0))throw Error('Current displayed legacy ElfF self required');return h;}
 function current(r){let h;try{h=host();}catch{return false;}return active===r&&h.characterId===r.h.characterId&&h.actorKey===r.h.actorKey&&h.epoch===r.h.epoch&&h.body===r.h.body&&h.profession===r.h.profession;}
 function discard(r){if(!r)return;r.released=true;if(r.target&&!r.targetDisposed){r.targetDisposed=true;r.target.dispose();}if(r.producer&&!r.producerReleased){r.producerReleased=true;Promise.resolve(r.producer.release?.()).catch(()=>{});}if(active===r)active=null;}
 function record(token){const r=records.get(token);if(!r||!current(r)){discard(r);return null;}return r;}
 async function execute(r,run){if(r.busy)throw Error('Original Gather producer call already pending');r.busy=true;try{const value=await run();if(!current(r)){discard(r);return null;}return value;}catch(e){if(current(r)){discard(r);onError(e);}throw e;}finally{r.busy=false;}}
 return{
  async begin(){const h=host();discard(active);const token=Object.freeze({}),r={h:{...h},scope:`gather:${h.characterId}:${h.epoch}:${++serial}`,phase:'starting',last:null,busy:false,released:false};active=r;records.set(token,r);
   try{r.producer=await makeProducer({scope:r.scope,actorKey:h.actorKey,profession:h.profession});if(!current(r)){discard(r);return null;}
    r.target=await makeTarget({body:h.body,actorKey:h.actorKey});if(!current(r)){discard(r);return null;}
    const started=await execute(r,()=>r.producer.begin());if(started===null)return null;r.phase='chant';return token;
   }catch(e){if(current(r))onError(e);discard(r);throw e;}
  },
  async frame(token,milliseconds,timeval){const r=record(token);if(!r)return null;if(!Number.isInteger(milliseconds)||milliseconds<0||milliseconds>1000)throw Error('Actual bounded frame delta required');
   const v=await execute(r,()=>r.producer.frame(milliseconds,timeval));if(v===null)return null;
   if(v?.scope!==r.scope||v.actorKey!==r.h.actorKey||v.phase!==r.phase||typeof v.settled!=='boolean'||!v.pose){discard(r);throw Error('Owned original Gather producer result required');}
   // Validate/apply atomically before retaining, so a later draw cannot first
   // discover malformed data after replacing the last good source result.
   try{r.target.apply(v.pose);r.last=structuredClone(v.pose);}catch(e){discard(r);throw e;}
   if(v.settled&&r.phase!=='chant'){discard(r);return {settled:true};}return {settled:false};
  },
  async finish(token,kind){const r=record(token);if(!r)return null;if(r.phase!=='chant'||!['success','interrupt'].includes(kind))throw Error('One explicit current outcome required');
   const v=await execute(r,()=>r.producer.finish(kind));if(v===null)return null;if(v?.scope!==r.scope||v.phase!==kind){discard(r);throw Error('Original local exit result required');}r.phase=kind;return {phase:kind};
  },
  afterBaseUpdate(token){const r=record(token);return r?.last?r.target.apply(r.last):false;},
  invalidate(){discard(active);},
  inspect(){return active&&current(active)?{characterId:active.h.characterId,actorKey:active.h.actorKey,epoch:active.h.epoch,phase:active.phase,pose:active.target?.inspect()||null}:null;}
 };
}
