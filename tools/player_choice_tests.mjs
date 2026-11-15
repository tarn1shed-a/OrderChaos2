import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,existsSync,mkdirSync,mkdtempSync,cpSync,symlinkSync,rmSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {createPlayerChoiceRegistry} from '../deploy/player_choice_registry.mjs';
import {createPlayerChoiceManager,stagePlayerChoiceServer,stagePlayerChoiceRead,stagePlayerChoiceStoreSource} from '../deploy/player_choice_server.mjs';
import {entryServer,installEntryManagement} from '../deploy/entry_manage.mjs';
const root=resolve('.'),raw=join(root,'analysis/raw/player-choice-recovery-20261115'),profileFile=join(raw,'registry-v1.json'),
 original=join(root,'analysis/raw/played-species-routing-20261115/immutable-inputs/prototype'),
 packages=join(root,'backups/prototype-withdrawal-20261108-224729/prototype/node_modules');
const available=existsSync(profileFile)&&existsSync(join(original,'server.mjs'))&&existsSync(join(packages,'ws/wrapper.mjs'));
const hash=b=>createHash('sha256').update(b).digest('hex');

test('unknown registry and implicit runtime admission are refused',()=>{
 assert.throws(()=>createPlayerChoiceRegistry({}));
 assert.throws(()=>createPlayerChoiceManager({},new Map(),{},{}));
 assert.throws(()=>stagePlayerChoiceServer('unreviewed','https://example.org/registry'));
 assert.throws(()=>stagePlayerChoiceRead('unreviewed','file:///registry.mjs'));
});

test('all original 45 drafts are distinct choices, not 45 new bodies or learned states',{skip:!available},()=>{
 const profile=JSON.parse(readFileSync(profileFile)),registry=createPlayerChoiceRegistry(profile);let count=0;
 for(const body of profile.bodies)for(const c of body.choices){
  const input={race:body.uiRace,gender:body.gender,profession:c.profession},a=registry.draft(input);
  assert.deepEqual(registry.check(a,c.profession),a);assert.equal(a.sourceModelId,body.sourceModelId);assert.deepEqual(a.appearance,c.appearance);
  const bad=structuredClone(a);bad.appearance.hair++;assert.throws(()=>registry.check(bad,c.profession));
  assert.throws(()=>registry.check({...a,sourceModelId:999},c.profession));count++;
 }
 assert.equal(count,45);assert.throws(()=>registry.draft({race:4,gender:1,profession:1}));
 assert.throws(()=>registry.draft({race:5,gender:0,profession:1}));assert.throws(()=>registry.draft({race:0,gender:0,profession:6}));
});

test('45 actual HTTP creates/reads, two actual sockets and disk reload preserve source identity only',
 {skip:!available,timeout:60000},async()=>{
 mkdirSync(raw,{recursive:true});const directory=mkdtempSync(join(raw,'identity-'));
 let game;const sockets=[];const profile=JSON.parse(readFileSync(profileFile)),registry=createPlayerChoiceRegistry(profile);
 try{
  cpSync(join(original,'game'),join(directory,'game'),{recursive:true});symlinkSync(join(original,'public'),join(directory,'public'),'dir');symlinkSync(packages,join(directory,'node_modules'),'dir');
  writeFileSync(join(directory,'package.json'),'{"type":"module"}');
  const registryModule=join(directory,'registry.mjs');writeFileSync(registryModule,`import{readFileSync}from'node:fs';import{createPlayerChoiceRegistry}from${JSON.stringify(new URL('../deploy/player_choice_registry.mjs',import.meta.url).href)};export const registry=createPlayerChoiceRegistry(JSON.parse(readFileSync(${JSON.stringify(profileFile)},'utf8')));`);
  writeFileSync(join(directory,'game/character-store.mjs'),stagePlayerChoiceStoreSource(readFileSync(join(original,'game/character-store.mjs'),'utf8'),pathToFileURL(registryModule).href));
  writeFileSync(join(directory,'server.mjs'),stagePlayerChoiceServer(entryServer(readFileSync(join(original,'server.mjs'),'utf8'),new URL('../deploy/movement_trace.mjs',import.meta.url).href),pathToFileURL(registryModule).href));
  writeFileSync(join(directory,'read.mjs'),stagePlayerChoiceRead(readFileSync(join(root,'deploy/entry_read.mjs'),'utf8'),pathToFileURL(registryModule).href));
  const {createGameServer}=await import(pathToFileURL(join(directory,'server.mjs'))),{installEntryRead}=await import(pathToFileURL(join(directory,'read.mjs'))),
   {default:WebSocket}=await import(pathToFileURL(join(packages,'ws/wrapper.mjs')));
  const saveFile=join(directory,'characters.json');
  const start=async()=>{
   game=createGameServer({saveFile,motion:null,mapWindowMotion:null,navigation:null,gameplay:null,ai:false,casting:false,contextualLoot:false});
   installEntryManagement(game.server,createPlayerChoiceManager(game.entryStore,game.entryActive,registry,{admit:()=>true,archive:()=>{}}));
   installEntryRead(game.server,saveFile);await new Promise(ok=>game.server.listen(0,'127.0.0.1',ok));
  };
  const api=async(path,data)=>{const origin='http://127.0.0.1:'+game.server.address().port;const response=await fetch(origin+'/__entry/'+path,{method:'POST',headers:{'Content-Type':'application/json',Origin:origin},body:JSON.stringify(data)});assert.equal(response.status,200);return response.json();};
  await start();const roles=[];
  // Existing web records, both without source metadata and with the earlier
  // human metadata, retain their prototype container and every stored field.
  const legacy=game.entryStore.resolveCharacter('既有原档夹具',undefined,undefined,2).record;
  const oldHuman=game.entryStore.resolveCharacter('既有人体夹具',undefined,undefined,1).record;
  oldHuman.sourceAvatar=registry.draft({race:0,gender:0,profession:1});game.entryStore.touch(oldHuman);game.entryStore.flush();
  const preserved=[structuredClone(legacy),structuredClone(oldHuman)];
  for(const body of profile.bodies)for(const c of body.choices){
   const input={name:'选角验收'+String(roles.length+1).padStart(2,'0'),race:body.uiRace,gender:body.gender,profession:c.profession},created=await api('create',input);
   assert.deepEqual(created.character.sourceAvatar,registry.draft({race:input.race,gender:input.gender,profession:input.profession}));
   const record=game.entryStore.records.get(created.character.id);assert.deepEqual(record.inventory,{});assert.equal(record.level,1);assert.equal(record.xp,0);
   roles.push({characterId:created.character.id,resumeToken:created.resumeToken,input,avatar:created.character.sourceAvatar});
  }
  for(let start=0;start<45;start+=25){const batch=roles.slice(start,start+25),listed=await api('characters',{identities:batch.map(({characterId,resumeToken})=>({characterId,resumeToken}))});assert.equal(listed.characters.length,batch.length);for(const role of batch){const c=listed.characters.find(c=>c.id===role.characterId);assert.deepEqual(c.sourceAvatar,role.avatar);assert.equal(c.profession,role.input.profession);}}
  const until=async predicate=>{const stop=Date.now()+10000;while(!predicate()){if(Date.now()>stop)throw Error('Actual player identity snapshot did not arrive');await new Promise(ok=>setTimeout(ok,20));}};
  const connect=async(role)=>{
   const socket=new WebSocket('ws://127.0.0.1:'+game.server.address().port+'/ws'),messages=[];sockets.push(socket);socket.on('message',raw=>messages.push(JSON.parse(raw)));
   await new Promise((ok,bad)=>{socket.once('open',ok);socket.once('error',bad);});socket.send(JSON.stringify({type:'join',scene:'resources',room:'CHOICE-IDENTITY',name:role.input.name,characterId:role.characterId,resumeToken:role.resumeToken}));return{socket,messages};
  };
  const pair=[roles[0],roles[39]],clients=await Promise.all(pair.map(connect));
  await until(()=>clients.every(c=>c.messages.some(m=>m.type==='welcome')&&c.messages.some(m=>m.type==='state'&&m.players.length===2)));
  for(const c of clients)for(const role of pair){const snapshot=c.messages.find(m=>m.type==='state'&&m.players.length===2).players.find(p=>p.id===role.characterId);assert.deepEqual(snapshot.sourceAvatar,role.avatar);assert.equal(snapshot.profession,role.input.profession);}
  const before=[...game.entryStore.records].map(([id,r])=>[id,structuredClone(r.sourceAvatar)]);
  // Explicit denial proves matrix membership is independent of runtime admission.
  const denied=createPlayerChoiceManager(game.entryStore,game.entryActive,registry,{admit:()=>false,archive:()=>{}});
  assert.throws(()=>denied.create({name:'不能冒认可玩',race:1,gender:0,profession:1}));assert.equal(game.entryStore.records.size,47);
  await game.close();game=null;const first=readFileSync(saveFile),parsed=JSON.parse(first);
  assert.equal(parsed.characters.length,47);assert(!first.includes('sourceHumanPose'));assert(!first.includes('learnedSkill'));
  await start();assert.equal(hash(readFileSync(saveFile)),hash(first));
  for(const[id,avatar]of before)assert.deepEqual(game.entryStore.records.get(id).sourceAvatar,avatar);
  for(const record of preserved)assert.deepEqual(game.entryStore.records.get(record.id),record);
  const {CharacterStore}=await import(pathToFileURL(join(directory,'game/character-store.mjs')));
  const sample=parsed.characters.find(c=>c.sourceInventoryPolicy);
  for(const kind of ['item','policy','avatar']){
   const record=structuredClone(sample);
   if(kind==='item')record.inventory.trainingSword=1;
   if(kind==='policy')record.sourceInventoryPolicy='unknown';
   if(kind==='avatar')record.sourceAvatar.sourceModelId=999;
   const file=join(directory,'bad-'+kind+'.json');writeFileSync(file,JSON.stringify({version:6,characters:[record]}));
   assert.throws(()=>new CharacterStore(file));
  }
  const restored=await Promise.all(pair.map(connect));await until(()=>restored.every(c=>c.messages.some(m=>m.type==='welcome'&&m.restored===true)));
  writeFileSync(join(raw,'identity-acceptance-v1.json'),JSON.stringify({format:'oc2-player-choice-identity-test-v1',originalChoices:45,actualHTTPCreateAndRead:45,actualDiskReload:45,actualSockets:2,actualSocketRestore:2,wrongRuntimeAdmissionRefused:true,sourceInventoryGrant:false,legacyRecordsPreserved:2,invalidEmptyContainerOrAvatarRejected:3,originalClientWorldOrPhysicsClaimed:false,sourceAvatarFixturesUsedForIdentityOnly:true,legacyOrProductionSavesReadOrChanged:false,sourceProfileSHA256:hash(readFileSync(profileFile))},null,2)+'\n');
 }finally{for(const s of sockets)s.terminate();if(game)await game.close();rmSync(directory,{recursive:true,force:true});}
});
