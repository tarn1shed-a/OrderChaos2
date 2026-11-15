// Original recovered SVG entry plus optional stage-0 previews, on loopback.
// The identity reader sees an absent isolated save; all mutations are refused.
import http from 'node:http';
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {readFile} from 'node:fs/promises';
import {resolve,join,extname,sep} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {installEntryRead} from '../deploy/entry_read.mjs';

const ROOT=resolve(fileURLToPath(new URL('../',import.meta.url)));
const types={'.html':'text/html; charset=utf-8','.json':'application/json','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.woff':'font/woff','.glsl':'text/plain'};
const hash=b=>createHash('sha256').update(b).digest('hex');
export async function startCreationRaceQA({directory,staticRoot,port=0,
 entryAssets=join(ROOT,'analysis/raw/ordinary-quest-integration-20261115/source-entry-current'),
 threeRoot=join(ROOT,'analysis/raw/character-human-male-20261114/candidate-v1'),
 fontRoot=join(ROOT,'analysis/raw/showcase-20261110/running-preview/game-data/converted/ui')}={}){
 directory=resolve(directory);staticRoot=resolve(staticRoot);
 if(![directory,staticRoot].every(p=>p.startsWith(join(ROOT,'analysis/raw')+sep))||existsSync(directory))throw Error('New isolated QA session and private static root required');
 const stat=JSON.parse(readFileSync(join(staticRoot,'qa-static.json'),'utf8'));
 if(stat.format!=='oc2-original-race-preview-static-qa-v1'||stat.savesImported!==false)throw Error('Prepared selection-only closure required');
 mkdirSync(directory,{recursive:true,mode:0o700});
 const characterFile=join(directory,'isolated-empty-characters.json'),events=[];
 const html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>混沌与秩序2</title><body style="margin:0;background:#000"><script type="module" src="/__race_qa_host.mjs"></script></body></html>';
 const host=`import{createSourceEntry}from'/__delivery/entry_ui.mjs';const entry=createSourceEntry({previewURL:${JSON.stringify(stat.profileURL)},connect(){throw Error('Read-only creation-preview QA does not start a game');}});entry.ready();entry.open();`;
 const save=()=>writeFileSync(join(directory,'http-receipts.json'),JSON.stringify({format:'oc2-original-race-preview-http-qa-v1',events},null,2)+'\n',{mode:0o600});
 const server=http.createServer(async(req,res)=>{
  const path=new URL(req.url,'http://localhost').pathname;
  const send=(status,type,data)=>{res.writeHead(status,{'Content-Type':type,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(data);};
  try{
   if(req.method!=='GET')return send(405,'application/json',JSON.stringify({error:'Preview-only QA does not create, remove or move characters'}));
   if(path==='/')return send(200,'text/html; charset=utf-8',html);
   if(path==='/__race_qa_host.mjs')return send(200,'text/javascript',host);
   if(path==='/__race_qa_status.json')return send(200,'application/json',JSON.stringify({originalSVG:true,previewURL:stat.profileURL,additionalOriginalPreviews:stat.additionalOriginalPreviews,characterMutations:false,WebSockets:0,physicsWorkers:0}));
   if(path.includes('..')||path.includes('\\'))return send(404,'text/plain','Not found');
   let file;
   if(path.startsWith('/__delivery/')){
    const name=path.slice('/__delivery/'.length);
    if(!['entry_ui.mjs','entry_ui.css','entry_name.mjs','creation_preview.mjs','attribute_preview.mjs','attribute_state.mjs'].includes(name))return send(404,'text/plain','Not found');
    file=join(ROOT,'deploy',name);
   }else if(path.startsWith('/assets/source-entry/'))file=resolve(entryAssets,path.slice('/assets/source-entry/'.length));
   else if(path.startsWith('/assets/ui/'))file=resolve(fontRoot,path.slice('/assets/ui/'.length));
   else if(path.startsWith('/assets/'))file=resolve(staticRoot,'game-data/converted',path.slice('/assets/'.length));
   else if(['/vendor/three.module.js','/vendor/three.core.js'].includes(path))file=join(threeRoot,path.split('/').at(-1));
   else file=resolve(staticRoot,'prototype/public',path.replace(/^\//,''));
   if(!file.startsWith(ROOT+sep))return send(404,'text/plain','Not found');
   const raw=await readFile(file);events.push({path,status:200,bytes:raw.length,sha256:hash(raw)});send(200,types[extname(file)]||'application/octet-stream',raw);
  }catch{events.push({path,status:404});if(!res.headersSent)send(404,'text/plain','Not found');else res.end();}
 });
 installEntryRead(server,characterFile);
 await new Promise((ok,bad)=>{server.once('error',bad);server.listen(port,'127.0.0.1',ok);});
 const origin='http://127.0.0.1:'+server.address().port;
 const profile={format:'oc2-original-race-preview-ui-qa-v1',origin,url:origin+'/',staticRoot,profileURL:stat.profileURL,
  additionalOriginalPreviews:stat.additionalOriginalPreviews,originalSVG:true,gameStart:false,saveFileExists:existsSync(characterFile),
  characterMutations:false,WebSockets:0,physicsWorkers:0};
 writeFileSync(join(directory,'qa-session.json'),JSON.stringify(profile,null,2)+'\n');save();
 return{...profile,async close(){await new Promise(ok=>server.close(ok));save();if(existsSync(characterFile))throw Error('Preview-only QA unexpectedly created a save');}};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
 const qa=await startCreationRaceQA({directory:process.argv[2],staticRoot:process.argv[3],port:process.argv[4]?Number(process.argv[4]):0});
 console.log(JSON.stringify(qa));let closing=false;
 const stop=async()=>{if(closing)return;closing=true;await qa.close();process.exit(0);};process.on('SIGINT',stop);process.on('SIGTERM',stop);
}
