// Real reviewed server, WebSockets, original collision worker and temporary saves.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync,mkdirSync,mkdtempSync,rmSync,symlinkSync,realpathSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {stageSourceAvatarServer,stageSourceSpeciesCollision} from '../deploy/source_avatar_server.mjs';
import {entryServer,trialRoleManager,installEntryManagement} from '../deploy/entry_manage.mjs';
import {installEntryRead} from '../deploy/entry_read.mjs';
import {createSourceAvatarDraft} from '../deploy/source_avatar_draft.mjs';

const root=resolve('.'),privateRoot=resolve('analysis/raw/played-species-routing-20261115'),
  original=resolve(process.env.OC2_REVIEWED_RUNTIME||join(privateRoot,'immutable-inputs/prototype')),
  profileFile=resolve(process.env.OC2_SOURCE_SPECIES_PROFILES||'analysis/raw/species-world-router-20261115/profiles-v1.json'),
  creationFile=resolve(process.env.OC2_HUMAN_DRAFT_MANIFEST||'analysis/raw/character-human-creation-defaults-20261115/candidate-v1/manifest.json'),
  configFile=resolve(process.env.OC2_NATIVE_QA_CONFIG||'analysis/raw/selection-stage-release-20261115/mac-equivalent-inputs/native-physics.json'),
  packages=resolve(process.env.OC2_REVIEWED_NODE_MODULES||'analysis/raw/showcase-20261110/running-preview/prototype/node_modules'),
  available=[profileFile,creationFile,configFile,join(original,'server.mjs'),join(packages,'ws/wrapper.mjs')].every(existsSync);
const hash=b=>createHash('sha256').update(b).digest('hex');

test('collision copy admits only the reviewed original input',()=>{
  assert.throws(()=>stageSourceSpeciesCollision('unreviewed'),/identity/);
});

test('two actual sockets preserve separate source identities through movement, save and restart',{skip:!available,timeout:45000},async()=>{
  mkdirSync(privateRoot,{recursive:true});
  const folder=mkdtempSync(join(privateRoot,'socket-')),
    modules=join(original,'node_modules');
  if(!existsSync(modules))symlinkSync(packages,modules,'dir');else assert.equal(realpathSync(modules),realpathSync(packages));
  const config=JSON.parse(readFileSync(configFile,'utf8'));
  config.sourceSpeciesProfiles={path:profileFile,sha256:hash(readFileSync(profileFile))};
  config.python=process.env.OC2_QA_PYTHON||join(root,'.venv/bin/python');config.worker=join(root,'tools/source_species_worker.py');
  config.config=join(folder,'native-physics.json');writeFileSync(config.config,JSON.stringify(config));
  const collisionCopy=join(original,'game/native-species-window-collision-test.mjs'),serverCopy=join(original,'source-avatar-server-test.mjs');
  writeFileSync(collisionCopy,stageSourceSpeciesCollision(readFileSync(join(original,'game/native-window-collision.mjs'),'utf8')));
  writeFileSync(serverCopy,stageSourceAvatarServer(entryServer(readFileSync(join(original,'server.mjs'),'utf8'),new URL('../deploy/movement_trace.mjs',import.meta.url).href)));
  const {loadNativeWindowCollision}=await import(pathToFileURL(collisionCopy));
  const {createGameServer}=await import(pathToFileURL(serverCopy));
  const {default:WebSocket}=await import(pathToFileURL(join(packages,'ws/wrapper.mjs')));
  let motion=loadNativeWindowCollision(pathToFileURL(config.config));const saveFile=join(folder,'characters.json');
  let game,sockets=[];
  const connect=async(identity,name)=>{
    const socket=new WebSocket(`ws://127.0.0.1:${game.server.address().port}/ws`),messages=[];
    sockets.push(socket);socket.on('message',b=>messages.push(JSON.parse(b)));
    await new Promise((ok,bad)=>{socket.once('open',ok);socket.once('error',bad);});
    socket.send(JSON.stringify({type:'join',scene:'resources',mapWindow:'tutorial',room:'AVATAR-SOURCE',name,characterId:identity.record.id,resumeToken:identity.resumeToken}));
    return{socket,messages};
  };
  const until=async(predicate)=>{
    const until=Date.now()+12000;
    while(!predicate()){if(Date.now()>until)throw Error('Expected authoritative socket state did not arrive');await new Promise(ok=>setTimeout(ok,20));}
  };
  try{
    game=createGameServer({saveFile,mapWindowMotion:motion,motion:null,gameplay:null,navigation:null});
    const creation=JSON.parse(readFileSync(creationFile,'utf8')),draft=creation.sourceHumanCreationDraft.variants.find(v=>v.professionIndex===0).draft;
    installEntryManagement(game.server,trialRoleManager(game.entryStore,game.entryActive,{archive:()=>{},sourceAvatarDraft:createSourceAvatarDraft(creation,hash(readFileSync(creationFile)))}));
    installEntryRead(game.server,saveFile);
    await new Promise(ok=>game.server.listen(0,'127.0.0.1',ok));
    const origin=`http://127.0.0.1:${game.server.address().port}`;
    const response=await fetch(origin+'/__entry/create',{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify({name:'原人体测试',race:0,gender:0,profession:1})});
    assert.equal(response.status,200);const created=await response.json();
    const human={record:game.entryStore.records.get(created.character.id),resumeToken:created.resumeToken};
    assert.equal(human.record.sourceAvatar.creationDisplayId,draft.displayId);
    assert.equal(human.record.sourceAvatar.appearance.hair,draft.hair);
    const listed=await fetch(origin+'/__entry/characters',{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify({identities:[{characterId:human.record.id,resumeToken:human.resumeToken}]})}).then(r=>r.json());
    assert.deepEqual(listed.characters[0].sourceAvatar,human.record.sourceAvatar);
    const legacy=game.entryStore.resolveCharacter('旧模型测试',undefined,undefined,2);
    const p=motion.logical([-2235.5,108.55000305175781,12]);
    for(const identity of [human,legacy]){identity.record.positions={resources:{...p,groundY:108.55000305175781}};game.entryStore.touch(identity.record);}
    game.entryStore.flush();
    const h=await connect(human,'原人体测试'),l=await connect(legacy,'旧模型测试');
    try{await until(()=>[h,l].every(c=>c.messages.some(m=>m.type==='welcome')&&c.messages.some(m=>m.type==='state'&&m.players.length===2&&m.players.every(p=>p.sourceAnimation?.available))));}
    catch(error){throw Error(error.message+': '+JSON.stringify([h,l].map(c=>c.messages.slice(-2).map(m=>({type:m.type,message:m.message,players:m.players?.map(p=>({id:p.id,worldY:p.worldY,sourceAnimation:p.sourceAnimation}))})))));}
    const welcome=h.messages.find(m=>m.type==='welcome');assert.deepEqual(welcome.character.sourceAvatar,human.record.sourceAvatar);
    assert.equal(l.messages.find(m=>m.type==='welcome').character.sourceAvatar,undefined);
    for(const c of [h,l])c.socket.send(JSON.stringify({type:'input',x:1,y:0,sourceForward:true}));
    await until(()=>h.messages.filter(m=>m.type==='state').some(s=>s.players.find(p=>p.id===human.record.id)?.sourceAnimation?.current?.clip==='run_normal_front'));
    const one=h.messages.filter(m=>m.type==='state').at(-1);
    await until(()=>l.messages.some(s=>s.type==='state'&&s.tick===one.tick));
    assert.deepEqual(one.players,l.messages.find(s=>s.type==='state'&&s.tick===one.tick).players);
    const a=one.players.find(p=>p.id===human.record.id),b=one.players.find(p=>p.id===legacy.record.id);
    assert.deepEqual(a.sourceAvatar,human.record.sourceAvatar);assert.equal(a.sourceAnimation.sourceMotion.key,'human-male');
    assert.equal(b.sourceAvatar,undefined);assert.equal(b.sourceAnimation.sourceMotion,undefined);
    assert.notEqual(a.x,p.x);assert.equal(a.x,b.x);assert.equal(a.y,b.y);assert.equal(a.worldY,b.worldY);
    for(const c of [h,l])c.socket.send(JSON.stringify({type:'input',x:0,y:0}));
    await until(()=>h.messages.filter(m=>m.type==='state').some(s=>s.tick>one.tick&&s.players.every(p=>p.sourceAnimation?.current?.clip==='idle')));
    await game.close();game=null;motion=null;
    const first=JSON.parse(readFileSync(saveFile,'utf8'));
    motion=loadNativeWindowCollision(pathToFileURL(config.config));
    game=createGameServer({saveFile,mapWindowMotion:motion,motion:null,gameplay:null,navigation:null});
    assert.deepEqual(game.entryStore.records.get(human.record.id).sourceAvatar,human.record.sourceAvatar);
    assert.equal(game.entryStore.records.get(legacy.record.id).sourceAvatar,undefined);
    assert.deepEqual(JSON.parse(readFileSync(saveFile,'utf8')),first);
    await new Promise(ok=>game.server.listen(0,'127.0.0.1',ok));
    const h2=await connect(human,'原人体测试'),l2=await connect(legacy,'旧模型测试');
    await until(()=>[h2,l2].every(c=>c.messages.some(m=>m.type==='welcome'&&m.restored===true)&&c.messages.some(m=>m.type==='state'&&m.players.length===2&&m.players.every(p=>p.sourceAnimation?.available))));
    const restored=h2.messages.find(m=>m.type==='state'&&m.players.length===2&&m.players.every(p=>p.sourceAnimation?.available));
    assert.deepEqual(restored.players.find(p=>p.id===human.record.id).sourceAvatar,human.record.sourceAvatar);
    assert.equal(restored.players.find(p=>p.id===human.record.id).sourceAnimation.sourceMotion.key,'human-male');
    assert.equal(restored.players.find(p=>p.id===legacy.record.id).sourceAvatar,undefined);
    const receipt={actualTwoWebSockets:true,actualOriginalPhysicsCPU:true,sourceAvatarPersistedAndBroadcast:true,
      ownModelMotionStamped:true,legacyUnchanged:true,positionsEqual:true,firstMovingTick:one.tick,
      humanActions:[...new Set(h.messages.filter(m=>m.type==='state').flatMap(s=>s.players.filter(p=>p.id===human.record.id).map(p=>p.sourceAnimation?.current?.clip)).filter(Boolean))],
      actualRestartAndSocketRestore:true,productionOrUserSavesTouched:false,combatRestoredClaimed:false,browserAcceptanceClaimed:false};
    writeFileSync(join(privateRoot,'two-socket-source-avatar-v1.json'),JSON.stringify(receipt,null,2));
  }finally{
    for(const s of sockets)s.terminate();
    if(game)await game.close();else if(motion)await motion.close();
    rmSync(folder,{recursive:true,force:true});
  }
});
