// CPU binding test; genuine GPU compilation and screenshots are separate QA.
import fs from'node:fs/promises';import path from'node:path';import os from'node:os';import{pathToFileURL}from'node:url';import assert from'node:assert/strict';
const[candidate,base,threePath,envFile]=process.argv.slice(2);if(!envFile)throw Error('Usage: node FLOOR BASE THREE ENV');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-floor-'));
try{
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');await fs.copyFile(new URL('./preview/selection_scene_water_floor.js',import.meta.url),path.join(temp,'floor.js'));
 const geometry=await fs.readFile(new URL('./preview/source-map-geometry.js',import.meta.url),'utf8');await fs.writeFile(path.join(temp,'source-map-geometry.js'),geometry);
 const THREE=await import(pathToFileURL(path.resolve(threePath))),{createSelectionWaterFloorAppend,validateSelectionWaterFloor}=await import(pathToFileURL(path.join(temp,'floor.js')));
 const file=u=>path.join(path.resolve(u.startsWith('/assets/source-selection-water-floor/')?candidate:base),u.replace(/^\//,'')),json=async u=>JSON.parse(await fs.readFile(file(u),'utf8')),text=u=>fs.readFile(file(u),'utf8');
 const p=await json('/assets/source-selection-water-floor/overlay.json');validateSelectionWaterFloor(p);const bad=structuredClone(p);bad.nativeFinalLayerGroups=false;assert.throws(()=>validateSelectionWaterFloor(bad));
 const env=JSON.parse(await fs.readFile(envFile,'utf8')),uniforms=Object.fromEntries(Object.entries(env.uniformInputs).map(([k,v])=>[k,{value:Array.isArray(v)?(v.length===3?new THREE.Vector3(...v):new THREE.Vector2(...v)):v}]));
 const texture=async u=>{const b=await fs.readFile(file(u));return new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});};
 const origin=new THREE.Vector3(-2583,0,-100),r=await createSelectionWaterFloorAppend(THREE,p,{origin,lighting:{sourceSelectionRegion:211,uniforms},json,text,texture});
 assert.equal(r.floorRoot.children.length,9);assert.equal(r.borderRoot.children.length,152);let indices=0,gDisposed=0,mDisposed=0;
 const camera={position:new THREE.Vector3(20,140,80),projectionMatrix:new THREE.Matrix4(),matrixWorldInverse:new THREE.Matrix4()};
 for(const mesh of r.floorRoot.children){indices+=mesh.geometry.index.count;for(const m of mesh.material){assert.equal(m.depthFunc,THREE.LessDepth);assert.equal(m.depthWrite,true);assert.equal(m.glslVersion,THREE.GLSL3);assert.equal(m.defines.WATER,1);mesh.onBeforeRender(null,null,camera,null,m);assert.deepEqual(m.uniforms.global_light_lightMap.value.toArray(),p.sourceTerrainRGB);}}
  assert.equal(indices,152*384);assert(r.materials.some(m=>m.fragmentShader.includes('sourceFloorOutput.rgb = color;')&&m.fragmentShader.includes('sourceFloorOutput.a=1.0;')));
 for(const mesh of r.borderRoot.children){assert.equal(mesh.material.depthFunc,THREE.LessEqualDepth);assert.equal(mesh.material.depthWrite,false);assert.equal(mesh.renderOrder,-1);mesh.onBeforeRender(null,null,camera,null,mesh.material);}
 const special=r.floorRoot.children.find(m=>m.userData.selectionWaterFloor.tile.join(',')==='-41,-3');assert(special.material.some(m=>m.defines.TEXTURE_LAYER_MASK===7));
 const gs=new Set();r.root.traverse(o=>{if(o.geometry)gs.add(o.geometry);});for(const g of gs)g.addEventListener('dispose',()=>gDisposed++);for(const m of r.materials)m.addEventListener('dispose',()=>mDisposed++);
 r.dispose();assert.equal(gDisposed,10);assert.equal(mDisposed,r.materials.length);
 console.log(JSON.stringify({cpuOnly:true,wetChunks:152,borderChunks:152,triangles:indices/3,originalFinalLayerGroups:true,source211Environment:true,disposal:true,GLSLCompiled:false}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
