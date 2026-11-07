import {existsSync,readFileSync} from 'node:fs';
import {Vector3} from 'three';
const distance=(a,b)=>Math.hypot(a[0]-b[0],a[2]-b[2]);
const midpoint=portal=>portal[0].map((v,i)=>(v+portal[1][i])/2);
function closest(point,vertices){
  const crosses=vertices.map((a,i)=>{const b=vertices[(i+1)%vertices.length];return (b[0]-a[0])*(point[2]-a[2])-(b[2]-a[2])*(point[0]-a[0]);});
  const inside=crosses.every(n=>n>=-1e-7)||crosses.every(n=>n<=1e-7);
  let best=null,score=Infinity;
  for(let i=1;i<vertices.length-1;i++){
    const [a,b,c]=[vertices[0],vertices[i],vertices[i+1]],den=(b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2]);
    if(Math.abs(den)<1e-10)continue;
    const u=((b[2]-c[2])*(point[0]-c[0])+(c[0]-b[0])*(point[2]-c[2]))/den;
    const v=((c[2]-a[2])*(point[0]-c[0])+(a[0]-c[0])*(point[2]-c[2]))/den,w=1-u-v;
    if(inside&&Math.min(u,v,w)>=-1e-6)return [point[0],a[1]*u+b[1]*v+c[1]*w,point[2]];
  }
  for(const [i,a]of vertices.entries()){
    const b=vertices[(i+1)%vertices.length],dx=b[0]-a[0],dz=b[2]-a[2],s=dx*dx+dz*dz;
    const t=s?Math.max(0,Math.min(1,((point[0]-a[0])*dx+(point[2]-a[2])*dz)/s)):0;
    const p=a.map((v,k)=>v+(b[k]-v)*t),d=distance(p,point);if(d<score){best=p;score=d;}
  }
  return best;
}
export function createNavigation(profile){
  if(profile?.format!=='oc2-source-navigation-v1'||!Array.isArray(profile.nodes)||!profile.nodes.length||profile.nodes.length>100000)throw new Error('导航资源版本不匹配');
  const nodes=profile.nodes;
  for(const n of nodes){
    if(!Array.isArray(n.vertices)||n.vertices.length<3||n.vertices.length>6||!Array.isArray(n.edges)||
      ![n.center,...n.vertices,...n.edges.flatMap(e=>e.portal||[])].every(v=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite))||
      n.edges.some(e=>!Number.isSafeInteger(e.to)||e.to<0||e.to>=nodes.length||e.portal?.length!==2))throw new Error('导航节点或连接无效');
  }
  function nearest(point,{maxDistance=3,maxHeight=2}={}){
    let result=null,score=Infinity;
    for(const [index,n]of nodes.entries()){
      const p=closest(point,n.vertices);if(!p)continue;const d=distance(p,point),height=Math.abs(p[1]-point[1]);
      if(d>maxDistance||height>maxHeight)continue;
      const cost=d+height*.2;if(cost<score){score=cost;result={index,point:p,distance:d};}
    }
    return result;
  }
  function path(start,end,{clear=()=>true,maxDistance=3,maxHeight=2}={}){
    const from=nearest(start,{maxDistance,maxHeight}),to=nearest(end,{maxDistance,maxHeight});
    if(!from||!to)return null;
    if(from.index===to.index)return clear(start,to.point)?{points:[to.point],polygons:[from.index],projectedEnd:to.distance>1e-5}:null;
    const open=new Set([from.index]),cost=new Map([[from.index,0]]),parents=new Map(),closed=new Set();let found=false;
    while(open.size){
      let current=null,best=Infinity;
      for(const id of open){const f=cost.get(id)+distance(nodes[id].center,nodes[to.index].center);if(f<best){best=f;current=id;}}
      open.delete(current);if(current===to.index){found=true;break;}closed.add(current);
      for(const edge of nodes[current].edges){
        if(closed.has(edge.to))continue;
        const portal=midpoint(edge.portal),a=current===from.index?from.point:nodes[current].center,b=edge.to===to.index?to.point:nodes[edge.to].center;
        if(!clear(a,portal)||!clear(portal,b))continue;
        const next=cost.get(current)+distance(nodes[current].center,nodes[edge.to].center);
        if(next>=(cost.get(edge.to)??Infinity))continue;
        cost.set(edge.to,next);parents.set(edge.to,{from:current,portal});open.add(edge.to);
      }
    }
    if(!found)return null;
    const points=[to.point],polygons=[to.index];let at=to.index;
    while(at!==from.index){const p=parents.get(at);points.unshift(p.portal);polygons.unshift(p.from);at=p.from;}
    return {points,polygons,projectedEnd:to.distance>1e-5};
  }
  return {profile,nearest,path};
}
export function loadNavigation(path=new URL('../../game-data/converted/maps/navigation.json',import.meta.url)){
  return existsSync(path)?createNavigation(JSON.parse(readFileSync(path,'utf8'))):null;
}

// Paths are world-space; the existing world/physics solver owns actual motion.
export class RouteFollower {
  constructor(navigation,motion){this.navigation=navigation;this.motion=motion;this.reset();}
  reset(){this.route=null;this.goal=null;this.plannedAt=-Infinity;this.stalledAt=null;this.remaining=0;}
  world(entity){const p=this.motion.point(entity.x,entity.y);return [p.x,entity.worldY??this.motion.terrainHeight(p.x,p.z),p.z];}
  clear(a,b){const hit=this.motion.raycast(new Vector3(a[0],a[1]+.5,a[2]),new Vector3(b[0],b[1]+.5,b[2]));return !hit||Math.abs(hit.normal.y)>=.5;}
  follow(entity,goal,now,dt,world){
    const from=this.world(entity),end=this.world(goal);
    if(!this.goal||distance(this.goal,end)>.6||Math.abs(this.goal[1]-end[1])>1||now-this.plannedAt>=500){
      this.route=this.navigation.path(from,end,{clear:(a,b)=>this.clear(a,b)});this.goal=end;this.plannedAt=now;
    }
    if(!this.route){this.stalledAt??=now;this.remaining=0;return {blocked:true,stalledMs:now-this.stalledAt};}
    while(this.route.points.length>1&&distance(from,this.route.points[0])<.12)this.route.points.shift();
    this.remaining=this.route.points.length;const next=this.route.points[0];
    if(!next||distance(from,end)<.12&&Math.abs(from[1]-end[1])<2){this.stalledAt=null;return {arrived:true};}
    if(!this.clear(from,next)){this.route=null;this.plannedAt=-Infinity;this.stalledAt??=now;return {blocked:true,stalledMs:now-this.stalledAt};}
    const target=this.motion.logical(new Vector3(...next)),dx=target.x-entity.x,dy=target.y-entity.y,d=Math.hypot(dx,dy);
    const step=world.speed*Math.min(dt,.05),factor=step>0?Math.min(1,d/step):0;
    const old={x:entity.x,y:entity.y,worldY:entity.worldY,grounded:entity.grounded};
    this.motion.move(entity,{x:d?dx/d*factor:0,y:d?dy/d*factor:0},dt,world);
    const after=this.world(entity),onMesh=this.navigation.nearest(after,{maxDistance:.12,maxHeight:2});
    if(!onMesh)Object.assign(entity,old);
    const travelled=Math.hypot(entity.x-old.x,entity.y-old.y);
    if(dt>0&&travelled<step*.15)this.stalledAt??=now;else if(travelled>0)this.stalledAt=null;
    return {blocked:this.stalledAt!==null,stalledMs:this.stalledAt===null?0:now-this.stalledAt,arrived:distance(this.world(entity),end)<.12&&Math.abs(entity.worldY-end[1])<2};
  }
}
