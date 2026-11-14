// Original fresh stage2 UI choices -> explicit web avatar metadata only.
// Display clothing, initial inventory, skills and spawn are not inferred here.
import {sourceAvatar,SOURCE_AVATAR_FORMAT} from './source_avatar_state.mjs';
const professions=[1,3,2,5,4];
export function createSourceAvatarDraft(manifest,sha256){
  const d=manifest?.sourceHumanCreationDraft;
  if(manifest?.format!=='oc2-human-male-original-creation-draft-v1'||manifest.race!==0||manifest.gender!==0||
    manifest.sourceModelId!==1||d?.sourceBodyModelId!==1||d.requiresExplicitDraftSelection!==true||
    d.originalServerDefaultAppearanceKnown!==false||d.originalServerInitialEquipmentKnown!==false||
    typeof sha256!=='string'||!/^[0-9a-f]{64}$/.test(sha256)||d.variants?.length!==5||
    d.variants.some((r,i)=>r.professionIndex!==i||r.sourceBodyModelId!==1||r.sourceClothingGranted!==false||
      !r.sourceEquipment||typeof r.sourceEquipment!=='object'||Array.isArray(r.sourceEquipment)||Object.keys(r.sourceEquipment).length))
    throw Error('Pinned original fresh creation draft required');
  const choices=d.variants.map(r=>sourceAvatar({format:SOURCE_AVATAR_FORMAT,key:'human-male',race:0,gender:0,
    sourceModelId:1,creationDisplayId:r.draft.displayId,sourceProfileSHA256:sha256,
    appearance:{face:r.draft.face,hair:r.draft.hair,beard:r.draft.beard,skinColor:r.draft.skinColorWord,hairColor:r.draft.hairColorWord}}));
  return input=>{
    if(input?.race!==0||input?.gender!==0)return null;
    const index=professions.indexOf(input.profession);
    if(index<0)throw Error('Original profession selection unavailable');
    return sourceAvatar(choices[index]);
  };
}
