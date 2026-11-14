// CPU construction and matrix/clock interfaces. Does not compile original GLSL.
import fs from 'node:fs/promises';import path from 'node:path';import os from 'node:os';
import {pathToFileURL} from 'node:url';import assert from 'node:assert/strict';
const[candidate,publicDir,threePath,envFile]=process.argv.slice(2);
if(!envFile)throw Error('Usage: node selection_scene_waterfalls_tests.mjs APPEND PUBLIC_DIR THREE_MODULE FRESH_ENV_JSON');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-waterfalls-'));
try{
 for(const n of await fs.readdir(publicDir))if(n.endsWith('.js'))await fs.symlink(path.resolve(publicDir,n),path.join(temp,n));
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');
 await fs.copyFile(new URL('./preview/selection_scene_waterfalls_material.js',import.meta.url),path.join(temp,'selection_scene_waterfalls_material.js'));
 const THREE=await import(pathToFileURL(path.resolve(threePath)));
 const {validateSelectionWaterfalls,createSelectionWaterfallsAppend}=await import(pathToFileURL(path.join(temp,'selection_scene_waterfalls_material.js')));
 const {createWindClock}=await import(pathToFileURL(path.join(temp,'source-dynamic-wind.js')));
 const file=u=>path.join(path.resolve(candidate),u.replace(/^\//,'')),json=async u=>JSON.parse(await fs.readFile(file(u),'utf8')),text=u=>fs.readFile(file(u),'utf8');
 const p=await json('/assets/source-selection-waterfalls/overlay.json'),data=await json(p.models[0].url);validateSelectionWaterfalls(p,p.models[0],data);
 const fake=structuredClone(data);fake.selectionWaterfall.sourceDATApplied=true;assert.throws(()=>validateSelectionWaterfalls(p,p.models[0],fake),/不匹配/);
 const raw=[];const texture=async u=>{const b=await fs.readFile(file(u));const t=new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});raw.push(t);t.colorSpace=THREE.NoColorSpace;t.flipY=false;return t;};
 const env=JSON.parse(await fs.readFile(envFile,'utf8'));assert.equal(env.freshStartOnly,true);
 const uniforms=Object.fromEntries(Object.entries(env.uniformInputs).map(([k,v])=>[k,{value:Array.isArray(v)?(v.length===3?new THREE.Vector3(...v):new THREE.Vector2(...v)):v}]));
 const lighting={sourceSelectionRegion:211,uniforms},origin=new THREE.Vector3(-2583,0,-100),clock=createWindClock(123000000);
 const result=await createSelectionWaterfallsAppend(THREE,p,{origin,lighting,json,text,texture,clock});
 assert.equal(result.instances,2);assert.equal(result.parts.length,2);assert.equal(result.originalGPUObserved,false);assert.equal(result.sourceDATApplied,false);
 const camera={projectionMatrix:new THREE.Matrix4(),matrixWorldInverse:new THREE.Matrix4()}; // Explicit CPU matrix fixture only.
 clock.update(124000000);
 for(const e of p.models){
  const inst=e.instances[0],group=result.root.children.find(g=>g.userData.selectionWaterfall.id===inst.id),mesh=group.children[0],m=mesh.material;
  assert.deepEqual(group.position.toArray(),inst.position.map((v,i)=>v-origin.getComponent(i)));assert.deepEqual(group.quaternion.toArray(),inst.quaternion);assert.deepEqual(group.scale.toArray(),inst.scale);
  assert.equal(mesh.geometry.index.count,180);assert.equal(mesh.geometry.getAttribute('TexCoord1').count,42);
  assert.equal(m.transparent,true);assert.equal(m.blending,THREE.CustomBlending);assert.equal(m.depthWrite,false);assert.equal(m.depthTest,true);assert.equal(m.side,THREE.DoubleSide);
  assert.equal(m.defines.ETC_SPLIT_ALPHA,'');assert.equal(m.defines.COLOR_TONE,'');assert.equal(m.defines.WATER,undefined);
  assert.ok(m.fragmentShader.includes('uniform lowp sampler2D sourceFallTexture;'));assert.ok(m.fragmentShader.includes('texture(maskMap_alpha'));
  mesh.onBeforeRender(null,null,camera);assert.equal(m.uniforms.time.value,1);assert.equal(m.uniforms.light_affected_rate.value,.5);
  assert.deepEqual(m.uniforms.global_light_common.value.toArray(),p.sourceGlobalLightCommon);assert.deepEqual(m.uniforms.WorldViewT.value.elements,mesh.matrixWorld.clone().transpose().elements);
  assert.equal(m.uniforms.fogstartend.value.x,58);assert.equal(m.uniforms.fogstartend.value.z,1/148);
 }
 clock.update(125000000);for(const part of result.parts){part.mesh.onBeforeRender(null,null,camera);assert.equal(part.material.uniforms.time.value,2);}
 let lights=0,gd=0,md=0,rd=0;result.root.traverse(o=>{if(o.isLight)lights++;if(o.isMesh)o.geometry.addEventListener('dispose',()=>gd++);});
 for(const m of result.materials)m.addEventListener('dispose',()=>md++);for(const t of raw)t.addEventListener('dispose',()=>rd++);
 result.dispose();assert.deepEqual([gd,md,rd,lights],[2,2,0,0]);
 console.log(JSON.stringify({cpuOnly:true,models:2,instances:2,vertices:84,triangles:120,originalSplitImages:4,
  explicitClock:true,sourceCommonLight:true,originalTRSPreserved:true,noAtlas:true,blend:'SrcAlpha/OneMinusSrcAlpha',
  lights,GLSLCompiled:false,textureFixtures:'actual PNG dimensions; no GPU',disposalObserved:true}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
