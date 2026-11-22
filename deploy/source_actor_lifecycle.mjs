// Browser ownership only. Existing format adapters validate resources/poses.
// No action clock, numerical sampler or game rule lives here.
const opaque=v=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&Object.getPrototypeOf(v)!==Object.prototype&&Object.getPrototypeOf(v)!==null;
const cancelled=()=>Object.assign(Error('Source owner expired'),{name:'AbortError'});
const aggregate=(errors,message)=>errors.length?new AggregateError(errors,message):null;
const active=check=>check()===true;

// World lease, independent of actor count. Verified, versioned keys come from
// the caller. Release priorities place dependent overlays before base inputs.
export function createSourceResourceScope({current}={}){
  if(typeof current!=='function')throw Error('Actual world owner check required');
  const entries=new Map(),jobs=new Set(),cleanupErrors=[],controller=new AbortController();
  let disposed=false,serial=0,failures=0;
  const live=()=>!disposed&&active(current);
  function release(row){
    if(row.released||!row.hasValue)return;
    row.released=true;row.state='Disposed';
    try{row.dispose(row.value);}catch(error){cleanupErrors.push(error);throw error;}
    finally{row.value=null;}
  }
  function load(key,prepare,{dispose,priority=0}={}){
    if(typeof key!=='string'||!key||typeof prepare!=='function'||typeof dispose!=='function'||!Number.isSafeInteger(priority)||priority<0)
      throw Error('Verified resource key, prepare, release and priority required');
    if(!live())throw cancelled();
    const previous=entries.get(key);
    if(previous){if(previous.priority!==priority)throw Error('Resource release priority changed');return previous.promise;}
    const row={key,priority,serial:++serial,state:'Pending',dispose,hasValue:false,value:null,released:false,promise:null};
    entries.set(key,row);
    row.promise=Promise.resolve().then(()=>{
      if(!live())throw cancelled();
      return prepare({current:live,signal:controller.signal});
    }).then(value=>{
      if(value===null||value===undefined)throw Error('Prepared resource is absent');
      row.value=value;row.hasValue=true;
      if(!live()){release(row);throw cancelled();}
      row.state='ResourcesReady';return value;
    }).catch(error=>{
      failures++;if(entries.get(key)===row)entries.delete(key);
      if(row.hasValue&&!row.released)try{release(row);}catch(cleanup){error=new AggregateError([error,cleanup],'Prepared resource cleanup failed');}
      throw error;
    }).finally(()=>jobs.delete(row));
    jobs.add(row);return row.promise;
  }
  function dispose(){
    if(disposed)return false;
    disposed=true;controller.abort();const errors=[];
    for(const row of [...entries.values()].sort((a,b)=>b.priority-a.priority||b.serial-a.serial))
      if(row.hasValue)try{release(row);}catch(error){errors.push(error);}
    entries.clear();const error=aggregate(errors,'World resource release failed');if(error)throw error;
    return true;
  }
  async function drain(){
    await Promise.allSettled([...jobs].map(row=>row.promise));
    const error=aggregate(cleanupErrors,'Late world resource cleanup failed');if(error)throw error;
  }
  return Object.freeze({load,dispose,drain,inspect:()=>({disposed,current:live(),pending:jobs.size,
    ready:[...entries.values()].filter(row=>row.state==='ResourcesReady').length,failures,cleanupErrors:cleanupErrors.length,
    entries:[...entries.values()].map(({key,priority,state})=>({key,priority,state}))})});
}

// resolve is the verified registry/catalog adapter, not another body registry.
// Every job retains its own current/session check, never a later sync callback.
export function createSourceActorLifecycle({actors,resolve,install,update,remove,readReady,onError=()=>{}}={}){
  if(typeof actors?.create!=='function'||[resolve,install,update,remove,readReady,onError].some(fn=>typeof fn!=='function'))
    throw Error('Explicit actor, verified definition, scene and readiness ports required');
  const live=new Map(),pending=new Map(),jobs=new Set(),cleanupErrors=[],reported=new WeakSet();
  let epoch=0,disposed=false,connection=null,latest=new Map();
  const counts={created:0,released:0,cancelled:0};
  function report(error){
    if(error&&typeof error==='object'){if(reported.has(error))return;reported.add(error);}
    onError(error);
  }
  const belongs=row=>!disposed&&!row.cancelled&&row.epoch===epoch&&row.connection===connection&&active(row.current)&&latest.get(row.id)?.identity===row.identity;
  function suspend(row){
    if(row.cancelled)return;
    row.cancelled=true;row.state='Suspended';counts.cancelled++;row.controller.abort();
  }
  function release(row){
    if(row.released)return;
    suspend(row);row.released=true;const errors=[];
    if(live.get(row.id)===row)live.delete(row.id);
    if(pending.get(row.id)===row)pending.delete(row.id);
    try{if(row.actor)row.actor.dispose();}catch(error){errors.push(error);}
    try{if(row.entry)remove(row.entry);}catch(error){errors.push(error);}
    row.state='Disposed';row.actor=null;row.entry=null;
    if(row.hadActor)counts.released++;
    if(errors.length){cleanupErrors.push(...errors);throw new AggregateError(errors,'Actor release failed');}
  }
  function cancelPending(row){
    suspend(row);if(pending.get(row.id)===row)pending.delete(row.id);
    // The factory may still own pending work; dispose its late value once.
    // Per-actor abort never aborts a world resource scope shared by a peer.
  }
  function clear(){
    epoch++;latest=new Map();connection=null;
    for(const row of [...pending.values()])cancelPending(row);
    const errors=[];for(const row of [...live.values()])try{release(row);}catch(error){errors.push(error);}
    const error=aggregate(errors,'Scene actor cleanup failed');if(error)throw error;
  }
  function readiness(row){
    if(!belongs(row))return false;
    if(readReady(row.entry,latest.get(row.id).record)===true){row.state='Playable';return true;}
    row.state='AuthorityBound';return false;
  }
  function start(row){
    const currentActor=()=>belongs(row);
    pending.set(row.id,row);jobs.add(row);
    row.promise=(async()=>{
      if(!currentActor())return;
      const actor=await actors.create(row.initial,{current:currentActor,signal:row.controller.signal,definition:row.definition});
      if(!actor){if(currentActor())throw Error('Current factory returned no actual actor');return;}
      row.actor=actor;row.hadActor=true;counts.created++;
      if(typeof actor.apply!=='function'||typeof actor.dispose!=='function')throw Error('Actual actor apply/release required');
      row.state='ResourcesReady';
      if(!currentActor()){release(row);return;}
      const newest=latest.get(row.id);
      actor.apply(newest.record,newest.at);
      if(!currentActor()){release(row);return;}
      row.entry=install(actor,newest.record,newest.at);
      if(!row.entry||typeof row.entry!=='object')throw Error('Actual scene binding required');
      if(row.entry.actor!==undefined&&row.entry.actor!==actor)throw Error('Scene bound another actor');
      row.entry.actor=actor;
      if(!currentActor()){release(row);return;}
      live.set(row.id,row);row.state='AuthorityBound';
      update(row.entry,newest.record,newest.at);readiness(row);
    })().catch(error=>{
      let wasCurrent=false,scopeError;
      try{wasCurrent=currentActor();}catch(failure){scopeError=failure;}
      try{release(row);}catch(cleanup){error=new AggregateError([error,cleanup],'Actor preparation failed');}
      if(scopeError)throw new AggregateError([error,scopeError],'Actor owner check failed');
      if(wasCurrent)throw error;
      // Stale resource failures cannot close a different live session. Cleanup
      // failures stay visible in inspectLifecycle/drain, rather than fake success.
    }).finally(()=>{
      if(pending.get(row.id)===row)pending.delete(row.id);
      if(!row.actor&&!row.entry)row.state='Disposed';jobs.delete(row);
    });
    return row.promise;
  }
  async function sync(records,at,{current,connection:nextConnection}={}){
    let scope=epoch;
    try{
      if(!Array.isArray(records)||typeof current!=='function'||!opaque(nextConnection))throw Error('Actual scene records and explicit connection required');
      if(disposed||!active(current))return;
      // Resolve all definitions before disturbing a valid previous scene.
      const next=new Map();
      for(const record of records){
        if(typeof record?.id!=='string'||!record.id||next.has(record.id))throw Error('Distinct actual actor identities required');
        const resolved=resolve(record),definition=resolved&&typeof resolved==='object'?Object.freeze({...resolved}):null;
        if(!definition||typeof definition!=='object'||typeof definition.definitionKey!=='string'||!definition.definitionKey)throw Error('Verified actor definition required');
        const identity=JSON.stringify([record.id,record.profession,definition.definitionKey]);
        next.set(record.id,{record,at,definition,identity});
      }
      if(connection!==null&&connection!==nextConnection)clear();
      connection=nextConnection;scope=epoch;latest=next;
      const errors=[];
      for(const row of [...pending.values()])if(!belongs(row))cancelPending(row);
      for(const row of [...live.values()])if(!belongs(row))try{release(row);}catch(error){errors.push(error);}
      const cleanup=aggregate(errors,'Replaced actor cleanup failed');if(cleanup)throw cleanup;
      const work=[];
      for(const [id,newest]of latest){
        const entry=live.get(id);
        if(entry){
          try{update(entry.entry,newest.record,newest.at);readiness(entry);}
          catch(error){try{release(entry);}catch(cleanup){error=new AggregateError([error,cleanup],'Actor update cleanup failed');}throw error;}
          continue;
        }
        const waiting=pending.get(id);
        if(waiting){work.push(waiting.promise);continue;}
        const row={id,initial:newest.record,definition:newest.definition,identity:newest.identity,current,connection,
          epoch,state:'DataResolved',controller:new AbortController(),cancelled:false,released:false,actor:null,entry:null,hadActor:false,promise:null};
        work.push(start(row));
      }
      return await Promise.all(work);
    }catch(error){
      let currentScope=false;try{currentScope=typeof current==='function'&&active(current);}catch{}
      if(!disposed&&scope===epoch&&(connection===nextConnection||connection===null)&&currentScope)report(error);
      throw error;
    }
  }
  function refreshReadiness(){
    if(disposed)return;
    for(const row of [...live.values()]){
      try{if(!belongs(row)){release(row);continue;}readiness(row);}
      catch(error){try{release(row);}catch(cleanup){error=new AggregateError([error,cleanup],'Actor readiness cleanup failed');}report(error);throw error;}
    }
  }
  function dispose(){if(disposed)return false;disposed=true;clear();return true;}
  async function drain(){
    await Promise.allSettled([...jobs].map(row=>row.promise));
    const error=aggregate(cleanupErrors,'Late actor cleanup failed');if(error)throw error;
  }
  const inspectLifecycle=()=>({disposed,epoch,actors:live.size,pending:pending.size,inflight:jobs.size,
    cancelledInflight:[...jobs].filter(row=>row.cancelled).length,cleanupErrors:cleanupErrors.length,counts:{...counts},
    states:[...new Set([...live.values(),...pending.values()])].map(row=>({id:row.id,definitionKey:row.definition.definitionKey,
      state:row.state,playable:row.state==='Playable'&&belongs(row)}))});
  return Object.freeze({sync,clear,dispose,refreshReadiness,drain,inspectLifecycle,
    isPlayable:id=>{const row=live.get(id);return !!row&&row.state==='Playable'&&belongs(row);},
    inspect:()=>({actors:live.size,pending:pending.size,epoch})});
}
