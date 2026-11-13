// Disposable Linux acceptance. Credentials/reports stay in the Docker QA volume.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import WebSocket from 'ws';

const phase=process.argv[2]||'initial';
assert(['initial','restore'].includes(phase));
const url=process.env.OC2_QA_URL||'http://127.0.0.1:8080';
const receipt='/data/qa/acceptance.json';
const peers=[];
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(check,label,timeout=20000){const end=Date.now()+timeout;while(!check()){if(Date.now()>end)throw Error('Acceptance timeout: '+label);await delay(30);}}
async function connect(name,identity={}){
  const socket=new WebSocket(url.replace(/^http/,'ws')+'/ws',{origin:url});
  const messages=[];socket.on('message',raw=>messages.push(JSON.parse(raw)));
  socket.on('error',()=>{});
  const p={socket,messages,send:m=>socket.send(JSON.stringify(m))};peers.push(p);
  await new Promise((ok,fail)=>{socket.once('open',ok);socket.once('error',fail);});
  p.send({type:'join',scene:'resources',mapWindow:'tutorial',room:'LINUX-QA-01',name,profession:2,...identity});
  await until(()=>messages.some(m=>m.type==='welcome'||m.type==='error'),'join');
  assert(!messages.some(m=>m.type==='error'),messages.find(m=>m.type==='error')?.message);
  p.welcome=messages.find(m=>m.type==='welcome');
  p.state=()=>messages.findLast(m=>m.type==='state');
  p.player=()=>p.state()?.players.find(v=>v.id===p.welcome.id);
  p.progress=()=>messages.findLast(m=>m.type==='progress')?.character||p.welcome.character;
  return p;
}
try{
  const health=await(await fetch(url+'/health')).json();assert(health.ok);assert.equal(health.persistence,'file');
  for(const path of ['/explore-map.html','/explore.js','/vendor/three.module.js','/vendor/three.core.js','/assets/gameplay/native.json','/assets/source-layers/elf-female.json']){
    const response=await fetch(url+path);assert.equal(response.status,200,path);assert((await response.arrayBuffer()).byteLength>0,path);
  }
  // The durable save and original native inputs must never be HTTP-served.
  for(const path of ['/data/saves/characters.json','/native-physics.json','/assets/../../native-inputs/library.so']){
    const response=await fetch(url+path);assert([403,404].includes(response.status),path);
  }
  if(phase==='initial'){
    const a=await connect('Linux验收甲');await until(()=>a.state()?.players.length===1,'single player');
    const b=await connect('Linux验收乙');await until(()=>[a,b].every(p=>p.state()?.players.length===2),'two connections');
    const before={...a.player()};
    for(let i=0;i<12;i++){a.send({type:'input',x:1,y:0});await delay(100);}
    a.send({type:'input',x:0,y:0});await delay(500);
    assert(Math.hypot(a.player().x-before.x,a.player().y-before.y)>.1,'Real source movement advances');
    const current=a.player();
    await until(()=>b.state().players.some(v=>v.id===a.welcome.id&&Math.abs(v.x-current.x)<1e-5&&Math.abs(v.worldY-current.worldY)<1e-5),'authoritative movement broadcast');
    assert(Number.isFinite(current.worldY));
    a.send({type:'equip',slot:'chest',itemId:'linenArmor'});
    await until(()=>a.progress().equipment.chest==='linenArmor','save equipment');
    await until(()=>b.state().players.find(v=>v.id===a.welcome.id)?.equipment.chest==='linenArmor','equipment broadcast');
    await delay(300);
    mkdirSync('/data/qa',{recursive:true});
    writeFileSync(receipt,JSON.stringify({peers:[a,b].map(p=>({name:p.progress().name,identity:{characterId:p.welcome.id,resumeToken:p.welcome.resumeToken},position:p.player(),character:p.progress()}))},null,2),{mode:0o600,flag:'wx'});
    console.log(JSON.stringify({singlePlayer:true,twoConnections:true,realMovement:true,positionBroadcast:true,equipmentBroadcast:true,staticAssets:true,privatePathsNotServed:true,phase}));
  }else{
    const previous=JSON.parse(readFileSync(receipt,'utf8'));
    for(const saved of previous.peers){
      const p=await connect(saved.name,saved.identity);assert.equal(p.welcome.restored,true);
      await until(()=>p.player(),'restored state');
      for(const key of ['level','xp','gold','profession'])assert.equal(p.welcome.character[key],saved.character[key]);
      for(const key of ['equipment','inventory','look','hotbar'])assert.deepEqual(p.welcome.character[key],saved.character[key]);
      for(const key of ['x','y','worldY'])assert(Math.abs(p.player()[key]-saved.position[key])<.01,'persisted position '+key);
    }
    await until(()=>peers.every(p=>p.state()?.players.length===2),'restored two connections');
    console.log(JSON.stringify({restoredCharacters:true,positionPreserved:true,equipmentPreserved:true,inventoryPreserved:true,staticAssets:true,twoConnections:true,phase}));
  }
}finally{for(const p of peers)p.socket.close();await delay(250);for(const p of peers)p.socket.terminate();}
