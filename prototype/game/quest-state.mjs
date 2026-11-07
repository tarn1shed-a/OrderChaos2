import {emptyInteractionState,mergeInteractionState} from '../public/object-interaction-state.js';

// A client-state projection, not recovered quest scripts or an original-network
// decoder. Only trusted server adapters may update these flags; no socket action
// accepts them. Source catalog entries never create an accepted quest/reward.
export class QuestState {
  constructor(profile){
    this.objects=new Map(profile.objects.map(o=>[o.id,{id:o.id,spawnId:o.spawnId,entry:o.entry,revision:0,state:emptyInteractionState()}]));
    this.recipients=new Map();
  }
  applySourceState(characterId,id,patch){
    if(typeof characterId!=='string'||!characterId)throw new Error('Missing state recipient');
    const base=this.objects.get(id);if(!base)throw new Error('Unknown source object');
    const objects=this.recipients.get(characterId)||new Map(),object=objects.get(id)||structuredClone(base);
    const state=mergeInteractionState(object.state,patch);
    if(JSON.stringify(state)!==JSON.stringify(object.state)){object.state=state;object.revision++;}
    objects.set(id,object);this.recipients.set(characterId,objects);
  }
  snapshot(characterId){const own=this.recipients.get(characterId);return {mode:'source-reference',active:[],objects:structuredClone([...this.objects].map(([id,base])=>own?.get(id)||base))};}
}
