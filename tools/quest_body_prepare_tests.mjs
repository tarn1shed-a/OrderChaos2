import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {createQuestMotion,prepareQuestBodies} from '../deploy/quest_motion.mjs';

// Startup/lifecycle transport fixtures only. They execute no original library,
// scene physics, body construction or game timestep.
const descriptor=key=>({key,field:key==='human-male'?'sourceHumanPose':'sourceFemalePose',bindingId:(key==='human-male'?'a':'b').repeat(64),valueBytes:key==='human-male'?1992:1928});
const info={frame:{min:[0,0,0],max:[64,0,64],width:640,height:1280},nativeSHA256:'f'.repeat(64),instanceIds:[],
  sourceSpeciesKeys:['human-male','human-female']};
for(const key of info.sourceSpeciesKeys){const {field,...row}=descriptor(key);info[field]=row;}
const ready=key=>{const {field,bindingId,valueBytes}=descriptor(key);return{key,ready:true,pose:{field,bindingId,valueBytes},milliseconds:15,rssBytes:32*1024*1024};};
const workerURL=new URL('data:text/javascript,'+encodeURIComponent(`
import {parentPort,workerData} from 'node:worker_threads';
import {appendFileSync} from 'node:fs';
parentPort.on('message',m=>{
  appendFileSync(workerData.trace,JSON.stringify({operation:m.close?'close':m.operation,species:m.data?.species})+'\\n');
  if(m.close){parentPort.close();return;}
  let response;
  if(m.operation==='init')response={result:workerData.info};
  else if(m.operation==='prepareOwnBody'){
    if(workerData.fail===m.data.species)response={error:'Explicit fixture body failed'};
    else response={result:workerData.responses[m.data.species]};
  }else response={error:'Unexpected startup fixture operation'};
  const raw=new TextEncoder().encode(JSON.stringify(response)),flag=new Int32Array(m.shared,0,2);
  new Uint8Array(m.shared,8,raw.length).set(raw);Atomics.store(flag,1,raw.length);Atomics.store(flag,0,1);Atomics.notify(flag,0);
});
`));
const rows=file=>readFileSync(file,'utf8').trim().split('\n').filter(Boolean).map(line=>JSON.parse(line));
function fixture(fail){const directory=mkdtempSync(join(tmpdir(),'oc2-body-prepare-')),trace=join(directory,'trace.jsonl');
  return{directory,trace,config:{trace,info,responses:Object.fromEntries(info.sourceSpeciesKeys.map(key=>[key,ready(key)])),fail}};}

test('complete body plan is checked before any CPU preparation request',()=>{
  const calls=[],rpc={request:(op,data)=>{calls.push([op,data]);return ready(data.species);}};
  for(const keys of [['human-male','absent'],['human-male','human-male'],['__proto__'],[''],{},[1]]){
    assert.throws(()=>prepareQuestBodies(rpc,info,keys));assert.deepEqual(calls,[]);
  }
  assert.deepEqual(prepareQuestBodies(rpc,{},null),[]);
  assert.deepEqual(prepareQuestBodies(rpc,{},[]),[]);
});

test('preparation is sequential and each actual-ready binding must match its declaration',()=>{
  const calls=[],rpc={request:(operation,data)=>{calls.push([operation,data.species]);return ready(data.species);}};
  const result=prepareQuestBodies(rpc,info,['human-female','human-male']);
  assert.deepEqual(calls,[['prepareOwnBody','human-female'],['prepareOwnBody','human-male']]);
  assert.deepEqual(result.map(r=>r.key),['human-female','human-male']);assert.equal(Object.isFrozen(result),true);
  for(const change of [r=>r.ready=false,r=>r.key='human-female',r=>r.pose.field='sourceFemalePose',
    r=>r.pose.bindingId='b'.repeat(64),r=>r.pose.valueBytes=1928,r=>r.milliseconds=-1,r=>r.rssBytes=0]){
    const bad=ready('human-male');change(bad);
    assert.throws(()=>prepareQuestBodies({request:()=>bad},info,['human-male']));
  }
});

test('actual startup worker prepares all requested bodies before returning the motion interface',async()=>{
  const f=fixture();let motion;
  try{
    motion=createQuestMotion(f.config,workerURL,[0,0,0],{prepareBodies:['human-female','human-male']});
    assert.deepEqual(rows(f.trace),[{operation:'init'},{operation:'prepareOwnBody',species:'human-female'},{operation:'prepareOwnBody',species:'human-male'}]);
    assert.deepEqual(motion.preparedPlayerBodies.map(r=>r.key),['human-female','human-male']);
    assert.equal(motion.world.speed,32);assert.equal(motion.step,.5);
    await motion.close();motion=null;assert.equal(rows(f.trace).at(-1).operation,'close');
  }finally{if(motion)await motion.close();rmSync(f.directory,{recursive:true,force:true});}
});

test('legacy startup sends no additional body RPC and failure closes the partial worker',async()=>{
  const legacy=fixture();let motion;
  try{
    motion=createQuestMotion(legacy.config,workerURL,[0,0,0]);
    assert.deepEqual(rows(legacy.trace),[{operation:'init'}]);assert.equal('preparedPlayerBodies'in motion,false);
    await motion.close();motion=null;
  }finally{if(motion)await motion.close();rmSync(legacy.directory,{recursive:true,force:true});}
  const failure=fixture('human-female');
  try{
    assert.throws(()=>createQuestMotion(failure.config,workerURL,[0,0,0],{prepareBodies:['human-male','human-female']}),/fixture body failed/);
    const deadline=Date.now()+3000;
    while(!rows(failure.trace).some(r=>r.operation==='close')){assert.ok(Date.now()<deadline,'Failed worker must receive close');await delay(10);}
    assert.deepEqual(rows(failure.trace).map(r=>r.operation),['init','prepareOwnBody','prepareOwnBody','close']);
  }finally{rmSync(failure.directory,{recursive:true,force:true});}
});
