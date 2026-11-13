// Browser preparation schedule only. Original geometry/material/binding functions are reused.
import {sourceArchiveWindow} from '/source-archive-window.js';
import {preparationWindow} from '/__delivery/streaming_window.mjs';
export function createSceneStages({canvas,scene,archiveObjects,terrain,offsets,radius,initial}){
  const tiles=terrain.sourceTiles.map(t=>t.tile),window=sourceArchiveWindow(tiles,offsets,radius);
  const first=window.update(initial.x,initial.z),critical=preparationWindow(tiles,offsets,first.center).prepared,jobs=new Map();
  let active=0,started=false,display=null,epoch=0,presentedEpoch=-1;
  const state=canvas.dataset,key=t=>t.join(',');
  state.loadingStage='entry';state.loadingEntryTiles=String(first.resident.size);state.loadingPreparedEntryTiles=String(critical.size);
  function job(tile,fn){const id=key(tile);if(!jobs.has(id))jobs.set(id,{tile,steps:[],status:'pending',priority:2});jobs.get(id).steps.push(fn);}
  function report(){state.loadingBackgroundDone=String([...jobs.values()].filter(j=>j.status==='done').length);state.loadingBackgroundTotal=String(jobs.size);api.onProgress?.();}
  function pump(){
    if(!started)return;
    while(active<2){
      const center=display?.center||first.center;
      const next=[...jobs.values()].filter(j=>j.status==='pending').sort((a,b)=>a.priority-b.priority||Math.max(Math.abs(a.tile[0]-center[0]),Math.abs(a.tile[1]-center[1]))-Math.max(Math.abs(b.tile[0]-center[0]),Math.abs(b.tile[1]-center[1])))[0];
      if(!next)break;active++;next.status='loading';
      (async()=>{for(const step of next.steps){await new Promise(resolve=>setTimeout(resolve,0));await step();}next.status='done';epoch++;})().catch(error=>{next.status='failed';state.loadingBackgroundError=error.message;}).finally(()=>{active--;report();pump();});
    }
    if(state.loadingStage!=='complete'&&[...jobs.values()].every(j=>j.status==='done')){state.loadingStage='complete';state.loadingBackgroundMs=String(Math.round(performance.now()));}
  }
  const api={onProgress:null,
    async terrain(create,T,data,materials,origin,texture,lighting){
      const subset=set=>[{...data,sourceTiles:data.sourceTiles.filter(t=>set.has(key(t.tile)))},{...materials,tiles:materials.tiles.filter(t=>set.has(key(t.tile)))},{...lighting,profile:{...lighting.profile,tiles:lighting.profile.tiles.filter(t=>set.has(key(t.tile)))}}];
      async function build(set){const[d,m,l]=subset(set);return create(T,d,m,origin,texture,l);}
      const roots=await build(critical);
      for(const tile of tiles)if(!critical.has(key(tile)))job(tile,async()=>{for(const root of await build(new Set([key(tile)]))){root.visible=false;roots.push(root);archiveObjects.push({root,tile});scene.add(root);}});
      return roots;
    },
    async scenery(items,load){
      // Shared model tasks live in the original entry's template cache.
      for(const item of items){const near=item.instances.filter(i=>critical.has(key(i.tile)));if(near.length)await load(item,near);}
      for(const item of items){const groups=new Map();for(const row of item.instances)if(!critical.has(key(row.tile))){const id=key(row.tile);if(!groups.has(id))groups.set(id,[]);groups.get(id).push(row);}for(const rows of groups.values())job(rows[0].tile,()=>load(item,rows));}
    },
    start(){started=true;state.loadingStage='background';state.loadingEntryReadyMs=String(Math.round(performance.now()));report();pump();},
    present(change){
      if(change){display=change;epoch++;const margin=preparationWindow(tiles,offsets,display.center).prepared;for(const [id,row]of jobs)row.priority=display.resident.has(id)?0:margin.has(id)?1:2;pump();}
      if(!display)return false;
      if([...display.resident].some(id=>jobs.has(id)&&jobs.get(id).status!=='done')){state.loadingPresentation='waiting-for-complete-window';return false;}
      if(epoch!==presentedEpoch){for(const entry of archiveObjects)entry.root.visible=display.resident.has(key(entry.tile));presentedEpoch=epoch;}
      state.loadingPresentation='complete-window';state.sourceArchiveWindow=JSON.stringify({center:display.center,resident:[...display.resident],scope:'original-offset-and-distance-branches;host-buffer-residency'});return true;
    }
  };return api;
}
