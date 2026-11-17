// Deployment transport/paths and opt-in timing only. Reviewed files are immutable;
// a separately generated, SHA-guarded server copy adds observational timing hooks.
import {readFileSync, existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {installDelivery} from './static_delivery.mjs';
import {sourceWorldBodies} from './source_world_bodies.mjs';
import {writeFileSync} from 'node:fs';
import {entryServer,trialRoleManager,installEntryManagement} from './entry_manage.mjs';
import {installEntryRead} from './entry_read.mjs';
import {configureTrialEntry,trialEntryPosition} from './tutorial_entry.mjs';
import {createNameDrawer,installNameDraw} from './name_draw_server.mjs';
import {createRuntimeRecovery} from './runtime_recovery.mjs';
import {installAdmin} from './admin_server.mjs';
import {createMapInspector,stageInspectorServer} from './map_inspector.mjs';
import {applyPositionRepair} from './role_position_repair.mjs';
import {stageSourceAvatarServer} from './source_avatar_server.mjs';
import {stageOrdinaryQuestServer} from './quest_server_overlay.mjs';
import {OrdinaryQuestLedger} from './ordinary_quests.mjs';
import {createQuestMotion} from './quest_motion.mjs';
import {installQuestTransport} from './quest_transport.mjs';
import {createQuestCollection} from './quest_collection.mjs';
import {createQuestGatherServer} from './quest_gather_server.mjs';
import {deferNativeMotion} from './deferred_native_motion.mjs';

const root=resolve(new URL('../',import.meta.url).pathname);
const runtime=resolve(root,'analysis/raw/portable/running-preview');
const manifest=JSON.parse(readFileSync(resolve(root,'tools/local_mvp_runtime.json'),'utf8'));
for(const [name,digest] of Object.entries(manifest.files)) {
  const file=resolve(runtime,name);
  if(!file.startsWith(runtime+'/')||!existsSync(file)||createHash('sha256').update(readFileSync(file)).digest('hex')!==digest)
    throw Error('Reviewed runtime identity differs: '+name);
}
const port=Number(process.env.PORT||8080),maxPlayers=Number(process.env.MAX_PLAYERS_PER_ROOM||8);
if(!Number.isInteger(port)||port<1||port>65535)throw Error('Invalid PORT');
if(!Number.isInteger(maxPlayers)||maxPlayers<1||maxPlayers>32)throw Error('Invalid MAX_PLAYERS_PER_ROOM');
const base=pathToFileURL(runtime+'/prototype/');
const {loadNativeWindowCollision}=await import(new URL('game/native-window-collision.mjs',base));
const {loadGameplay}=await import(new URL('game/basic-attack.mjs',base));
const observed=new URL('server-observed.mjs',base);
const questProfileFile=resolve(runtime,'game-data/converted/ordinary-quests/profile.json');
const questConfigFile=resolve(runtime,'native-inputs/ordinary-quest/native-physics.json');
if(existsSync(questProfileFile)!==existsSync(questConfigFile))throw Error('Incomplete ordinary-quest runtime');
const ordinaryQuestLayer=existsSync(questProfileFile)?new OrdinaryQuestLedger(JSON.parse(readFileSync(questProfileFile,'utf8')),{saveFile:'/data/saves/ordinary-quests.json'}):null;
const collectionFile=resolve(runtime,'game-data/converted/source-quest461-channel-v1/execution.json');
const collection=existsSync(collectionFile)?createQuestCollection({ledger:ordinaryQuestLayer,profile:JSON.parse(readFileSync(collectionFile,'utf8'))}):null;
const sourceBodies=sourceWorldBodies(process.env.OC2_HUMAN_FEMALE_WORLD==='1',process.env.OC2_SOURCE_WORLD_BODIES);
const sourceWorld=sourceBodies.length?await(await import('./source_world_runtime.mjs')).loadSourceWorldRuntime({root,runtime,enabledBodyKeys:sourceBodies,gatherEnabled:process.env.OC2_SOURCE_GATHER==='1'}):null;
if(sourceWorld&&!ordinaryQuestLayer)throw Error('Source body requires the reviewed ordinary world');
let serverSource=entryServer(readFileSync(new URL('server.mjs',base),'utf8'),new URL('./movement_trace.mjs',import.meta.url).href);
serverSource=stageInspectorServer(sourceWorld?sourceWorld.stagePlayerChoice(serverSource):stageSourceAvatarServer(serverSource));
if(ordinaryQuestLayer)serverSource=stageOrdinaryQuestServer(serverSource);
if(sourceWorld)serverSource=sourceWorld.stageServer(serverSource);
writeFileSync(observed,serverSource);
const {createGameServer}=await import(observed);
const loadTutorialMotion=()=>configureTrialEntry(loadNativeWindowCollision(new URL('native-physics.json',base)));
const motion=sourceWorld?deferNativeMotion(loadTutorialMotion):loadTutorialMotion();
if(!sourceWorld&&!motion?.sourceNative)throw Error('Original collision inputs are unavailable; no fallback');
const gameplay=loadGameplay();
if(!gameplay)throw Error('Reviewed gameplay data unavailable');
let game,gather=null;
const inspector=createMapInspector({identityFile:'/data/map-inspector.json',entryPosition:()=>trialEntryPosition(motion)});
const recovery=createRuntimeRecovery({close:()=>game.close(),exit:code=>process.exit(code)});
// The second original scene's CPU worker is started only when a player enters
// that map. It does not replace or reload the tutorial's worker or positions.
let questMotion;
const loadQuestMotion=()=>questMotion||=createQuestMotion(JSON.parse(readFileSync(questConfigFile,'utf8')),new URL('game/native-physics-thread.mjs',base),ordinaryQuestLayer.profile.entryPosition||ordinaryQuestLayer.profile.actors[0].position);
let ordinaryQuestMotion=ordinaryQuestLayer?{get world(){return loadQuestMotion().world;},fork:()=>loadQuestMotion().fork(),close:()=>questMotion?.close()}:null;
let sourceRoute=null;
const runtimeClock=Date.now;
try {
  if(sourceWorld){sourceRoute=sourceWorld.createRoute({legacyMotion:loadQuestMotion(),clock:runtimeClock,entryPosition:ordinaryQuestLayer.profile.entryPosition||ordinaryQuestLayer.profile.actors[0].position,onFault:error=>console.error('Source body:',error.message)});ordinaryQuestMotion=sourceRoute.motion;}
  if(collection){const ports={runtime,collection,readGame:()=>game,onFault:fault=>console.error('Compatible gather presentation:',JSON.stringify(fault))};gather=await sourceWorld?.createGather(ports)||await createQuestGatherServer(ports);}
  game=createGameServer({clock:runtimeClock,inspector,maxPlayersPerRoom:maxPlayers,saveFile:'/data/saves/characters.json',gameplay,motion:null,mapWindowMotion:motion,navigation:null,onRuntimeFailure:error=>recovery.fail(error),...(ordinaryQuestLayer?{ordinaryQuestLayer,ordinaryQuestMotion,ordinaryGatherEvents:gather?.tape}:{}),...(sourceRoute?{sourceWorldGate:sourceRoute.gate,pendingSourceJoins:sourceRoute.pending}:{})});
  try{const repaired=applyPositionRepair(game.entryStore,'/data/role-position-repair.json',()=>trialEntryPosition(motion));if(repaired)console.log(JSON.stringify({positionRepair:repaired}));}
  catch(error){console.error('Position repair refused: '+error.message);}
  await installDelivery(game.server,root);
  if(sourceWorld)await sourceWorld.installRead(game.server,'/data/saves/characters.json');else installEntryRead(game.server,'/data/saves/characters.json');
  installNameDraw(game.server,createNameDrawer(root));
  const managerOptions={entryPosition:()=>trialEntryPosition(motion)};
  installEntryManagement(game.server,sourceWorld?sourceWorld.manager(game.entryStore,game.entryActive,managerOptions):trialRoleManager(game.entryStore,game.entryActive,managerOptions));
  if(ordinaryQuestLayer){const ports={ledger:ordinaryQuestLayer,store:game.entryStore,active:game.entryActive,collection:gather?.collection||collection};installQuestTransport(game.server,sourceWorld?{...ports,...sourceWorld.questPorts(ports)}:ports);}
  installAdmin(game.server,{inspector,store:game.entryStore,active:game.entryActive,passwordHash:process.env.OC2_ADMIN_PASSWORD_HASH,secureCookies:process.env.OC2_ADMIN_LOCAL_HTTP!=='1'});
  await new Promise((ok,fail)=>{game.server.once('error',fail);game.server.listen(port,'0.0.0.0',()=>{game.server.off('error',fail);ok();});});
} catch(error) { try{if(game)await game.close();else{await sourceWorld?.close();await questMotion?.close();await motion.close();}}finally{gather?.dispose();}throw error; }
console.log(JSON.stringify({listening:port,host:'0.0.0.0',saveFile:'/data/saves/characters.json',maxPlayers,sourceNative:true}));
let closing=false;
async function stop(){if(closing)return;closing=true;try{await game.close();gather?.dispose();process.exit(0);}catch(error){console.error(error.message);process.exit(1);}}
process.on('SIGTERM',stop);process.on('SIGINT',stop);
