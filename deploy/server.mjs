// Deployment transport/paths and opt-in timing only. Reviewed files are immutable;
// a separately generated, SHA-guarded server copy adds observational timing hooks.
import {readFileSync, existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {installDelivery} from './static_delivery.mjs';
import {writeFileSync} from 'node:fs';
import {entryServer,trialRoleManager,installEntryManagement} from './entry_manage.mjs';
import {installEntryRead} from './entry_read.mjs';
import {configureTrialEntry,trialEntryPosition} from './tutorial_entry.mjs';
import {createNameDrawer,installNameDraw} from './name_draw_server.mjs';
import {createRuntimeRecovery} from './runtime_recovery.mjs';
import {installAdmin} from './admin_server.mjs';

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
writeFileSync(observed,entryServer(readFileSync(new URL('server.mjs',base),'utf8'),new URL('./movement_trace.mjs',import.meta.url).href));
const {createGameServer}=await import(observed);
const motion=configureTrialEntry(loadNativeWindowCollision(new URL('native-physics.json',base)));
if(!motion?.sourceNative)throw Error('Original collision inputs are unavailable; no fallback');
const gameplay=loadGameplay();
if(!gameplay)throw Error('Reviewed gameplay data unavailable');
let game;
const recovery=createRuntimeRecovery({close:()=>game.close(),exit:code=>process.exit(code)});
try {
  game=createGameServer({maxPlayersPerRoom:maxPlayers,saveFile:'/data/saves/characters.json',gameplay,motion:null,mapWindowMotion:motion,navigation:null,onRuntimeFailure:error=>recovery.fail(error)});
  await installDelivery(game.server,root);
  installEntryRead(game.server,'/data/saves/characters.json');
  installNameDraw(game.server,createNameDrawer(root));
  installEntryManagement(game.server,trialRoleManager(game.entryStore,game.entryActive,{entryPosition:()=>trialEntryPosition(motion)}));
  installAdmin(game.server,{store:game.entryStore,active:game.entryActive,passwordHash:process.env.OC2_ADMIN_PASSWORD_HASH,secureCookies:process.env.OC2_ADMIN_LOCAL_HTTP!=='1',sourcePoint:(x,y)=>motion.point(x,y)});
  await new Promise((ok,fail)=>{game.server.once('error',fail);game.server.listen(port,'0.0.0.0',()=>{game.server.off('error',fail);ok();});});
} catch(error) { if(game)await game.close();else await motion.close();throw error; }
console.log(JSON.stringify({listening:port,host:'0.0.0.0',saveFile:'/data/saves/characters.json',maxPlayers,sourceNative:true}));
let closing=false;
async function stop(){if(closing)return;closing=true;try{await game.close();process.exit(0);}catch(error){console.error(error.message);process.exit(1);}}
process.on('SIGTERM',stop);process.on('SIGINT',stop);
