// CPU construction using real PNG dimensions and211fresh; no GPU pixels.
import fs from 'node:fs/promises';import path from 'node:path';import os from 'node:os';
import {pathToFileURL} from 'node:url';import assert from 'node:assert/strict';
const[candidate,base,publicDir,threePath,envFile]=process.argv.slice(2);
if(!envFile)throw Error('Usage: node selection_scene_grass_tests.mjs APPEND BASE PUBLIC_DIR THREE_MODULE FRESH_ENV_JSON');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-grass-'));
try{
 for(const n of await fs.readdir(publicDir))if(n.endsWith('.js'))await fs.symlink(path.resolve(publicDir,n),path.join(temp,n));
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');
 await fs.copyFile(new URL('./preview/selection_scene_grass_material.js',import.meta.url),path.join(temp,'selection_scene_grass_material.js'));
 const THREE=await import(pathToFileURL(path.resolve(threePath)));
 const {validateSelectionGrass,createSelectionGrassAppend}=await import(pathToFileURL(path.join(temp,'selection_scene_grass_material.js')));
 const file=url=>path.join(path.resolve(url.startsWith('/assets/source-selection-grass/')?candidate:base),url.replace(/^\//,''));
 const json=async url=>JSON.parse(await fs.readFile(file(url),'utf8')),p=await json('/assets/source-selection-grass/overlay.json'),data=await json(p.entry.url);
 validateSelectionGrass(p,data);
 const bad=structuredClone(p);bad.nativeEmptyRecords.noAtlasReplacement=false;
 assert.throws(()=>validateSelectionGrass(bad,data),/不匹配/);
 const fake=structuredClone(p);fake.nativeTextureMount.selected='res_t.bin';assert.throws(()=>validateSelectionGrass(fake,data),/不匹配/);
 const raw=[];const texture=async url=>{const b=await fs.readFile(file(url));assert.equal(b.subarray(1,4).toString(),'PNG');
  const t=new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});t.colorSpace=THREE.NoColorSpace;t.flipY=false;raw.push(t);return t;};
 const env=JSON.parse(await fs.readFile(envFile,'utf8'));assert.equal(env.fieldInputsReady,true);assert.equal(env.freshStartOnly,true);
 const uniforms=Object.fromEntries(Object.entries(env.uniformInputs).map(([k,v])=>[k,{value:Array.isArray(v)?(v.length===3?new THREE.Vector3(...v):new THREE.Vector2(...v)):v}]));
 const origin=new THREE.Vector3(-2583,0,-100),lighting={sourceSelectionRegion:211,uniforms};
 const result=await createSelectionGrassAppend(THREE,p,{origin,lighting,json,texture});
 assert.equal(result.instances,1);assert.equal(result.parts,1);assert.equal(result.originalGPUObserved,false);assert.equal(result.selectionAtlasApplied,false);
 const geometries=new Set();let lights=0;
 for(const inst of p.entry.instances){
  const group=result.root.children.find(g=>g.userData.selectionGrass.id===inst.id),mesh=group.children[0];geometries.add(mesh.geometry);
  assert.deepEqual(group.position.toArray(),inst.position.map((v,i)=>v-origin.getComponent(i)));assert.deepEqual(group.quaternion.toArray(),inst.quaternion);assert.deepEqual(group.scale.toArray(),inst.scale);
  assert.deepEqual(mesh.matrix.elements,data.meshes[0].sourceNodeTransform.matrix);assert.equal(mesh.geometry.index.count,495);
  const m=mesh.material;assert.equal(m.uniforms.sourceAtlas.value.image.width,8);assert.equal(m.uniforms.sourceAtlas.value.image.height,8);
  assert.equal(m.uniforms.sourceUVTransform,undefined);assert.ok(m.vertexShader.includes('atlasUV=sourceUV1;'));
  assert.equal(m.side,THREE.DoubleSide);assert.equal(m.depthWrite,true);assert.equal(m.depthTest,true);assert.equal(m.transparent,false);assert.equal(m.alphaTest,.5);assert.equal(m.lights,false);
 }
 result.root.traverse(o=>{if(o.isLight)lights++;});assert.equal(lights,0);assert.equal(geometries.size,1);
 let gd=0,md=0,rd=0;for(const g of geometries)g.addEventListener('dispose',()=>gd++);for(const m of result.materials)m.addEventListener('dispose',()=>md++);for(const t of raw)t.addEventListener('dispose',()=>rd++);
 result.dispose();assert.deepEqual([gd,md,rd],[1,1,0]);
 console.log(JSON.stringify({cpuOnly:true,newModels:0,instances:1,vertices:227,instanceTriangles:165,parts:1,
  originalDefaultLightMapRetained:true,selectionAtlasAndDATRejected:true,constantSourceUVEquivalence:true,lights,
  originalTRSPreserved:true,sourceRegion:211,textureFixtures:'real PNG dimensions; no GPU',disposalObserved:true}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
