// Isolated local integration of original ordinary-quest assets and the new
// compatible execution layer. Never starts with a user's character save path.
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {readFile} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {entryServer,trialRoleManager,installEntryManagement} from '../deploy/entry_manage.mjs';
import {installEntryRead} from '../deploy/entry_read.mjs';
import {stageSourceAvatarServer} from '../deploy/source_avatar_server.mjs';
import {stageInspectorServer} from '../deploy/map_inspector.mjs';
import {stageOrdinaryQuestServer} from '../deploy/quest_server_overlay.mjs';
import {createQuestMotion} from '../deploy/quest_motion.mjs';
import {OrdinaryQuestLedger} from '../deploy/ordinary_quests.mjs';
import {installQuestTransport} from '../deploy/quest_transport.mjs';
import {retirePrototypeHTML} from '../deploy/retire_prototype.mjs';

export const ROOT=resolve(fileURLToPath(new URL('../',import.meta.url)));
export const BASE=resolve(ROOT,'analysis/raw/showcase-20261110/running-preview');
const TYPES={'.json':'application/json','.js':'text/javascript','.mjs':'text/javascript','.svg':'image/svg+xml','.png':'image/png','.html':'text/html; charset=utf-8','.css':'text/css','.woff':'font/woff'};
const hash=b=>createHash('sha256').update(b).digest('hex');

export async function startOrdinaryQuestLocal({directory,port=8904,
  mapDirectory=resolve(ROOT,'analysis/raw/plain-quest-map1-20261115/candidate-v3'),
  actorsDirectory=resolve(ROOT,'analysis/raw/plain-quest-feasibility-20261115/actors-v4'),
  uiDirectory=resolve(ROOT,'analysis/raw/quest-ui-compatible-20261115/qa-v1'),
  profileFile=resolve(ROOT,'analysis/raw/plain-quest-feasibility-20261115/executor-profile-v3.json')}={}){
  directory=resolve(directory);if(!directory.startsWith(resolve(ROOT,'analysis/raw/')+sep))throw Error('Only an isolated ignored integration directory is accepted');
  mkdirSync(directory,{recursive:true,mode:0o700});
  const read=p=>JSON.parse(readFileSync(p,'utf8')),profile=read(profileFile),mapRoot=resolve(mapDirectory,'assets/source-ordinary-quest-map1');
  const manifest=read(resolve(mapRoot,'manifest.json')),terrain=read(resolve(mapRoot,'terrain.json')),collision=read(resolve(mapRoot,'collision.json'));
  const min=terrain.bounds.min,max=terrain.bounds.max;
  const coordinateFrame={min,max,width:1280,height:1280};
  const collisionFile=resolve(directory,'collision.json');writeFileSync(collisionFile,JSON.stringify({...collision,coordinateFrame}));
  const baseConfig=read(resolve(BASE,'prototype/native-physics.json'));
  const configFile=resolve(directory,'native-physics.json');
  const config={python:baseConfig.python,worker:resolve(ROOT,'tools/source_physics_worker.py'),config:configFile,
    library:baseConfig.library,nativeSHA256:baseConfig.nativeSHA256,
    terrain:resolve(mapRoot,'terrain.json'),terrainLighting:resolve(mapRoot,'terrain-lighting.json'),collision:collisionFile,
    sourceFiles:Object.fromEntries(Object.entries(collision.sourceFiles).map(([name,m])=>[name,{path:resolve(mapDirectory,m.file),sha256:m.sha256}]))};
  writeFileSync(configFile,JSON.stringify(config,null,2));
  const runtimeURL=pathToFileURL(resolve(BASE,'prototype/')+sep);
  // The source task's start-zone anchor is an explicit test-area entry, not an
  // asserted original first spawn. Existing map5 locations are not consulted.
  const entry=profile.entryPosition||profile.actors[0].position;
  const motion=createQuestMotion(config,new URL('game/native-physics-thread.mjs',runtimeURL),entry);
  const ledger=new OrdinaryQuestLedger(profile,{saveFile:resolve(directory,'quests.json')});
  const original=readFileSync(resolve(BASE,'prototype/server.mjs'),'utf8');
  const identity=read(resolve(ROOT,'tools/local_mvp_runtime.json'));
  if(hash(original)!==identity.files['prototype/server.mjs'])throw Error('Reviewed server differs');
  const generated=resolve(BASE,'prototype/ordinary-server-'+hash(Buffer.from(directory)).slice(0,12)+'.mjs');
  const source=stageOrdinaryQuestServer(stageInspectorServer(stageSourceAvatarServer(entryServer(original,new URL('../deploy/movement_trace.mjs',import.meta.url).href))));
  if(existsSync(generated)&&readFileSync(generated,'utf8')!==source)throw Error('Preserve previous generated server; use a new integration directory');
  writeFileSync(generated,source);
  const {createGameServer}=await import(pathToFileURL(generated));
  const {loadGameplay}=await import(new URL('game/basic-attack.mjs',runtimeURL));
  let game;
  try{
    game=createGameServer({saveFile:resolve(directory,'characters.json'),gameplay:loadGameplay(),motion:null,mapWindowMotion:null,navigation:null,ordinaryQuestLayer:ledger,ordinaryQuestMotion:motion});
    const originalHandlers=game.server.listeners('request');for(const f of originalHandlers)game.server.removeListener('request',f);
    const core=resolve(BASE,'prototype/public'),baseAssets=resolve(BASE,'game-data/converted');
    const modules=JSON.parse(readFileSync(resolve(ROOT,'analysis/raw/plain-quest-map1-20261115/gpu-qa-v1/module-closure.json'),'utf8'));
    const entries=resolve(ROOT,'analysis/raw/ordinary-quest-integration-20261115/source-entry-current');
    game.server.on('request',async(req,res)=>{
      const path=new URL(req.url,'http://localhost').pathname;
      if(path==='/health'||path.startsWith('/__entry/')||path.startsWith('/__quests/')){for(const f of originalHandlers)f.call(game.server,req,res);return;}
      try{
        let file;
        if(path==='/'||path==='/quests.html'){
          const html=retirePrototypeHTML(readFileSync(resolve(core,'explore-map.html'),'utf8'))
            .replace(/<script type="module" src="[^"]*explore-map\.js[^"]*"><\/script>/,'<script type="module" src="/__delivery/quest_world.mjs"></script>');
          res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});res.end(html);return;
        }
        if(path==='/assets/ordinary-quests/profile.json'){res.writeHead(200,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify({...profile,sourceProofs:undefined}));return;}
        if(path==='/assets/ordinary-quests/item-assets.json')file=resolve(uiDirectory,'item-assets.json');
        else if(path==='/assets/ordinary-quests/quality-frames.json')file=resolve(uiDirectory,'quality-frames.json');
        else if(path==='/assets/ordinary-quests/program-v1.json')file=resolve(uiDirectory,'program-v1.json');
        else if(path==='/__delivery/mission_program.mjs')file=resolve(uiDirectory,'mission_program.mjs');
        else if(path.startsWith('/__delivery/')){
          const name=path.slice('/__delivery/'.length);if(!/^[a-z_]+\.(?:mjs|css)$/.test(name))throw Error('Unknown module');file=resolve(ROOT,'deploy',name);
        }else if(path.startsWith('/assets/source-ordinary-quest-map1/'))file=resolve(mapDirectory,'.'+path);
        else if(path.startsWith('/assets/source-ordinary-quest-actors/'))file=resolve(actorsDirectory,'.'+path);
        else if(path.startsWith('/assets/source-entry/'))file=resolve(entries,path.slice('/assets/source-entry/'.length));
        else if(path.startsWith('/assets/')&&existsSync(resolve(uiDirectory,'.'+path)))file=resolve(uiDirectory,'.'+path);
        else if(path.startsWith('/assets/'))file=resolve(baseAssets,path.slice('/assets/'.length));
        else if(path.startsWith('/vendor/'))file=resolve(BASE,'prototype/node_modules/three/build',path.slice('/vendor/'.length));
        else if(Object.hasOwn(modules,path.slice(1)))file=resolve(ROOT,modules[path.slice(1)]);
        else if(['/source-ordinary-quest-actors.mjs','/source-npc-final-pair-material.js','/source-npc-material.js'].includes(path))file=resolve(ROOT,'tools/preview',path.slice(1));
        else file=resolve(core,'.'+path);
        if(!file.startsWith(ROOT+sep)||path.includes('..'))throw Error('Unsafe asset path');
        const bytes=await readFile(file);res.writeHead(200,{'Content-Type':TYPES[extname(file)]||'application/octet-stream','Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});res.end(bytes);
      }catch(error){res.writeHead(404);res.end('Not found');}
    });
    installEntryRead(game.server,resolve(directory,'characters.json'));
    installEntryManagement(game.server,trialRoleManager(game.entryStore,game.entryActive));
    installQuestTransport(game.server,{ledger,store:game.entryStore,active:game.entryActive});
    await new Promise((ok,fail)=>{game.server.once('error',fail);game.server.listen(port,'127.0.0.1',ok);});
    return {game,ledger,motion,url:'http://127.0.0.1:'+game.server.address().port+'/quests.html?room=QUEST-01',close:()=>game.close()};
  }catch(error){if(game)await game.close();else await motion.close();throw error;}
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  const running=await startOrdinaryQuestLocal({directory:process.argv[2],port:Number(process.argv[3]||8904)});
  console.log(JSON.stringify({url:running.url,originalQuest:461,compatibleExecution:true,existingSavesImported:false}));
  let stopping=false;const stop=async()=>{if(stopping)return;stopping=true;await running.close();process.exit(0);};
  process.on('SIGINT',stop);process.on('SIGTERM',stop);
}
