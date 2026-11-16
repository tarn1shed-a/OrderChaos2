// Web carrier for the recovered source queues. Selection events and shared
// history are explicit inputs; completing an HTTP/GPU load never selects a class.
export const CLASS_MOTION_MANIFEST='/assets/source-creation-control-v1/manifest-class-v1.json';
export const INITIAL_MOTION_MANIFEST='/assets/source-creation-initial-idle-v1/manifest.json';
const bodies={'0:0':'human-male','0:1':'human-female','1:0':'mendel-male','1:1':'mendel-female','2:0':'elf-male','2:1':'elf-female','3:0':'orc-male','3:1':'orc-female','4:0':'kartan'};
const classes=['warrior','ranger','mage','ds','monk'];
export const creationMotionKey=i=>bodies[`${i.race}:${i.gender}`]+'-'+classes[i.professionIndex];
export function createCreationMotionLibrary({json,bytes,crypto,importModule=url=>import(url)}){
 if([json,bytes,importModule].some(f=>typeof f!=='function')||!crypto?.subtle)throw Error('Explicit checked source input readers required');
 const resource=(base,path)=>{
  if(typeof path!=='string'||!/^\.\/[A-Za-z0-9_./-]+$/.test(path)||path.includes('..')||path.includes('//'))throw Error('Unsafe original motion resource');
  return base.slice(0,base.lastIndexOf('/')+1)+path.slice(2);
 };
 const pending=new Map();
 async function source(kind){
  if(!pending.has(kind))pending.set(kind,(async()=>{
   const url=kind==='show'?CLASS_MOTION_MANIFEST:INITIAL_MOTION_MANIFEST,manifest=await json(url);
   const expected=kind==='show'?'oc2-all-class-safe-source-pose-assets-v1':'oc2-creation-initial-idle-browser-assets-v1';
   if(manifest?.format!==expected||!manifest.profiles||!manifest.banks)throw Error('Original Class motion manifest differs');
   const entry=resource(url,manifest.entry.url),api=await importModule(entry);
   const queueURL=kind==='show'?'/assets/source-creation-control-runtime-v1/modules/source_class_queue_runtime_v1.mjs':'/assets/source-creation-control-runtime-v1/modules/source_initial_queue_runtime_v1.mjs';
   return {url,manifest,api,queues:await importModule(queueURL)};
  })().catch(error=>{pending.delete(kind);throw error;}));
  return pending.get(kind);
 }
 return Object.freeze({
  async prepare({identity,data,kind,ownerBefore,initialGlobals,current}){
   if(identity?.panel!==1||!['show','initial'].includes(kind)||typeof current!=='function')throw Error('Explicit own Class event required');
   if(kind==='initial'&&initialGlobals===null)return null;
   const s=await source(kind),key=creationMotionKey(identity),row=s.manifest.profiles[key];
   if(!current())return null;
   if(!row)return null; // A missing own full profile never borrows another body.
   const bank=s.manifest.banks[row.bank];if(!bank)throw Error('Own source motion bank absent');
   const [profileBytes,tracksBytes]=await Promise.all([bytes(resource(s.url,row.url)),bytes(resource(s.url,bank.url))]);
   if(!current())return null;
   let sampler,queue,unknownProbe=null;
   try{
    const options={key,profileBytes,tracksBytes,rigNodes:data.rig.nodes,sourceCreation:data.sourceCreation,crypto};
    sampler=await (kind==='show'?s.api.createCreationPoseSampler:s.api.createCreationInitialPoseSampler)(options);
    if(!current()){sampler.dispose();return null;}
    if(kind==='show'){
     // This conditional input represents the web host's exact constructed
     // display, not original 53d3e8 cache membership or Android GPU readiness.
     const decision=s.queues.classEntryDecision({key,ownerSelection:ownerBefore,exactDisplayCacheEntryFound:true});
     if(decision.kind!=='conditional-source-show')throw Error('Class change event did not select a new source show');
     if(initialGlobals===null){
      // The unrestored Race callback may leave history unknown. The source
      // Class-show selection overwrites both globals before either is read.
      // Check the two boundary seeds through that exact queue, then retain
      // only the identical post-selection state; no seed is reported as history.
      queue=s.queues.createSourceClassQueue({key,sampler,initialGlobals:{counter:0,selected:0}});
      unknownProbe=s.queues.createSourceClassQueue({key,sampler,initialGlobals:{counter:2147483647,selected:6}});
      queue.startConditionalShow(decision);unknownProbe.startConditionalShow(decision);
     }else{queue=s.queues.createSourceClassQueue({key,sampler,initialGlobals});queue.startConditionalShow(decision);}
    }else{
     queue=s.queues.createSourceInitialIdleQueue({key,sampler,initialGlobals});
     queue.startConditionalInitialIdle({initialClip:'idle',arg2:0,engineFlags:3,conditionalBodyLoadedBranch:true});
    }
    let live=true;
    return Object.freeze({
     kind,key,
     update(milliseconds,actor){
      if(!live||!current())throw Error('Retired Class motion owner');
      const frame=queue.tick(milliseconds);
      if(unknownProbe){
       const other=unknownProbe.tick(milliseconds);
       if(JSON.stringify(frame)!==JSON.stringify(other))throw Error('Unknown history affects source Class-show selection');
       unknownProbe.dispose();unknownProbe=null;
      }
      const pose=queue.pose();if(pose)actor.applySourcePose(pose);
      return {counter:frame.counter,selected:frame.selected,clip:frame.layers[0].current?.clip,ageMs:frame.layers[0].current?.ageMs};
     },
     inspect(){return unknownProbe?{key,historyKnown:false,sourceFrame:null}:queue.inspect();},
     dispose(){if(!live)return;live=false;unknownProbe?.dispose();unknownProbe=null;queue.dispose();sampler.dispose();},
    });
   }catch(error){unknownProbe?.dispose();queue?.dispose();sampler?.dispose();throw error;}
  },
 });
}
