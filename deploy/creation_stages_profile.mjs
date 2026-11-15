// Delivery metadata only. A visible preview is not permission to create a role.
export const CREATION_STAGES_PROFILE='/assets/source-creation-stage/manifest-stages-v1.json';
export const CREATION_STAGES_PROFILE_V2='/assets/source-creation-stage/manifest-stages-v2.json';
export const CREATION_STAGES_PROFILES=[CREATION_STAGES_PROFILE_V2,CREATION_STAGES_PROFILE];
export const CREATION_STAGES_DELIVERY_FORMAT='oc2-source-creation-stages-delivery-v1';
export const STAGE_CONTRACT_URL='/assets/source-creation-stages/contract.json';
export const STAGE_CONTRACT_SHA256='26ad805cd6b9abb68026e30996b8344e100673b37fb41a230cc9f30e1017a8ba';
export const RACE_PROFILE='/assets/source-creation-stage/manifest-conditional-v1.json';
const safe=url=>typeof url==='string'&&/^\/assets\/source-[A-Za-z0-9_./-]+$/.test(url)&&!url.includes('..')&&!url.includes('//');
export function validateCreationStagesDelivery(p,{profileURL=null}={}){
 if(p?.format!==CREATION_STAGES_DELIVERY_FORMAT||p.mapId!==7||p.sourceSelectionRegion!==211||p.freshStartOnly!==true||
  p.createsPlayableRole!==false||p.wholeCreationRestored!==false||p.raceProfileURL!==RACE_PROFILE||
  p.contractURL!==STAGE_CONTRACT_URL||p.contractSHA256!==STAGE_CONTRACT_SHA256||
  !p.candidates||Array.isArray(p.candidates)||typeof p.candidates!=='object'||
  Object.keys(p.candidates).length<1||Object.keys(p.candidates).length>90||
  (p.actorVersion!==undefined&&p.actorVersion!==3))throw Error('Original stage delivery scope differs');
 if(profileURL!==null&&(!CREATION_STAGES_PROFILES.includes(profileURL)||
  (profileURL===CREATION_STAGES_PROFILE_V2?p.actorVersion!==3:p.actorVersion!==undefined)))
  throw Error('Original stage factory version differs');
 for(const [key,row]of Object.entries(p.candidates)){
  const parts=key.split(':');
  if(!/^[12]:[0-4]:[01]:[0-4]$/.test(key)||parts[1]==='4'&&parts[2]!=='0'||
   !safe(row?.baseURL)||!row.baseURL.endsWith('/')||!/^[-\w]+$/.test(row.sourceKey||''))
   throw Error('Original stage candidate route differs');
 }
 return p;
}
export function stageCandidateChoice(key){
 const [panel,race,gender,professionIndex]=key.split(':').map(Number);
 return {screen:panel===1?'CharacterChooseClass':'CharacterChoosePart',race,gender,professionIndex};
}
