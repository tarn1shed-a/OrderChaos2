import {readFileSync,existsSync} from 'node:fs';
import {Vector3,Matrix3,Matrix4,Quaternion,Box3,Ray} from 'three';
import {sampleHeight} from '../public/heightfield.js';
import {advance,walkable,RESOURCE_WORLD} from '../public/world.js';
import {nativeJumpStep,JUMP} from '../public/jump.js';
const V=a=>new Vector3(...a),UP=new Vector3(0,1,0);
const BOX_FACES=[[0,2,1],[1,2,3],[4,5,6],[5,7,6],[0,1,4],[1,5,4],[2,6,3],[3,6,7],[0,4,2],[2,4,6],[1,3,5],[3,7,5]];

export function createCollision(profile,terrain,world=RESOURCE_WORLD) {
  if(profile.format!=='oc2-scene-collision-v1'||!terrain.grid||!Array.isArray(profile.instances))throw new Error('碰撞资源版本不匹配');
  const min=terrain.bounds.min,max=terrain.bounds.max;
  const grid={width:terrain.grid.width,depth:terrain.grid.height,values:terrain.grid.heights};
  const margin=profile.query.forwardMargin,step=profile.query.stepProbeCap;
  if(!(margin>0&&margin<1&&step>0&&step<2))throw new Error('碰撞参数无效');
  const colliders=[];
  for(const instance of profile.instances) {
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
      colliders.push({triangles,box:new Box3().setFromPoints(vertices),instanceId:instance.id,flags:shape.flags,
        kind:shape.kind,inverse:matrix.clone().invert(),normalMatrix:new Matrix3().getNormalMatrix(matrix),half:shape.halfExtents});
    }
  }
  function point(x,y){return new Vector3(min[0]+x/world.width*(max[0]-min[0]),0,min[2]+y/world.height*(max[2]-min[2]));}
  function logical(p){return {x:(p.x-min[0])/(max[0]-min[0])*world.width,y:(p.z-min[2])/(max[2]-min[2])*world.height};}
  function terrainHeight(x,z){return sampleHeight(grid,(x-min[0])/(max[0]-min[0])*(grid.width-1),(z-min[2])/(max[2]-min[2])*(grid.depth-1));}
  function raycast(from,to,{extension=0,ground=false}={}){
    const direction=to.clone().sub(from),length=direction.length();if(length<1e-9)return null;
    direction.divideScalar(length);const ray=new Ray(from,direction),hit=new Vector3();let result=null,best=length+extension;
    for(const collider of colliders){
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
  function support(x,z,ceiling=Infinity){
    let height=terrainHeight(x,z);
    const top=Number.isFinite(ceiling)?ceiling:max[1]+100;
    const hit=raycast(new Vector3(x,top+1e-5,z),new Vector3(x,min[1]-100,z),{ground:true});
    if(hit&&hit.point.y<=top+1e-4&&hit.point.y>height)height=hit.point.y;
    return height;
  }
  function place(entity){const p=point(entity.x,entity.y);entity.worldY=Math.fround(support(p.x,p.z,terrainHeight(p.x,p.z)+step));entity.grounded=true;}
  function move(entity,input,dt,selectedWorld=world){
    if(!Number.isFinite(entity.worldY))place(entity);
    const proposal={x:entity.x,y:entity.y};advance(proposal,input,dt,selectedWorld);
    const from=point(entity.x,entity.y),to=point(proposal.x,proposal.y),delta=to.clone().sub(from),length=delta.length();
    if(length<1e-9)return;
    const lift=Math.min(length*profile.query.stepProbeMultiplier,step);
    from.y=to.y=entity.worldY+lift;
    const hit=raycast(from,to,{extension:margin});
    let destination=to;
    if(hit&&Math.abs(hit.normal.y)<profile.query.wallNormalYThreshold){
      const direction=delta.clone().normalize(),travel=Math.max(0,Math.min(length,hit.distance-margin));
      const contact=from.clone().addScaledVector(direction,travel);
      const remaining=to.clone().sub(contact),normal=hit.normal.clone();normal.y=0;normal.normalize();
      remaining.addScaledVector(normal,-remaining.dot(normal));
      const slid=contact.clone().add(remaining);
      const second=raycast(contact,slid,{extension:margin});
      destination=second?contact:slid;
    }
    const xy=logical(destination);
    if(walkable(xy.x,xy.y,selectedWorld)){entity.x=xy.x;entity.y=xy.y;}
    if(entity.grounded){
      const p=point(entity.x,entity.y),floor=support(p.x,p.z,entity.worldY+step);
      // An unsupported edge becomes a fall; a walking entity never snaps down
      // an arbitrary cliff. The source full landing state machine is separate.
      if(entity.worldY-floor<=step)entity.worldY=Math.fround(floor);else entity.grounded=false;
    }
  }
  function vertical(entity,nextY){
    const p=point(entity.x,entity.y),old=entity.worldY;
    if(nextY>old){
      const hit=raycast(new Vector3(p.x,old+step,p.z),new Vector3(p.x,nextY+step,p.z),{extension:margin});
      if(hit&&hit.normal.y<-.5)return {y:Math.fround(Math.max(old,hit.point.y-step-margin)),ceiling:true,grounded:false};
    }
    const floor=support(p.x,p.z,Math.max(old,nextY)+1e-4);
    return nextY<=floor+1e-5?{y:Math.fround(floor),grounded:true}:{y:nextY,grounded:false};
  }
  function settle(entity){
    if(!Number.isFinite(entity.worldY))place(entity);
    if(entity.grounded)return;
    const state=nativeJumpStep({height:entity.worldY,velocity:entity.fallVelocity??0,acceleration:entity.fallAcceleration??JUMP.gravity},50);
    const contact=vertical(entity,state.height);entity.worldY=contact.y;entity.grounded=contact.grounded;
    entity.fallVelocity=contact.grounded?0:state.velocity;entity.fallAcceleration=state.acceleration;
  }
  return {point,logical,terrainHeight,support,raycast,place,move,vertical,settle,colliders,margin,step};
}
export function loadCollision(root=new URL('../../game-data/converted/',import.meta.url)) {
  const path=new URL('maps/collision.json',root),map=new URL('maps/tutorial-preview.json',root);
  if(!existsSync(path))return null;
  if(!existsSync(map))throw new Error('碰撞资源缺少匹配地形');
  return createCollision(JSON.parse(readFileSync(path,'utf8')),JSON.parse(readFileSync(map,'utf8')));
}
