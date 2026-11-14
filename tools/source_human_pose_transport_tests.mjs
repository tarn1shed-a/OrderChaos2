import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync,mkdirSync,mkdtempSync,cpSync,symlinkSync,rmSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {sourceHumanPose,stageSourceHumanPoseCollision} from '../deploy/source_human_pose.mjs';
import {stageSourceAvatarServer} from '../deploy/source_avatar_server.mjs';
import {entryServer,trialRoleManager,installEntryManagement} from '../deploy/entry_manage.mjs';
import {createSourceAvatarDraft} from '../deploy/source_avatar_draft.mjs';

const root=resolve('.'),area=resolve('analysis/raw/human-pose-worker-20261115'),
 original=resolve(process.env.OC2_REVIEWED_RUNTIME||'analysis/raw/played-species-routing-20261115/immutable-inputs/prototype'),
 configFile=resolve(process.env.OC2_HUMAN_POSE_QA_CONFIG||join(area,'runtime-v1/native-physics.json')),
 creationFile=resolve('analysis/raw/character-human-creation-defaults-20261115/candidate-v1/manifest.json'),
 packages=resolve(process.env.OC2_REVIEWED_NODE_MODULES||'backups/prototype-withdrawal-20261108-224729/prototype/node_modules'),
 available=[configFile,creationFile,join(original,'server.mjs'),join(packages,'ws/wrapper.mjs')].every(existsSync),
 hash=b=>createHash('sha256').update(b).digest('hex');

test('unknown pose inputs and collision copies are refused',()=>{
 for(const v of [null,{}, {format:'oc2-human-original-fast-pose-v1'}])assert.throws(()=>sourceHumanPose(v,'scope:actor','actor'));
 assert.throws(()=>stageSourceHumanPoseCollision('unreviewed'));
});

test('two actual clients receive their own original poses and restore without saving pose packets',
 {skip:!available,timeout:60000},async()=>{
 mkdirSync(area,{recursive:true});const folder=mkdtempSync(join(area,'websocket-'));
 let game,motion;const sockets=[];
 try{
  writeFileSync(join(folder,'package.json'),'{"type":"module"}');
  cpSync(join(original,'game'),join(folder,'game'),{recursive:true});
  symlinkSync(join(original,'public'),join(folder,'public'),'dir');symlinkSync(packages,join(folder,'node_modules'),'dir');
  writeFileSync(join(folder,'game/native-window-collision.mjs'),stageSourceHumanPoseCollision(readFileSync(join(original,'game/native-window-collision.mjs'),'utf8')));
  writeFileSync(join(folder,'server.mjs'),stageSourceAvatarServer(entryServer(readFileSync(join(original,'server.mjs'),'utf8'),new URL('../deploy/movement_trace.mjs',import.meta.url).href)));
  const config=JSON.parse(readFileSync(configFile));config.python=process.env.OC2_QA_PYTHON||join(root,'.venv/bin/python');
  config.config=join(folder,'native-physics.json');writeFileSync(config.config,JSON.stringify(config));
  const {loadNativeWindowCollision}=await import(pathToFileURL(join(folder,'game/native-window-collision.mjs'))),
   {createGameServer}=await import(pathToFileURL(join(folder,'server.mjs'))),
   {default:WebSocket}=await import(pathToFileURL(join(packages,'ws/wrapper.mjs')));
  const saveFile=join(folder,'characters.json');
  const start=async()=>{
   motion=loadNativeWindowCollision(pathToFileURL(config.config));
   game=createGameServer({saveFile,mapWindowMotion:motion,motion:null,gameplay:null,navigation:null,ai:false,casting:false,contextualLoot:false});
   const raw=readFileSync(creationFile),creation=JSON.parse(raw);
   installEntryManagement(game.server,trialRoleManager(game.entryStore,game.entryActive,{archive:()=>{},sourceAvatarDraft:createSourceAvatarDraft(creation,hash(raw))}));
   await new Promise(ok=>game.server.listen(0,'127.0.0.1',ok));
  };
  const until=async predicate=>{const end=Date.now()+18000;while(!predicate()){if(Date.now()>end)throw Error('Original human pose state did not arrive');await new Promise(ok=>setTimeout(ok,20));}};
  const connect=async record=>{
   const socket=new WebSocket(`ws://127.0.0.1:${game.server.address().port}/ws`),messages=[];sockets.push(socket);
   socket.on('message',raw=>messages.push(JSON.parse(raw)));
   await new Promise((ok,bad)=>{socket.once('open',ok);socket.once('error',bad);});
   socket.send(JSON.stringify({type:'join',scene:'resources',mapWindow:'tutorial',room:'HUMAN-POSE',name:record.name,characterId:record.id,resumeToken:record.token}));
   return {socket,messages};
  };
  const ready=c=>c.messages.some(s=>s.type==='state'&&s.players.length===2&&s.players.every(p=>p.sourceHumanPose));
  await start();const origin=`http://127.0.0.1:${game.server.address().port}`,roles=[];
  for(const [index,name]of ['人体联机甲','人体联机乙'].entries()){
   const response=await fetch(origin+'/__entry/create',{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify({name,race:0,gender:0,profession:index?2:1})});
   assert.equal(response.status,200);const value=await response.json();roles.push({id:value.character.id,token:value.resumeToken,name});
  }
  const location=motion.logical([-2235.5,108.55000305175781,12]);
  for(const role of roles){const record=game.entryStore.records.get(role.id);record.positions={resources:{...location,groundY:108.55000305175781}};game.entryStore.touch(record);}
  game.entryStore.flush();const clients=await Promise.all(roles.map(connect));await until(()=>clients.every(ready));
  clients[0].socket.send(JSON.stringify({type:'input',x:1,y:0,sourceForward:true}));
  await until(()=>clients[0].messages.some(s=>s.type==='state'&&s.players.find(p=>p.id===roles[0].id)?.sourceAnimation?.current?.clip==='run_normal_front'));
  const moving=clients[0].messages.filter(s=>s.type==='state').at(-1);await until(()=>clients[1].messages.some(s=>s.type==='state'&&s.tick===moving.tick));
  assert.deepEqual(moving.players,clients[1].messages.find(s=>s.type==='state'&&s.tick===moving.tick).players);
  assert.notEqual(moving.players[0].sourceHumanPose.values,moving.players[1].sourceHumanPose.values);
  for(const p of moving.players){assert.equal(p.sourceHumanPose.actorKey,p.id);assert.equal(p.sourceHumanPose.values.length,2656);assert.equal(p.sourceHumanPose.valueBytes,1992);}
  const own=moving.players.find(p=>p.id===roles[0].id).sourceHumanPose;
  assert.throws(()=>sourceHumanPose(own,'another-actor',roles[0].id));
  const bad=structuredClone(own),bytes=Buffer.from(bad.values,'base64');bytes.writeFloatLE(NaN,bytes.length-4);bad.values=bytes.toString('base64');
  assert.throws(()=>sourceHumanPose(bad,roles[0].id,roles[0].id));
  clients[0].socket.send(JSON.stringify({type:'input',x:0,y:0}));
  await until(()=>clients[0].messages.some(s=>s.type==='state'&&s.tick>moving.tick&&s.players.every(p=>p.sourceAnimation?.current?.clip==='idle')));
  await game.close();game=null;motion=null;
  const saved=readFileSync(saveFile);assert(!saved.toString().includes('sourceHumanPose'));assert(!saved.toString().includes('float32-le-base64'));
  await start();assert.deepEqual(readFileSync(saveFile),saved);
  const restored=await Promise.all(roles.map(connect));await until(()=>restored.every(ready));
  for(const c of restored)assert(c.messages.some(s=>s.type==='welcome'&&s.restored===true));
  writeFileSync(join(area,'two-websocket-current.json'),JSON.stringify({actualTwoWebSockets:true,originalHumanPoseCPU:true,
   ownActorIdentityMapped:true,sameTickIdenticalPlayers:true,oneMovingOneIdleDifferentPoses:true,actualSaveAndRestart:true,
   posePacketsNotSaved:true,userOrProductionSavesTouched:false,sourceCreationOrCombatAdmitted:false,sourceGPUClaimed:false},null,2));
 }finally{
  for(const s of sockets)s.terminate();
  if(game)await game.close();else if(motion)await motion.close();
  rmSync(folder,{recursive:true,force:true});
 }
});
