// Native-backed panel/display selection. No account, role, inventory or skill
// permission is granted here; actual material/geometry construction is supplied
// by the stage-specific factory, never by a reused race costume.
export const CLASS_PART_CONTRACT='oc2-original-creation-class-part-contract-v1';
export const CLASS_PART_CANDIDATE='oc2-creation-class-part-candidate-v1';
export const MATRIX_SHA256='ec94d7fc08d20c436bec662efe8e6b37f834cb665d635e682d107e55a6ca32bc';
export const NATIVE_SHA256='77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4';
const screens=Object.freeze({CharacterChooseRace:{panel:0,group:3},CharacterChooseClass:{panel:1,group:3},CharacterChoosePart:{panel:2,group:2}});
const professions=Object.freeze([1,3,2,5,4]);
const body=(r,g)=>Number.isInteger(r)&&r>=0&&r<=4&&Number.isInteger(g)&&g>=0&&g<=1&&!(r===4&&g===1);
const equivalent=(a,b)=>{
 if(a===b)return true;
 if(!a||!b||typeof a!=='object'||typeof b!=='object'||Array.isArray(a)!==Array.isArray(b))return false;
 const keys=Object.keys(a).sort(),other=Object.keys(b).sort();
 return keys.length===other.length&&keys.every((key,i)=>key===other[i]&&equivalent(a[key],b[key]));
};
export function stageResourceURL(baseURL,path,documentURL=globalThis.location?.href){
 const base=new URL(baseURL,documentURL);
 if(!base.pathname.endsWith('/')||base.search||base.hash||typeof path!=='string'||!/^\/?[A-Za-z0-9_./-]+$/.test(path)||path.includes('..')||path.includes('//'))throw Error('Unsafe original stage resource path');
 const value=new URL(path.replace(/^\//,''),base);
 if(value.origin!==base.origin||!value.pathname.startsWith(base.pathname))throw Error('Original stage resource escaped its namespace');
 return value.href;
}
export function checkedStageContract(contract){
 if(contract?.format!==CLASS_PART_CONTRACT||contract.nativeSHA256!==NATIVE_SHA256||contract.sourceMatrixSHA256!==MATRIX_SHA256||
  JSON.stringify(contract.panelTable)!=='[3,3,2,2,0,0,1,0]'||contract.identityCases?.length!==45||
  contract.scope?.originalCameraCPUExecuted!==true||contract.scope.originalGPUObserved!==false||contract.scope.classOrPartHostReady!==false)
  throw Error('Original Class/Part source contract differs');
 const unique=new Set();
 for(const row of contract.identityCases){
  const key=`${row.uiRace}:${row.gender}:${row.uiProfessionIndex}`;
  if(!body(row.uiRace,row.gender)||!Number.isInteger(row.uiProfessionIndex)||professions[row.uiProfessionIndex]!==row.profession||unique.has(key)||
   row.classRequest?.arg2!==1||row.classRequest.arg3!==1||row.partRequest?.arg2!==0||row.partRequest.arg3!==0||
   !Number.isInteger(row.classRequest.displayId)||!Number.isInteger(row.partRequest.displayId)||!row.classSourceModel?.ModelPath||!row.partSourceModel?.ModelPath)
   throw Error('Original Class/Part display identity differs');
  unique.add(key);
 }
 return contract;
}
export function selectStageIdentity(contract,{screen,race,gender,professionIndex}){
 checkedStageContract(contract);
 const stage=screens[screen];
 if(!stage||!body(race,gender)||!Number.isInteger(professionIndex)||!Object.hasOwn(professions,professionIndex))throw Error('Original reachable creation choice required');
 const row=contract.identityCases.find(r=>r.uiRace===race&&r.gender===gender&&r.uiProfessionIndex===professionIndex);
 if(!row)throw Error('Original source display choice absent');
 const request=stage.panel===0?row.raceRequest:stage.panel===1?row.classRequest:row.partRequest;
 const model=stage.panel===1?row.classSourceModel:row.partSourceModel;
 return Object.freeze({screen,panel:stage.panel,cameraGroup:stage.group,race,gender,professionIndex,profession:row.profession,
  request:Object.freeze({...request}),sourceModel:Object.freeze({...model}),
  freshAppearance:stage.panel===2?Object.freeze({...row.partFreshAppearance}):null,
  sourceMatrixSHA256:MATRIX_SHA256,createsPlayableRole:false,grantsEquipment:false,writesCharacter:false});
}
export function checkedStageCandidate(manifest,identity){
 if(identity.panel===0)throw Error('Stage0 retains its frozen original race factory');
 if(manifest?.format!==CLASS_PART_CANDIDATE||manifest.screen!==identity.screen||manifest.panel!==identity.panel||
  manifest.cameraGroup!==identity.cameraGroup||manifest.race!==identity.race||manifest.gender!==identity.gender||
  manifest.professionIndex!==identity.professionIndex||manifest.profession!==identity.profession||
  manifest.sourceMatrixSHA256!==MATRIX_SHA256||!equivalent(manifest.sourceRequest,identity.request)||
  !equivalent(manifest.sourceModel,identity.sourceModel)||manifest.createdRole!==false||manifest.grantsEquipment!==false||manifest.writesCharacter!==false)
  throw Error('Stage-specific original display/model scope differs');
 return manifest;
}
export function createStageSwitch({contract,track,scene,construct,applyTransform}){
 checkedStageContract(contract);
 if(typeof track?.select!=='function'||typeof scene?.add!=='function'||typeof construct!=='function'||typeof applyTransform!=='function')throw Error('Existing source scene/camera and actual actor factory required');
 let serial=0,current=null,disposed=false;
 const remove=()=>{if(current){current.root.visible=false;current.dispose();current=null;}};
 return {
  async show(choice){
   if(disposed)throw Error('Original stage switch disposed');
   const identity=selectStageIdentity(contract,choice),token=++serial;
   // Original 6fed70 performs panel camera selection before display update.
   // Same group early-return is owned by the original camera-track consumer.
   track.select(identity.cameraGroup,identity.race);
   remove();
   const next=await construct(identity);
   if(token!==serial||disposed){next?.dispose();return {status:'superseded',identity};}
   if(!next)return {status:'scene-only',identity};
   try{
    checkedStageCandidate(next.manifest,identity);
    if(!next.root||typeof next.dispose!=='function')throw Error('Completed source actor object absent');
    applyTransform(next.root,identity);next.root.visible=true;scene.add(next.root);current=next;
    return {status:'host-constructed',identity,actor:next,originalGPUObserved:false};
   }catch(error){next?.dispose();throw error;}
  },
  hide(){serial++;remove();},
  update(delta){current?.update(delta);},
  dispose(){serial++;remove();disposed=true;},
 };
}
