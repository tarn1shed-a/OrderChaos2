// Cache only public static bytes by verified content hash. No saves, API or sockets.
const BLOBS='oc2-public-bytes-v1',META='oc2-public-index-v1';
const indexes=new Map(),bindings=new Map(),pending=new Map(),bindingTasks=new Map();
const key=(kind,value)=>new URL('/__delivery/'+kind+'/'+value,self.location.origin).href;
const jsonResponse=value=>new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});
self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
async function fetchIndex(id){
  const response=await fetch('/__delivery/index.json',{cache:'no-store'});
  if(!response.ok)throw Error('Delivery index unavailable');
  const index=await response.json();if(index.format!=='oc2-delivery-v1')throw Error('Unknown delivery index');
  indexes.set(index.revision,index);bindings.set(id,index.revision);
  try{const cache=await caches.open(META);await cache.put(key('index',index.revision),jsonResponse(index));await cache.put(key('client',id),jsonResponse({revision:index.revision}));}catch{}
  return index;
}
function bind(id){
  if(!bindingTasks.has(id)){const task=fetchIndex(id);bindingTasks.set(id,task);task.finally(()=>bindingTasks.delete(id)).catch(()=>{});}
  return bindingTasks.get(id);
}
async function forClient(id){
  let revision=bindings.get(id);
  if(!revision){try{const cache=await caches.open(META),saved=await cache.match(key('client',id));if(saved){revision=(await saved.json()).revision;bindings.set(id,revision);}}catch{}}
  if(revision){if(indexes.has(revision))return indexes.get(revision);try{const saved=await(await caches.open(META)).match(key('index',revision));if(saved){const index=await saved.json();indexes.set(revision,index);return index;}}catch{}}
  return bind(id);
}
async function resource(url,meta){
  const identity=meta.sha256+'-'+meta.type.replace(/\W/g,'_'),cacheKey=key('content',identity);let cache,saved;
  try{cache=await caches.open(BLOBS);saved=await cache.match(cacheKey);}catch{}
  if(saved&&saved.headers.get('X-OC2-Content-SHA256')===meta.sha256)return saved;
  if(!pending.has(identity)){
    const task=(async()=>{
      const response=await fetch(url,{cache:'no-cache',credentials:'same-origin'});
      if(!response.ok)throw Error('Static download failed: '+response.status);
      const body=await response.arrayBuffer(),digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',body)),v=>v.toString(16).padStart(2,'0')).join('');
      if(body.byteLength!==meta.bytes||digest!==meta.sha256)throw Error('Static content checksum differs');
      const verified=new Response(body,{headers:{'Content-Type':meta.type,'Cache-Control':'public, max-age=0, must-revalidate','X-OC2-Content-SHA256':meta.sha256}});
      try{if(cache)await cache.put(cacheKey,verified.clone());}catch{/* A full/unavailable browser cache never blocks gameplay. */}
      return verified;
    })();
    pending.set(identity,task);task.finally(()=>pending.delete(identity)).catch(()=>{});
  }
  return (await pending.get(identity)).clone();
}
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=='GET'||url.origin!==self.location.origin||event.request.mode==='navigate'||url.pathname.endsWith('.html')||url.pathname.startsWith('/__delivery/')||['/health','/ws'].includes(url.pathname))return;
  event.respondWith((async()=>{
    let index;try{index=await forClient(event.clientId);}catch{return fetch(event.request);}
    const meta=index.files[url.pathname];return meta?resource(url.pathname,meta):fetch(event.request);
  })());
});
self.addEventListener('message',event=>{
  const id=event.source?.id,port=event.ports[0];if(!id||!port)return;
  event.waitUntil((async()=>{
    try{
      if(event.data?.type==='BIND'){const index=await bind(id);port.postMessage({ok:true,revision:index.revision});return;}
      if(event.data?.type!=='WARM')return;
      const index=await forClient(id),plan=index.plans[event.data.entry]||[],background=event.data.phase==='background';
      const urls=Array.isArray(plan)?(background?[]:plan):(background?plan.background:plan.critical);let cursor=0,completed=0,failed=0;
      const started=Date.now();
      async function worker(){while(cursor<urls.length){const url=urls[cursor++];try{await resource(url,index.files[url]);}catch{failed++;}completed++;if(completed%32===0)port.postMessage({completed,total:urls.length,failed});}}
      await Promise.all(Array.from({length:background?4:12},worker));port.postMessage({done:true,completed,total:urls.length,failed,milliseconds:Date.now()-started});
    }catch(error){port.postMessage({ok:false,error:error.message});}
  })());
});
