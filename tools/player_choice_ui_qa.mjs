// Entry-only QA over the unchanged recovered original UI. No game/WS/physics.
// Original assets, identity receipts and all test saves stay in analysis/raw.
import http from 'node:http';
import {readFileSync,writeFileSync,mkdirSync,existsSync,symlinkSync} from 'node:fs';
import {readFile} from 'node:fs/promises';
import {resolve,join,extname,sep} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {createPlayerChoiceRegistry,createPlayerChoiceStore} from '../deploy/player_choice_registry.mjs';
import {createPlayerChoiceManager,stagePlayerChoiceStoreSource,stagePlayerChoiceRead} from '../deploy/player_choice_server.mjs';
import {installEntryManagement} from '../deploy/entry_manage.mjs';

const ROOT=resolve(fileURLToPath(new URL('../',import.meta.url)));
const hash=b=>createHash('sha256').update(b).digest('hex');
const json=p=>JSON.parse(readFileSync(p,'utf8'));
const STORE='49a9f84c2ec5d4a0708932d2e77cc1296077e3b988d5614ef7e840e95de16eba';
const TYPES={'.json':'application/json','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.woff':'font/woff'};
const bodyKey=(race,gender)=>race+':'+gender;

export async function startPlayerChoiceEntryQA({directory,
 registryFile=join(ROOT,'analysis/raw/player-choice-recovery-20261115/registry-v1.json'),
 entryAssets=join(ROOT,'analysis/raw/ordinary-quest-integration-20261115/source-entry-current'),
 runtime=join(ROOT,'analysis/raw/showcase-20261110/running-preview/prototype'),ports=null}={}){
 directory=resolve(directory||'analysis/raw/player-choice-ui-20261115/session-v1');
 if(!directory.startsWith(join(ROOT,'analysis/raw')+sep))throw Error('An ignored isolated entry-QA directory is required');
 if(existsSync(join(directory,'characters.json')))throw Error('Preserve existing QA identities; use a new session directory');
 mkdirSync(directory,{recursive:true,mode:0o700});mkdirSync(join(directory,'game'),{recursive:true});
 const profile=json(registryFile),registry=createPlayerChoiceRegistry(profile),entry=json(join(entryAssets,'entry.json'));
 if(registry.count!==45||entry.format!=='oc2-source-entry-ui-v1')throw Error('Reviewed original registry and entry resources required');
 if(ports!==null&&(!Array.isArray(ports)||ports.length!==9||ports.some(p=>!Number.isInteger(p)||p<1024||p>65535)||new Set(ports).size!==9))throw Error('Nine distinct explicit loopback ports required');
 const source=readFileSync(join(runtime,'game/character-store.mjs'),'utf8');if(hash(source)!==STORE)throw Error('Reviewed base store differs');
 const registryModule=join(directory,'registry.mjs'),registryURL=pathToFileURL(registryModule).href;
 writeFileSync(registryModule,`import{readFileSync}from'node:fs';import{createPlayerChoiceRegistry}from${JSON.stringify(new URL('../deploy/player_choice_registry.mjs',import.meta.url).href)};export const registry=createPlayerChoiceRegistry(JSON.parse(readFileSync(${JSON.stringify(registryFile)},'utf8')));`);
 writeFileSync(join(directory,'game/character-store.mjs'),stagePlayerChoiceStoreSource(source,registryURL));
 writeFileSync(join(directory,'entry_read.mjs'),stagePlayerChoiceRead(readFileSync(join(ROOT,'deploy/entry_read.mjs'),'utf8'),registryURL));
 writeFileSync(join(directory,'package.json'),'{"type":"module"}');
 if(!existsSync(join(directory,'public')))symlinkSync(join(runtime,'public'),join(directory,'public'),'dir');
 const {CharacterStore}=await import(pathToFileURL(join(directory,'game/character-store.mjs'))),Store=createPlayerChoiceStore(CharacterStore,registry);
 const {installEntryRead}=await import(pathToFileURL(join(directory,'entry_read.mjs')));
 const characterFile=join(directory,'characters.json'),store=new Store(characterFile),events=[],servers=[],origins=[];
 const eventFile=join(directory,'ui-http-events.json');
 const saveEvents=()=>writeFileSync(eventFile,JSON.stringify({format:'oc2-original-entry-ui-http-receipts-v1',events},null,2)+'\n',{mode:0o600});
 const word=key=>entry.strings[key].text.replace(/<[^>]+>/g,'');
 const raceNames=['01','02','03','04','14'].map(v=>word('GENERAL_CH_SELEC_'+v));
 const classNames=['05','06','07','08','15'].map(v=>word('GENERAL_CH_SELEC_'+v));
 const active=new Map();
 const uiSource=readFileSync(join(ROOT,'deploy/entry_ui.mjs'),'utf8');
 if(!uiSource.includes('slice(0,32)')||!uiSource.includes('if(!previewURL)return;'))throw Error('Review changed UI storage/optional-preview behavior');
 const html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>原选角 · 隔离界面验收</title><body style="margin:0;background:#000"><script type="module" src="/__entry_qa_host.mjs"></script></body></html>';
 const host=`import{createSourceEntry}from'/__delivery/entry_ui.mjs';const entry=createSourceEntry({previewURL:null,connect(){throw Error('Entry-only QA does not admit a game or Start action');}});document.documentElement.dataset.entryOnlyQA='1';entry.open();`;
 try{
  for(const [bodyIndex,body]of profile.bodies.entries()){
   const expected={uiRace:body.uiRace,gender:body.gender,key:body.key,sourceModelId:body.sourceModelId};
   const manager=createPlayerChoiceManager(store,active,registry,{admit:(selected,avatar)=>
    selected.race===body.uiRace&&selected.gender===body.gender&&avatar.key===body.key,archive:()=>{throw Error('No deletion in entry-only QA');}});
   const disabled=()=>{throw Error('This entry-only QA permits creation and reading only');};
   let origin;
   const server=http.createServer(async(req,res)=>{
    const path=new URL(req.url,'http://localhost').pathname;
    const send=(status,type,content)=>{res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(content);};
    try{
     if(req.method!=='GET')return send(405,'text/plain','Unsupported request');
     if(path==='/')return send(200,'text/html; charset=utf-8',html);
     if(path==='/__entry_qa_host.mjs')return send(200,'text/javascript',host);
     if(path==='/__entry_qa_status.json')return send(200,'application/json',JSON.stringify({entryOnly:true,no3D:true,noPhysicsWorkers:true,noStart:true,body:expected,records:store.records.size}));
     if(path.includes('..'))return send(404,'text/plain','Not found');
     let file;
     if(path.startsWith('/__delivery/')){
      const name=path.slice('/__delivery/'.length);if(!['entry_ui.mjs','entry_ui.css','entry_name.mjs'].includes(name))return send(404,'text/plain','Not found');file=join(ROOT,'deploy',name);
     }else if(path.startsWith('/assets/source-entry/'))file=resolve(entryAssets,path.slice('/assets/source-entry/'.length));
     else if(path.startsWith('/assets/ui/')&&/^[a-zA-Z0-9_-]+\.woff$/.test(path.slice('/assets/ui/'.length)))file=join(ROOT,'analysis/raw/showcase-20261110/running-preview/game-data/converted',path.slice('/assets/'.length));
     else return send(404,'text/plain','Not found');
     if(!file.startsWith(ROOT+sep))throw Error('Asset path outside workspace');
     send(200,TYPES[extname(file)]||'application/octet-stream',await readFile(file));
    }catch{if(!res.headersSent)send(404,'text/plain','Not found');else res.end();}
   });
   // These are the original HTTP parsers and limits. Only the manager callback
   // records the decoded UI payload; it never rewrites race/class/gender.
   installEntryManagement(server,{create(data){
    const beforeCount=store.records.size;
    try{
     const created=manager.create(data),record=store.records.get(created.character.id);
     events.push({event:'create',via:'original-management-HTTP-parser',origin,bodyIndex,expectedBody:expected,
      request:structuredClone(data),record:{id:record.id,name:record.name,profession:record.profession,sourceAvatar:structuredClone(record.sourceAvatar),
       level:record.level,inventory:structuredClone(record.inventory),equipment:structuredClone(record.equipment),hotbar:record.hotbar,
       sourceInventoryPolicy:record.sourceInventoryPolicy},beforeCount,afterCount:store.records.size});saveEvents();return created;
    }catch(error){events.push({event:'create-rejected',origin,bodyIndex,request:structuredClone(data),error:error.message,beforeCount,afterCount:store.records.size});saveEvents();throw error;}
   },challenge:disabled,remove:disabled,returnEntry:disabled});
   installEntryRead(server,characterFile);
   // Observe read responses only. Resume tokens are not copied to reports.
   server.prependListener('request',(req,res)=>{
    if(new URL(req.url,'http://localhost').pathname!=='/__entry/characters')return;
    const end=res.end;
    res.end=function(chunk,...args){
     if(res.statusCode===200&&chunk){try{const result=JSON.parse(String(chunk));events.push({event:'characters',origin,bodyIndex,characters:result.characters});saveEvents();}catch{}}
     return end.call(this,chunk,...args);
    };
   });
   await new Promise((ok,bad)=>{server.once('error',bad);server.listen(ports?.[bodyIndex]||0,'127.0.0.1',ok);});
   origin='http://127.0.0.1:'+server.address().port;servers.push(server);
   origins.push({bodyIndex,origin,url:origin+'/',...expected,raceLabel:raceNames[body.uiRace],genderLabel:body.gender?word('GENERAL_CH_SELEC_23'):word('GENERAL_CH_SELEC_24'),
    choices:body.choices.map(c=>({profession:c.profession,uiProfessionIndex:c.professionIndex,classLabel:classNames[c.professionIndex],creationDisplayId:c.creationDisplayId,
     expectedAvatar:registry.draft({race:body.uiRace,gender:body.gender,profession:c.profession}),testName:'界面'+String(bodyIndex+1)+'职业'+String(c.professionIndex+1)}))});
  }
  const files=['deploy/entry_ui.mjs','deploy/entry_ui.css','deploy/entry_name.mjs','deploy/entry_manage.mjs','deploy/entry_read.mjs','deploy/player_choice_registry.mjs','deploy/player_choice_server.mjs'];
  const qa={format:'oc2-original-entry-45-ui-qa-v1',originalUIUntouched:true,sourceEntryProfile:{path:join(entryAssets,'entry.json'),sha256:hash(readFileSync(join(entryAssets,'entry.json')))},
   originalMatrix:{path:join(ROOT,'analysis/raw/player-choice-recovery-20261115/matrix-source-v1.json'),sha256:hash(readFileSync(join(ROOT,'analysis/raw/player-choice-recovery-20261115/matrix-source-v1.json')))},
   registry:{path:registryFile,sha256:hash(readFileSync(registryFile))},sourceModules:Object.fromEntries(files.map(f=>[f,hash(readFileSync(join(ROOT,f)))])),
   originIsolation:'Nine explicit localhost QA origins, not an original account-slot or admission rule.',savedIdentityLimitUnchanged:32,
   perOriginCombinationCount:5,combinationCount:45,storeFile:characterFile,physicsWorkers:0,WebSocketServers:0,original3DPreviewEnabled:false,StartEnabled:false,origins};
  writeFileSync(join(directory,'qa-profile.json'),JSON.stringify(qa,null,2)+'\n');saveEvents();
  return {store,origins,profile:qa,directory,events,async close(){for(const server of servers)await new Promise(ok=>server.close(ok));store.flush();saveEvents();}};
 }catch(error){for(const server of servers)server.close();throw error;}
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
 const qa=await startPlayerChoiceEntryQA({directory:process.argv[2]});
 console.log(JSON.stringify({directory:qa.directory,origins:qa.origins.map(({bodyIndex,url,key})=>({bodyIndex,url,key})),physicsWorkers:0,StartEnabled:false}));
 let closing=false;const close=async()=>{if(closing)return;closing=true;await qa.close();process.exit(0);};process.on('SIGINT',close);process.on('SIGTERM',close);
}
