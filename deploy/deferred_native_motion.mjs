// Defer an unused original map worker. The first map operation still executes
// its unchanged constructor; no frame, position or collision result is cached.
export function deferNativeMotion(load){
  if(typeof load!=='function')throw Error('Original native motion loader required');
  let value=null,closed=false,closing=null;
  function current(){
    if(closed)throw Error('Native motion owner closed');
    if(!value){const made=load();if(made?.sourceNative!==true)throw Error('Original native motion unavailable');value=made;}
    return value;
  }
  return new Proxy(Object.create(null),{get(_target,key){
    if(key==='then')return undefined;
    if(key==='sourceNative')return value?.sourceNative===true;
    if(key==='close')return()=>{if(!closed){closed=true;closing=value?.close?.()??Promise.resolve();}return closing;};
    const owner=current(),member=owner[key];return typeof member==='function'?member.bind(owner):member;
  }});
}
