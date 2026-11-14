// Independent192 dry native chunks; original geometry and verified211 inputs.
import fs from 'node:fs/promises';import path from 'node:path';import os from 'node:os';
import {pathToFileURL} from 'node:url';import assert from 'node:assert/strict';
const[candidate,base,publicDir,threePath,envFile]=process.argv.slice(2);
if(!envFile)throw Error('Usage: node selection_scene_water_tests.mjs APPEND BASE PUBLIC_DIR THREE_MODULE FRESH_ENV_JSON');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-water-'));
try{
 for(const n of await fs.readdir(publicDir))if(n.endsWith('.js'))await fs.symlink(path.resolve(publicDir,n),path.join(temp,n));
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');
 await fs.copyFile(new URL('./preview/selection_scene_water_material.js',import.meta.url),path.join(temp,'selection_scene_water_material.js'));
 const THREE=await import(pathToFileURL(path.resolve(threePath)));
 const {validateSelectionWaterDry,createSelectionWaterDryAppend}=await import(pathToFileURL(path.join(temp,'selection_scene_water_material.js')));
 const file=u=>path.join(path.resolve(u.startsWith('/assets/source-selection-water/')?candidate:base),u.replace(/^\//,''));
 const json=async u=>JSON.parse(await fs.readFile(file(u),'utf8')),p=await json('/assets/source-selection-water/overlay.json');
 const [terrain,mats,lights]=await Promise.all([p.terrain,p.terrainMaterials,p.terrainLighting].map(json));validateSelectionWaterDry(p,terrain,mats,lights);
 const bad=structuredClone(p);bad.rows[0].nativeFlags[0].flags|=0x10000;assert.throws(()=>validateSelectionWaterDry(bad,terrain,mats,lights),/原湿区/);
 const duplicate=structuredClone(p);duplicate.rows[0].chunks.push(duplicate.rows[0].chunks[0]);duplicate.rows[0].nativeFlags.push(duplicate.rows[0].nativeFlags[0]);assert.throws(()=>validateSelectionWaterDry(duplicate,terrain,mats,lights));
 const texture=async u=>{const b=await fs.readFile(file(u));return new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});};
 const env=JSON.parse(await fs.readFile(envFile,'utf8'));
 const uniforms=Object.fromEntries(Object.entries(env.uniformInputs).map(([k,v])=>[k,{value:Array.isArray(v)?(v.length===3?new THREE.Vector3(...v):new THREE.Vector2(...v)):v}]));
 const lighting={sourceSelectionRegion:211,uniforms},origin=new THREE.Vector3(-2583,0,-100);
 const result=await createSelectionWaterDryAppend(THREE,p,{origin,lighting,json,texture});assert.equal(result.chunks,192);assert.equal(result.tiles,10);assert.equal(result.remainingWet,152);
 let indexCount=0,gd=0,md=0,sceneLights=0;
 for(const mesh of result.root.children){
  const row=p.rows.find(r=>JSON.stringify(r.tile)===JSON.stringify(mesh.userData.selectionWaterDry.tile));
  indexCount+=mesh.geometry.index.count;assert.equal(mesh.geometry.index.count,row.chunks.length*384);
  const tile=terrain.sourceTiles.find(t=>JSON.stringify(t.tile)===JSON.stringify(row.tile));
  assert.equal(mesh.geometry.attributes.position.count,4225);assert.deepEqual([...mesh.geometry.index.array].sort((a,b)=>a-b),row.chunks.flatMap(c=>p.triangleIndices[String((row.tile[0]+row.tile[1])&1)][c[1]*8+c[0]]).sort((a,b)=>a-b));
  mesh.geometry.addEventListener('dispose',()=>gd++);
  for(const m of mesh.material){assert.equal(m.depthWrite,true);assert.equal(m.depthTest,true);assert.equal(m.transparent,false);assert.equal(m.side,THREE.FrontSide);assert.equal(m.uniforms.sourceTerrainLight.value,uniforms.sourceTerrainLight.value);m.addEventListener('dispose',()=>md++);}
 }
 result.root.traverse(o=>{if(o.isLight)sceneLights++;});assert.equal(sceneLights,0);assert.equal(indexCount,192*384);
 result.dispose();assert.equal(gd,10);assert.equal(md,result.materials.length);
 console.log(JSON.stringify({cpuOnly:true,tiles:10,restoredDryChunks:192,triangles:indexCount/3,remainingWet:152,originalFullResolutionCPUIndices:true,originalTRNHeightsAndColors:true,sourceRegion:211,waterSurfaceActivated:false,wetFloorActivated:false,lights:sceneLights,disposalObserved:true,GLSLCompiled:false}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
