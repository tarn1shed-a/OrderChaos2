// Inspection-world adapter. PHY data and the grounded consumer are source-backed;
// shape intersection and input cadence remain host adapters. Airborne is absent.
import {readFileSync,existsSync}from'node:fs';
import {Vector3}from'three';
import {createCollision}from'./collision.mjs';
import {RESOURCE_WORLD,advance,walkable}from'../public/world.js';
import {sourceGroundedMove}from'../public/source-walk.js';
import {sourceTerrainSample}from'../public/source-height.js';
const f=Math.fround,V=a=>new Vector3(...a),length3=d=>f(Math.sqrt(f(f(f(d[0]*d[0])+f(d[1]*d[1]))+f(d[2]*d[2]))));
export function createSourceWindowCollision(profile,terrain,legacy,materials){
  if(profile.sourceMovement!=='a878c0-grounded-only'||!terrain.sourceTiles)throw Error('Original window collision data missing');
  if(materials.tiles.some(t=>t.chunks.some(c=>c.flags&0x20000)))throw Error('Original disabled-ground chunks need a separate consumer');
  const frame=profile.coordinateFrame,min=frame.min,max=frame.max;
  const logical=p=>({x:(p[0]-min[0])/(max[0]-min[0])*frame.width,y:(p[2]-min[2])/(max[2]-min[2])*frame.height});
  const lo=logical(terrain.bounds.min),hi=logical(terrain.bounds.max);
  const world={...RESOURCE_WORLD,bounds:{minX:lo.x,minY:lo.y,maxX:hi.x,maxY:hi.y},sourceCollisionWindow:true};
  const shapeWorld=createCollision(profile,legacy,RESOURCE_WORLD),point=shapeWorld.point;
  const tiles=terrain.sourceTiles,lightTiles=new Map(materials.tiles.map(t=>[t.tile.join(','),t]));
  const sample=(x,z)=>sourceTerrainSample(tiles,x,z);
  const available=(x,z)=>{
    try{const s=sample(x,z);return lightTiles.get(s.tile.join(','))?.chunks[s.chunk]?.sourceWaterPending===false;}
    catch{return false;}
  };
  let observer=null;
  function rawRay(a,b){const h=shapeWorld.raycast(V(a),V(b)),hit=h?{distance:f(h.distance),normal:h.normal.toArray().map(f),instanceId:h.instanceId}:null;
    observer?.({from:a.slice(),to:b.slice(),hit});return hit;}
  function ray(a,b,margin){
    const d=b.map((v,i)=>f(v-a[i]));let length=length3(d);
    if(length===0)return null;
    const inv=f(1/length),n=d.map(v=>f(v*inv)),extended=a.map((v,i)=>f(v+f(f(length+margin)*n[i])));
    const actual=extended.map((v,i)=>f(v-a[i]));length=length3(actual);
    const unit=actual.map(v=>f(v*f(1/length))),hit=rawRay(a,extended);
    if(!hit)return null;const travel=Math.max(f(hit.distance-margin),0);
    return {...hit,point:a.map((v,i)=>f(v+f(unit[i]*travel)))};
  }
  function ground(x,z,top){
    const s=sample(x,z),bottom=s.height<=top?s.height:-400;
    const hit=rawRay([x,top,z],[x,bottom,z]);
    return hit?{height:f(top-hit.distance),normal:hit.normal,instanceId:hit.instanceId}:s;
  }
  function support(x,z,top=Infinity){return ground(x,z,Number.isFinite(top)?f(top):terrain.bounds.max[1]+100).height;}
  function place(entity){const p=point(entity.x,entity.y);entity.worldY=f(support(p.x,p.z,sample(p.x,p.z).height+.5));entity.grounded=true;}
  function move(entity,input,dt){
    if(!Number.isFinite(entity.worldY))place(entity);
    if(!entity.grounded)return; // The original airborne consumer is outside this bounded port.
    const target={x:entity.x,y:entity.y};advance(target,input,dt,world);
    const a=point(entity.x,entity.y),b=point(target.x,target.y);
    if(!available(b.x,b.z))return; // Missing original water consumer stays unavailable.
    const result=sourceGroundedMove([a.x,entity.worldY,a.z],[b.x-a.x,0,b.z-a.z],{ray,ground});
    const xy=logical(result.position);if(!walkable(xy.x,xy.y,world))return;
    Object.assign(entity,xy,{worldY:result.position[1],sourceWalkCode:result.code});
  }
  return {...shapeWorld,profile,world,point,logical:p=>logical(p.toArray?p.toArray():p),terrainHeight:(x,z)=>sample(x,z).height,
    sample,available,rawRay,ray,ground,support,place,move,
    vertical:()=>{throw Error('Original airborne consumer not recovered');},settle:()=>{},traceQueries:fn=>{observer=fn;},
    fork:()=>createSourceWindowCollision(profile,terrain,legacy,materials)};
}
export function loadSourceWindowCollision(root=new URL('../../game-data/converted/',import.meta.url)){
  const p=new URL('maps/window-collision.json',root);if(!existsSync(p))return null;
  const read=n=>JSON.parse(readFileSync(new URL(n,root),'utf8'));
  return createSourceWindowCollision(read('maps/window-collision.json'),read('maps/tutorial-window.json'),read('maps/tutorial-preview.json'),read('geometry-map/terrain-materials.json'));
}
