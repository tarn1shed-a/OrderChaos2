import {createWorldTrackQueue} from './source-world-track-queue-v1.mjs';
const clone=x=>structuredClone(x);
/** Original 3a9250 xorshift128 stored as four uint64 words. The host must
 * supply the state: no original seed or actor-session initial state is known. */
export function createSourceRandom(words){
 if(!Array.isArray(words)||words.length!==4||words.some(v=>typeof v!=='string'||!/^\d+$/.test(v)||BigInt(v)>0xffffffffffffffffn))throw Error('Explicit four uint64 RNG words required');let w=words.map(BigInt);
 return Object.freeze({range(a,b){if(!Number.isInteger(a)||!Number.isInteger(b)||a< -0x80000000||b< -0x80000000||a>0x7fffffff||b>0x7fffffff)throw Error('Exact original int32 RNG bounds required');if(a===b)return a;let value,guard=0;do{if(++guard>1024)throw Error('Source RNG rejection bound');const t=BigInt.asUintN(64,w[0]^(w[0]<<11n)),next=BigInt.asUintN(64,w[3]^(BigInt.asIntN(64,w[3])>>19n)^t^(BigInt.asIntN(64,t)>>8n));w=[w[1],w[2],w[3],next];value=Number(next&0x7fffn);}while(value===0x7fff);return value%(Math.max(a,b)-Math.min(a,b))+Math.min(a,b);},inspect:()=>w.map(String)});
}
/** Bounded original 5/8 action3000/800, unarmed loaded two-layer path only.
 * No input, physical movement, activity, cast authorization or inventory. */
export function createSourceGatherController({ranges,randomWords,initialIdleVariant,sourceContext}={}){
 const expected={movementState:5,postureState:8,actionState:0x800,actorFlag4c:0,actorPointer638:null,kindAttribute0:0x120a,rawActorByte114:1,cachedWeaponEvent:0,sourceClassWeaponRow:null,explicitNoWeaponRecord:true,loadedEngineFlags:3,sourceFilterByte:0};
 if(!sourceContext||Object.entries(expected).some(([k,v])=>!Object.hasOwn(sourceContext,k)||sourceContext[k]!==v)||Object.keys(sourceContext).length!==Object.keys(expected).length||initialIdleVariant!==0)throw Error('Covered explicit original loaded presentation context required');
 const queue=createWorldTrackQueue(ranges),rng=createSourceRandom(randomWords);let idleVariant=initialIdleVariant,first=true,pending=null,action=0x800,loopAction=0,preAction=0,advanced=[],phase=null,scope=null,actorKey=null,profession=null,disposed=false;
 const check=()=>{if(disposed)throw Error('Source Gather controller disposed');};
 function request(name,channel,flags,kind='play',blend=150){const r={kind,name,channel,flags,speed:1,begin:0,blend};queue.request(r);return r;}
 function originalBaseIdle(requests){
  const q=queue.inspect();
  if((q[0].record?.flags&16||q[0].completed)&&q[0].record?.name!=='idle')requests.push(request('idle',0,22,'play',-1));
  if(q[1].record?.flags&16||q[1].completed)requests.push(request('idle',1,278,'play',-1));
  requests.push(request('idle',0xffffffff,276,'default',-1));
 }
 function emitAction(row,append,requests){
  if(row!==1&&row!==58)throw Error('Uncovered original source action');const name=row===58?'item_loading':'idle',loop=row===58||append,flags=(append?8:1)|(loop?16:0);
  requests.push(request(name,1,flags));requests.push(request(name,0,flags));
 }
 return Object.freeze({
  begin(input){check();if(scope!==null)throw Error('Release prior source presentation');if(!input||Object.keys(input).sort().join(',')!=='actorKey,profession,scope'||typeof input.scope!=='string'||!input.scope||typeof input.actorKey!=='string'||!input.actorKey||![1,2,3,4,5].includes(input.profession))throw Error('Explicit current owner/scope required');
   if(actorKey!==null&&(actorKey!==input.actorKey||profession!==input.profession))throw Error('Source controller belongs to one immutable actor/profession');({scope,actorKey,profession}=input);phase='chant';pending=0x3000;
   return{scope,actorKey,phase,originalRequestReturn:0,pose:null,translatedOriginalCPU:true,originalCastOrActivityProduced:false};
  },
  finish(currentScope,kind){check();if(currentScope!==scope||phase!=='chant'||!['success','interrupt'].includes(kind))throw Error('Current single terminal source event required');phase=kind;pending=0x800;queue.clearPending();queue.forceSelect();return{scope,phase,sourceExitEntries:kind==='success'?['5ba444','5d2148','5d13a4','5bdda0','5d23f8','9e09a0','a3cf28']:['5d23f8','9e09a0','a3cf28'],awardOrProtocolProduced:false};
  },
  frame(currentScope,dt,timeval){check();if(currentScope!==scope||scope===null||!Number.isInteger(dt)||dt<0||dt>1000||!Array.isArray(timeval)||timeval.length!==2||!Number.isInteger(timeval[0])||timeval[0]<0||timeval[0]>0x7fffffff||!Number.isInteger(timeval[1])||timeval[1]<0||timeval[1]>=1000000)throw Error('Current explicit source frame/timeval required');
   const requests=[];
   if(first){const bucket=rng.range(0,0x500)>>8;if(bucket<3)idleVariant=0;else if(idleVariant!==0)idleVariant=idleVariant===1?2:1;else idleVariant=bucket<4?2:1;rng.range(5000,15000);first=false;}
   if(pending!==null){action=pending;pending=null;originalBaseIdle(requests);advanced=[];advanced.unshift(action===0x3000?{pre:0,loop:58}:{pre:idleVariant?1:-1,loop:0});queue.forceSelect(1);}
   const current=queue.inspect()[1],isLoop=!!(current.record?.flags&16);
   if((!isLoop&&current.completed)||(isLoop&&advanced.length)){
    if(advanced.length){const a=advanced.shift();preAction=a.pre;loopAction=a.loop;if(preAction>0||loopAction>0){emitAction(preAction>0?preAction:loopAction,false,requests);if(loopAction>0)emitAction(loopAction,true,requests);}}
   }
   const layers=queue.tick(dt),settled=phase!=='chant'&&action===0x800&&layers.every(v=>v.current?.clip==='idle'&&v.weights[0]===1&&v.weights[1]===0);
   return{scope,actorKey,phase,sourceActionState:action,sourceLayers:layers,settled,requests,sourceTimeval:timeval.slice(),qualificationOrProtocolProduced:false};
  },
  release(currentScope){check();if(currentScope!==scope||scope===null)throw Error('Current presentation release required');scope=null;return{released:true};},
  inspect(){check();return{scope,actorKey,profession,phase,action,pending,idleVariant,preAction,loopAction,advanced:clone(advanced),randomWords:rng.inspect(),queue:queue.inspect()};},
  dispose(){if(disposed)return;disposed=true;scope=null;advanced=[];}
 });
}
