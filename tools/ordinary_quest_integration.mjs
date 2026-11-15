// Real HTTP + two WebSocket clients, authoritative original CPU walking, one
// original task's full compatible lifecycle, and a disk restart. Private data
// stays in a new ignored directory; no production/local character file used.
import assert from 'node:assert/strict';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {setTimeout as delay} from 'node:timers/promises';
import {execFileSync} from 'node:child_process';
import {startOrdinaryQuestLocal,ROOT} from './ordinary_quest_local.mjs';

const directory=resolve(process.argv[2]||'analysis/raw/ordinary-quest-integration-20261115/wire-v1');
mkdirSync(directory,{recursive:true,mode:0o700});
const profile=JSON.parse(readFileSync(resolve(ROOT,'analysis/raw/plain-quest-feasibility-20261115/executor-profile-v3.json')));
const task=profile.quests[0],npc=profile.actors[0];
const map=JSON.parse(readFileSync(resolve(ROOT,'analysis/raw/plain-quest-map1-20261115/candidate-v3/assets/source-ordinary-quest-map1/terrain.json')));
const report={format:'oc2-ordinary-quest-wire-acceptance-v1',questId:task.id,compatibleExecution:true,originalServerRecovered:false,existingSavesImported:false,walks:[],assertions:[]};
let running,connections=[];
const external=process.env.OC2_QUEST_ACCEPTANCE_URL||null,container=process.env.OC2_QUEST_ACCEPTANCE_CONTAINER||null;
if(external&&(!/^http:\/\/127\.0\.0\.1:[0-9]+\/quests\.html/.test(external)||!/^oc2-quest-linux-[0-9]+$/.test(container||'')))throw Error('External restart checks only target an explicitly named isolated local Linux container');
if(external&&execFileSync('docker',['inspect','--format','{{index .Config.Labels "oc2.task"}}',container],{encoding:'utf8'}).trim()!=='ordinary-quest')throw Error('Refuse to restart an unrelated container');
function source(p){return [map.bounds.min[0]+p.x/1280*(map.bounds.max[0]-map.bounds.min[0]),p.worldY,map.bounds.min[2]+p.y/1280*(map.bounds.max[2]-map.bounds.min[2])];}
async function until(fn,ms=15000){const start=Date.now();while(Date.now()-start<ms){const value=fn();if(value)return value;await delay(25);}throw Error('Timed out waiting for live authoritative state');}
async function api(path,data){const url=new URL(running.url).origin;const r=await fetch(url+path,{method:'POST',headers:{'Content-Type':'application/json',Origin:url},body:JSON.stringify(data)});const value=await r.json();if(!r.ok)throw Error(value.error||String(r.status));return value;}
async function create(name){const value=await api('/__entry/create',{name,race:2,gender:1,profession:2});return {name,characterId:value.character.id,resumeToken:value.resumeToken};}
async function connect(identity){
  const url=new URL('/ws',running.url);url.protocol='ws:';const ws=new WebSocket(url);
  const client={ws,identity,states:0,positions:[],welcome:null,player:null,errors:[]};connections.push(client);
  ws.addEventListener('message',event=>{const msg=JSON.parse(event.data);
    if(msg.type==='welcome')client.welcome=msg;
    if(msg.type==='error')client.errors.push(msg.message);
    if(msg.type==='state'){client.states++;client.player=msg.players.find(p=>p.id===identity.characterId);if(client.player)client.positions.push(source(client.player));}
  });
  await new Promise((ok,fail)=>{ws.addEventListener('open',ok,{once:true});ws.addEventListener('error',fail,{once:true});});
  ws.send(JSON.stringify({type:'join',scene:'resources',mapWindow:'heaven-landing',room:'QUEST-QA',...identity}));
  await until(()=>client.welcome||client.errors.length);assert.deepEqual(client.errors,[]);await until(()=>client.player);return client;
}
const input=(c,x,y)=>c.ws.send(JSON.stringify({type:'input',x,y}));
async function walk(client,target,range){
  const before=source(client.player),start=Date.now();let previous=Infinity,stalled=0;
  while(Date.now()-start<45000){
    const p=source(client.player),dx=target[0]-p[0],dz=target[2]-p[2],d=Math.hypot(dx,dz);
    if(d<=range){input(client,0,0);await delay(120);const end=source(client.player);report.walks.push({from:before,to:end,target,durationMs:Date.now()-start,distinctPositions:new Set(client.positions.map(p=>p.map(v=>v.toFixed(3)).join(','))).size});return;}
    stalled=d>=previous-.02?stalled+1:0;previous=d;
    if(stalled>25){
      // Tester's deliberate sidestep, not a new game navigation rule.
      const sign=report.walks.length%2?1:-1;input(client,-dz/d*sign,dx/d*sign);await delay(700);stalled=0;
    }else{input(client,dx/d,dz/d);await delay(70);}
  }
  input(client,0,0);throw Error('Actual source-physics walk did not reach '+JSON.stringify(target)+'; last '+JSON.stringify(source(client.player)));
}
async function query(client){return (await api('/__quests/query',{identity:client.identity,questId:task.id})).info;}
async function action(client,type,extra={}){const info=await query(client);return api('/__quests/action',{identity:client.identity,command:{type,questId:task.id,revision:info.revision,...extra}});}

try{
  running=external?{url:external,close:async()=>{}}:await startOrdinaryQuestLocal({directory,port:0});
  const aIdentity=await create('任务联机甲'),bIdentity=await create('任务联机乙');
  let a=await connect(aIdentity),b=await connect(bIdentity);
  assert.equal((await query(a)).Status,6);assert.equal((await query(b)).Status,6);
  await action(a,'accept');assert.equal((await query(a)).Status,4);assert.equal((await query(b)).Status,6);report.assertions.push('independent-two-player-acceptance');
  const targets=[...profile.objects].sort((a,b)=>Math.hypot(a.position[0]-npc.position[0],a.position[2]-npc.position[2])-Math.hypot(b.position[0]-npc.position[0],b.position[2]-npc.position[2])).slice(0,4);
  for(const object of targets){
    await walk(a,object.position,object.range*.6);await action(a,'collect',{objectId:object.id});
    console.log(JSON.stringify({collected:object.id,position:source(a.player)}));
  }
  assert.equal((await query(a)).Status,9);assert.equal((await query(b)).Status,6);report.assertions.push('four-original-objects-collected-by-walking');
  await walk(a,npc.position,npc.range*.6);
  const result=await action(a,'complete');assert.deepEqual(result.state.rewards,{xp:task.reward.xp,money:task.reward.money,favor:task.reward.favor,items:Object.fromEntries(task.reward.items.map(r=>[String(r.id),r.count]))});
  assert.deepEqual(result.state.inventory,{});report.assertions.push('turn-in-consumes-four-items-and-awards-original-row-once');
  const state=await api('/__quests/state',{identity:a.identity});
  await assert.rejects(()=>action(a,'complete'),/已交付|已经交付|尚未完成/);
  assert.deepEqual((await api('/__quests/state',{identity:a.identity})).state.rewards,state.state.rewards);report.assertions.push('repeat-completion-not-paid');
  assert.ok(a.states>10&&b.states>10);assert.equal(b.errors.length,0);report.assertions.push('second-live-client-observed-authoritative-room');
  for(const c of connections)c.ws.close();await delay(250);await running.close();connections=[];
  const saved=external?JSON.parse(execFileSync('docker',['exec',container,'cat','/data/saves/characters.json'],{encoding:'utf8'})):JSON.parse(readFileSync(resolve(directory,'characters.json')));
  for(const role of saved.characters){assert.equal(role.xp,0);assert.equal(role.level,1);assert.deepEqual(role.positions,{});}
  report.assertions.push('legacy-character-positions-and-xp-not-reinterpreted');
  if(external){
    execFileSync('docker',['restart',container],{stdio:'pipe'});
    const deadline=Date.now()+120000;let healthy=false;
    while(Date.now()<deadline){try{healthy=(await fetch(new URL('/health',external))).ok;}catch{}if(healthy)break;await delay(300);}
    assert.ok(healthy,'Linux service did not recover');report.platform='linux/amd64';
  }else running=await startOrdinaryQuestLocal({directory,port:0});
  a=await connect(aIdentity);b=await connect(bIdentity);
  assert.equal((await query(a)).Status,0);assert.equal((await query(b)).Status,6);
  assert.deepEqual((await api('/__quests/state',{identity:a.identity})).state.rewards,state.state.rewards);report.assertions.push('restart-restores-independent-task-and-reward-ledger');
  report.pass=true;report.playerFrames=[a.states,b.states];
}catch(error){report.pass=false;report.error=error.stack;throw error;}
finally{
  for(const c of connections)c.ws.close();if(running)await running.close();
  writeFileSync(resolve(directory,'acceptance.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({pass:report.pass,assertions:report.assertions,report:resolve(directory,'acceptance.json')}));
}
