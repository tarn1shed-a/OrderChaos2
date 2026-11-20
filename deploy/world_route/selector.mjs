// One lazy selector on the existing ordinary-map motion. No renderer/ticker.
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function assertSameWorldFrame(legacy,value){
 if(!value?.sourceNative)throw Error('Actual own native body route required');
 for(const k of ['width','height','sourceMapId','bounds','spawn'])if(!same(legacy.world[k],value.world[k]))throw Error('Own and legacy map frames differ');
 for(const[x,y]of[[0,0],[legacy.world.width,legacy.world.height]])if(!same(legacy.point(x,y),value.point(x,y)))throw Error('Own and legacy source conversion differs');
}
export function createNineBodyMotionSelector({legacy,registry,readSourceMotion,isClosed=()=>false,onOwnerCount=()=>{}}){
 if(!legacy?.sourceNative||registry?.count!==45||typeof readSourceMotion!=='function')throw Error('Existing legacy native world and trusted body route required');
 const owners=new WeakMap();
 function selected(p){
  if(isClosed())throw Error('Closed source world route');
  const signature=JSON.stringify([p.id,p.profession,p.sourceAvatar]),old=owners.get(p);
  if(old){if(old.signature!==signature)throw Error('A live actor cannot change body or profession');return old.motion;}
  let value=legacy,key='legacy';
  if(Object.hasOwn(p,'sourceAvatar')){
   key=registry.check(p.sourceAvatar,p.profession).key;value=readSourceMotion(p).fork();
   assertSameWorldFrame(legacy,value);
  }
  owners.set(p,{signature,motion:value,key});onOwnerCount(1,key);return value;
 }
 const result={...legacy,
  place:p=>selected(p).place(p),restoreHeight:(p,h)=>selected(p).restoreHeight(p,h),
  move:(p,input,dt)=>selected(p).move(p,input,dt),jumpPressed:(p,pressed)=>selected(p).jumpPressed(p,pressed),
  forget(p){const owned=owners.get(p);if(!owned)return;try{return owned.motion.forget?.(p);}finally{owners.delete(p);onOwnerCount(-1,owned.key);}},
  readGatherPresentationContext(p){const owner=owners.get(p);if(!owner||owner.key!=='human-female'||owner.signature!==JSON.stringify([p.id,p.profession,p.sourceAvatar]))return null;return owner.motion.readGatherPresentationContext?.(p)??null;},
  fork:()=>createNineBodyMotionSelector({legacy:legacy.fork(),registry,readSourceMotion,isClosed,onOwnerCount}),
 };
 // The route, not a per-player fork, closes the two shared native domains.
 delete result.close;
 return Object.freeze(result);
}
