// External delivery bootstrap only; imports the original game module without edits.
const params=new URL(import.meta.url).searchParams,entry=new URL(params.get('entry')||'',location.origin);
if(entry.origin!==location.origin||!['/explore-map.js','/explore.js'].includes(entry.pathname))throw Error('Invalid game entry');
const diagnostics=document.documentElement.dataset;
diagnostics.deliveryStarted=String(Date.now());diagnostics.deliveryStatus='starting';
const readyObserver=new MutationObserver(()=>{
  const button=document.getElementById('join');if(!button||button.disabled)return;
  diagnostics.deliveryReadyMs=String(Math.round(performance.now()));readyObserver.disconnect();
});
readyObserver.observe(document.documentElement,{subtree:true,attributes:true,attributeFilter:['disabled']});
try{
  if(!('serviceWorker'in navigator)||!('caches'in window)||!isSecureContext)throw Error('Public byte cache unsupported');
  const registration=await navigator.serviceWorker.register('/__delivery/delivery_worker.mjs',{scope:'/',type:'module',updateViaCache:'none'});
  await Promise.race([navigator.serviceWorker.ready,new Promise((_,reject)=>setTimeout(()=>reject(Error('Worker activation timeout')),6000))]);
  if(!navigator.serviceWorker.controller)await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{navigator.serviceWorker.removeEventListener('controllerchange',change);reject(Error('Worker control timeout'));},3000);
    function change(){if(navigator.serviceWorker.controller){clearTimeout(timer);navigator.serviceWorker.removeEventListener('controllerchange',change);resolve();}}
    navigator.serviceWorker.addEventListener('controllerchange',change);change();
  });
  const worker=navigator.serviceWorker.controller||registration.active;
  const result=await new Promise((resolve,reject)=>{const channel=new MessageChannel(),timer=setTimeout(()=>reject(Error('Delivery bind timeout')),8000);channel.port1.onmessage=event=>{clearTimeout(timer);channel.port1.close();event.data.ok?resolve(event.data):reject(Error(event.data.error));};worker.postMessage({type:'BIND'},[channel.port2]);});
  diagnostics.deliveryRevision=result.revision;diagnostics.deliveryStatus='active';
  const warm=new MessageChannel();warm.port1.onmessage=event=>{
    const value=event.data;if(value.completed!==undefined)diagnostics.deliveryPrefetched=String(value.completed);
    if(value.done){diagnostics.deliveryPrefetchMs=String(value.milliseconds);diagnostics.deliveryPrefetchFailed=String(value.failed);warm.port1.close();}
  };
  worker.postMessage({type:'WARM',entry:entry.pathname},[warm.port2]);
}catch(error){diagnostics.deliveryStatus='fallback';diagnostics.deliveryFallback=error.message;}
// Warm downloads continue in parallel. The original renderer determines readiness.
await import(entry.href);
