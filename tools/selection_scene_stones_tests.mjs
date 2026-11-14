// Source-backed CPU construction only. No browser/GPU, character or save work.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';

const[candidate,base,publicDir,threePath,envFile]=process.argv.slice(2);
if(!envFile)throw Error('Usage: node selection_scene_stones_tests.mjs APPEND BASE PUBLIC_DIR THREE_MODULE FRESH_ENV_JSON');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-stones-'));
try{
 for(const n of await fs.readdir(publicDir))if(n.endsWith('.js'))await fs.symlink(path.resolve(publicDir,n),path.join(temp,n));
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');
 await fs.copyFile(new URL('./preview/selection_scene_stones_material.js',import.meta.url),path.join(temp,'selection_scene_stones_material.js'));
 const THREE=await import(pathToFileURL(path.resolve(threePath)));
 const {validateSelectionStones,validateSelectionStoneModel,createSelectionStonesAppend}=await import(pathToFileURL(path.join(temp,'selection_scene_stones_material.js')));
 const file=url=>path.join(path.resolve(url.startsWith('/assets/source-selection-stones/')?candidate:base),url.replace(/^\//,''));
 const json=async url=>JSON.parse(await fs.readFile(file(url),'utf8'));
 const p=await json('/assets/source-selection-stones/overlay.json');validateSelectionStones(p);
 const foreign=structuredClone(p);foreign.bindings[0].bindings[0].atlas='texture/lightmap/tutorial/lightmap/-41_-3.tga';
 assert.throws(()=>validateSelectionStones(foreign),/图集/);
 const wrongType=structuredClone(p);wrongType.models[0].instances[0].sourceType=15;
 assert.throws(()=>validateSelectionStones(wrongType),/摆放/);
 const model=await json(p.models[0].url),noUV=structuredClone(model);delete noUV.meshes[0].sourceUV2;
 assert.throws(()=>validateSelectionStoneModel(p.models[0],noUV,p),/模型数据/);
 const rawTextures=[];
 const texture=async url=>{
  const b=await fs.readFile(file(url));assert.equal(b.subarray(1,4).toString(),'PNG');
  const t=new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});rawTextures.push(t);
  t.colorSpace=THREE.NoColorSpace;t.flipY=false;return t;
 };
 const env=JSON.parse(await fs.readFile(envFile,'utf8'));
 assert.equal(env.fieldInputsReady,true);assert.equal(env.freshStartOnly,true);
 const uniforms=Object.fromEntries(Object.entries(env.uniformInputs).map(([k,v])=>[k,{value:Array.isArray(v)?
  (v.length===3?new THREE.Vector3(...v):new THREE.Vector2(...v)):v}]));
 const lighting={sourceSelectionRegion:211,uniforms},origin=new THREE.Vector3(-2583,0,-100);
 await assert.rejects(()=>createSelectionStonesAppend(THREE,p,{origin,lighting:{uniforms},json,texture}),/环境/);
 const result=await createSelectionStonesAppend(THREE,p,{origin,lighting,json,texture});
 assert.equal(result.instances,6);assert.equal(result.parts,9);assert.equal(result.originalGPUObserved,false);
 assert.equal(result.root.children.length,6);assert.equal(result.materials.length,9);
 let lights=0,triangles=0;const geometries=new Set();
 for(const e of p.models){
  const data=await json(e.url),source=data.meshes[0];
  for(const inst of e.instances){
   const group=result.root.children.find(g=>g.userData.selectionStone.id===inst.id),mesh=group.children[0];geometries.add(mesh.geometry);
   assert.deepEqual(group.position.toArray(),inst.position.map((v,i)=>v-origin.getComponent(i)));
   assert.deepEqual(group.quaternion.toArray(),inst.quaternion);assert.deepEqual(group.scale.toArray(),inst.scale);
   assert.deepEqual(mesh.matrix.elements,source.sourceNodeTransform.matrix);
   assert.deepEqual(Array.from(mesh.geometry.getAttribute('sourceUV2').array),source.sourceUV2);
   assert.equal(mesh.geometry.getAttribute('sourceUV2').count,source.vertexCount);
   assert.equal(mesh.geometry.groups.length,e.partToMaterial.length);triangles+=mesh.geometry.index.count/3;
   const binding=p.bindings.find(b=>b.objectId===inst.id).bindings[0];
   for(const m of mesh.material){
    assert.deepEqual(m.uniforms.sourceUVTransform.value.toArray(),binding.uvTransform);
    assert.ok(m.uniforms.selectionSecond.value);assert.equal(m.side,THREE.DoubleSide);
    assert.equal(m.depthTest,true);assert.equal(m.depthWrite,true);assert.equal(m.depthFunc,THREE.LessEqualDepth);
    assert.equal(m.transparent,false);assert.equal(m.alphaTest,0);assert.equal(m.lights,false);
    assert.equal(m.uniforms.sourceModelLight,uniforms.sourceModelLight);
    assert.ok(m.vertexShader.includes('selectionSecondUV=sourceUV2;'));
    const shader=m.fragmentShader;assert.ok(shader.indexOf('color*=texture2D(selectionSecond')<shader.indexOf('color.rgb*=texture2D(sourceAtlas'));
   }
  }
 }
 result.root.traverse(o=>{if(o.isLight)lights++;});assert.equal(lights,0);assert.equal(geometries.size,2);assert.equal(triangles,1032);
 let gd=0,md=0,td=0;
 for(const g of geometries)g.addEventListener('dispose',()=>gd++);
 for(const m of result.materials)m.addEventListener('dispose',()=>md++);
 for(const t of rawTextures)t.addEventListener('dispose',()=>td++);
 result.dispose();assert.equal(gd,2);assert.equal(md,9);assert.equal(td,0);
 console.log(JSON.stringify({cpuOnly:true,models:2,instances:6,uniqueVertices:496,renderedTriangles:1032,parts:9,
  twoTextureRGBAProduct:true,originalSecondUV:true,individualDATTransforms:true,sourceTRSPreserved:true,
  rejectedMissingUV:true,rejectedForeignAtlas:true,rejectedType15:true,sourceRegion:211,lights,
  textureFixtures:'real PNG dimensions, no GPU',disposalObserved:true}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
