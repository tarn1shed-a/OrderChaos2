// Web-coordinate/worker adapter for the original CPU collision routines in a
// separate original ordinary-quest area. No fallback geometry or collision.
import {Worker} from 'node:worker_threads';
import {randomUUID} from 'node:crypto';

class NativeQuestRPC{
  constructor(config,threadURL){this.worker=new Worker(threadURL,{workerData:config,execArgv:[]});this.shared=new SharedArrayBuffer(65536);this.exited=new Promise(resolve=>this.worker.once('exit',resolve));this.worker.unref();}
  request(operation,data={}){
    if(this.failure)throw this.failure;
    const flag=new Int32Array(this.shared,0,2);Atomics.store(flag,0,0);this.worker.postMessage({operation,data,shared:this.shared});
    if(Atomics.wait(flag,0,0,20000)==='timed-out'){
      // The existing recovery supervisor recognizes this transport failure.
      // Never reuse the shared buffer after a possibly late native response.
      this.failure=Error('原碰撞执行超时；没有切换到替代算法');this.close();throw this.failure;
    }
    const response=JSON.parse(new TextDecoder().decode(new Uint8Array(this.shared,8,Atomics.load(flag,1))));
    if(response.error)throw Error(response.error);return response.result;
  }
  close(){if(this.closed)return this.closed;if(this.worker.threadId!==-1){this.worker.ref();this.worker.postMessage({close:true});}return this.closed=this.exited;}
}

export function bindQuestMotion(rpc,info,entry,scope=randomUUID(),playerChoice=null){
  const f=info.frame,min=f.min,max=f.max;
  if(![...min,...max,f.width,f.height].every(Number.isFinite)||max[0]<=min[0]||max[2]<=min[2])throw Error('普通任务坐标框架无效');
  const logical=p=>({x:(p[0]-min[0])/(max[0]-min[0])*f.width,y:(p[2]-min[2])/(max[2]-min[2])*f.height});
  const point=(x,y)=>({x:min[0]+x/f.width*(max[0]-min[0]),z:min[2]+y/f.height*(max[2]-min[2])});
  const world={width:f.width,height:f.height,speed:32,radius:2,obstacles:[],sourceCollisionWindow:true,
    bounds:{minX:0,minY:0,maxX:f.width,maxY:f.height},spawn:logical(entry),sourceMapId:1};
  const pending=new WeakMap(),initialized=new WeakSet(),identity=p=>scope+':'+p.id;
  const sourcePlayer=playerChoice?.(info);
  const ground=(x,z,top)=>rpc.request('ground',{point:[x,z,top]});
  const motion={sourceNative:true,sourceCameraCPU:false,world,point,logical:p=>logical(p.toArray?p.toArray():[p.x,p.y,p.z]),step:.5,
    profile:{format:'oc2-source-native-physics-v1',nativeSHA256:info.nativeSHA256,instances:info.instanceIds.map(id=>({id}))},
    place(p){const v=point(p.x,p.y),floor=rpc.request('sample',{point:[v.x,v.z]}).height;p.worldY=ground(v.x,v.z,floor+.5).height;p.grounded=true;p.jump=null;initialized.delete(p);},
    restoreHeight(p,height){const v=point(p.x,p.y);p.worldY=ground(v.x,v.z,height+.01).height;initialized.delete(p);},
    move(p,input,dt){
      const v=point(p.x,p.y),n=Math.max(1,Math.hypot(input.x,input.y)),speed=world.speed*(max[0]-min[0])/f.width;
      if(!initialized.has(p)){rpc.request('reset',{identity:identity(p),position:[v.x,p.worldY,v.z],...sourcePlayer?.reset(p,identity(p))});initialized.add(p);}
      const control=pending.get(p)||{pressed:false,request:false};
      const result=rpc.request('tick',{identity:identity(p),position:[v.x,p.worldY,v.z],velocity:[input.x/n*speed,input.y/n*speed],milliseconds:Math.round(dt*1000),jump:control.request,...sourcePlayer?.tick(p,identity(p),input)});
      const sourceFields=sourcePlayer?.consume(p,identity(p),result);
      control.request=false;pending.set(p,control);
      Object.assign(p,logical(result.position),{worldY:result.position[1],grounded:result.grounded,sourcePosture:result.lastPosture,sourceVelocityY:result.velocityY},sourceFields);
      if(!result.grounded&&[0x28,0x30].includes(result.lastPosture))p.jump={physics:'source-world-v1',startedAt:Date.now(),updatedAt:Date.now(),endsAt:Date.now()+60000,moving:Math.hypot(input.x,input.y)>0,falling:result.lastPosture===0x30,stationaryAvailable:false,landedAt:null};
      else if(result.grounded)p.jump=null;
    },
    jumpPressed(p,pressed){const c=pending.get(p)||{pressed:false,request:false};if(pressed&&!c.pressed)c.request=true;c.pressed=pressed;pending.set(p,c);},
    cameraInput(){},settle(){},support:(x,z,top)=>ground(x,z,top).height,terrainHeight:(x,z)=>rpc.request('sample',{point:[x,z]}).height,
    fork:()=>bindQuestMotion(rpc,info,entry,randomUUID(),playerChoice),close:()=>rpc.close()};
  return motion;
}

export function createQuestMotion(config,threadURL,entry,{playerChoice=null}={}){
  const rpc=new NativeQuestRPC(config,threadURL);
  try{return bindQuestMotion(rpc,rpc.request('init'),entry,randomUUID(),playerChoice);}catch(error){rpc.close();throw error;}
}
