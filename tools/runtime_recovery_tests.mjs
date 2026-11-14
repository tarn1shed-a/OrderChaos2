import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createRuntimeRecovery,isPhysicsTransportFailure} from '../deploy/runtime_recovery.mjs';
import {entryServer} from '../deploy/entry_manage.mjs';
import {readFileSync,writeFileSync,mkdtempSync,rmSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const timeout=()=>Error('原碰撞执行超时；没有切换到替代算法');
test('only identified original physics transport failures request recovery',()=>{
 assert(isPhysicsTransportFailure(timeout()));
 assert(isPhysicsTransportFailure(Error('Original physics worker exited (1): fixture')));
 for(const error of [Error('ENOSPC'),Error('permission denied'),Error('unknown'),null,'原碰撞执行超时；没有切换到替代算法'])assert.equal(isPhysicsTransportFailure(error),false);
});
test('recovery unwinds, closes once, then asks the platform to restart',async()=>{
 const calls=[],recovery=createRuntimeRecovery({close:async()=>{calls.push('flush-and-close');},exit:code=>calls.push(code)});
 assert.equal(recovery.fail(Error('disk full')),false);
 assert(recovery.fail(timeout()));assert.equal(recovery.fail(timeout()),false);assert.deepEqual(calls,[]);
 await recovery.completion;assert.deepEqual(calls,['flush-and-close',1]);
});
test('a failed final save is reported and cannot be claimed as successful recovery',async()=>{
 const calls=[],recovery=createRuntimeRecovery({close:async()=>{throw Error('ENOSPC');},report:message=>calls.push(message),exit:code=>calls.push(code)});
 recovery.fail(timeout());await recovery.completion;
 assert.deepEqual(calls,['运行服务关闭失败：ENOSPC',1]);
});

const runtime=process.env.OC2_RUNTIME_TEST_ROOT;
test('real reviewed server distinguishes runtime failure, flushes two roles and resumes them',
 {skip:!runtime||!existsSync(join(runtime,'prototype/server.mjs')),timeout:15000},async()=>{
 const base=pathToFileURL(resolve(runtime,'prototype')+'/');
 const {default:WebSocket}=await import(new URL('node_modules/ws/wrapper.mjs',base));
 const dir=mkdtempSync(join(tmpdir(),'oc2-recovery-')),save=join(dir,'characters.json');
 const generated=new URL('server-recovery-fixture-'+process.pid+'.mjs',base);
 writeFileSync(generated,entryServer(readFileSync(new URL('server.mjs',base),'utf8'),new URL('../deploy/movement_trace.mjs',import.meta.url).href));
 const {createGameServer}=await import(generated);let failure=false;const failures=[],sockets=[];
 const motion={sourceNative:true,place:p=>{p.worldY=10;p.grounded=true;},point:(x,z)=>({x,z}),support:()=>10,step:.5,move:()=>{if(failure)throw timeout();},settle(){},fork(){return this;},close:async()=>{}};
 let game;
 const open=async(options={})=>{game=createGameServer({saveFile:save,gameplay:null,motion,mapWindowMotion:null,navigation:null,contextualLoot:false,ai:false,casting:false,onRuntimeFailure:error=>failures.push(error),...options});await new Promise(ok=>game.server.listen(0,'127.0.0.1',ok));return 'http://127.0.0.1:'+game.server.address().port;};
 async function joinRole(url,name,credentials={}){
  const ws=new WebSocket(url.replace('http:','ws:')+'/ws');sockets.push(ws);
  const messages=[];ws.on('message',data=>messages.push(JSON.parse(data)));
  await new Promise((ok,no)=>{ws.once('open',ok);ws.once('error',no);});
  ws.send(JSON.stringify({type:'join',scene:'resources',room:'RECOVERY-TEST',name,...credentials}));
  const deadline=Date.now()+3000;while(!messages.some(m=>m.type==='welcome')){if(Date.now()>deadline)throw Error('Fixture join timed out');await new Promise(ok=>setTimeout(ok,10));}
  return {ws,messages,welcome:messages.find(m=>m.type==='welcome')};
 }
 const retained=characters=>characters.map(({updatedAt,...record})=>record).sort((a,b)=>a.id.localeCompare(b.id));
 try{
  const url=await open(),a=await joinRole(url,'恢复核查甲'),b=await joinRole(url,'恢复核查乙');
  const before=retained([...game.entryStore.records.values()].map(r=>structuredClone(r)));
  failure=true;const deadline=Date.now()+3000;while(!failures.length){if(Date.now()>deadline)throw Error('No recovery signal');await new Promise(ok=>setTimeout(ok,10));}
  assert.equal(failures.length,1);const health=await fetch(url+'/health');assert.equal(health.status,503);assert.equal((await health.json()).ok,false);
  assert(a.messages.some(m=>m.type==='notice'&&m.message.includes('场景计算')));assert(!a.messages.some(m=>m.message?.includes('存档当前不可用')));
  const exits=[],recovery=createRuntimeRecovery({close:()=>game.close(),exit:code=>exits.push(code)});recovery.fail(failures[0]);await recovery.completion;assert.deepEqual(exits,[1]);
  assert.deepEqual(retained(JSON.parse(readFileSync(save)).characters),before);
  failure=false;const next=await open();
  for(const role of [a,b]){
   const resumed=await joinRole(next,role.welcome.character.name,{characterId:role.welcome.id,resumeToken:role.welcome.resumeToken});assert.equal(resumed.welcome.id,role.welcome.id);assert(resumed.welcome.restored);
  }
  assert.equal((await fetch(next+'/health')).status,200);
  assert.deepEqual(retained([...game.entryStore.records.values()]),before);
 }finally{
  for(const socket of sockets)socket.terminate();if(game)await game.close();rmSync(generated,{force:true});rmSync(dir,{recursive:true,force:true});
 }
});
