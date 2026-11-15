// Original accepted-book field contract over the existing authorized ordinary
// ledger. Session/revision guards are web transport, never original approvals.
export const JOURNAL_FORMAT='oc2-original-ordinary-journal-v1';
const clone=v=>structuredClone(v),uint=v=>Number.isSafeInteger(v)&&v>=0;
const requireValue=(v,message)=>{if(!v)throw TypeError(message);};

export function validateJournalProfile(p){
  requireValue(p?.format===JOURNAL_FORMAT&&p.questId===461&&p.mapId===1,'Verified original journal profile required');
  requireValue(p.sourceSHA256==='bd5c5a2d392dd63b872104148a74e075f8ec05c887a246015490ed16c95bf851'&&
    p.methods?.getQuestList==='4a61cda6e462fc9916af21bb18b4277491eb015ef5c5c14e9d4dd4260c227f13','Original journal consumer differs');
  requireValue(p.displayLevel===2&&p.questType===2&&Array.isArray(p.steps)&&p.steps.length===2,'Original ordinary task fields required');
  requireValue(p.steps[0].sourceType===2&&p.steps[0].total===4&&p.steps[1].sourceType===6&&p.steps[1].total===0,'Original objective sequence differs');
  requireValue(p.steps.every(s=>typeof s.text==='string'&&typeof s.icon==='string'&&s.icon.startsWith('ui/icons/quest/')),'Original objective text/icon required');
  requireValue(p.reward?.id===20028&&p.reward.count===1&&p.reward.icon==='ui/icons/item/red_skull_plan.png'&&
    p.reward.slotType===9&&p.reward.quality===0,'Original type9 reward display contract required');
  return p;
}

export function journalRows(p,state){
  validateJournalProfile(p);
  requireValue(state?.origin==='compatible-quest-layer'&&state.mapId===p.mapId&&uint(state.revision)&&
    Array.isArray(state.quests)&&Array.isArray(state.completedQuestIds),'Actual compatible accepted state required');
  const ids=new Set();
  const rows=state.quests.map((q,index)=>{
    requireValue(q.id===p.questId&&!ids.has(q.id)&&!state.completedQuestIds.includes(q.id),'Unsupported or contradictory accepted quest');ids.add(q.id);
    requireValue([4,9].includes(q.status)&&uint(q.current)&&q.required===4&&q.current<=4&&
      (q.status===9)===(q.current===4),'Actual original objective progress required');
    requireValue(typeof q.title==='string','Accepted quest title required');
    return {questId:q.id,title:q.title,displayLevel:p.displayLevel,displayIndex:index+1,questType:p.questType,status:q.status,
      current:q.current,total:q.required};
  });
  // A static catalog, available query, inventory, or completed row cannot
  // manufacture an accepted task. No original capacity is inferred here.
  return rows;
}

export function journalDetail(p,state,info,trackedQuestId){
  const rows=journalRows(p,state),row=rows.find(v=>v.questId===info?.questId);
  requireValue(row&&info.origin==='compatible-quest-layer'&&info.revision===state.revision&&info.Status===row.status,'Matching accepted detail/revision required');
  for(const key of ['Title','Objective','Detail'])requireValue(typeof info[key]==='string','Original task text required');
  requireValue(info.Title===row.title&&info.progress?.current===row.current&&info.progress.required===row.total,'Detail and accepted objective differ');
  requireValue(info.hasReward===true&&info.NumGold===9&&info.NumXp===512&&info.NumFever===5&&info.NumAdvExp===0&&
    info.NumItem===1&&info.NumItemOp===0&&info.fixedItems?.length===1,'Verified original reward fields required');
  const item=info.fixedItems[0];requireValue(item.id===p.reward.id&&item.count===p.reward.count&&item.icon===p.reward.icon,'Original reward item differs');
  requireValue(trackedQuestId===null||trackedQuestId===p.questId,'Explicit compatible tracking selection required');
  const step=p.steps[row.status===9?1:0];
  return {origin:'compatible-quest-layer',nativeMessage:false,accepted:true,questId:row.questId,revision:state.revision,
    title:info.Title,objective:info.Objective,detail:info.Detail,status:row.status,displayLevel:row.displayLevel,displayIndex:row.displayIndex,
    tracked:trackedQuestId===row.questId,step:{...step,current:step.total?row.current:0},
    rewards:{money:info.NumGold,xp:info.NumXp,favor:info.NumFever,items:[{id:item.id,count:item.count,icon:item.icon,
      // This is the checked source type9 view, not the items table quality.
      quality:p.reward.quality,slotType:9,nativeActionID:null}]}};
}

export function createJournalController({profile,program,programFactory,readSession,readState,query,action,readTrackedQuest,onChange,onError=()=>{}}){
  validateJournalProfile(profile);
  requireValue([programFactory,readSession,readState,query,action,readTrackedQuest,onChange,onError].every(v=>typeof v==='function'),'Journal session and transport providers required');
  let visible=false,binding=null,state=null,detail=null,rows=[],modal=null,pending=false,disposed=false,serial=0,lifetime=0,load=null,questionLoad=null;
  const current=()=>{const s=readSession();return s?.connected===true&&typeof s.characterId==='string'&&Number.isSafeInteger(s.epoch)?{characterId:s.characterId,epoch:s.epoch}:null;};
  const matches=b=>{const s=current();return !!s&&!!b&&s.characterId===b.characterId&&s.epoch===b.epoch;};
  const inspect=()=>({visible,pending:pending||!!questionLoad,modal:modal?'abandon':null,rows:clone(rows),detail:detail?clone(detail):null,revision:state?.revision??null,
    nativeMessage:false,compatibilityLayer:true});
  const notify=()=>onChange(inspect());
  function close(){serial++;lifetime++;visible=false;binding=null;state=null;detail=null;rows=[];modal=null;pending=false;load=null;questionLoad=null;notify();}
  function valid(){if(disposed||!visible)return false;if(!matches(binding)){close();return false;}return true;}
  async function loadDetail(snapshot){
    if(!valid())return null;
    const next=journalRows(profile,snapshot);
    if(state&&snapshot.revision<state.revision)return inspect();
    if(state&&state.revision===snapshot.revision){
      requireValue(JSON.stringify(next)===JSON.stringify(rows),'Same-revision accepted rows changed');
      if(detail)return inspect();
    }
    rows=next;state=clone(snapshot);
    if(!rows.length){serial++;load=null;detail=null;modal=null;notify();return inspect();}
    const key=binding.characterId+':'+binding.epoch+':'+snapshot.revision;
    if(load?.key===key)return load.promise;
    const token=++serial,b=clone(binding);modal=null;detail=null;notify();
    const promise=(async()=>{
      try{
        const info=await query(rows[0].questId);
        if(!valid()||!matches(b)||token!==serial)return null;
        detail=journalDetail(profile,state,info,readTrackedQuest());notify();return inspect();
      }catch(error){
        if(!valid()||!matches(b)||token!==serial)return null;
        detail=null;notify();onError(error);throw error;
      }finally{if(load?.promise===promise)load=null;}
    })();
    load={key,promise};return promise;
  }
  function update(snapshot){
    if(!valid())return false;
    const next=journalRows(profile,snapshot);
    if(state&&snapshot.revision<state.revision)return false;
    if(state&&snapshot.revision===state.revision){
      requireValue(JSON.stringify(next)===JSON.stringify(rows),'Same-revision accepted rows changed');return false;
    }
    void loadDetail(snapshot).catch(()=>{});return true;
  }
  async function open(){
    if(disposed)throw Error('Journal controller disposed');
    close();const b=current();requireValue(b,'Active character session required');binding=b;visible=true;
    const window=lifetime;
    try{
      const snapshot=await readState();if(window!==lifetime||!valid()||!matches(b))return null;
      // readState can synchronously notify the host's ordinary state listener.
      // Reuse its same-revision query instead of sending a second request.
      if(state&&state.revision>snapshot.revision)return inspect();
      return await loadDetail(snapshot);
    }catch(error){if(window!==lifetime||!valid()||!matches(b))return null;close();onError(error);throw error;}
  }
  async function askAbandon(){
    if(!valid()||pending||questionLoad||!detail||modal)return null;
    const b=clone(binding),revision=detail.revision,id=detail.questId,token=serial;
    const ticket={};questionLoad=ticket;notify();
    try{
      const vm=await programFactory(program,{rows:[{questId:id}],selectedIndex:0,isPUB:false,paramsStringCallback:true,abandonCallback:true});
      if(!valid()||!matches(b)||token!==serial||detail?.revision!==revision)return null;
      const result=vm.abandon(),show=result.actions.filter(v=>v.boundary==='ShowMsg');
      requireValue(show.length===1&&!result.actions.some(v=>v.boundary==='Hero_AbandonQuest'),'Original question branch required');
      modal={vm,questId:id,revision};
    }catch(error){if(!valid()||!matches(b)||token!==serial||questionLoad!==ticket)return null;throw error;
    }finally{if(questionLoad===ticket){questionLoad=null;if(valid())notify();}}
    return inspect();
  }
  async function answerAbandon(yes){
    requireValue(typeof yes==='boolean','Explicit original Yes/No required');
    if(!valid()||pending||!modal)return null;
    const b=clone(binding),question=modal,window=lifetime;
    if(!yes){question.vm.messageButton('onCancelClick',{enableSound:true,fullScreenClose:false,forwardToBook:true});modal=null;notify();return {sent:false,cancelled:true};}
    pending=true;notify();
    try{
      const fresh=await readState();if(window!==lifetime||!valid()||!matches(b))return null;
      if(fresh.revision!==question.revision||state?.revision!==question.revision||!fresh.quests?.some(q=>q.id===question.questId)){
        modal=null;await loadDetail(fresh);
        if(window!==lifetime||!valid()||!matches(b))return null;
        return {sent:false,reason:'state-changed'};
      }
      requireValue(modal===question&&detail?.questId===question.questId,'Question target changed');
      const result=question.vm.messageButton('onOkClick',{enableSound:true,fullScreenClose:false,forwardToBook:true});
      const intents=result.actions.filter(v=>v.boundary==='Hero_AbandonQuest');
      requireValue(intents.length===1&&intents[0].arguments.length===1&&intents[0].arguments[0]===question.questId,'Original abandon intent required');
      const reply=await action({type:'abandon',questId:question.questId,revision:question.revision,origin:'compatible-quest-layer'});
      if(window!==lifetime||!valid()||!matches(b))return null;
      requireValue(reply?.ok===true,'Compatible abandon rejected');modal=null;
      if(reply.state)await loadDetail(reply.state);else await loadDetail(await readState());
      if(window!==lifetime||!valid()||!matches(b))return null;
      return {sent:true,result:reply};
    }catch(error){if(window!==lifetime||!valid()||!matches(b))return null;modal=null;onError(error);throw error;}
    finally{if(window===lifetime&&valid()&&matches(b)){pending=false;notify();}}
  }
  return Object.freeze({open,close,update,askAbandon,answerAbandon,inspect,invalidate:close,
    dispose(){if(disposed)return;close();disposed=true;}});
}
