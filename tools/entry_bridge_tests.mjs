import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {entryCharacters,installEntryRead} from '../deploy/entry_read.mjs';
import {savedEntryIdentities} from '../deploy/entry_ui.mjs';
import http from 'node:http';
import {mkdtemp,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

const token='a'.repeat(64),id='12345678-1234-1234-1234-123456789abc';
const record={id,name:'已有角色',level:3,profession:2,tokenHash:createHash('sha256').update(token).digest('hex'),positions:{resources:{x:17,y:31}},updatedAt:123,inventory:{privateItem:1}};
test('entry authenticates each existing role and reveals no save/credential fields',()=>{
 const data={version:6,characters:[structuredClone(record)]},before=structuredClone(data);
 assert.deepEqual(entryCharacters(data,[{characterId:id,resumeToken:'b'.repeat(64)}]),[]);
 assert.deepEqual(entryCharacters(data,[{characterId:id,resumeToken:token},{characterId:id,resumeToken:token}]),[{id,name:record.name,level:3,profession:2}]);
 assert.deepEqual(data,before);assert.throws(()=>entryCharacters(data,Array(33).fill({})),/Invalid/);
});
test('browser role enumeration retains distinct existing identities and never fabricates one',()=>{
 const storage={getItem:()=>JSON.stringify({characters:{a:{id,token},bad:{id:'wrong',token:'secret'}}})};
 assert.deepEqual(savedEntryIdentities(storage),[{characterId:id,resumeToken:token}]);
 assert.deepEqual(savedEntryIdentities({getItem:()=>'{broken'}),[]);assert.deepEqual(savedEntryIdentities({getItem:()=>null}),[]);
});
test('HTTP bridge is same-origin, uncached, bounded and leaves the save byte-identical',async()=>{
 const folder=await mkdtemp(join(tmpdir(),'oc2-entry-')),file=join(folder,'roles.json');await writeFile(file,JSON.stringify({version:6,characters:[record]}));
 const before=await readFile(file),server=http.createServer((req,res)=>{res.writeHead(404);res.end();});installEntryRead(server,file);await new Promise(ok=>server.listen(0,'127.0.0.1',ok));
 const url='http://127.0.0.1:'+server.address().port;
 try{
  const options={method:'POST',headers:{'Content-Type':'application/json',origin:url},body:JSON.stringify({identities:[{characterId:id,resumeToken:token}]})};
  const r=await fetch(url+'/__entry/characters',options);assert.equal(r.status,200);assert.equal(r.headers.get('cache-control'),'no-store');assert.deepEqual(await r.json(),{characters:[{id,name:record.name,level:3,profession:2}]});
  // A new device must see an empty result, never someone else's existing role.
  const fresh=await fetch(url+'/__entry/characters',{...options,body:JSON.stringify({identities:[]})});
  assert.deepEqual(await fresh.json(),{characters:[]});assert.deepEqual(await readFile(file),before);
  assert.equal((await fetch(url+'/__entry/characters',{...options,headers:{...options.headers,origin:'https://other.invalid'}})).status,403);
  assert.equal((await fetch(url+'/__entry/characters',{...options,body:'x'.repeat(17000)})).status,413);
  assert.equal((await fetch(url+'/__entry/characters')).status,405);
  assert.deepEqual(await readFile(file),before);
  await rm(file);const empty=await fetch(url+'/__entry/characters',options);assert.deepEqual(await empty.json(),{characters:[]});await assert.rejects(readFile(file),{code:'ENOENT'});
 }finally{await new Promise(ok=>server.close(ok));await rm(folder,{recursive:true});}
});
