// CPU constructor/matrix/clock check; actual shader compilation is browser QA.
import fs from 'node:fs/promises';import path from 'node:path';import os from 'node:os';import {pathToFileURL}from'node:url';import assert from'node:assert/strict';
const[candidate,threePath,envFile]=process.argv.slice(2);if(!envFile)throw Error('Usage: node selection_scene_water_surface_tests.mjs APPEND THREE_MODULE FRESH_ENV_JSON');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-surface-'));
try{
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');await fs.copyFile(new URL('./preview/selection_scene_water_surface.js',import.meta.url),path.join(temp,'surface.js'));
 const THREE=await import(pathToFileURL(path.resolve(threePath))),{createSelectionWaterSurfaceAppend,selectionWaterBump,validateSelectionWaterSurface}=await import(pathToFileURL(path.join(temp,'surface.js')));
 const file=u=>path.join(path.resolve(candidate),u.replace(/^\//,'')),json=async u=>JSON.parse(await fs.readFile(file(u),'utf8')),text=u=>fs.readFile(file(u),'utf8');
 const p=await json('/assets/source-selection-water-surface/overlay.json');validateSelectionWaterSurface(p);const bad=structuredClone(p);bad.selection.sourceBatching=false;assert.throws(()=>validateSelectionWaterSurface(bad));
 for(const [t,offset]of Object.entries(p.scroll.probe))assert.deepEqual(selectionWaterBump(Number(t),p.scroll),offset);
 const env=JSON.parse(await fs.readFile(envFile,'utf8')),uniforms=Object.fromEntries(Object.entries(env.uniformInputs).map(([k,v])=>[k,{value:Array.isArray(v)?(v.length===3?new THREE.Vector3(...v):new THREE.Vector2(...v)):v}]));
 const origin=new THREE.Vector3(-2583,0,-100),lighting={sourceSelectionRegion:211,uniforms};let seconds=1;
 const texture=async u=>{const b=await fs.readFile(file(u));return new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});};
 const result=await createSelectionWaterSurfaceAppend(THREE,p,{origin,lighting,json,text,texture,clock:{value:()=>seconds}});assert.equal(result.chunks,152);assert.equal(result.tiles,9);
 const camera={position:new THREE.Vector3(20,140,80),projectionMatrix:new THREE.Matrix4(),matrixWorldInverse:new THREE.Matrix4()};let gd=0,md=0,vertices=0,indices=0;
 for(const mesh of result.root.children){
  const row=p.tiles.find(t=>JSON.stringify(t.tile)===JSON.stringify(mesh.userData.selectionWaterSurface.tile)),source=await json(row.batch.url);vertices+=mesh.geometry.attributes.position.count;indices+=mesh.geometry.index.count;
  assert.deepEqual([...mesh.geometry.index.array],source.indices);assert.deepEqual([...mesh.geometry.attributes.TexCoord0.array],source.uvs);
  assert.deepEqual([...mesh.geometry.attributes.position.array],source.positions.map((v,i)=>Math.fround(v-origin.getComponent(i%3))));
  const m=mesh.material;assert.equal(m.depthWrite,false);assert.equal(m.depthTest,true);assert.equal(m.side,THREE.DoubleSide);assert.equal(m.blending,THREE.CustomBlending);assert.equal(m.glslVersion,THREE.GLSL3);
  mesh.onBeforeRender(null,null,camera);assert.deepEqual(m.uniforms.camerapos.value.toArray(),camera.position.clone().add(origin).toArray());assert.deepEqual(m.uniforms.waterBumpOffset.value.toArray(),p.scroll.probe['1000']);
  assert.deepEqual(m.uniforms.global_light_waterSurface.value.toArray(),p.sourceWaterSurfaceRGB);assert.equal(m.uniforms.fadeAlpha.value,1);
  mesh.geometry.addEventListener('dispose',()=>gd++);m.addEventListener('dispose',()=>md++);
 }
 assert.equal(vertices,608);assert.equal(indices,912);seconds=2;result.root.children[0].onBeforeRender(null,null,camera);assert.deepEqual(result.materials[0].uniforms.waterBumpOffset.value.toArray(),selectionWaterBump(2000,p.scroll));
 result.dispose();assert.deepEqual([gd,md],[9,9]);console.log(JSON.stringify({cpuOnly:true,tiles:9,chunks:152,originalBatchVertices:608,triangles:304,ownSelectionReflection:true,source211WaterRGB:true,explicitClock:true,disposal:true,GLSLCompiled:false}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
