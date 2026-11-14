// Existing web credentials only. Read atomically saved JSON; never create/touch a role.
import {readFile} from 'node:fs/promises';
import {createHash,timingSafeEqual} from 'node:crypto';
import {sourceAvatar} from './source_avatar_state.mjs';
export function entryCharacters(save,identities){
  if(save.version!==6||!Array.isArray(save.characters))throw Error('Unsupported saved roles');
  if(!Array.isArray(identities)||identities.length>32)throw Error('Invalid role request');
  const result=[],seen=new Set();
  for(const identity of identities){
    if(!identity||typeof identity.characterId!=='string'||typeof identity.resumeToken!=='string'||! /^[0-9a-f]{64}$/.test(identity.resumeToken))continue;
    const c=save.characters.find(v=>v.id===identity.characterId);
    if(!c||seen.has(c.id)||! /^[0-9a-f]{64}$/.test(c.tokenHash))continue;
    const actual=createHash('sha256').update(identity.resumeToken).digest();
    if(!timingSafeEqual(actual,Buffer.from(c.tokenHash,'hex')))continue;
    seen.add(c.id);result.push({id:c.id,name:c.name,level:c.level,profession:c.profession,
      ...(Object.hasOwn(c,'sourceAvatar')?{sourceAvatar:sourceAvatar(c.sourceAvatar)}:{})});
  }
  return result;
}
export function installEntryRead(server,saveFile){
  const original=server.listeners('request');for(const listener of original)server.removeListener('request',listener);
  server.on('request',async(req,res)=>{
    if(new URL(req.url,'http://localhost').pathname!=='/__entry/characters'){for(const listener of original)listener.call(server,req,res);return;}
    const reply=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(data));};
    if(req.method!=='POST'||req.headers['content-type']?.split(';')[0]!=='application/json')return reply(405,{error:'Unsupported request'});
    try{if(req.headers.origin&&new URL(req.headers.origin).host!==req.headers.host)return reply(403,{error:'Origin rejected'});}catch{return reply(403,{error:'Origin rejected'});}
    try{
      const chunks=[];let bytes=0;
      for await(const chunk of req){bytes+=chunk.length;if(bytes>16384){reply(413,{error:'Request too large'});req.resume();return;}chunks.push(chunk);}
      const request=JSON.parse(Buffer.concat(chunks).toString());
      let save;
      try{save=JSON.parse(await readFile(saveFile,'utf8'));}catch(error){if(error.code!=='ENOENT')throw error;save={version:6,characters:[]};}
      reply(200,{characters:entryCharacters(save,request.identities)});
    }catch{reply(400,{error:'Unable to read saved roles'});}
  });
}
