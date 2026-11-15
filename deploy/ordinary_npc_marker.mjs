// Candidate reader for the explicitly authorized compatible quest461 only.
// Receiver handles are host-owned lifetimes, not network authentication.
// No original activity/qualification/GUID or task approval is synthesized.
import {validateQuestView} from './quest_ui.mjs';

const icons=Object.freeze({
  6:['quest_available.png','a361292574e8f7c07b4798338c231e94e583ff9df50f13f13032dbca77b1213d',16,4],
  4:['quest_unfinished.png','6365e38da2771d45551e9101407a689c36fc6c7f297c360daf6e2d4ecebf3914',16384,14],
  9:['quest_complete.png','c2a100b67727486da71300eca6b91ff911d215518640fd416cbf8707f01dba28',8,3],
});
const integer=v=>Number.isSafeInteger(v)&&v>=0,copy=v=>structuredClone(v);
const closed=reason=>({selected:false,display:false,reason,questId:461,npcEntry:2079,
  compatibilityProjection:true,originalActivity:false,taskApproved:false});

export function createOrdinaryNPCQuestMarkerReader({readHost}={}){
  if(typeof readHost!=='function')throw TypeError('Host-owned rendered actor reader required');
  let live=null,info=null,revision=-1,disposed=false;
  const current=receiver=>!disposed&&receiver===live;
  const clear=()=>{info=null;};
  function state(value){
    if(value?.origin!=='compatible-quest-layer'||value.mapId!==1||!integer(value.revision)||
      !Array.isArray(value.quests)||!Array.isArray(value.completedQuestIds)||
      value.quests.length>1||value.quests.some(q=>q.id!==461||![4,9].includes(q.status)||q.required!==4||!integer(q.current)||q.current>4)||
      value.completedQuestIds.some(id=>id!==461)||new Set(value.completedQuestIds).size!==value.completedQuestIds.length)
      throw TypeError('Single authorized quest461 state required');
    const row=value.quests[0],done=value.completedQuestIds.includes(461);
    if(done&&row||row&&(row.status===9)!==(row.current===4))throw TypeError('Inconsistent compatible progress');
    return {revision:value.revision,row,done};
  }
  function receiveState(receiver,value){
    if(!current(receiver))return false;
    let s;try{s=state(value);}catch(error){clear();throw error;}
    if(s.revision<revision)return false;
    if(s.revision!==revision||s.done)clear();revision=s.revision;return true;
  }
  function receiveQuery(receiver,response){
    if(!current(receiver))return false;
    let s,next;
    try{
      s=state(response?.state);if(s.revision<revision)return false;
      if(s.done){clear();revision=s.revision;return true;}
      next=validateQuestView(response.info);
      const phase={6:'available',4:'accepted',9:'ready'}[next.Status];
      if(next.questId!==461||!phase||next.phase!==phase||next.revision!==s.revision||
        next.progress?.required!==4||!integer(next.progress.current)||
        (next.Status===6?Boolean(s.row)||next.progress.current!==0:!s.row||s.row.status!==next.Status||s.row.current!==next.progress.current))
        throw TypeError('Actual compatible query/state for461 must agree');
    }catch(error){clear();throw error;}
    revision=s.revision;info=next;return true;
  }
  function inspect(receiver){
    if(!current(receiver))return closed('inactive-session');
    if(!info)return closed('no-current-query');
    let host;try{host=readHost();}catch{return closed('host-unavailable');}
    if(host?.mapId!==1||host.sourceID!=='npc:6598'||host.entry!==2079||host.displayed!==true)
      return closed('compatible-NPC2079-not-displayed');
    const [name,sha256,referenceMask,referenceIndex]=icons[info.Status];
    return {selected:true,display:false,reason:'original-actor-admission-and-cache-schedule-not-recovered',questId:461,npcEntry:2079,
      revision,status:info.Status,sourceIcon:'ui/icons/head_obj/'+name,assetFile:sha256+'.png',sha256,sourceImageSize:[96,96],
      referenceMask,referenceIndex,window:'MissionDialog',requiresListCommon:false,
      originalActivity:false,originalActorQualification:false,compatibilityProjection:true,taskApproved:false};
  }
  return Object.freeze({
    beginSession(){if(disposed)throw Error('Marker reader disposed');clear();revision=-1;live=Object.freeze({});return live;},
    receiveState,receiveQuery,inspect,
    detailIntent(receiver){const p=inspect(receiver);return p.selected?{kind:'compatible-open-quest-detail',questId:461,
      window:p.window,isOpenedFromList:false,isAutoAccepted:false,requiresListCommon:false,networkSent:false,taskApproved:false}:null;},
    invalidate(){live=null;clear();revision=-1;},
    dispose(){live=null;clear();revision=-1;disposed=true;},
  });
}
