// Delivery metadata only. A visible preview is not permission to create a role.
export const CREATION_STAGES_PROFILE='/assets/source-creation-stage/manifest-stages-v1.json';
export const CREATION_STAGES_PROFILE_V2='/assets/source-creation-stage/manifest-stages-v2.json';
export const CREATION_STAGES_PROFILE_V3='/assets/source-creation-stage/manifest-stages-v3.json';
export const CREATION_STAGES_PROFILE_V4='/assets/source-creation-stage/manifest-stages-v4.json';
export const CREATION_STAGES_PROFILES=[CREATION_STAGES_PROFILE_V4,CREATION_STAGES_PROFILE_V3,CREATION_STAGES_PROFILE_V2,CREATION_STAGES_PROFILE];
export const SHARED_STAGE_POLICY='/assets/source-creation-shared-v1/policy.json';
export const SHARED_STAGE_REGISTRY='/assets/source-creation-shared-v1/capabilities.json';
export const SHARED_POLICY_SHA='bca0b324a56c3e7c577b6b0b63761f4b4ec6efb66e50c1dd4ca1a626aeefdac4';
export const SHARED_REGISTRY_SHA='337c79ea6501456014771e94222648257f676464e261e33cb367853a5fdabc60';
export const SHARED_BODY_POLICIES=Object.freeze({
 '0:0':'20ac2edc9eb0e4a232372cfd52d289d73341419efc6b63081384546d848d38c7',
 '0:1':SHARED_POLICY_SHA,
 '1:0':'14d1d8cae37a6e5c44b87886bf1ddf097ce2e48a7a7b091db80111f6564437c7',
 '1:1':'b9f37f0daa2f8f1003b87c2540913cdbcf1201fb37b910aff3b2dc8b99631dcf',
 '2:0':'42a91ea4d87ee43b8c214941a2b43fb34680374f9599bc2939405b1a11f9ee8b',
 '2:1':'61b34eb5730a4363ed2213edd7b47808dd323acc5fa78b99f35f3dd9d6122d76',
 '3:0':'956439b5be45a3363b9565a6e9f96c7015f203c04eef518810c9463bfe734bb5',
 '3:1':'18bc40dc0eceb0bba6446795e748b1f6172b6a9b89263bede8d22c8cb83fe252',
 '4:0':'58dbb1056fb6ea2fb1dcdd2f4317946b2aa74b241afcf4bff58c94f011b7fc4d',
});
export const sharedBodyPolicyURL=key=>'/assets/source-creation-shared-v2/policies/'+key.replace(':','-')+'.json';
const LEGACY_STAGE_KEYS=new Set(['1:0:0:0','1:0:0:1','1:2:1:1','1:2:1:4','2:0:0:0','2:0:0:1']);
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
  (profileURL!==CREATION_STAGES_PROFILE?p.actorVersion!==3:p.actorVersion!==undefined)))
  throw Error('Original stage factory version differs');
 const shared=p.sharedGeometry,batch=shared?.version===2;
 if(batch){
  if(profileURL!==null&&profileURL!==CREATION_STAGES_PROFILE_V4||p.actorVersion!==3||
   shared.registryURL!==SHARED_STAGE_REGISTRY||shared.registrySHA256!==SHARED_REGISTRY_SHA||
   shared.fullClassQueueRestored!==false||shared.initialSourceIdleOnly!==true||
   Object.keys(shared.bodies||{}).sort().join(',')!==Object.keys(SHARED_BODY_POLICIES).sort().join(',')||
   Object.entries(SHARED_BODY_POLICIES).some(([key,hash])=>shared.bodies[key].policyURL!==sharedBodyPolicyURL(key)||shared.bodies[key].policySHA256!==hash))
   throw Error('Original source body batch policy differs');
 }
 else if(shared!==undefined){
  if(profileURL!==null&&profileURL!==CREATION_STAGES_PROFILE_V3||p.actorVersion!==3||shared.version!==1||
   shared.policyURL!==SHARED_STAGE_POLICY||shared.registryURL!==SHARED_STAGE_REGISTRY||
   shared.policySHA256!==SHARED_POLICY_SHA||shared.registrySHA256!==SHARED_REGISTRY_SHA||
   shared.fullClassQueueRestored!==false||shared.initialSourceIdleOnly!==true)
    throw Error('Original shared geometry policy differs');
 }else if([CREATION_STAGES_PROFILE_V3,CREATION_STAGES_PROFILE_V4].includes(profileURL))throw Error('Original shared geometry policy absent');
 if(profileURL===CREATION_STAGES_PROFILE_V4&&!batch)throw Error('Original source body batch policy absent');
 for(const [key,row]of Object.entries(p.candidates)){
  const parts=key.split(':');
  if(!/^[12]:[0-4]:[01]:[0-4]$/.test(key)||parts[1]==='4'&&parts[2]!=='0'||
   !safe(row?.baseURL)||!row.baseURL.endsWith('/')||!/^[-\w]+$/.test(row.sourceKey||''))
   throw Error('Original stage candidate route differs');
  if(row.provider!==undefined&&!(row.provider==='shared-source-geometry-v1'&&shared&&/^[12]:0:1:[0-4]$/.test(key))&&
   !(row.provider==='shared-source-geometry-v2'&&batch))
   throw Error('Unproved shared source stage route');
 }
 if(shared&&!batch&&Object.entries(p.candidates).filter(([k,r])=>k.startsWith('1:')&&r.provider==='shared-source-geometry-v1').map(([k])=>k).sort().join(',')!==
  '1:0:1:0,1:0:1:1,1:0:1:2,1:0:1:3,1:0:1:4')throw Error('Original five source stage routes incomplete');
 const part=Object.entries(p.candidates).filter(([k,r])=>k.startsWith('2:')&&r.provider==='shared-source-geometry-v1').map(([k])=>k).sort();
 if(part.length&&part.join(',')!=='2:0:1:0,2:0:1:1,2:0:1:2,2:0:1:3,2:0:1:4')throw Error('Original five source Part routes incomplete');
 if(batch){
  const keys=Object.keys(SHARED_BODY_POLICIES).flatMap(body=>[1,2].flatMap(panel=>[0,1,2,3,4].map(index=>`${panel}:${body}:${index}`))).sort();
  if(Object.keys(p.candidates).sort().join(',')!==keys.join(','))throw Error('Original ninety source stage routes incomplete');
  for(const [key,row]of Object.entries(p.candidates)){
   const expected=LEGACY_STAGE_KEYS.has(key)?undefined:/^[12]:0:1:[0-4]$/.test(key)?'shared-source-geometry-v1':'shared-source-geometry-v2';
   if(row.provider!==expected)throw Error('Original source route provider differs');
  }
 }
 return p;
}
export function stageCandidateChoice(key){
 const [panel,race,gender,professionIndex]=key.split(':').map(Number);
 return {screen:panel===1?'CharacterChooseClass':'CharacterChoosePart',race,gender,professionIndex};
}
