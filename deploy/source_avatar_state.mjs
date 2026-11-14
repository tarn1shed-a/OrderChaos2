// Web persistence of an explicit original creation draft. This is not an
// original account record, spawn rule, initial gear or learned-skill grant.
const FORMAT='oc2-web-source-avatar-v1';
const keys=(value,names)=>value&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).sort().join(',')===[...names].sort().join(',');

export function sourceAvatar(value){
  if(!keys(value,['format','key','race','gender','sourceModelId','creationDisplayId','sourceProfileSHA256','appearance'])||
    value.format!==FORMAT||value.key!=='human-male'||value.race!==0||value.gender!==0||value.sourceModelId!==1||
    ![2053,2710,2055,2712,2054].includes(value.creationDisplayId)||
    typeof value.sourceProfileSHA256!=='string'||!/^[0-9a-f]{64}$/.test(value.sourceProfileSHA256)||
    !keys(value.appearance,['face','hair','beard','skinColor','hairColor'])||
    value.appearance.face!==0||value.appearance.beard!==0||![0,1].includes(value.appearance.hair)||
    !['skinColor','hairColor'].every(k=>Number.isSafeInteger(value.appearance[k])&&value.appearance[k]>=0&&value.appearance[k]<=0xffffffff))
    throw Error('Unverified explicit original avatar record');
  return {...value,appearance:{...value.appearance}};
}

export function sourceCharacterView(record,originalView){
  const result=originalView(record);
  if(Object.hasOwn(record,'sourceAvatar'))result.sourceAvatar=sourceAvatar(record.sourceAvatar);
  return result;
}

export function createSourceAvatarStore(OriginalStore){
  if(typeof OriginalStore!=='function')throw Error('Reviewed character store required');
  return class SourceAvatarStore extends OriginalStore{
    get sourceAvatarPersistence(){return true;}
    constructor(...args){
      super(...args);
      for(const record of this.records.values())if(Object.hasOwn(record,'sourceAvatar'))sourceAvatar(record.sourceAvatar);
    }
    resolveCharacter(name,id,token,profession,avatar){
      if(avatar===undefined)return super.resolveCharacter(name,id,token,profession);
      if(id!==undefined||token!==undefined||this._sourceCreating)throw Error('An existing avatar cannot be replaced');
      const checked=sourceAvatar(avatar),entries=[...this.records],dirty=this.dirty,savedAt=this.savedAt;
      this._sourceCreating={avatar:checked,existing:new Set(this.records.keys())};
      try{return super.resolveCharacter(name,id,token,profession);}
      catch(error){this.records.clear();for(const[k,v]of entries)this.records.set(k,v);this.dirty=dirty;this.savedAt=savedAt;throw error;}
      finally{this._sourceCreating=null;}
    }
    touch(record){
      // The reviewed base inserts a fresh record, calls touch, then flushes.
      // Attach the chosen draft before that FIRST atomic disk write.
      if(this._sourceCreating){
        if(this._sourceCreating.existing.has(record.id)||Object.hasOwn(record,'sourceAvatar'))throw Error('Cannot reinterpret a saved role');
        record.sourceAvatar=sourceAvatar(this._sourceCreating.avatar);
      }
      return super.touch(record);
    }
  };
}

export const SOURCE_AVATAR_FORMAT=FORMAT;
