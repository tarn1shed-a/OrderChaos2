import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash,webcrypto} from 'node:crypto';
import vm from 'node:vm';

const production=await readFile(new URL('./quest_world.mjs',import.meta.url),'utf8');
// Execute the actual production helper + full loadBody closure. Loading the
// whole scene would need WebGL/DOM; these explicit IO fixtures test its lexical
// scope and original byte/text transport without native resources or services.
function fixture(source=production){
 const start=source.indexOf('    const sourceText=async url=>');
 const end=source.indexOf('    const femaleDataText=',start);
 const loadStart=source.indexOf('      loadBody:async(routeId,route)=>{',end);
 const loadEnd=source.indexOf('\n      readHost:',loadStart);
 assert(start>=0&&end>start&&loadStart>end&&loadEnd>loadStart,'Unique production Gather closure anchors required');
 const helpers=source.slice(start,end),property=source.slice(loadStart,loadEnd).trim().replace(/,$/,'');
 const blobs=new Map(),requests=[],ownBodyText=new Map();
 const pin=(url,text)=>{const b=new TextEncoder().encode(text);blobs.set(url,b);return{url,bytes:b.length,sha256:createHash('sha256').update(b).digest('hex')};};
 const route={id:'own-fixture-body',routeId:'own-fixture-body',bodyKey:'fixture-body',seeded:true,normalBinding:'explicit-normal-fixture',
  source:pin('/assets/cpu-source.json','source fixture'),binding:pin('/assets/cpu-binding.json','binding fixture'),clipAppend:pin('/assets/cpu-clips.json','clip fixture')};
 const bodyText=' { "originalTextFixture" : true }\n';pin('/assets/cpu-body.json',bodyText);
 const context=vm.createContext({TextEncoder,Uint8Array,crypto:webcrypto,ownBodyText,npcPageLive:true,npcPageEpoch:1,page:1,
  bodyCatalog:{packs:{'fixture-body':{data:{url:'/assets/cpu-body.json'}}}},
  lookup:{getGatherContract:id=>id===route.routeId?route:null,getNormalContract:key=>key===route.bodyKey?{policy:{bindingId:route.normalBinding}}:null},
  fetch:async url=>{requests.push(url);const bytes=blobs.get(url);assert(bytes,'Explicit fixture URL required: '+url);return{ok:true,arrayBuffer:async()=>bytes.slice().buffer,text:async()=>new TextDecoder().decode(bytes)};}});
 vm.runInContext(helpers+'\nglobalThis.actualLoadBody=({'+property+'}).loadBody;',context,{filename:'quest_world.mjs:production-gather-closure'});
 return{loadBody:context.actualLoadBody,route,blobs,requests,ownBodyText,bodyText,context,pin};
}

test('actual own loadBody executes all three pinned reads and preserves exact body text',async()=>{
 const f=fixture(),input=await f.loadBody(f.route.routeId,f.route);
 assert.deepEqual([...input.sourceBytes],[...f.blobs.get(f.route.source.url)]);
 assert.deepEqual([...input.bindingBytes],[...f.blobs.get(f.route.binding.url)]);
 assert.deepEqual([...input.clipAppendBytes],[...f.blobs.get(f.route.clipAppend.url)]);
 assert.equal(f.ownBodyText.get(f.route.bodyKey),f.bodyText);assert.equal(f.requests.length,4);
});

test('the same executable check catches the original sourceBytes lexical TDZ',async()=>{
 assert(production.includes('readPinnedGatherBytes'));
 const f=fixture(production.replaceAll('readPinnedGatherBytes','sourceBytes'));
 await assert.rejects(f.loadBody(f.route.routeId,f.route),error=>error.name==='ReferenceError'&&/before initialization/.test(error.message));
 assert.equal(f.ownBodyText.size,0);
});

test('the production HF legacy branch retains its separate two-byte-input ABI',async()=>{
 const f=fixture(),prefix='/assets/quest461-world-gather-v2/data/';
 f.pin(prefix+'human-female-seeded-source-v1.json','HF source fixture');f.pin(prefix+'human-female-binding.json','HF binding fixture');
 const input=await f.loadBody('human-female',{bodyKey:'human-female'});
 assert.equal(new TextDecoder().decode(input.sourceBytes),'HF source fixture');assert.equal(new TextDecoder().decode(input.bindingBytes),'HF binding fixture');
 assert.equal(Object.hasOwn(input,'clipAppendBytes'),false);assert.equal(f.ownBodyText.size,0);
});
