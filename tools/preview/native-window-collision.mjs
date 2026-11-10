// Server binding for recovered normal, unmounted, dry static-scene movement.
// Input timing, logical coordinates, visual playback and storage remain host code.
import {readFileSync,existsSync}from'node:fs';
import {Worker}from'node:worker_threads';
import {randomUUID}from'node:crypto';
import {RESOURCE_WORLD}from'../public/world.js';
class NativeRPC{
  constructor(config){this.worker=new Worker(new URL('./native-physics-thread.mjs',import.meta.url),{workerData:config,execArgv:[]});this.shared=new SharedArrayBuffer(65536);this.worker.unref();}
  request(operation,data={}){const flag=new Int32Array(this.shared,0,2);Atomics.store(flag,0,0);this.worker.postMessage({operation,data,shared:this.shared});
    if(Atomics.wait(flag,0,0,20000)==='timed-out')throw Error('原碰撞执行超时；没有切换到替代算法');
    const response=JSON.parse(new TextDecoder().decode(new Uint8Array(this.shared,8,Atomics.load(flag,1))));if(response.error)throw Error(response.error);return response.result;}
  close(){this.worker.ref();return new Promise(resolve=>{this.worker.once('exit',resolve);this.worker.postMessage({close:true});});}
}
function bind(rpc,info,scope=randomUUID()){
  const f=info.frame,min=f.min,max=f.max,logical=p=>({x:(p[0]-min[0])/(max[0]-min[0])*f.width,y:(p[2]-min[2])/(max[2]-min[2])*f.height});
  const lo=logical(info.bounds.min),hi=logical(info.bounds.max),pending=new WeakMap(),initialized=new WeakSet(),identity=e=>scope+':'+e.id;
  const world={...RESOURCE_WORLD,sourceCollisionWindow:true,bounds:{minX:lo.x,minY:lo.y,maxX:hi.x,maxY:hi.y}};
  const point=(x,y)=>({x:min[0]+x/f.width*(max[0]-min[0]),y:0,z:min[2]+y/f.height*(max[2]-min[2])});
  const ground=(x,z,top)=>rpc.request('ground',{point:[x,z,top]});
  function place(entity){const p=point(entity.x,entity.y),floor=rpc.request('sample',{point:[p.x,p.z]}).height,
    h=ground(p.x,p.z,Number.isFinite(entity.worldY)?entity.worldY+.5:floor+.5);
    entity.worldY=h.height;entity.grounded=true;entity.jump=null;initialized.delete(entity);}
  function move(entity,input,dt){
    const p=point(entity.x,entity.y),n=Math.max(1,Math.hypot(input.x,input.y)),speed=world.speed*(max[0]-min[0])/f.width;
    if(!initialized.has(entity)){rpc.request('reset',{identity:identity(entity),position:[p.x,entity.worldY,p.z]});initialized.add(entity);}
    const control=pending.get(entity)||{pressed:false,request:false};const now=Date.now();
    const result=rpc.request('tick',{identity:identity(entity),position:[p.x,entity.worldY,p.z],velocity:[input.x/n*speed,input.y/n*speed],milliseconds:Math.round(dt*1000),jump:control.request});
    control.request=false;pending.set(entity,control);Object.assign(entity,logical(result.position),{worldY:result.position[1],grounded:result.grounded});
    entity.sourcePosture=result.lastPosture;entity.sourceVelocityY=result.velocityY;
    if(!result.grounded){
      if(!entity.jump)entity.jump={physics:'source-world-v1',startedAt:now,updatedAt:now,endsAt:now+60000,moving:Math.hypot(input.x,input.y)>0,falling:result.lastPosture===0x30,stationaryAvailable:false,landedAt:null};
      entity.jump.updatedAt=now;entity.jump.height=Math.max(0,entity.worldY-ground(result.position[0],result.position[2],entity.worldY).height);
    }else if(entity.jump&&entity.jump.landedAt===null){entity.jump.landedAt=now;entity.jump.landAt=now;entity.jump.endsAt=now+300;entity.jump.height=0;}
    if(entity.jump&&now>=entity.jump.endsAt)entity.jump=null;
  }
  return {sourceNative:true,world,point,logical:p=>logical(p.toArray?p.toArray():[p.x,p.y,p.z]),place,move,step:.5,
    profile:{format:'oc2-source-native-physics-v1',instances:info.instanceIds.map(id=>({id})),nativeSHA256:info.nativeSHA256},
    support:(x,z,top)=>ground(x,z,top).height,terrainHeight:(x,z)=>rpc.request('sample',{point:[x,z]}).height,
    raycast:(a,b)=>{const h=rpc.request('ray',{from:[a.x,a.y,a.z],to:[b.x,b.y,b.z]});return h?{...h,normal:{x:h.normal[0],y:h.normal[1],z:h.normal[2]},point:{x:h.point[0],y:h.point[1],z:h.point[2]}}:null;},
    jumpPressed:(entity,pressed)=>{const state=pending.get(entity)||{pressed:false,request:false};if(pressed&&!state.pressed)state.request=true;state.pressed=pressed;pending.set(entity,state);},
    settle:()=>{},fork:()=>bind(rpc,info),close:()=>rpc.close()};
}
export function loadNativeWindowCollision(configURL=new URL('../native-physics.json',import.meta.url)){
  if(!existsSync(configURL))return null;
  const config=JSON.parse(readFileSync(configURL,'utf8')),rpc=new NativeRPC(config);
  try{return bind(rpc,rpc.request('init'));}catch(e){rpc.close();throw e;}
}
