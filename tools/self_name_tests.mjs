import {test}from'node:test';import assert from'node:assert/strict';
import {canShowSelf,distanceScale,sourceDistance,SOURCE_SELF_NAME}from'../deploy/self_name.mjs';
import {validName,installNameDraw}from'../deploy/name_draw_server.mjs';
import {createServer}from'node:http';
test('only a ready self actor with a verified anchor is eligible; missing remote state stays absent',()=>{
 const v={id:'self',selfId:'self',name:'精灵',modelReady:true,anchorReady:true};assert(canShowSelf(v));
 for(const missing of ['id','selfId','name','modelReady','anchorReady'])assert(!canShowSelf({...v,[missing]:null}));
 assert(!canShowSelf({...v,id:'peer'}));assert.equal(SOURCE_SELF_NAME.type,0x120a);assert.equal(SOURCE_SELF_NAME.color,0xfffed8a2);
 for(const d of [0,1,5])assert.equal(distanceScale(d),1);
 for(const d of [5.01,10,100])assert(Math.abs(distanceScale(d)-(d/15+2/3))<1e-6);
 assert.equal(sourceDistance({x:1,y:2,z:3},{x:1,y:5,z:7}),5);
});
test('font transport limits input and returns generated pixels without any store dependency',async()=>{
 assert(validName('精灵Kevin'));assert(!validName(''));assert(!validName('x'.repeat(25)));assert(!validName('x\ny'));assert(!validName('\ud800'));
 const seen=[],server=createServer((req,res)=>{res.end('game');});installNameDraw(server,async name=>{seen.push(name);return {format:'test',name};});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
 try{
  assert.equal(await(await fetch(base+'/')).text(),'game');
  const post=(body,headers={})=>fetch(base+'/__name/draw',{method:'POST',headers:{'Content-Type':'application/json',...headers},body:JSON.stringify(body)});
  assert.equal((await post({name:'精灵'})).status,200);assert.deepEqual(seen,['精灵']);
  assert.equal((await post({name:''})).status,400);assert.equal((await post({name:'x'.repeat(1500)})).status,413);
  assert.equal((await post({name:'精灵'},{Origin:'https://wrong.invalid'})).status,403);assert.deepEqual(seen,['精灵']);
 }finally{await new Promise(r=>server.close(r));}
});
