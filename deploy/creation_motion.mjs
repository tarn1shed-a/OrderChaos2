// Web carrier only: source libraries own queues/poses; HTTP ready is not selection.
export const CLASS_MOTION_MANIFEST='/assets/source-creation-control-v1/manifest-class-v1.json';
export const INITIAL_MOTION_MANIFEST='/assets/source-creation-initial-idle-v1/manifest.json';
export const INITIAL_ALL_MOTION_MANIFEST='/assets/source-creation-initial-all-v1/manifest.json';
export const RACE_MOTION_MANIFEST='/assets/source-creation-race-control-v1/manifest.json';
export const PARTIAL_MOTION_MANIFEST='/assets/source-creation-partial-class-v1/manifest.json';
const roots=['control-v1','control-runtime-v1','initial-idle-v1','initial-all-v1','race-control-v1','partial-class-v1'].map(n=>'/assets/source-creation-'+n+'/');
export function creationMotionResourceURL(base,path){
 if(typeof path!=='string'||!/^\.?\.?\/?[A-Za-z0-9_./-]+$/.test(path)||path.includes('//')||!path.startsWith('./')&&!path.startsWith('../')&&!path.startsWith('/assets/'))throw Error('Unsafe original motion resource');
 const url=new URL(path,'https://source.invalid'+base);
 if(url.origin!=='https://source.invalid'||url.search||url.hash||!roots.some(prefix=>url.pathname.startsWith(prefix)))throw Error('Motion resource outside known same-origin source assets');
 return url.pathname;
}
const bodies={'0:0':'human-male','0:1':'human-female','1:0':'mendel-male','1:1':'mendel-female','2:0':'elf-male','2:1':'elf-female','3:0':'orc-male','3:1':'orc-female','4:0':'kartan'},classes=['warrior','ranger','mage','ds','monk'];
export const creationMotionKey=i=>bodies[`${i.race}:${i.gender}`]+'-'+classes[i.professionIndex];
export const creationRaceMotionKey=i=>'race-'+bodies[`${i.race}:${i.gender}`];
// Original UI event/owner ordering, before asynchronous web carrier loading.
// This chooses no clip, does not acknowledge a resource, and never invents history.
export function creationMotionEventPlan({version,screen,event,target,ownerSelection,requested,history}){
 const same=requested?.screen===screen&&requested.race===target.race&&requested.gender===target.gender;
 if(event==='class-selection'&&same&&requested.professionIndex===target.professionIndex||version===2&&event==='race-selection'&&same&&ownerSelection?.race===target.race&&ownerSelection.gender===target.gender)return{noop:true};
 if(!version)return{noop:false,kind:null,ownerBefore:ownerSelection?{...ownerSelection}:null,initialGlobals:null};
 if(!history)throw Error('Explicit selection history carrier required');
 const ownerBefore=ownerSelection?{...ownerSelection}:null;
 if(screen==='CharacterChooseRace'&&event==='page-enter'){
  if(version===2)history.enterRace(target,{sourceQueueEnabled:true});
  else history.unresolvedCarrier(); // V5 UI already issued its one enterRace write.
 }
 const initialGlobals=history.read(),matching=ownerBefore?.race===target.race&&ownerBefore?.gender===target.gender;
 const kind=screen==='CharacterChooseClass'?(event==='class-selection'&&matching&&ownerBefore.professionIndex!==target.professionIndex?'show':'initial'):
  screen==='CharacterChooseRace'&&version===2?(event==='race-selection'&&ownerBefore&&!matching?'race-show':'race-initial'):null;
 if(kind)history.unresolvedCarrier();
 return{noop:false,kind,ownerBefore,initialGlobals};
}
export function createCreationMotionLibrary({json,bytes,crypto,importModule=url=>import(url),version=1}){
 if(![1,2].includes(version)||[json,bytes,importModule].some(f=>typeof f!=='function')||!crypto?.subtle)throw Error('Explicit checked source input readers/version required');
 const pending=new Map(),resource=creationMotionResourceURL;
 async function source(kind){
  const name=kind.startsWith('race-')?'race':kind;
  if(!pending.has(name))pending.set(name,(async()=>{
   const config=name==='show'?[CLASS_MOTION_MANIFEST,'oc2-all-class-safe-source-pose-assets-v1','createCreationPoseSampler']:
    name==='partial-show'?[PARTIAL_MOTION_MANIFEST,'oc2-creation-partial-class-browser-v1','createCreationPartialClassPoseSampler']:
    name==='race'?[RACE_MOTION_MANIFEST,'oc2-creation-race-source-control-assets-v1','createCreationRacePoseSampler']:
    version===2?[INITIAL_ALL_MOTION_MANIFEST,'oc2-creation-initial-all-browser-assets-v1','createCreationInitialPoseSampler']:
    [INITIAL_MOTION_MANIFEST,'oc2-creation-initial-idle-browser-assets-v1','createCreationInitialPoseSampler'];
   const[url,format,poseExport]=config,manifest=await json(url);
   if(manifest?.format!==format||!manifest.profiles||!manifest.banks)throw Error('Original selection motion manifest differs');
   const api=await importModule(resource(url,manifest.entry.url));
   const queueURL=(name==='show'||name==='partial-show')?(version===2?'/assets/source-creation-partial-class-v1/modules/source_partial_class_runtime_v1.mjs':'/assets/source-creation-control-runtime-v1/modules/source_class_queue_runtime_v1.mjs'):
    name==='race'||version===2?resource(url,manifest.runtimeQueue.url):'/assets/source-creation-control-runtime-v1/modules/source_initial_queue_runtime_v1.mjs';
   if(typeof api[poseExport]!=='function')throw Error('Exact source sampler export absent');
   return {url,manifest,api,poseExport,queues:await importModule(queueURL)};
  })().catch(error=>{pending.delete(name);throw error;}));
  return pending.get(name);
 }
 return Object.freeze({
  async prepare({identity,data,kind,ownerBefore,initialGlobals,current}){
   const race=identity?.panel===0;
   if(typeof current!=='function'||!(race?version===2&&['race-show','race-initial'].includes(kind):identity?.panel===1&&['show','initial'].includes(kind)))throw Error('Explicit own Class/Race event required');
   if(kind.endsWith('initial')&&initialGlobals===null)return null;
   let s=await source(kind),key=race?creationRaceMotionKey(identity):creationMotionKey(identity),row=s.manifest.profiles[key];
   if(!current())return null;
   if(!row&&kind==='show'&&version===2){s=await source('partial-show');row=s.manifest.profiles[key];if(!current())return null;}
   if(!row)return null;
   const bank=s.manifest.banks[row.bank];if(!bank)throw Error('Own source motion bank absent');
   const [profileBytes,tracksBytes]=await Promise.all([bytes(resource(s.url,row.url)),bytes(resource(s.url,bank.url))]);
   if(!current())return null;
   let sampler,queue,unknownProbe=null;
   try{
    sampler=await s.api[s.poseExport]({key,profileBytes,tracksBytes,rigNodes:data.rig.nodes,sourceCreation:data.sourceCreation,crypto});
    if(!current()){sampler.dispose();return null;}
    if(kind==='show'){
     const decision=s.queues.classEntryDecision({key,ownerSelection:ownerBefore,exactDisplayCacheEntryFound:true});
     if(decision.kind!=='conditional-source-show')throw Error('Class change event did not select a new source show');
     if(initialGlobals===null){
      // Private boundary probes are discarded after the actual first selection.
      queue=s.queues.createSourceClassQueue({key,sampler,initialGlobals:{counter:0,selected:0}});
      unknownProbe=s.queues.createSourceClassQueue({key,sampler,initialGlobals:{counter:2147483647,selected:6}});
      queue.startConditionalShow(decision);unknownProbe.startConditionalShow(decision);
     }else{queue=s.queues.createSourceClassQueue({key,sampler,initialGlobals});queue.startConditionalShow(decision);}
    }else if(race){
     const decision=kind==='race-show'?s.queues.raceEntryDecision({key,ownerSelection:ownerBefore,exactDisplayCacheEntryFound:true}):null;
     // Init may have accepted another body before ENTER_RACE superseded show.
     // Retain owner.class; actual host construction precedes this preparation.
     const ownerAfter=decision?.ownerAfter??(ownerBefore?{...ownerBefore,race:identity.race,gender:identity.gender}:null);
     queue=s.queues.createSourceRaceQueue({key,sampler,ownerSelection:ownerAfter,initialGlobals});
     if(kind==='race-show')queue.startConditionalRaceShow(decision);
     else queue.startConditionalInitialIdle({initialClip:'idle',arg2:0,engineFlags:3,conditionalBodyLoadedBranch:true});
    }else{
     queue=s.queues.createSourceInitialIdleQueue({key,sampler,initialGlobals});
     queue.startConditionalInitialIdle({initialClip:'idle',arg2:0,engineFlags:3,conditionalBodyLoadedBranch:true});
    }
    let live=true,first=true;
    return Object.freeze({
     kind,key,
     update(milliseconds,actor){
      if(!live||!current())throw Error('Retired selection motion owner');
      if(first&&initialGlobals===null&&milliseconds!==0)throw Error('Unknown history requires the actual first zero-delta source selection');
      const frame=queue.tick(milliseconds);
      if(unknownProbe){const other=unknownProbe.tick(milliseconds);if(JSON.stringify(frame)!==JSON.stringify(other))throw Error('Unknown history affects source Class-show selection');unknownProbe.dispose();unknownProbe=null;}
      const pose=queue.pose();if(pose)actor.applySourcePose(pose);first=false;
      return {counter:frame.counter,selected:frame.selected,clip:frame.layers[0].current?.clip,ageMs:frame.layers[0].current?.ageMs};
     },
     inspect(){return unknownProbe||race&&first?{key,historyKnown:false,sourceFrame:null}:queue.inspect();},
     dispose(){if(!live)return;live=false;unknownProbe?.dispose();unknownProbe=null;queue.dispose();sampler.dispose();},
    });
   }catch(error){unknownProbe?.dispose();queue?.dispose();sampler?.dispose();throw error;}
  },
 });
}
