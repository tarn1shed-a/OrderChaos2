// Lossless transport sidecars and a public-file allowlist. Original files are read-only.
import {readFile,writeFile,mkdir,stat,rename} from 'node:fs/promises';
import {createReadStream,createWriteStream} from 'node:fs';
import {pipeline} from 'node:stream/promises';
import {createBrotliCompress,createGzip,constants} from 'node:zlib';
import {createHash} from 'node:crypto';
import {resolve,dirname,extname,posix} from 'node:path';
import {fileURLToPath} from 'node:url';
import {stageEntry} from './stage_runtime.mjs';
import {stagePlan} from './stage_plan.mjs';

export const TYPES={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json','.png':'image/png','.woff':'font/woff','.glsl':'text/plain; charset=utf-8','.rgba':'application/octet-stream','.glb':'model/gltf-binary'};
const sha=raw=>createHash('sha256').update(raw).digest('hex');
const compressible=new Set(['.json','.js','.mjs','.css','.html','.glsl','.rgba']);

export async function prepare(root,{stage=false}={}){
  const runtime=resolve(root,'analysis/raw/portable/running-preview');
  const bundle=JSON.parse(await readFile(resolve(runtime,'bundle-manifest.json'),'utf8'));
  const destination=resolve(root,'analysis/raw/delivery');await mkdir(destination,{recursive:true});
  const files={};
  for(const [name,meta]of Object.entries(bundle.files)){
    let url;
    if(name.startsWith('game-data/converted/'))url='/assets/'+name.slice('game-data/converted/'.length);
    else if(name.startsWith('prototype/public/'))url='/'+name.slice('prototype/public/'.length);
    else continue;
    files[url]={...meta,path:resolve(runtime,name),type:TYPES[extname(name)]||'application/octet-stream'};
  }
  for(const name of ['three.module.js','three.core.js']){
    const path=resolve(root,'deploy/node_modules/three/build',name),raw=await readFile(path);
    files['/vendor/'+name]={path,bytes:raw.length,sha256:sha(raw),type:TYPES['.js']};
  }
  if(stage){
    const path=resolve(destination,'staged-entry.js'),raw=Buffer.from(stageEntry(await readFile(files['/explore-map.js'].path,'utf8')));
    await writeFile(path,raw);files['/explore-map.js']={path,bytes:raw.length,sha256:sha(raw),type:TYPES['.js']};
    const helper=resolve(root,'deploy/staged_scene.mjs'),bytes=await readFile(helper);
    files['/__delivery/staged_scene.mjs']={path:helper,bytes:bytes.length,sha256:sha(bytes),type:TYPES['.mjs']};
  }
  const urls=Object.keys(files).sort(),sidecars=new Map();let cursor=0;
  async function worker(){while(cursor<urls.length){
    const url=urls[cursor++],meta=files[url];
    if(!compressible.has(extname(url))||meta.bytes<1024)continue;
    if(!sidecars.has(meta.sha256))sidecars.set(meta.sha256,(async()=>{const result={};for(const encoding of ['br','gzip']){
      const path=resolve(destination,meta.sha256+'.'+encoding);
      try{await stat(path);}catch{
        const temporary=path+'.tmp';
        const compressor=encoding==='br'?createBrotliCompress({params:{[constants.BROTLI_PARAM_QUALITY]:4}}):createGzip({level:6});
        await pipeline(createReadStream(meta.path),compressor,createWriteStream(temporary));await rename(temporary,path);
      }
      const size=(await stat(path)).size;
      if(size<meta.bytes*.97)result[encoding]={path,bytes:size};
    }return result;})());
    meta.encodings=await sidecars.get(meta.sha256);
  }}
  await Promise.all([worker(),worker()]);
  const publicFiles=Object.fromEntries(urls.map(url=>{const m=files[url];return[url,{sha256:m.sha256,bytes:m.bytes,type:m.type}];}));
  const revision=sha(JSON.stringify(publicFiles));
  // Resolve references from the actual entry modules, without changing render residency.
  function closure(entry,documents=texts){
    const found=new Set(),pending=[entry];
    while(pending.length){
      const url=pending.shift().split('?')[0],meta=files[url];
      if(!meta||found.has(url))continue;found.add(url);
      const text=documents.get(url);if(!text)continue;
      for(const match of text.matchAll(/["'](\/assets\/[^"'`\s]+)["']/g))pending.push(match[1]);
      if(/\.m?js$/.test(url))for(const match of text.matchAll(/(?:from\s*|import\s*(?:\(\s*)?)["']([^"']+)["']/g)){
        const value=match[1];if(value.startsWith('/'))pending.push(value);else if(value.startsWith('.'))pending.push(posix.resolve(posix.dirname(url),value));
      }
    }
    return [...found];
  }
  const texts=new Map();
  for(const url of urls)if(['.json','.js','.mjs'].includes(extname(url)))texts.set(url,await readFile(files[url].path,'utf8'));
  const plans={};for(const entry of ['/explore-map.js','/explore.js'])if(files[entry])plans[entry]=closure(entry);
  if(stage)plans['/explore-map.js']=await stagePlan(texts,closure);
  const index={format:'oc2-delivery-v1',revision,files:publicFiles,plans};
  const internal={...index,files};
  await writeFile(resolve(destination,'index.json'),JSON.stringify(internal));
  const totals=urls.reduce((a,u)=>{const m=files[u];a.original+=m.bytes;a.brotli+=m.encodings?.br?.bytes??m.bytes;return a;},{original:0,brotli:0});
  console.log(JSON.stringify({deliveryPrepared:true,files:urls.length,...totals,plans:Object.fromEntries(Object.entries(plans).map(([k,v])=>[k,Array.isArray(v)?v.length:{critical:v.critical.length,background:v.background.length,scope:v.scope}]))}));
  return internal;
}

if(process.argv[1]&&import.meta.url===new URL('file://'+resolve(process.argv[1])).href)await prepare(fileURLToPath(new URL('../',import.meta.url)),{stage:process.env.OC2_STAGED_LOADING!=='0'});
