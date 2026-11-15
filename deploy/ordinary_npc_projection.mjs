// Original461 icon/math/material over the explicitly authorized compatible
// quest actor. Host visibility/session wiring is not original actor admission.
import {createOrdinaryNPCQuestMarkerReader} from './ordinary_npc_marker.mjs';
import {createNPC2079HeadMathBridge} from '/ordinary-npc-name-basis.mjs';
import {createSourceHeadTexture,createSourceNPCHeadQuad} from '/ordinary-npc-head-material.mjs';

export async function createOrdinaryNPCQuestProjection({THREE,actor,data,camera,scene,sceneOrigin,readHost,assets,bytes,text}={}){
  if(!(scene instanceof THREE.Scene)||typeof bytes!=='function'||typeof text!=='function'||
    assets?.format!=='oc2-ordinary-npc-quest-marker-assets-v1'||assets.questId!==461||assets.npcEntry!==2079)
    throw TypeError('Verified461 source assets and current host scene required');
  const reader=createOrdinaryNPCQuestMarkerReader({readHost}),headNode=new THREE.Object3D();
  const math=createNPC2079HeadMathBridge({THREE,actor,data,camera,headNode,sceneOrigin});
  const views=new Map(),pendingTextures=new Set();let live=null,disposed=false;
  try{
    const [vertexSource,fragmentSource]=await Promise.all([text(assets.vertexURL),text(assets.fragmentURL)]);
    for(const status of [6,4,9]){
      const row=assets.assets[status];if(!row?.pngURL||!row?.rgbaURL)throw Error('Source marker image route missing');
      const [png,rgba]=await Promise.all([bytes(row.pngURL),bytes(row.rgbaURL)]);
      const texture=await createSourceHeadTexture({THREE,status,png,rgba});
      pendingTextures.add(texture);
      const view=await createSourceNPCHeadQuad({THREE,status,texture,vertexSource,fragmentSource});
      pendingTextures.delete(texture);
      views.set(status,view);scene.add(view.mesh);
    }
  }catch(error){for(const view of views.values())view.dispose();for(const texture of pendingTextures)texture.dispose();math.dispose();reader.dispose();throw error;}
  const hide=()=>{for(const view of views.values())view.update({visible:false});};
  const current=receiver=>!disposed&&receiver===live;
  return Object.freeze({
    beginSession(){if(disposed)throw Error('NPC quest presentation released');hide();live=reader.beginSession();return live;},
    receiveState(receiver,value){if(!current(receiver))return false;const accepted=reader.receiveState(receiver,value);if(accepted)hide();return accepted;},
    receiveQuery(receiver,value){if(!current(receiver))return false;const accepted=reader.receiveQuery(receiver,value);if(!accepted)hide();return accepted;},
    update(){
      if(disposed||!live)return false;
      const selected=reader.inspect(live);hide();if(!selected.selected)return false;
      // Current Dummy_Name observation is an explicit web projection adapter.
      // It does not fabricate actor590 refresh events or any original flags.
      const sample=math.sample({offsetMode:'named-current'});
      views.get(selected.status).update({visible:true,sceneSubmitMatrix:sample.sceneSubmitMatrix});return true;
    },
    inspect(){const selected=live?reader.inspect(live):null;return {active:!disposed&&!!live,selected,
      visibleStatuses:[...views].filter(([,v])=>v.inspect().visible).map(([s])=>s),
      compatibilityProjection:true,originalActorQualification:false,originalCacheSchedule:false,taskApproved:false};},
    invalidate(){if(disposed)return;live=null;reader.invalidate();hide();},
    dispose(){if(disposed)return;live=null;reader.dispose();hide();for(const view of views.values())view.dispose();math.dispose();disposed=true;},
  });
}
