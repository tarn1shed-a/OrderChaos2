// Data-only extension of the existing shared policy/typed capability adapters.
// One geometry core and one source-policy core; no new actor/renderer/math.
import {createCreationStageAdapters as existing} from './stage_adapters_v5.mjs';
import {createPinnedCreationStageAdapters} from './stage_adapter_core_v1.mjs';
import {createTypedArmorRootValidator} from './typed_armor_root.mjs';
import {checkArmorRoot} from './contracts.mjs';
const ADDITIONS=Object.freeze([
 '20ac2edc9eb0e4a232372cfd52d289d73341419efc6b63081384546d848d38c7',
 '61b34eb5730a4363ed2213edd7b47808dd323acc5fa78b99f35f3dd9d6122d76',
]);
export async function createCreationStageAdapters(args){
 const {policyBytes,registryBytes,crypto}=args;
 if(!(policyBytes instanceof Uint8Array)||!crypto?.subtle)throw Error('Exact source policy bytes required');
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',policyBytes)),v=>v.toString(16).padStart(2,'0')).join('');
 if(!ADDITIONS.includes(digest))return existing(args);
 const base=await createPinnedCreationStageAdapters({...args,policySHA256:digest});
 const armor=await createTypedArmorRootValidator({registryBytes,crypto});
 return Object.freeze({...base,
  validateStageModel(manifest,data,identity){
   const result=base.validateStageModel(manifest,data,identity);
   if(manifest.sourceCatalogCoverage!=null||data.sourceCatalogCoverage!=null)throw Error('No non-catalog body exception belongs to these exact source bodies');
   return result;
  },
  armorRootValidator(row,source,identity){base.inspect();return row.mount?.format==='oc2-source-typed-rigid-armor-root-v1'?armor.validate(row,source,identity):checkArmorRoot(row,source,identity);},
  dispose(){armor.dispose();base.dispose();},
 });
}
