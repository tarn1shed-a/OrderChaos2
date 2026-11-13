import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash,webcrypto} from 'node:crypto';
import vm from 'node:vm';
const script=await readFile(new URL('../deploy/delivery_worker.mjs',import.meta.url),'utf8');
const sha=value=>createHash('sha256').update(value).digest('hex');
function platform(){
  const stores=new Map(),state={text:'first source bytes',downloads:0,indexRequests:0,denyCache:false,corrupt:false};
  state.index=()=>({format:'oc2-delivery-v1',revision:sha(state.text),files:{'/assets/model.json':{bytes:Buffer.byteLength(state.text),sha256:sha(state.text),type:'application/json'}},plans:{'/explore-map.js':state.plan||['/assets/model.json']}});
  const caches={async open(name){if(state.denyCache)throw Error('Cache unavailable');if(!stores.has(name))stores.set(name,new Map());const store=stores.get(name);return{async match(key){return store.get(String(key))?.clone();},async put(key,response){store.set(String(key),response.clone());}};}};
  const fetch=async url=>{
    const path=new URL(typeof url==='string'?url:url.url,'https://local.test').pathname;
    await new Promise(resolve=>setTimeout(resolve,5));
    if(path==='/__delivery/index.json'){state.indexRequests++;return state.indexOffline?new Response('unavailable',{status:503}):Response.json(state.index());}
    if(path==='/assets/model.json'){state.downloads++;return new Response(state.corrupt?'damaged transport':state.text);}
    throw Error('Unexpected request '+path);
  };
  return {state,stores,caches,fetch};
}
function worker(platform){
  const handlers={};const self={location:{origin:'https://local.test'},addEventListener:(name,fn)=>handlers[name]=fn,skipWaiting:async()=>{},clients:{claim:async()=>{}}};
  vm.runInNewContext(script,{self,caches:platform.caches,fetch:platform.fetch,crypto:webcrypto,Request,Response,URL,console});
  async function bind(id){let done,value;handlers.message({source:{id},data:{type:'BIND'},ports:[{postMessage:v=>value=v}],waitUntil:p=>done=p});await done;assert.equal(value.ok,true);assert.equal(value.protocol,2);}
  async function get(id,path='/assets/model.json'){
    let response;handlers.fetch({clientId:id,request:new Request('https://local.test'+path),respondWith:p=>response=p});return response?await response:null;
  }
  async function warm(id,phase){let done;const messages=[];handlers.message({source:{id},data:{type:'WARM',entry:'/explore-map.js',phase},ports:[{postMessage:v=>messages.push(v)}],waitUntil:p=>done=p});await done;return messages.at(-1);}
  return{bind,get,warm};
}
test('background-only files are not prefetched until the entry-ready phase',async()=>{
  const p=platform();p.state.plan={critical:[],background:['/assets/model.json']};const w=worker(p);await w.bind('phased');
  assert.equal((await w.warm('phased')).completed,0);assert.equal(p.state.downloads,0);
  const result=await w.warm('phased','background');assert.equal(result.completed,1);assert.equal(result.failed,0);assert.equal(p.state.downloads,1);
});
test('parallel same-byte requests download once and return original bytes',async()=>{
  const p=platform(),w=worker(p);await w.bind('client');const result=await Promise.all(Array.from({length:8},()=>w.get('client')));
  for(const response of result)assert.equal(await response.text(),p.state.text);
  assert.equal(p.state.downloads,1);await w.get('client');assert.equal(p.state.downloads,1);
});
test('new content hash refreshes new clients while existing clients retain their loaded version',async()=>{
  const p=platform(),w=worker(p);await w.bind('old');assert.equal(await(await w.get('old')).text(),'first source bytes');
  p.state.text='updated source bytes';await w.bind('new');assert.equal(await(await w.get('new')).text(),'updated source bytes');assert.equal(await(await w.get('old')).text(),'first source bytes');assert.equal(p.state.downloads,2);
});
test('worker restart recovers client version and bytes from persistent asset caches',async()=>{
  const p=platform(),first=worker(p);await first.bind('existing');await first.get('existing');p.state.text='next source bytes';const restarted=worker(p);
  assert.equal(await(await restarted.get('existing')).text(),'first source bytes');assert.equal(p.state.downloads,1);
});
test('checksum failures never enter cache and can recover on the next valid download',async()=>{
  const p=platform(),w=worker(p);await w.bind('client');p.state.corrupt=true;await assert.rejects(w.get('client'),/checksum/);
  assert.equal(p.stores.get('oc2-public-bytes-v1').size,0);p.state.corrupt=false;assert.equal(await(await w.get('client')).text(),p.state.text);
});
test('unavailable browser cache still delivers verified original bytes',async()=>{
  const p=platform();p.state.denyCache=true;const w=worker(p);await w.bind('client');assert.equal(await(await w.get('client')).text(),p.state.text);
});
test('health and sockets never enter the asset cache',async()=>{
  const p=platform(),w=worker(p);assert.equal(await w.get('client','/health'),null);assert.equal(await w.get('client','/ws'),null);assert.equal(p.state.indexRequests,0);assert.equal(p.state.downloads,0);
});
test('simultaneous requests on an unbound page coalesce index downloads',async()=>{
  const p=platform(),w=worker(p);await Promise.all(Array.from({length:12},()=>w.get('fresh-page')));assert.equal(p.state.indexRequests,1);assert.equal(p.state.downloads,1);
});
test('an unavailable delivery index degrades to the original HTTP asset path',async()=>{
  const p=platform();p.state.indexOffline=true;const w=worker(p);assert.equal(await(await w.get('client')).text(),p.state.text);assert.equal(p.state.downloads,1);
});
