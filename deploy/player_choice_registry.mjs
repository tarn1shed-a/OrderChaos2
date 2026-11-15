// Explicit original creation choices and web identity only. No initial gear,
// learned skills, original-server admission or combat capability is inferred.
const FORMAT='oc2-web-source-avatar-v1';
const MODELS=[[0,0,0,1,'human-male'],[0,1,0,32,'human-female'],[1,0,5,34,'mendel-male'],[1,1,5,31,'mendel-female'],
 [2,0,1,33,'elf-male'],[2,1,1,2,'elf-female'],[3,0,2,28,'orc-male'],[3,1,2,30,'orc-female'],[4,0,4,29,'kartan']];
const PROFESSIONS=[1,3,2,5,4],appearanceKeys=['face','hair','beard','skinColor','hairColor'];
const exact=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join(',')===[...keys].sort().join(',');
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
const uint=value=>Number.isSafeInteger(value)&&value>=0&&value<=0xffffffff;

export function createPlayerChoiceRegistry(profile){
 if(profile?.format!=='oc2-original-player-choice-registry-v1'||!digest(profile.sourceMatrixSHA256)||
   profile.originalAccountAdmissionKnown!==false||profile.initialEquipmentKnown!==false||profile.learnedSkillsKnown!==false||
   profile.bodies?.length!==9)throw Error('Pinned original player-choice registry required');
 const rows=new Map();
 for(const [index,expected]of MODELS.entries()){
  const row=profile.bodies[index],[uiRace,gender,race,model,key]=expected;
  if(row.uiRace!==uiRace||row.gender!==gender||row.race!==race||row.sourceModelId!==model||row.key!==key||
    row.choices?.length!==5||!digest(row.sourceProfileSHA256))throw Error('Original UI/body mapping differs');
  for(const [slot,choice]of row.choices.entries()){
   if(choice.profession!==PROFESSIONS[slot]||choice.professionIndex!==slot||!Number.isSafeInteger(choice.creationDisplayId)||choice.creationDisplayId<=0||
     !exact(choice.appearance,appearanceKeys)||!Object.values(choice.appearance).every(uint))throw Error('Exact original fresh choice required');
   const id=uiRace+':'+gender+':'+choice.profession;
   if(rows.has(id))throw Error('Duplicate original player choice');
   rows.set(id,Object.freeze({format:FORMAT,key,race,gender,sourceModelId:model,creationDisplayId:choice.creationDisplayId,
    sourceProfileSHA256:row.sourceProfileSHA256,appearance:Object.freeze({...choice.appearance})}));
  }
 }
 function draft(input){
  if(!exact(input,['race','gender','profession'])||![input.race,input.gender,input.profession].every(Number.isSafeInteger))throw Error('Explicit UI selection required');
  const value=rows.get(input.race+':'+input.gender+':'+input.profession);
  if(!value)throw Error('Original player combination unavailable');
  return structuredClone(value);
 }
 function check(value,profession){
  if(!exact(value,['format','key','race','gender','sourceModelId','creationDisplayId','sourceProfileSHA256','appearance'])||
    !exact(value.appearance,appearanceKeys)||!PROFESSIONS.includes(profession))throw Error('Original choice identity required');
  const row=MODELS.find(r=>r[4]===value.key);if(!row)throw Error('Unknown original body');
  const expected=draft({race:row[0],gender:row[1],profession});
  if(!same(value,expected)){
   // Object key order is irrelevant; every field and original integer is not.
   if(Object.entries(expected).some(([k,v])=>k==='appearance'?appearanceKeys.some(p=>value.appearance[p]!==v[p]):value[k]!==v))
    throw Error('Stored original choice does not match its profession');
  }
  return structuredClone(expected);
 }
 return Object.freeze({draft,check,count:rows.size,bodyKeys:Object.freeze(MODELS.map(r=>r[4])),
  originalAccountAdmissionKnown:false,initialEquipmentKnown:false,learnedSkillsKnown:false});
}

export function createPlayerChoiceStore(OriginalStore,registry){
 if(typeof OriginalStore!=='function'||OriginalStore.prototype.sourceChoiceEmptyInventory!==true||registry?.count!==45)throw Error('Reviewed empty-container store and complete original registry required');
 return class PlayerChoiceStore extends OriginalStore{
  get sourceAvatarPersistence(){return true;}
  constructor(...args){super(...args);for(const record of this.records.values())if(record.sourceAvatar)registry.check(record.sourceAvatar,record.profession);}
  resolveCharacter(name,id,token,profession,avatar){
   if(avatar===undefined)return super.resolveCharacter(name,id,token,profession);
   if(id!==undefined||token!==undefined||this._playerChoiceCreating)throw Error('An existing player choice cannot be replaced');
   const checked=registry.check(avatar,profession),before=[...this.records],dirty=this.dirty,savedAt=this.savedAt;
   this._playerChoiceCreating={avatar:checked,ids:new Set(this.records.keys())};
   try{return super.resolveCharacter(name,id,token,profession);}
   catch(error){this.records.clear();for(const[k,v]of before)this.records.set(k,v);this.dirty=dirty;this.savedAt=savedAt;throw error;}
   finally{this._playerChoiceCreating=null;}
  }
  touch(record){
   const creating=this._playerChoiceCreating;
   if(creating){
    if(creating.ids.has(record.id)||record.sourceAvatar)throw Error('Cannot reinterpret a saved player');
    record.sourceAvatar=registry.check(creating.avatar,record.profession);
    // Only this just-created record: no prototype training items are original
    // starter-gear evidence. Existing records and their inventory stay intact.
    record.inventory={};
    record.sourceInventoryPolicy='empty-compatible-container-v1';
   }
   return super.touch(record);
  }
 };
}

export function playerChoiceView(record,originalView,registry){
 const value=originalView(record);if(record.sourceAvatar)value.sourceAvatar=registry.check(record.sourceAvatar,record.profession);return value;
}
