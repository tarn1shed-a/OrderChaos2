import {readFileSync,existsSync} from 'node:fs';
import {Vector3,Matrix3,Matrix4,Quaternion,Box3,Ray} from 'three';
import {sampleHeight} from '../public/heightfield.js';
import {advance,walkable,RESOURCE_WORLD} from '../public/world.js';
import {nativeJumpStep,JUMP} from '../public/jump.js';
const V=a=>new Vector3(...a),UP=new Vector3(0,1,0);
const BOX_FACES=[[0,2,1],[1,2,3],[4,5,6],[5,7,6],[0,1,4],[1,5,4],[2,6,3],[3,6,7],[0,4,2],[2,4,6],[1,3,5],[3,7,5]];

export function createCollision(profile,terrain,world=RESOURCE_WORLD) {
  if(profile.format!=='oc2-scene-collision-v2'||!terrain.grid||!Array.isArray(profile.instances))throw new Error('碰撞资源版本不匹配');
  const min=terrain.bounds.min,max=terrain.bounds.max;
  const grid={width:terrain.grid.width,depth:terrain.grid.height,values:terrain.grid.heights};
  const margin=profile.query.forwardMargin,step=profile.query.stepProbeCap;
  if(!(margin>0&&margin<1&&step>0&&step<2))throw new Error('碰撞参数无效');
  const colliders=[],dynamic=new Map();
  function appendInstance(instance,target=colliders) {
    const source=profile.sources[instance.sourcePHY];if(!source)throw new Error('碰撞实例缺少源形状');
    const transform=new Matrix4().compose(V(instance.position),new Quaternion(...instance.quaternion),V(instance.scale));
    for(const shape of source.shapes) {
      const matrix=transform.clone().multiply(new Matrix4().makeTranslation(...shape.center)).multiply(new Matrix4().makeRotationY(shape.yawRadians));
      let points,faces;
      if(shape.kind==='box'||shape.kind==='cylinder'){
        const [x,y]=shape.halfExtents,z=shape.kind==='cylinder'?x:shape.halfExtents[2];
        points=Array.from({length:8},(_,i)=>[i&1?x:-x,i&2?y:-y,i&4?z:-z]);faces=BOX_FACES;
      }else if(shape.kind==='polyhedron'){points=shape.vertices;faces=shape.faces;}
      else throw new Error('未知碰撞形状');
      const vertices=points.map(p=>V(p).applyMatrix4(matrix));
      if(vertices.some(p=>!p.toArray().every(Number.isFinite)))throw new Error('碰撞形状包含无效坐标');
      const triangles=faces.map(face=>{
        if(face.slice(0,3).some(i=>!vertices[i]))throw new Error('碰撞面索引无效');
        const [a,b,c]=face.map(i=>vertices[i]);const normal=b.clone().sub(a).cross(c.clone().sub(a)).normalize();
        return {a,b,c,normal,flags:face[3]??0};
      });
      target.push({triangles,box:new Box3().setFromPoints(vertices),instanceId:instance.id,flags:shape.flags,
        kind:shape.kind,inverse:matrix.clone().invert(),normalMatrix:new Matrix3().getNormalMatrix(matrix),half:shape.halfExtents});
    }
  }
  for(const instance of profile.instances)appendInstance(instance);
  function updateDynamic(instance){
    if(typeof instance.id!=='string'||!instance.id)throw new Error('动态碰撞对象缺少身份');
    const next=[];appendInstance(instance,next);
    for(const shape of next)Object.assign(shape,{dynamic:true,ownerId:instance.ownerId??null,
      disabled:Boolean(instance.disabled),extendedDisabled:Boolean(instance.extendedDisabled)});
    dynamic.set(instance.id,next);
  }
  function point(x,y){return new Vector3(min[0]+x/world.width*(max[0]-min[0]),0,min[2]+y/world.height*(max[2]-min[2]));}
  function logical(p){return {x:(p.x-min[0])/(max[0]-min[0])*world.width,y:(p.z-min[2])/(max[2]-min[2])*world.height};}
  function terrainHeight(x,z){return sampleHeight(grid,(x-min[0])/(max[0]-min[0])*(grid.width-1),(z-min[2])/(max[2]-min[2])*(grid.depth-1));}
  function raycast(from,to,{extension=0,ground=false,excludeOwner=null,extendedFilter=false}={}){
    const direction=to.clone().sub(from),length=direction.length();if(length<1e-9)return null;
    direction.divideScalar(length);const ray=new Ray(from,direction),hit=new Vector3();let result=null,best=length+extension;
    // Native 363d30 queries registered runtime objects before static tiles,
    // excludes the querying owner, and filters byte 0x118 and the optional byte-0x11a filter.
    for(const collider of [...dynamic.values()].flat().concat(colliders)){
      if(collider.disabled||(extendedFilter&&collider.extendedDisabled)||(excludeOwner!==null&&collider.ownerId===excludeOwner))continue;
      if(!ray.intersectsBox(collider.box))continue;
      if(collider.kind==='cylinder'){
        const o=from.clone().applyMatrix4(collider.inverse),d=from.clone().add(direction).applyMatrix4(collider.inverse).sub(o);
        const [radius,height]=collider.half,a=d.x*d.x+d.z*d.z,b=2*(o.x*d.x+o.z*d.z),c=o.x*o.x+o.z*o.z-radius*radius;
        const tests=[];const disc=b*b-4*a*c;
        if(a>1e-12&&disc>=0)for(const t of [(-b-Math.sqrt(disc))/(2*a),(-b+Math.sqrt(disc))/(2*a)]){
          const p=o.clone().addScaledVector(d,t);if(Math.abs(p.y)<=height)tests.push({t,n:new Vector3(p.x,0,p.z).normalize()});
        }
        if(Math.abs(d.y)>1e-12)for(const sign of [-1,1]){
          const t=(sign*height-o.y)/d.y,p=o.clone().addScaledVector(d,t);
          if(p.x*p.x+p.z*p.z<=radius*radius+1e-9)tests.push({t,n:new Vector3(0,sign,0)});
        }
        for(const {t,n} of tests){
          n.applyNormalMatrix(collider.normalMatrix);if(t<1e-7||t>best||(ground&&n.y<.5))continue;
          best=t;if(n.dot(direction)>0)n.negate();result={distance:t,point:from.clone().addScaledVector(direction,t),normal:n,instanceId:collider.instanceId,shapeFlags:collider.flags};
        }
        continue;
      }
      for(const triangle of collider.triangles){
        if(ground&&triangle.normal.y<.5)continue;
        if(!ray.intersectTriangle(triangle.a,triangle.b,triangle.c,false,hit))continue;
        const distance=hit.distanceTo(from);if(distance>best||distance<1e-7)continue;
        best=distance;const normal=triangle.normal.clone();if(normal.dot(direction)>0)normal.negate();
        result={distance,point:hit.clone(),normal,instanceId:collider.instanceId,shapeFlags:collider.flags,faceFlags:triangle.flags};
      }
    }
    return result;
  }
  function support(x,z,ceiling=Infinity,options={}){
    let height=terrainHeight(x,z);
    const top=Number.isFinite(ceiling)?ceiling:max[1]+100;
    const hit=raycast(new Vector3(x,top+1e-5,z),new Vector3(x,min[1]-100,z),{...options,ground:true});
    if(hit&&hit.point.y<=top+1e-4&&hit.point.y>height)height=hit.point.y;
    return height;
  }
  // The old point foot fell between stair lips while the forward clearance
  // ray stopped the centre before it could reach the next tread. Use the
  // existing actor radius for a small support footprint; source PHY geometry
  // and the maximum step query remain unchanged.
  const radiusX=Math.max(margin,world.radius/world.width*(max[0]-min[0])),radiusZ=Math.max(margin,world.radius/world.height*(max[2]-min[2]));
  const footprint=[[0,0],[1,0],[-1,0],[0,1],[0,-1],...[[-1,-1],[-1,1],[1,-1],[1,1]].map(([x,z])=>[x*Math.SQRT1_2,z*Math.SQRT1_2])];
  function footSupport(x,z,ceiling,options={}){
    return Math.max(...footprint.map(([dx,dz])=>support(x+dx*radiusX,z+dz*radiusZ,ceiling,options)));
  }
  function place(entity){const p=point(entity.x,entity.y);entity.worldY=Math.fround(footSupport(p.x,p.z,terrainHeight(p.x,p.z)+step));entity.grounded=true;}
  function move(entity,input,dt,selectedWorld=world){
    if(!Number.isFinite(entity.worldY))place(entity);
    const proposal={x:entity.x,y:entity.y};advance(proposal,input,dt,selectedWorld);
    const from=point(entity.x,entity.y),to=point(proposal.x,proposal.y),delta=to.clone().sub(from),length=delta.length();
    if(length<1e-9)return;
    if(entity.grounded){
      const floor=footSupport(from.x,from.z,entity.worldY+step,{excludeOwner:entity.id??null});
      if(floor>entity.worldY&&floor-entity.worldY<=step){
        const overhead=raycast(new Vector3(from.x,entity.worldY+step,from.z),new Vector3(from.x,floor+step,from.z),{excludeOwner:entity.id??null});
        if(!overhead||overhead.normal.y>=-.5)entity.worldY=Math.fround(floor);
      }
    }
    const lift=Math.min(length*profile.query.stepProbeMultiplier,step);
    from.y=to.y=entity.worldY+lift;
    const hit=raycast(from,to,{extension:margin,excludeOwner:entity.id??null});
    let destination=to;
    if(hit&&Math.abs(hit.normal.y)<profile.query.wallNormalYThreshold){
      const direction=delta.clone().normalize(),travel=Math.max(0,Math.min(length,hit.distance-margin));
      const contact=from.clone().addScaledVector(direction,travel);
      const remaining=to.clone().sub(contact),normal=hit.normal.clone();normal.y=0;normal.normalize();
      remaining.addScaledVector(normal,-remaining.dot(normal));
      const slid=contact.clone().add(remaining);
      const second=raycast(contact,slid,{extension:margin,excludeOwner:entity.id??null});
      destination=second?contact:slid;
    }
    const xy=logical(destination);
    if(walkable(xy.x,xy.y,selectedWorld)){entity.x=xy.x;entity.y=xy.y;}
    if(entity.grounded){
      const p=point(entity.x,entity.y),floor=footSupport(p.x,p.z,entity.worldY+step,{excludeOwner:entity.id??null});
      // An unsupported edge becomes a fall; a walking entity never snaps down
      // an arbitrary cliff. The source full landing state machine is separate.
      if(Math.abs(entity.worldY-floor)<=step)entity.worldY=Math.fround(floor);else entity.grounded=false;
    }
  }
  function vertical(entity,nextY){
    const p=point(entity.x,entity.y),old=entity.worldY;
    if(nextY>old){
      const hit=raycast(new Vector3(p.x,old+step,p.z),new Vector3(p.x,nextY+step,p.z),{extension:margin,excludeOwner:entity.id??null});
      if(hit&&hit.normal.y<-.5)return {y:Math.fround(Math.max(old,hit.point.y-step-margin)),ceiling:true,grounded:false};
    }
    const floor=footSupport(p.x,p.z,Math.max(old,nextY)+1e-4,{excludeOwner:entity.id??null});
    return nextY<=floor+1e-5?{y:Math.fround(floor),grounded:true}:{y:nextY,grounded:false};
  }
  function settle(entity){
    if(!Number.isFinite(entity.worldY))place(entity);
    if(entity.grounded)return;
    const state=nativeJumpStep({height:entity.worldY,velocity:entity.fallVelocity??0,acceleration:entity.fallAcceleration??JUMP.gravity},50);
    const contact=vertical(entity,state.height);entity.worldY=contact.y;entity.grounded=contact.grounded;
    entity.fallVelocity=contact.grounded?0:state.velocity;entity.fallAcceleration=state.acceleration;
  }
  return {point,logical,terrainHeight,support,footSupport,raycast,place,move,vertical,settle,colliders,margin,step,
    updateDynamic,removeDynamic:id=>dynamic.delete(id),dynamicIds:()=>[...dynamic.keys()],
    fork:()=>createCollision(profile,terrain,world),profile};
}
export function loadCollision(root=new URL('../../game-data/converted/',import.meta.url)) {
  const path=new URL('maps/collision.json',root),map=new URL('maps/tutorial-preview.json',root);
  if(!existsSync(path))return null;
  if(!existsSync(map))throw new Error('碰撞资源缺少匹配地形');
  return createCollision(JSON.parse(readFileSync(path,'utf8')),JSON.parse(readFileSync(map,'utf8')));
}
