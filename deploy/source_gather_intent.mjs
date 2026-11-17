// Web input ordering only. A candidate may request the authoritative action;
// it is never proof of a readable native seed, task eligibility, or approval.
const capabilities=new WeakSet();
const HF_BINDING='15aab4f91ae4e3eca40bc5ef7759569c608d70932912bcfab979a707c3648d5d';
const HF=Object.freeze({poseField:'sourceFemalePose',bindingId:HF_BINDING,valueBytes:1928,idleClips:Object.freeze(['idle','idle_02'])});
const sameOwner=(a,b)=>a?.connected===true&&b?.connected===true&&['connection','epoch','actorKey'].every(k=>a[k]===b[k]);
const result=(state,reason)=>Object.freeze({state,reason,requestApproved:false,nativeSeedObserved:false});

// Both readers are trusted host closures over the installed NPC route/library
// maps. Do not supply browser JSON or a manifest in place of the live library.
export function createGatherCapabilityReader({readRoute,readLibrary}){
 if(typeof readRoute!=='function'||typeof readLibrary!=='function')throw Error('Installed route and live library readers required');
 const cache=new WeakMap();
 return player=>{
  const route=readRoute(player);
  if(!route?.seeded||route.id!=='own-'+route.bodyKey||player?.sourceAvatar?.key!==route.bodyKey)return null;
  const library=readLibrary(route,player);
  if(!library||typeof library.inspect!=='function')return null;
  const data=library.inspect();
  if(data?.format!=='oc2-world-gather-presentation-source-v1'||data.key!==route.bodyKey||data.sourceModelId!==route.model||data.bindingId!==route.bindingId||data.properties!==route.properties||data.valueBytes!==route.valueBytes||!Array.isArray(data.admittedClips)||!data.admittedClips.length||data.admittedClips.some(n=>typeof n!=='string'||!n)||new Set(data.admittedClips).size!==data.admittedClips.length)return null;
  let entries=cache.get(library);if(!entries){entries=new Map();cache.set(library,entries);}
  const prior=entries.get(route);
  if(prior&&JSON.stringify(prior.admittedClips)===JSON.stringify(data.admittedClips))return prior;
  const cap=Object.freeze({routeId:route.id,bodyKey:route.bodyKey,normalBindingId:route.normalBinding,normalMotionSHA256:route.normalMotion,gatherBindingId:data.bindingId,admittedClips:Object.freeze(data.admittedClips.slice())});
  capabilities.add(cap);entries.set(route,cap);return cap;
 };
}

export function observeGatherQueue({player:p,normalContract:row,gatherCapability:cap}){
 if(!cap||!capabilities.has(cap))return result('rejected','gather-library-unavailable');
 if(p?.sourceAvatar?.key!==cap.bodyKey||row?.bindingId!==cap.normalBindingId||row?.sourceMotion?.sha256!==cap.normalMotionSHA256)return result('rejected','gather-route-mismatch');
 if(p.grounded!==true||p.jump||p.cast)return result('waiting','standing-packet-required');
 const layers=p.sourceAnimation?.layers;
 if(!Array.isArray(row.idleClips)||!row.idleClips.length||!Array.isArray(layers)||layers.length!==2||layers.some((l,i)=>l?.channel!==i||typeof l.current?.clip!=='string'))return result('waiting','complete-two-layer-packet-required');
 if(layers.some(l=>!row.idleClips.includes(l.current.clip)))return result('waiting','standing-current-required');
 const ranges=new Set(cap.admittedClips);
 if(layers.some(l=>!ranges.has(l.current.clip)))return result('rejected','unsupported-current');
 if(layers.some(l=>l.previous!==null&&(typeof l.previous?.clip!=='string'||!ranges.has(l.previous.clip))))return result('rejected','unsupported-previous');
 // Public layers omit selected/default/pending native records. Those remain
 // mandatory actual-getter/library checks on the server, including at blend0.
 return result('candidate','observed-current-and-previous-covered');
}

export function createSourceGatherIntent({readOwner,readPlayer,readPoseContract=()=>null,readGatherCapability=()=>null}){
 if([readOwner,readPlayer,readPoseContract,readGatherCapability].some(fn=>typeof fn!=='function'))throw Error('Current actor and installed source readers required');
 const contract=p=>p?.sourceAvatar?.key==='human-female'?HF:readPoseContract(p);
 let pending=null,disposed=false,state=result('idle','no-request');
 function finish(value,next){const old=pending;pending=null;state=next;old?.resolve(value);}
 function changed(){
  if(!pending)return;
  try{
   const owner=readOwner(),p=readPlayer();
   if(disposed||!sameOwner(owner,pending.owner)||p?.id!==pending.id||p.profession!==pending.profession||p.sourceAvatar?.key!==pending.bodyKey)return finish(false,result('cancelled','actor-or-connection-changed'));
   const row=contract(p),pose=row&&p[row.poseField],layers=p.sourceAnimation?.layers;
   if(!row||row.poseField!==pending.poseField||row.bindingId!==pending.bindingId||row.valueBytes!==pending.valueBytes)return finish(false,result('cancelled','normal-contract-changed'));
   if(row.sourceMotion&&Object.entries(row.sourceMotion).some(([k,v])=>p.sourceAnimation?.sourceMotion?.[k]!==v))return finish(false,result('cancelled','normal-motion-changed'));
   if(pose?.actorKey!==p.id||pose.bindingId!==row.bindingId||pose.valueBytes!==row.valueBytes){state=result('waiting','matching-normal-pose-required');return;}
   // Existing HumanF behavior is deliberately retained in this bounded change.
   if(p.sourceAvatar.key==='human-female'){
    if(p.grounded===true&&!p.jump&&!p.cast&&Array.isArray(layers)&&layers.length===2&&layers.every(l=>row.idleClips.includes(l.current?.clip)))return finish(true,result('candidate','human-female-existing-path'));
    state=result('waiting','human-female-standing-required');return;
   }
   const next=observeGatherQueue({player:p,normalContract:row,gatherCapability:readGatherCapability(p)});state=next;
   if(next.state==='candidate')finish(true,next);else if(next.state==='rejected')finish(false,next);
  }catch{finish(false,result('rejected','source-reader-unavailable'));}
 }
 return Object.freeze({
  wait(){
   finish(false,result('cancelled','replaced'));if(disposed){state=result('cancelled','disposed');return Promise.resolve(false);}
   let owner,p,row;try{owner=readOwner();p=readPlayer();row=contract(p);}catch{state=result('rejected','source-reader-unavailable');return Promise.resolve(false);}
   if(!owner?.connected||!owner.connection||p?.id!==owner.actorKey||!row||typeof row.poseField!=='string'||typeof row.bindingId!=='string'||!Number.isSafeInteger(row.valueBytes)){state=result('rejected','current-actor-and-contract-required');return Promise.resolve(false);}
   state=result('waiting','existing-packet-required');
   return new Promise(resolve=>{pending={owner:{...owner},id:p.id,profession:p.profession,bodyKey:p.sourceAvatar?.key,poseField:row.poseField,bindingId:row.bindingId,valueBytes:row.valueBytes,resolve};changed();});
  },
  changed,
  cancel(){finish(false,result('cancelled','explicit-cancel'));},
  inspect(){return Object.freeze({...state,pending:!!pending});},
  dispose(){disposed=true;finish(false,result('cancelled','disposed'));},
 });
}
