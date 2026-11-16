// Web scene ownership only. Complete native poses remain the body's consumer's
// responsibility. Slow body loads never publish a stale character/session.
const stamp=record=>JSON.stringify([record.id,record.profession,record.sourceAvatar??null]);

export function createPlayerChoiceScene({actors,install,update,remove,onError=()=>{}}={}){
 if(typeof actors?.create!=='function'||typeof install!=='function'||typeof update!=='function'||typeof remove!=='function'||typeof onError!=='function')throw Error('Explicit scene actor interfaces required');
 const live=new Map(),pending=new Map(),reported=new WeakSet();let epoch=0,latest=new Map(),valid=()=>true;
 function report(error){if(error&&typeof error==='object'){if(reported.has(error))return;reported.add(error);}onError(error);}
 function forget(id){const entry=live.get(id);if(entry){live.delete(id);try{entry.actor.dispose();}finally{remove(entry);}}}
 function clear(){epoch++;latest=new Map();pending.clear();for(const id of [...live.keys()])forget(id);}
 async function sync(records,at,{current=()=>true}={}){
  const scope=epoch;
  try{
  if(!Array.isArray(records)||typeof current!=='function')throw Error('Actual scene records required');valid=current;
  const next=new Map();for(const record of records){if(typeof record?.id!=='string'||next.has(record.id))throw Error('Distinct actual actor identities required');next.set(record.id,{record,at,stamp:stamp(record)});}
  latest=next;
  for(const id of [...live.keys()])if(!latest.has(id))forget(id);
  const jobs=[];
  for(const [id,latestRow]of latest){
   const existing=live.get(id);
   if(existing){update(existing,latestRow.record,at);continue;}
   if(pending.has(id)){jobs.push(pending.get(id));continue;}
   const generation=epoch,identity=latestRow.stamp;
   const currentActor=()=>generation===epoch&&valid()&&latest.get(id)?.stamp===identity;
   const job=(async()=>{
    const actor=await actors.create(latestRow.record,{current:currentActor});if(!actor)return;
    if(!currentActor()){actor.dispose();return;}
    const row=latest.get(id);let entry;
    try{actor.apply(row.record,row.at);entry=install(actor,row.record,row.at);entry.actor=actor;live.set(id,entry);update(entry,row.record,row.at);}
    catch(error){live.delete(id);try{actor.dispose();}finally{if(entry)remove(entry);}throw error;}
   })().catch(error=>{if(currentActor())throw error;}).finally(()=>{if(pending.get(id)===job)pending.delete(id);});
   pending.set(id,job);jobs.push(job);
  }
  return await Promise.all(jobs);
  }catch(error){if(scope===epoch&&valid())report(error);throw error;}
 }
 return {sync,clear,inspect:()=>({actors:live.size,pending:pending.size,epoch})};
}
