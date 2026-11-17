import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';

// Execute the actual client source at its DOM/clock/Three interfaces. These
// tests do not load original art or manufacture a native actor/quest result.
const source=readFileSync(new URL('../deploy/quest_world.mjs',import.meta.url),'utf8');
function fragment(from,to){const a=source.indexOf(from),b=source.indexOf(to,a);assert.ok(a>=0&&b>a);return source.slice(a,b);}
const coordinates=fragment('function sourcePosition(', '\nasync function api(');
const timer=fragment('setInterval(()=>{\n  if(!connected', '\nsetInterval(()=>{if(connected');
const sync=fragment('function syncPlayers(', '\nfunction clearConnection(');
class Vector3{
 constructor(x=0,y=0,z=0){Object.assign(this,{x,y,z});}
 sub(v){this.x-=v.x;this.y-=v.y;this.z-=v.z;return this;}
 copy(v){Object.assign(this,v);return this;}
}
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-10,`${a} differs from ${b}`);
function frame({minX=-384,maxX=-128,minZ=-64,maxZ=128,width=2560,height=3840}={}){
 return {bounds:{min:[minX,0,minZ],max:[maxX,10,maxZ]},world:{width,height},origin:new Vector3()};
}
function logical(f,x,z){return {x:(x-f.bounds.min[0])/(f.bounds.max[0]-f.bounds.min[0])*f.world.width,y:(z-f.bounds.min[2])/(f.bounds.max[2]-f.bounds.min[2])*f.world.height};}

test('click input follows physical ground direction across square and rectangular coordinate windows',()=>{
 for(const f of [frame(),frame({minX:-320,maxX:-192,minZ:0,maxZ:64,width:1280,height:1280}),frame({minX:-64,maxX:64,minZ:-320,maxZ:-192,width:1280,height:1280})]){
  const x=f.bounds.min[0]+20,z=f.bounds.min[2]+20,p={...logical(f,x,z),worldY:2,hp:100};
  for(const [dx,dz]of [[1,1],[-3,4],[5,-2]]){
   let gatherCancelled=0;
   const sent=[],ctx={...f,THREE:{Vector3},connected:true,document:{hidden:false},me:()=>p,blocked:()=>false,
    gatherIntent:{cancel(){gatherCancelled++;}},joystickInput:{active:false},keys:new Set(),cameraYaw:0,destination:{source:{x:x+dx,z:z+dz},stopDistance:.35},send:v=>sent.push(v),setInterval:fn=>ctx.tick=fn};
   vm.runInNewContext(coordinates+'\n'+timer,ctx);ctx.tick();
   close(sent[0].x,dx/Math.hypot(dx,dz));close(sent[0].y,dz/Math.hypot(dx,dz));assert.equal(gatherCancelled,1);
  }
 }
});

test('animation distance and heading use rendered source units, not unequal logical axes',()=>{
 const f=frame(),old={x:-250,y:20},p={id:'one',...logical(f,-249,21),worldY:2,hp:100};
 const actor={target:new Vector3(),body:{rotation:{}},previous:old,lastAt:0},calls=[],sourceCalls=[];
 const sourcePlayer={id:'source-fixture',sourceAvatar:{key:'host-boundary-fixture'}};let gatherChanged=0;
 const ctx={...f,THREE:{Vector3},players:[p,sourcePlayer],avatars:new Map([['one',actor]]),
  connected:true,generation:3,npcPageLive:true,sourcePlayers:{sync:(...args)=>sourceCalls.push(args)},gatherIntent:{changed(){gatherChanged++;}},
  snapshotMotion:(...args)=>{calls.push(args);return {};},setCharacterEquipment(){},setCharacterLook(){},syncCharacterCombat(){},updateHUD(){},me:()=>p};
 vm.runInNewContext(coordinates+'\n'+sync,ctx);vm.runInNewContext('syncPlayers(1000)',ctx);
 close(calls[0][1].x,-249);close(calls[0][1].y,21);assert.equal(calls[0][3],1);
 close(actor.body.rotation.y,Math.PI/4);close(actor.previous.x,-249);close(actor.previous.y,21);
 assert.equal(calls.length,1,'Source actors delegate to their own host, not the legacy coordinate path');
 assert.equal(sourceCalls.length,1);assert.deepEqual(Array.from(sourceCalls[0][0]),[sourcePlayer]);assert.equal(sourceCalls[0][1],1000);
 assert.equal(sourceCalls[0][2].current(),true);ctx.generation++;assert.equal(sourceCalls[0][2].current(),false);
 assert.equal(gatherChanged,1);
});
