// HTTP delivery only. It never sees WebSocket messages, character data or /data files.
import {readFile} from 'node:fs/promises';
import {createReadStream} from 'node:fs';
import {pipeline} from 'node:stream/promises';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {brotliCompress,gzip,constants} from 'node:zlib';
import {promisify} from 'node:util';
const CSP="default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; worker-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'self'";
export function encoding(header,available){
  const qualities=new Map((header||'').split(',').filter(Boolean).map(part=>{const [name,...params]=part.trim().toLowerCase().split(';');let q=1;for(const p of params)if(p.trim().startsWith('q='))q=Number(p.trim().slice(2));return[name,Number.isFinite(q)&&q>=0&&q<=1?q:0];}));
  const candidates=['br','gzip','identity'].filter(e=>e==='identity'||available?.[e]).map(e=>[e,qualities.get(e)??(e==='identity'?(qualities.get('*')===0?0:1):(qualities.get('*')??0))]);
  candidates.sort((a,b)=>b[1]-a[1]);return candidates[0]?.[1]>0?candidates[0][0]:null;
}
export async function installDelivery(server,root){
  const index=JSON.parse(await readFile(resolve(root,'analysis/raw/delivery/index.json'),'utf8'));
  const original=server.listeners('request');for(const listener of original)server.removeListener('request',listener);
  const metadata={...index,files:Object.fromEntries(Object.entries(index.files).map(([u,m])=>[u,{sha256:m.sha256,bytes:m.bytes,type:m.type}]))};
  const generated=new Map();
  generated.set('/__delivery/index.json',Buffer.from(JSON.stringify(metadata)));
  for(const name of ['delivery_boot.mjs','delivery_worker.mjs'])generated.set('/__delivery/'+name,await readFile(resolve(root,'deploy',name)));
  const generatedEncodings=new Map();
  for(const [url,body]of generated)if(body.length>1024){
    const [br,gz]=await Promise.all([promisify(brotliCompress)(body,{params:{[constants.BROTLI_PARAM_QUALITY]:4}}),promisify(gzip)(body)]);
    generatedEncodings.set(url,{br:{body:br,bytes:br.length},gzip:{body:gz,bytes:gz.length}});
  }
  server.on('request',async(req,res)=>{
    try{
      const parsed=new URL(req.url,'http://localhost');let url;
      try{url=decodeURIComponent(parsed.pathname);}catch{res.writeHead(400);res.end();return;}
      if(!['GET','HEAD'].includes(req.method)||url==='/health'||url==='/ws'){for(const listener of original)listener.call(server,req,res);return;}
      let meta=index.files[url],body=generated.get(url);
      if(body)meta={bytes:body.length,sha256:createHash('sha256').update(body).digest('hex'),type:url.endsWith('.json')?'application/json':'text/javascript; charset=utf-8',encodings:generatedEncodings.get(url)};
      if(!meta){for(const listener of original)listener.call(server,req,res);return;}
      if(meta.type.startsWith('text/html')){
        body=await readFile(meta.path);
        // Only the external script entry is wrapped. Page nodes/styles/game modules stay unchanged.
        const text=body.toString().replace(/<script type="module" src="(\/explore(?:-map)?\.js[^"<>]*)"><\/script>/g,(_,entry)=>`<script type="module" src="/__delivery/delivery_boot.mjs?entry=${encodeURIComponent(entry)}"></script>`);
        body=Buffer.from(text);meta={...meta,bytes:body.length,sha256:createHash('sha256').update(body).digest('hex'),encodings:undefined};
      }
      const chosen=encoding(req.headers['accept-encoding'],meta.encodings);
      if(!chosen){res.writeHead(406,{'Vary':'Accept-Encoding'});res.end();return;}
      const variant=chosen==='identity'?meta:meta.encodings[chosen];
      const etag='"'+meta.sha256+'-'+chosen+'"';
      const headers={'Content-Type':meta.type,'Cache-Control':'public, max-age=0, must-revalidate','ETag':etag,'Vary':'Accept-Encoding','X-Content-Type-Options':'nosniff','Content-Security-Policy':CSP,'X-OC2-Content-SHA256':meta.sha256};
      if(url==='/__delivery/delivery_worker.mjs')headers['Service-Worker-Allowed']='/';
      if(chosen!=='identity')headers['Content-Encoding']=chosen;
      const tags=(req.headers['if-none-match']||'').split(',').map(s=>s.trim().replace(/^W\//,''));
      if(tags.includes(etag)||tags.includes('*')){res.writeHead(304,headers);res.end();return;}
      headers['Content-Length']=variant.bytes;res.writeHead(200,headers);
      if(req.method==='HEAD'){res.end();return;}
      if(body)res.end(chosen==='identity'?body:variant.body);else await pipeline(createReadStream(variant.path),res);
    }catch(error){if(!res.headersSent){res.writeHead(500,{'Cache-Control':'no-store'});res.end('Static delivery unavailable');}else res.destroy(error);}
  });
  return index;
}
