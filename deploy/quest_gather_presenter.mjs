// Authenticated room events own animation time. rAF only reapplies the last
// validated pose after the existing mixer; this sends no task action.
import {createGatherBrowserLibrary,createGatherEventReceiver} from './quest_gather/ordinary-quest461-gather-browser.mjs';
import {createGatherPoseTarget} from './quest_gather/ordinary-quest461-gather-pose.mjs';
import {createCompatible461GatherInbox} from './quest_gather/ordinary-quest461-gather-events.mjs';
const BINDING='c03c5f0cd41117b7f88b32f41d6a9a299f5bf0e802a6ea307de22e92ad37a473';
export async function createQuestGatherPresenter({readHost,readActor,queryReplay,legacyDataText,characterAnimationState,load=fetch,onFault=console.error}){
 const bytes=async name=>{const r=await load('/assets/source-quest461-gather-v1/'+name);if(!r.ok)throw Error('原收集动作资料未就绪');return new Uint8Array(await r.arrayBuffer());};
 const[sourceBytes,bindingBytes]=await Promise.all(['source.json','binding.json'].map(bytes));
 const library=await createGatherBrowserLibrary({sourceBytes,bindingBytes}),bindingText=new TextDecoder('utf-8',{fatal:true}).decode(bindingBytes);
 const targets=new Map();let disposed=false,epoch=0,replay=null;
 const current=h=>{const now=readHost();return !disposed&&now.connected&&['connection','epoch','characterId','roomKey'].every(k=>now[k]===h[k]);};
 const own=row=>targets.get(row.actorKey)===row;
 const packetFor=(packet,key)=>({...packet,records:Array.isArray(packet?.records)?packet.records.filter(r=>(r?.kind==='event'?r.event?.actorKey:r?.actorKey)===key):packet?.records});
 const makeInbox=row=>createCompatible461GatherInbox({readHost,readActor:key=>{
  const a=readActor(key);
  return key===row.actorKey&&own(row)&&row.target&&a?.body===row.body&&a.epoch===row.epoch&&a.profession===row.profession&&a.displayed?
   {...a,bodyKey:'elf-female',bindingId:BINDING}:null;
 },makeReceiver(record,actor){
  if(!own(row)||!row.target||actor.actorKey!==row.actorKey)return null;
  const session=library.createSession({sessionKey:record.sessionKey,actorKey:actor.actorKey,profession:actor.profession,...record.inputs});
  const receiver=createGatherEventReceiver({session,sessionKey:record.sessionKey,actorKey:actor.actorKey,profession:actor.profession,initialSequence:0});
  return {consume:event=>receiver.consume(event),apply:pose=>row.target.apply(pose),dispose:()=>receiver.dispose()};
 },onFault});
 const drop=row=>{row.inbox?.dispose();row.inbox=null;row.target?.dispose();row.target=null;row.queued=[];};
 function enqueue(row,packet){
  row.queued.push(packet);
  if(row.queued.length>256){row.queued=row.queued.slice(-1);row.inbox?.dispose();row.inbox=null;}
 }
 async function recover(){
  const h=readHost();if(disposed||!h.connected||replay)return;
  const now=performance.now(),rows=[...targets.values()].filter(r=>r.target&&!r.failed&&r.wanted&&now-r.lastRequest>=500);
  if(!rows.length)return;
  const token={epoch,host:{...h},rows};replay=token;for(const row of rows)row.lastRequest=now;
  try{
   const result=await queryReplay();if(replay!==token||token.epoch!==epoch||!current(token.host))return;
   for(const row of rows){
    if(!own(row)||!row.target||row.failed)continue;
    try{
     row.inbox?.dispose();row.inbox=makeInbox(row);
     const state=row.inbox.replay(packetFor(result.presentation,row.actorKey));row.wanted=!!state?.needsReplay;
     const packets=row.queued;row.queued=[];
     for(const packet of packets)if(packet.tick>result.presentation.tick){const next=row.inbox.consume(packet);row.wanted||=!!next?.needsReplay;}
    }catch(error){row.wanted=true;onFault(error);}
   }
  }catch(error){if(current(token.host))onFault(error);}
  finally{if(replay===token)replay=null;}
 }
 const invalidate=()=>{epoch++;replay=null;for(const row of targets.values())drop(row);targets.clear();};
 return Object.freeze({
  async register(actorKey,body,profession,bodyEpoch){
   if(disposed)return;
   const old=targets.get(actorKey);if(old?.body===body&&old.epoch===bodyEpoch&&old.profession===profession)return;
   if(old)drop(old);
   const row={actorKey,body,profession,epoch:bodyEpoch,target:null,failed:false,inbox:null,wanted:false,queued:[],lastRequest:-Infinity};targets.set(actorKey,row);
   try{
    const target=await createGatherPoseTarget({body,characterAnimationState,dataText:legacyDataText,bindingText,actorKey});
    const actual=readActor(actorKey);
    if(disposed||!own(row)||actual?.body!==body||actual.epoch!==bodyEpoch){target.dispose();return;}
    row.target=target;void recover();
   }catch(error){if(own(row)){row.failed=true;row.queued=[];onFault(error);}}
  },
  remove(actorKey){const row=targets.get(actorKey);targets.delete(actorKey);if(row)drop(row);},
  receive(packet){
   if(disposed||!readHost().connected||!packet)return;
   // A missing or rejected body remains strictly unsupported. Its queue or
   // retry cannot hold another actor's ready, independently validated rig.
   for(const row of targets.values()){
    if(row.failed)continue;
    const part=packetFor(packet,row.actorKey);
    if(!row.target){if(part.records?.length)row.wanted=true;continue;}
    if(row.wanted){enqueue(row,part);continue;}
    try{row.inbox||=makeInbox(row);const state=row.inbox.consume(part);if(state?.needsReplay){row.wanted=true;enqueue(row,part);}}
    catch(error){row.wanted=true;enqueue(row,part);onFault(error);}
   }
   void recover();
  },
  afterBaseUpdate(){if(!disposed)for(const row of targets.values())row.inbox?.afterBaseUpdate();},
  invalidate,
  dispose(){if(disposed)return;invalidate();disposed=true;library.dispose();},
 });
}
