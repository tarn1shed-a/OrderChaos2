// CPU construction and original-data contracts; no GPU/frame completion claim.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';

const [candidate,base,publicDir,threePath,environmentFile]=process.argv.slice(2);
if(!environmentFile)throw Error('Usage: node selection_scene_inside_tests.mjs APPEND BASE PUBLIC_DIR THREE_MODULE FRESH_ENV_JSON');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-inside-'));
try{
 for(const name of await fs.readdir(publicDir))if(name.endsWith('.js'))await fs.symlink(path.resolve(publicDir,name),path.join(temp,name));
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');
 await fs.copyFile(new URL('./preview/selection_scene_inside_material.js',import.meta.url),path.join(temp,'selection_scene_inside_material.js'));
 const THREE=await import(pathToFileURL(path.resolve(threePath)));
 const {validateSelectionInside,createSelectionInsideAppend}=await import(pathToFileURL(path.join(temp,'selection_scene_inside_material.js')));
 const {createWindClock}=await import(pathToFileURL(path.join(temp,'source-dynamic-wind.js')));
 const file=url=>path.join(path.resolve(url.startsWith('/assets/source-selection-inside/')?candidate:base),url.replace(/^\//,''));
 const json=async url=>JSON.parse(await fs.readFile(file(url),'utf8'));
 const overlay=await json('/assets/source-selection-inside/overlay.json'),data=await json(overlay.entry.url);
 validateSelectionInside(overlay,data);
 const badType=structuredClone(overlay);badType.entry.instances[0].sourceType=15;
 assert.throws(()=>validateSelectionInside(badType,data),/来源/);
 const badAtlas=structuredClone(overlay);badAtlas.bindings[0].bindings[0].atlas='texture/lightmap/tutorial/lightmap/-41_-2__1.tga';
 assert.throws(()=>validateSelectionInside(badAtlas,data),/图集/);
 const rawTextures=[];
 const texture=async url=>{
  const b=await fs.readFile(file(url));assert.equal(b.subarray(1,4).toString(),'PNG');
  // Dimension-only CPU fixture from the real PNG header. Pixels are not rendered.
  const t=new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});
  t.colorSpace=THREE.NoColorSpace;t.flipY=false;rawTextures.push(t);return t;
 };
 const env=JSON.parse(await fs.readFile(environmentFile,'utf8'));
 assert.equal(env.sourceSelectionRegion,211);assert.equal(env.fieldInputsReady,true);assert.equal(env.freshStartOnly,true);
 const uniforms=Object.fromEntries(Object.entries(env.uniformInputs).map(([name,value])=>[name,{value:Array.isArray(value)?
  (value.length===3?new THREE.Vector3(...value):new THREE.Vector2(...value)):value}]));
 const lighting={sourceSelectionRegion:211,uniforms},origin=new THREE.Vector3(-2583,0,-100),clock=createWindClock(123000000);
 await assert.rejects(()=>createSelectionInsideAppend(THREE,overlay,{origin,lighting,json,texture}),/时钟/);
 const result=await createSelectionInsideAppend(THREE,overlay,{origin,lighting,json,texture,clock});
 assert.equal(result.instances,1);assert.equal(result.parts,21);assert.equal(result.originalGPUObserved,false);
 const mesh=result.root.children[0];assert.equal(mesh.isMesh,true);assert.equal(result.root.children.length,1);
 assert.equal(mesh.geometry.index.count,23700);assert.equal(mesh.geometry.groups.length,21);assert.equal(result.materials.length,21);
 const inst=overlay.entry.instances[0];
 assert.deepEqual(result.root.position.toArray(),inst.position.map((v,i)=>v-origin.getComponent(i)));
 assert.deepEqual(result.root.quaternion.toArray(),inst.quaternion);assert.deepEqual(result.root.scale.toArray(),inst.scale);
 assert.deepEqual(mesh.matrix.elements,data.meshes[0].sourceNodeTransform.matrix);
 for(const name of ['uv','sourceUV1','sourceUV2','sourceUV3'])assert.equal(mesh.geometry.getAttribute(name).count,11817);
 let lights=0;result.root.traverse(o=>{if(o.isLight)lights++;});assert.equal(lights,0);
 const binding=overlay.bindings[0].bindings[0],atlas=result.materials[0].uniforms.sourceAtlas.value;
 for(const [i,m]of result.materials.entries()){
  assert.equal(m.uniforms.sourceAtlas.value,atlas);assert.deepEqual(m.uniforms.sourceUVTransform.value.toArray(),binding.uvTransform);
  assert.equal(m.side,THREE.DoubleSide);assert.equal(m.depthTest,true);assert.equal(m.depthWrite,true);
  assert.equal(m.depthFunc,THREE.LessEqualDepth);assert.equal(m.transparent,false);assert.equal(m.lights,false);
  assert.equal(m.uniforms.sourceModelLight,uniforms.sourceModelLight);
  assert.equal(m.alphaTest,[0,1,3].includes(i)?.5:0);
 }
 const lumin=result.materials[1];
 assert.deepEqual(lumin.uniforms.selectionUV2Speed.value.toArray(),[.10000000149011612,0]);
 assert.deepEqual(lumin.uniforms.selectionTint.value.toArray(),[.6549019813537598,1,.9960784912109375]);
 assert.equal(lumin.uniforms.selectionIntensity.value,1.600000023841858);
 assert.ok(lumin.vertexShader.includes('selectionMaskUV=sourceUV3'));
 const shader=lumin.fragmentShader;assert.ok(shader.indexOf('color.rgb*=vertexLight;')<shader.indexOf('color.rgb+=second.rgb'));
 assert.ok(shader.indexOf('color.rgb+=second.rgb')<shader.indexOf('color.rgb=mix(sourceFogColor'));
 assert.deepEqual(result.materials[3].uniforms.selectionUVSpeed.value.toArray(),[0,-.20000000298023224]);
 const animated=result.materials.filter(m=>m.uniforms.selectionTime);assert.equal(animated.length,3);
 clock.update(124000000);mesh.onBeforeRender();for(const m of animated)assert.equal(m.uniforms.selectionTime.value,1);
 clock.update(125000000);mesh.onBeforeRender();for(const m of animated)assert.equal(m.uniforms.selectionTime.value,2);
 let disposedGeometry=0,disposedMaterials=0,disposedRaw=0;
 mesh.geometry.addEventListener('dispose',()=>disposedGeometry++);
 for(const m of result.materials)m.addEventListener('dispose',()=>disposedMaterials++);
 for(const t of rawTextures)t.addEventListener('dispose',()=>disposedRaw++);
 result.dispose();assert.equal(disposedGeometry,1);assert.equal(disposedMaterials,21);assert.equal(disposedRaw,0);
 console.log(JSON.stringify({cpuOnly:true,sourceType:2,instances:1,vertices:11817,triangles:7900,parts:21,
  animatedMaterials:3,originalSelectionDatBindings:1,sharedByParts:21,lights,sourceTRSPreserved:true,
  rejectedType15:true,rejectedForeignAtlas:true,explicitClockRequired:true,sourceEnvironment:211,
  textures:'real PNG dimensions; CPU fixtures only',disposalObserved:true}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
