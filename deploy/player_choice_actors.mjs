// Browser actor ownership and asynchronous body dispatch only. Original body
// factories own their geometry, appearance checks and native pose consumption.
const MODELS={
 'human-male':[0,0,1],'human-female':[0,1,32],
 'mendel-male':[5,0,34],'mendel-female':[5,1,31],
 'elf-male':[1,0,33],'elf-female':[1,1,2],
 'orc-male':[2,0,28],'orc-female':[2,1,30],kartan:[4,0,29],
};
const stable=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
function selected(record){
 if(typeof record?.id!=='string'||!record.id||!Number.isSafeInteger(record.profession)||record.profession<1||record.profession>5)throw Error('Authenticated character identity required');
 const avatar=record.sourceAvatar;
 if(avatar===undefined){
  if(record.appearance&&(record.appearance.race!==2||record.appearance.gender!==1))throw Error('Legacy actor body is unavailable');
  return null;
 }
 const p=typeof avatar?.key==='string'&&Object.hasOwn(MODELS,avatar.key)?MODELS[avatar.key]:null;
 if(!p||avatar.format!=='oc2-web-source-avatar-v1'||avatar.race!==p[0]||avatar.gender!==p[1]||avatar.sourceModelId!==p[2])throw Error('Original selected body mapping differs');
 return avatar.key;
}

export function createPlayerChoiceActors({bodyKeys,loadBody,createLegacy}={}){
 if(!Array.isArray(bodyKeys)||new Set(bodyKeys).size!==bodyKeys.length||bodyKeys.some(k=>typeof k!=='string'||!Object.hasOwn(MODELS,k))||typeof loadBody!=='function'||typeof createLegacy!=='function')throw Error('Explicit body providers and legacy actor factory required');
 const allowed=new Set(bodyKeys),factories=new Map(),owners=new WeakMap();
 function supports(record){try{const key=selected(record);return key===null||allowed.has(key);}catch{return false;}}
 function factory(key){
  if(!factories.has(key)){
   const pending=Promise.resolve().then(()=>loadBody(key)).then(create=>{
    if(typeof create!=='function')throw Error('Original body factory did not load');return create;
   }).catch(error=>{if(factories.get(key)===pending)factories.delete(key);throw error;});
   factories.set(key,pending);
  }
  return factories.get(key);
 }
 return {supports,bodyKeys:Object.freeze([...bodyKeys]),async create(record,{current=()=>true}={}){
  if(typeof current!=='function')throw Error('Actor lifecycle predicate required');
  const snapshot=structuredClone(record),key=selected(snapshot);
  if(key!==null&&!allowed.has(key))throw Error('Selected original body is not admitted');
  if(!current())return null;
  const create=key===null?createLegacy:await factory(key);
  if(!current())return null;
  const view=await create(snapshot);
  const body=view?.body;
  // A bad provider must never dispose a body already owned by another actor.
  if(body&&typeof body==='object'&&owners.has(body))throw Error('An original body cannot be shared by two actors');
  let live;
  try{
   if(!body||typeof body!=='object'||typeof view.apply!=='function'||typeof view.dispose!=='function')throw Error('Complete independent actor interface required');
   live=current();
  }catch(error){
   if(typeof view?.dispose==='function'){
    try{view.dispose();}catch(cleanup){throw new AggregateError([error,cleanup],'Actor construction and cleanup failed');}
   }
   throw error;
  }
  let disposed=false;
  if(!live){view.dispose();return null;}
  const stamp=stable([snapshot.id,snapshot.profession,snapshot.sourceAvatar??null]);
  const actor={body,source:key!==null,key,
   apply(next,...args){
    if(disposed||stable([next?.id,next?.profession,next?.sourceAvatar??null])!==stamp)throw Error('Actor identity changed while its body was loaded');
    return view.apply(next,...args);
   },
   tick(...args){if(!disposed)return view.tick?.(...args);},
   inspect:()=>({id:snapshot.id,profession:snapshot.profession,key,source:key!==null,disposed,body:view.inspect?.()??null}),
   dispose(){if(disposed)return;disposed=true;owners.delete(body);view.dispose();},
  };
  owners.set(body,actor);return actor;
 }};
}
