// One shared policy core. New source metadata and typed armor are validators,
// not additional actor/renderer implementations or original ready callbacks.
import {createPinnedCreationStageAdapters} from './stage_adapter_core_v1.mjs';
import {createTypedArmorRootValidator} from './typed_armor_root.mjs';
import {same,checkArmorRoot} from './contracts.mjs';
const POLICIES=Object.freeze([
 'bca0b324a56c3e7c577b6b0b63761f4b4ec6efb66e50c1dd4ca1a626aeefdac4',
 '14d1d8cae37a6e5c44b87886bf1ddf097ce2e48a7a7b091db80111f6564437c7',
 'b9f37f0daa2f8f1003b87c2540913cdbcf1201fb37b910aff3b2dc8b99631dcf',
 '42a91ea4d87ee43b8c214941a2b43fb34680374f9599bc2939405b1a11f9ee8b',
 '956439b5be45a3363b9565a6e9f96c7015f203c04eef518810c9463bfe734bb5',
 '18bc40dc0eceb0bba6446795e748b1f6172b6a9b89263bede8d22c8cb83fe252',
 '58dbb1056fb6ea2fb1dcdd2f4317946b2aa74b241afcf4bff58c94f011b7fc4d',
]);
export async function createCreationStageAdapters({policyBytes,registryBytes,crypto}){
 if(!(policyBytes instanceof Uint8Array)||!crypto?.subtle)throw Error('Exact original source policy bytes required');
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',policyBytes)),v=>v.toString(16).padStart(2,'0')).join('');
 if(!POLICIES.includes(digest))throw Error('Source policy outside the frozen body registry');
 const policy=JSON.parse(new TextDecoder().decode(policyBytes));
 const base=await createPinnedCreationStageAdapters({policyBytes,registryBytes,crypto,policySHA256:digest});
 const armor=await createTypedArmorRootValidator({registryBytes,crypto});let live=true;
 const ensure=()=>{if(!live)throw Error('Source adapters disposed');};
 return Object.freeze({
  validateStageModel(manifest,data,identity){
   ensure();const result=base.validateStageModel(manifest,data,identity);
   if(identity.race===policy.race&&identity.gender===policy.gender){
    const row=policy.choices.find(r=>r.identity.displayId===identity.request.displayId);
    if(!same(manifest.sourceCatalogCoverage??null,row?.requiredCatalogCoverage??null)||!same(data.sourceCatalogCoverage??null,row?.requiredCatalogCoverage??null))
     throw Error('Original non-catalog body visibility contract differs');
   }
   return result;
  },
  samplerAddressResolver(...args){ensure();return base.samplerAddressResolver(...args);},
  armorRootValidator(row,source,identity){
   ensure();return row.mount?.format==='oc2-source-typed-rigid-armor-root-v1'?armor.validate(row,source,identity):checkArmorRoot(row,source,identity);
  },
  inspect(){ensure();return {...base.inspect(),typedArmorRootValidator:true};},
  dispose(){if(live){live=false;armor.dispose();base.dispose();}},
 });
}
