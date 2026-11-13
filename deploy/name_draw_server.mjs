// Read-only font drawing. No game messages, role/store mutation or source assets
// are accepted from the caller. Cache/queue bounds keep rendering off the tick.
import {spawn} from 'node:child_process';
import {resolve} from 'node:path';
import {gzipSync} from 'node:zlib';
import {encoding} from './static_delivery.mjs';
export function validName(name){return typeof name==='string'&&[...name].length>=1&&[...name].length<=24&&!/[\u0000-\u001f\u007f-\u009f\ud800-\udfff]/u.test(name);}
export function createNameDrawer(root){
 const cache=new Map(),queue=[];let active=0;
 const drain=()=>{while(active<2&&queue.length)queue.shift()();};
 return async name=>{
  if(!validName(name))throw Error('Invalid name');
  if(cache.has(name))return cache.get(name);
  if(queue.length>=16)throw Error('Name renderer busy');
  const promise=new Promise((ok,fail)=>{queue.push(()=>{
   active++;const child=spawn('python3',[resolve(root,'tools/source_name_worker.py'),resolve(root,'analysis/raw/portable/running-preview/prototype/native-physics.json')],{stdio:['pipe','pipe','pipe']});
   const chunks=[];let bytes=0,ended=false;
   const finish=(error,result)=>{if(ended)return;ended=true;clearTimeout(timer);active--;if(error){cache.delete(name);fail(error);}else ok(result);drain();};
   const timer=setTimeout(()=>{child.kill('SIGKILL');finish(Error('Font draw timed out'));},15000);
   child.stdout.on('data',data=>{bytes+=data.length;if(bytes>1024*1024){child.kill('SIGKILL');finish(Error('Font result too large'));}else chunks.push(data);});
   child.stderr.resume();child.once('error',e=>finish(e));
   child.stdin.once('error',e=>finish(e));
   child.once('close',code=>{if(code!==0)return finish(Error('Source font unavailable'));try{const packet=JSON.parse(Buffer.concat(chunks));if(packet.format!=='oc2-source-self-name-v1'||!packet.nativeGlyphCPU)throw Error('Font result differs');finish(null,packet);}catch(e){finish(e);}});
   child.stdin.end(JSON.stringify({name})+'\n');
  });drain();});
  cache.set(name,promise);if(cache.size>64)cache.delete(cache.keys().next().value);
  return promise;
 };
}
export function installNameDraw(server,draw){
 const original=server.listeners('request');for(const listener of original)server.removeListener('request',listener);
 server.on('request',async(req,res)=>{
  if(new URL(req.url,'http://localhost').pathname!=='/__name/draw'){for(const listener of original)listener.call(server,req,res);return;}
  const reply=(status,data)=>{const raw=Buffer.from(JSON.stringify(data)),gzip=encoding(req.headers['accept-encoding'],{gzip:true})==='gzip';res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff',...(gzip?{'Content-Encoding':'gzip','Vary':'Accept-Encoding'}:{})});res.end(gzip?gzipSync(raw):raw);};
  if(req.method!=='POST'||req.headers['content-type']?.split(';')[0]!=='application/json')return reply(405,{error:'Unsupported request'});
  try{if(req.headers.origin&&new URL(req.headers.origin).host!==req.headers.host)return reply(403,{error:'Origin rejected'});}catch{return reply(403,{error:'Origin rejected'});}
  try{const chunks=[];let bytes=0;for await(const chunk of req){bytes+=chunk.length;if(bytes>1024){req.resume();return reply(413,{error:'Request too large'});}chunks.push(chunk);}const {name}=JSON.parse(Buffer.concat(chunks));if(!validName(name))return reply(400,{error:'Invalid name'});reply(200,await draw(name));}catch{reply(503,{error:'Name rendering unavailable'});}
 });
}
