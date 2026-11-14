// Append only original dry chunks cleared by native per-chunk water bounds.
import {sourceTileVertex} from './source-map-geometry.js?geometry=2';
import {createLitTerrainMaterial,validateTerrainLighting} from './terrain-lighting-window.js?geometry=2';
import {guardSceneOrientation} from './scene-culling.js';
export const SELECTION_WATER_DRY_FORMAT='oc2-selection-scene-water-dry-append-v1';
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export function validateSelectionWaterDry(p,terrain,mats,lights){
 if(p?.format!==SELECTION_WATER_DRY_FORMAT||p.world!=='selection'||p.mapId!==7||p.sourceRegion!==211||p.profile!=='APK_Default'||
  p.originalPending!==344||p.restoredDryChunks!==192||p.remainingWetChunks!==152||p.nativeReaderExecuted!==true||p.freshStartOnly!==true||
  p.lightsChanged!==false||p.savesChanged!==false||p.geometrySourceChanged!==false||p.sourceWaterSurfaceActivated!==false||p.sourceWetFloorActivated!==false||
  terrain.world!=='selection'||mats.world!=='selection'||lights.world!=='selection'||terrain.sourceTiles?.length!==25)throw Error('原选角水边干地来源不匹配');
 validateTerrainLighting(terrain,mats,lights);
 let count=0;const seen=new Set();
 for(const row of p.rows){
  const mat=mats.tiles.find(t=>same(t.tile,row.tile));
  if(!mat||!terrain.sourceTiles.some(t=>same(t.tile,row.tile))||row.source!==`world/selection/terrain/${row.tile.map(v=>(v<0?'-':'')+String(Math.abs(v)).padStart(v<0?3:4,'0')).join('_')}.trn`||
   row.sourceSHA256!==mats.sources?.[row.source]?.sha256||row.chunks.length!==row.nativeFlags.length)throw Error('原选角水边干地区块来源缺失');
  for(const c of row.chunks){
   const j=c[1]*8+c[0],key=row.tile+':'+c,native=row.nativeFlags.find(x=>same(x.chunk,c));
   if(!c.every(v=>Number.isInteger(v)&&v>=0&&v<8)||seen.has(key)||!same(mat.chunks[j]?.chunk,c)||mat.chunks[j]?.sourceWaterPending!==true||
    !native||!Number.isInteger(native.flags)||(native.flags&0x10000)!==0)throw Error('不能重复干地或把原湿区套干地');
   const indices=p.triangleIndices?.[String((row.tile[0]+row.tile[1])&1)]?.[j];
   if(indices?.length!==384||indices.some(v=>!Number.isInteger(v)||v<0||v>=4225||v%65<c[0]*8||v%65>c[0]*8+8||Math.floor(v/65)<c[1]*8||Math.floor(v/65)>c[1]*8+8))throw Error('原CPU干地区块索引不匹配');
   seen.add(key);count++;
  }
 }
 if(count!==192)throw Error('原水边干地区块数量不匹配');return p;
}

export async function createSelectionWaterDryAppend(THREE,p,{origin,lighting,json,texture}){
 if(lighting?.sourceSelectionRegion!==211||!same(lighting.uniforms?.sourceTerrainLight?.value?.toArray(),p.sourceTerrainLightReference)||!origin||![origin.x,origin.y,origin.z].every(Number.isFinite))throw Error('原211环境/原点未接线');
 const [terrain,mats,lights]=await Promise.all([p.terrain,p.terrainMaterials,p.terrainLighting].map(json));validateSelectionWaterDry(p,terrain,mats,lights);
 const root=new THREE.Group(),geometries=[],materials=[],maps=new Map(),owned=new Set();
 const dispose=()=>{root.removeFromParent();for(const g of geometries)g.dispose();for(const m of materials)m.dispose();for(const t of owned)t.dispose();};
 async function sampler(url,repeat){
  const key=`${repeat}:${url}`;
  if(!maps.has(key))maps.set(key,Promise.resolve(texture(url,THREE.NoColorSpace)).then(raw=>{
   const t=raw.clone();t.colorSpace=THREE.NoColorSpace;t.flipY=false;t.wrapS=t.wrapT=repeat?THREE.RepeatWrapping:THREE.ClampToEdgeWrapping;t.needsUpdate=true;owned.add(t);return t;
  }));return maps.get(key);
 }
 const empty=new THREE.DataTexture(new Uint8Array(4),1,1);empty.flipY=false;empty.needsUpdate=true;owned.add(empty);
 try{
  for(const row of p.rows){
   const tile=terrain.sourceTiles.find(t=>same(t.tile,row.tile)),mat=mats.tiles.find(t=>same(t.tile,row.tile)),light=lights.tiles.find(t=>same(t.tile,row.tile));
   const positions=[],normals=[],uv=[],maskUV=[],colors=[],groups=new Map();
   for(let z=0;z<=64;z++)for(let x=0;x<=64;x++){
    const v=sourceTileVertex(tile,x,z);positions.push(v.position[0]-origin.x,v.position[1]-origin.y,v.position[2]-origin.z);normals.push(...v.normal);colors.push(...v.color);uv.push(x/8,z/8);maskUV.push(x/64,z/64);
   }
   for(const c of row.chunks){const j=c[1]*8+c[0],layers=mat.chunks[j].effectiveIndices,key=layers.join(',');
    if(!groups.has(key))groups.set(key,{layers,indices:[]});groups.get(key).indices.push(...p.triangleIndices[String((row.tile[0]+row.tile[1])&1)][j]);}
   const g=new THREE.BufferGeometry();geometries.push(g);
   for(const [n,a,s]of [['position',positions,3],['normal',normals,3],['uv',uv,2],['terrainMaskUV',maskUV,2]])g.setAttribute(n,new THREE.Float32BufferAttribute(a,s));
   g.setAttribute('terrainSourceColor',new THREE.Uint8BufferAttribute(colors,4,true));const indices=[],ms=[];
   const mask=mat.mask?await sampler(mat.mask.url,false):empty,atlas=await sampler(light.lightmap.url,true);
   for(const row of groups.values()){
    const textures=await Promise.all(row.layers.map(i=>sampler(i>=0?mat.textures[i].url:mats.fallback,true)));
    const m=createLitTerrainMaterial(THREE,row.layers,textures,mask,atlas,lighting);materials.push(m);g.addGroup(indices.length,row.indices.length,ms.length);indices.push(...row.indices);ms.push(m);
   }
   g.setIndex(indices);g.computeBoundingSphere();const mesh=new THREE.Mesh(g,ms);mesh.userData.selectionWaterDry={tile:row.tile,chunks:row.chunks};root.add(mesh);guardSceneOrientation(mesh);
  }
  root.updateMatrixWorld(true);return {root,materials,chunks:192,tiles:p.rows.length,remainingWet:152,originalGPUObserved:false,dispose};
 }catch(error){dispose();throw error;}
}
