// Route own source policies into the existing shared validators. No actor,
// animation arithmetic, source-ready callback or played-world permission.
import {createCreationStageAdapters} from './stage_adapters_all_v1.mjs';
import {checkedStageModel} from '../creation_class_stage/actor_v6.mjs';
import {same,sourceWrap,checkArmorRoot} from './contracts.mjs';

export async function createStageBatchGuard({policies,registryBytes,crypto}){
 const guards=new Map();let live=true;
 try{
  for(const [key,bytes]of Object.entries(policies)){
   const own=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
   if(key!==`${own.race}:${own.gender}`||guards.has(key))throw Error('Own stage body policy identity differs');
   const adapter=await createCreationStageAdapters({policyBytes:bytes,registryBytes,crypto});
   guards.set(key,{own,adapter});
  }
 }catch(error){for(const g of guards.values())g.adapter.dispose();throw error;}
 function forIdentity(identity){
  if(!live)throw Error('Source stage batch guard disposed');
  const g=guards.get(`${identity.race}:${identity.gender}`);
  if(!g)throw Error('Own source body policy absent');
  return g;
 }
 const api=Object.freeze({
  forIdentity(identity){
   const {own,adapter}=forIdentity(identity);
   const validate=(manifest,data,current)=>{
    if(forIdentity(current).adapter!==adapter)throw Error('Source body changed during construction');
    if(current.panel===1)return adapter.validateStageModel(manifest,data,current);
    checkedStageModel(manifest,data,current);
    if(current.panel!==2||!same(data.rig.nodes,own.bodyLiteralRigNodes)||manifest.modelEffects.length||
     manifest.appearanceComplete!==true||manifest.sourceIndependentEffectGate!=null||
     manifest.attachments.some(r=>r.kind!==undefined)||
     [...manifest.materials,...manifest.attachments.flatMap(r=>r.materials)].some(r=>Object.values(r.addressing).some(a=>
      a.addressU===4||a.addressV===4||a.sourceTypedMirrorProof||a.sourcePostTextureOverrideProof)))
     throw Error('Unproved special source Part recipe');
    return manifest;
   };
   return Object.freeze({checkedStageModel:validate,
    samplerAddressResolver:identity.panel===2?sourceWrap:adapter.samplerAddressResolver,
    armorRootValidator:identity.panel===2?checkArmorRoot:adapter.armorRootValidator});
  },
  checkedStageModel(manifest,data,identity){return api.forIdentity(identity).checkedStageModel(manifest,data,identity);},
  dispose(){if(!live)return;live=false;for(const g of guards.values())g.adapter.dispose();guards.clear();},
 });
 return api;
}
