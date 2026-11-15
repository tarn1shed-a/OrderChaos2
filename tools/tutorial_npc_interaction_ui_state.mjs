// Source-state-only NPC interaction plans. No static quest fallback, actor,
// server acceptance, network send or native model-ready event is produced.
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const integer=v=>Number.isInteger(v)&&v>=0&&v<=0x7fffffff;
const closed=reason=>({visible:false,reason,buttons:[],rows:[],networkSent:false,taskGranted:false});
const clone=v=>JSON.parse(JSON.stringify(v));
export function sourceWheelPosition(target,size,stage){
  if(!target||typeof target.guid!=='string'||!target.guid||!finite(target.NamePosX)||!finite(target.NamePosY)||
    !Array.isArray(size)||!Array.isArray(stage)||size.length!==2||stage.length!==2||![...size,...stage].every(v=>finite(v)&&v>0))return null;
  // Literal updateInteractPos branches, including the narrow-stage behavior.
  let x=target.NamePosX,y=target.NamePosY;
  if(x<size[0]/2)x=size[0]/2;else if(x>stage[0]-size[0]/2)x=stage[0]-size[0]/2;
  if(y<size[1]/2)y=size[1]/2;else if(y>stage[1]-size[1]/2)y=stage[1]-size[1]/2;
  return [x,y];
}
export function sourceQuestListIcon(profile,status){
  const s=profile.constants.questStatus,p='ui/icons/head_obj/';
  if(status===s.QMGR_QUEST_AVAILABLE)return p+'quest_available.png';
  if(status===s.QMGR_QUEST_DAILY_AVAILABLE)return p+'daily_quest_available.png';
  if(status===s.QMGR_QUEST_NOT_FINISHED)return p+'quest_unfinished.png';
  if(status===s.QMGR_QUEST_FINISHED)return p+'quest_complete.png';
  if([s.QMGR_QUEST_AVAILABLE_ENDLESS,s.QMGR_QUEST_DAILY_FINISHED].includes(status))return p+'daily_quest_complete.png';
  if([s.QMGR_QUEST_AVAILABLELOW_LEVEL,s.QMGR_QUEST_AVAILABLE_PERIOD_MISMATCH].includes(status))return p+'quest_available_lowlevel.png';
  return '';
}

export function createNPCInteractionUIReader({profile,admission,readWheelObservation,readQuestListObservation}={}){
  if(profile?.format!=='oc2-npc-interaction-ui-profile-v1')throw TypeError('Original UI profile required');
  const gate=ref=>{try{return admission?.inspect(ref);}catch{return null;}};
  const read=(fn,ref)=>{try{return typeof fn==='function'?fn(ref):null;}catch{return null;}};
  let wheel=closed('Initial state'),list=closed('Initial state');
  const clear=()=>{wheel=closed('Closed');list=closed('Closed');};
  const api={
    wheel(reference){
      const a=gate(reference);
      if(a?.sourceActivityEstablished!==true||a.wheelPreflight!==true){clear();return wheel=closed('No admitted original activity/interaction');}
      const o=read(readWheelObservation,reference);
      if(!o||o.actualGuid!==a.actualGuid||o.target?.guid!==a.actualGuid||o.originalWindowRequested!==true)
        return wheel=closed('Original current-target/window observations unavailable');
      const position=sourceWheelPosition(o.target,o.windowSize,o.stage);
      if(!position||!Array.isArray(o.events))return wheel=closed('Actual target projection/window measurement unavailable');
      const events=[];
      for(const e of o.events){
        // This bounded interface supports only the original root interaction /
        // quest buttons. Other levels/menu types remain an explicit boundary.
        if(!e||![0,2].includes(e.btnType)||e.level!==0||e.subBtnCount!==0||typeof e.isUpdate!=='boolean'||!profile.icons[e.Icon])
          return wheel=closed('Unrestored original wheel event/level');
        const old=events.findIndex(v=>v.btnType===e.btnType);
        if(e.isUpdate){if(old<0)return wheel=closed('Original update has no existing button');events[old]=clone(e);}
        else events.push(clone(e));
      }
      if(!events.length||events.length>profile.constants.NPCInteraction.INTERACT_BTN_COUNT)return wheel=closed('Original button list is empty or exceeds source slots');
      const buttons=events.map((e,index)=>({...e,index,enabled:true,sourceEnableDefault:true}));
      wheel={visible:true,actualGuid:a.actualGuid,position,stage:clone(o.stage),buttons,
        mid:{btnType:7,index:-1,Icon:'ui/icons/head_obj/menu.png'},networkSent:false,taskGranted:false};
      return clone(wheel);
    },
    queryIntent(reference,index){
      const current=api.wheel(reference),button=current.buttons[index];
      if(!current.visible||!button)return null;
      const a=gate(reference);
      if(button.btnType===2){
        if(!a.queryIntent){clear();return null;}
        clear();return {nativeCallback:'Hero_GetTargetQuest',request:clone(a.queryIntent),networkSent:false};
      }
      clear();return {nativeCallback:'Hero_InteractWithTarget',actualGuid:current.actualGuid,networkSent:false};
    },
    questList(reference){
      const a=gate(reference);
      if(a?.sourceActivityEstablished!==true||a.selectionPreflight!==true){clear();return list=closed('No admitted original current actor');}
      const o=read(readQuestListObservation,reference),p=o?.properties;
      if(!o||o.originalQueryReplyObserved!==true||o.originalListEvent?.typeList!==profile.constants.ListCommon.TYPE_QUEST_LIST||o.origin!=='Hero_GetQuestListNPC'||o.actualGuid!==a.actualGuid||
        p?.NPCGuid!==a.actualGuid||!integer(p.numQuest))return list=closed('Received query-cache list view unavailable');
      const count=Math.min(p.numQuest,profile.constants.ListCommon.maxListItemNum),rows=[];
      for(let i=0;i<count;i++){
        const id=p['questId'+i],status=p['status'+i],title=p['title'+i];
        if(!integer(id)||id===0||!integer(status)||typeof title!=='string')return list=closed('Incomplete native query-list row');
        rows.push({index:i,questId:id,status,title,icon:sourceQuestListIcon(profile,status),enabled:true});
      }
      const stage=o.stage,w=profile.windows.ListCommon;
      if(!Array.isArray(stage)||stage.length!==2||!stage.every(v=>finite(v)&&v>0))return list=closed('Actual UI stage unavailable');
      const position=[0,1].map(i=>Number(w.config[i?'relativeposY':'relativeposX'])*(stage[i]-w.measuredSize[i])+Number(w.config[i?'offsetY':'offsetX']));
      list={visible:true,actualGuid:a.actualGuid,title:profile.strings.GENERAL_TITLE_QUEST_LIST.text,
        rows,position,stage:clone(stage),scrollVisible:count>profile.constants.ListCommon.MAX_ITEM_INONEPAGE,
        nativeModel3DThumbnailRestored:false,acceptedCacheOwnership:null,networkSent:false,taskGranted:false};
      return clone(list);
    },
    detailIntent(reference,index){
      const current=api.questList(reference),row=current.rows[index];
      if(!current.visible||!row)return null;
      // Original onListItemClick: EventQuestDetail(questId,true,false), hide.
      clear();return {nativeCallback:'EventQuestDetail',arguments:[row.questId,true,false],
        receivedQueryOnly:true,acceptedCacheOwnership:null,networkSent:false,taskGranted:false};
    },
    close:clear,inspect:()=>({wheel:clone(wheel),questList:clone(list),actorCreated:false,networkSent:false})
  };
  return Object.freeze(api);
}

// Mount only an inert host container. The returned reader creates no content
// until its activity-gated plan is visible; the formal host owns rendering and
// the existing read-only MissionDialog/EventQuestDetail bridge.
export function mountNPCInteractionUIBoundary(host,reader){
  if(!(host instanceof Element)||typeof reader?.wheel!=='function'||typeof reader?.questList!=='function')throw TypeError('Host element and source reader required');
  const root=document.createElement('div');root.hidden=true;root.dataset.npcInteractionSourceBoundary='true';host.append(root);
  let plan=null;
  return Object.freeze({
    readWheel(reference){plan=reader.wheel(reference);if(!plan.visible){root.hidden=true;root.replaceChildren();}return clone(plan);},
    readQuestList(reference){plan=reader.questList(reference);if(!plan.visible){root.hidden=true;root.replaceChildren();}return clone(plan);},
    inspect:()=>({hidden:root.hidden,renderedChildren:root.childElementCount,plan:plan?clone(plan):null,
      rendererInstalled:false,actorCreated:false,networkSent:false}),
    close(){reader.close();plan=null;root.hidden=true;root.replaceChildren();},
    destroy(){reader.close();root.remove();}
  });
}
