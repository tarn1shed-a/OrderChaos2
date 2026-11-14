// Proposed read-only projection of an original-client cache snapshot.
// No DOM, storage, requests, defaults, learning or cast authorization.
const integer=v=>Number.isInteger(v);
export function projectSourceEquipped(role,catalog,snapshot=null){
 if(!snapshot)return{known:false,reason:'source-cache-unknown',slots:null,secondarySlots:null};
 if(snapshot.roleId!==role.id||snapshot.profession!==role.profession)return{known:false,reason:'source-role-or-profession-mismatch',slots:null,secondarySlots:null};
 if(snapshot.format!=='oc2-original-equipped-cache-v1')throw Error('Original equipped cache format differs');
 const bank=snapshot.operationBank;
 if(!integer(bank)||bank<0||bank>4)return{known:false,reason:'operation-bank-unknown',skillPageRaw:snapshot.skillPage,slots:null,secondarySlots:null};
 if(!Array.isArray(catalog)||catalog.some(s=>s.profession!==role.profession)||new Set(catalog.map(s=>s.skillId)).size!==catalog.length)throw Error('Profession catalog differs');
 const banks=snapshot.operationBanks,second=snapshot.actorSlots11To20;
 if(!Array.isArray(banks)||banks.length!==5||banks.some(a=>!Array.isArray(a)||a.length!==5||a.some(v=>!integer(v)||v< -2147483648||v>2147483647))||!Array.isArray(second)||second.length!==10||second.some(v=>!integer(v)||v<0||v>0xffffffff))throw Error('Original cache slot arrays differ');
 const learned=snapshot.learningRecords,learningKnown=Array.isArray(learned),learning=new Map();
 if(learned!=null&&!learningKnown)throw Error('Original learning snapshot differs');
 for(const pair of learned||[]){if(!Array.isArray(pair)||pair.length!==2||!integer(pair[0])||pair[0]<0||pair[0]>0xffffffff||!integer(pair[1])||pair[1]<0||pair[1]>3)throw Error('Original learning record differs');if(!learning.has(pair[0]))learning.set(pair[0],new Set());learning.get(pair[0]).add(pair[1]);}
 const runes=new Map();
 for(const pair of snapshot.selectedRunes||[]){if(!Array.isArray(pair)||pair.length!==2||!integer(pair[0])||!integer(pair[1])||pair[1]<0||pair[1]>255)throw Error('Original selected rune differs');runes.set(pair[0],pair[1]);}
 const entries=new Map(catalog.map(s=>[s.skillId,s]));
 function slot(rawSkillId,sourceSlot){
  if(rawSkillId===0)return{sourceSlot,rawSkillId,state:'empty'};
  if(rawSkillId===-1)return{sourceSlot,rawSkillId,state:'basic-attack-sentinel',resolvedAttackId:null};
  const row=entries.get(rawSkillId),runeIndex=runes.get(rawSkillId)??null,rune=row?.runes?.find(r=>r.index===runeIndex);
  return{sourceSlot,rawSkillId,state:'equipped-cache-value',catalogKnown:Boolean(row),catalogKind:row?.kind??null,
   selectedRuneIndex:runeIndex,runeInCatalog:Boolean(rune),sourceRuneId:rune?.sourceRuneId??null,
   baseLearned:learningKnown?Boolean(learning.get(rawSkillId)?.has(0)):null,
   selectedRuneLearned:learningKnown&&runeIndex!==null?Boolean(learning.get(rawSkillId)?.has(runeIndex)):null,
   reason:!row?'outside-profession-catalog':!learningKnown?'learning-unknown':!learning.get(rawSkillId)?.has(0)?'base-not-learned':!rune?'selected-rune-unknown':'separate-equipment-and-learning-evidence',
   castPermission:null};
 }
 return{known:true,roleId:role.id,profession:role.profession,operationBank:bank,skillPageRaw:snapshot.skillPage,
  slots:banks[bank].map((v,i)=>slot(v,i+1)),secondarySlots:second.map((v,i)=>slot(v,i+11)),
  learningKnown,fixture:snapshot.fixture===true,scope:'Source cache values only. No page-to-bank equivalence, default equipment, icon fill or cast eligibility.'};
}
