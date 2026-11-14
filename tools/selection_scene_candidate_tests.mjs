// CPU construction/contract review only. No browser GPU, camera or lights.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';

const [candidate,publicDir,threePath]=process.argv.slice(2);
if(!candidate||!publicDir||!threePath)throw Error('Usage: node selection_scene_candidate_tests.mjs CANDIDATE PUBLIC_DIR THREE_MODULE');
const temp=await fs.mkdtemp(path.join(os.tmpdir(),'oc2-selection-scene-'));
try{
 for(const name of await fs.readdir(publicDir))if(name.endsWith('.js'))await fs.symlink(path.resolve(publicDir,name),path.join(temp,name));
 await fs.writeFile(path.join(temp,'package.json'),'{"type":"module"}');
 await fs.copyFile(new URL('./preview/source-selection-scene.js',import.meta.url),path.join(temp,'source-selection-scene.js'));
 const THREE=await import(pathToFileURL(path.resolve(threePath)));
 const {validateSelectionScene,createSelectionScene}=await import(pathToFileURL(path.join(temp,'source-selection-scene.js')));
 const root=path.resolve(candidate),json=async url=>JSON.parse(await fs.readFile(path.join(root,url.replace(/^\//,'')),'utf8'));
 const manifest=await json('/assets/source-selection-scene/manifest.json');validateSelectionScene(manifest);
 const broken=structuredClone(manifest);broken.bindings[0].bindings[0].atlas='texture/lightmap/tutorial/lightmap/test.tga';
 assert.throws(()=>validateSelectionScene(broken),/图集/);
 // Dimension-only CPU texture fixtures; no claim of original pixels or GPU.
 const texture=async url=>{
  const b=await fs.readFile(path.join(root,url.replace(/^\//,'')));
  assert.equal(b.subarray(1,4).toString(),'PNG');
  const t=new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});t.colorSpace=THREE.NoColorSpace;t.flipY=false;return t;
 };
 const uniforms={sourceModelLight:{value:new THREE.Vector3()},sourceTerrainLight:{value:new THREE.Vector3()},
  sourceFogColor:{value:new THREE.Vector3()},sourceToneNear:{value:new THREE.Vector3()},sourceToneFar:{value:new THREE.Vector3()},
  sourceToneOffsetNear:{value:new THREE.Vector3()},sourceToneOffsetFar:{value:new THREE.Vector3()},
  sourceToneDistance:{value:new THREE.Vector2()},sourceFogNear:{value:0},sourceFogSpan:{value:1}};
 const origin=new THREE.Vector3(-2583,0,-100);
 await assert.rejects(()=>createSelectionScene(THREE,manifest,{origin,lighting:{uniforms},json,texture}),/环境/);
 const result=await createSelectionScene(THREE,manifest,{origin,lighting:{sourceSelectionRegion:211,uniforms},json,texture});
 assert.equal(result.instances,139);assert.equal(result.tiles,25);assert.equal(result.root.children.length,164);
 assert.equal(result.originalFinalFrameRestored,false);
 let lights=0,meshes=0;result.root.traverse(o=>{if(o.isLight)lights++;if(o.isMesh)meshes++;});
 assert.equal(lights,0);assert.equal(meshes,164);
 const inst=manifest.models[0].instances[0],container=result.root.children.find(o=>o.userData.sourceSelectionInstance?.id===inst.id);
 assert.deepEqual(container.position.toArray(),inst.position.map((v,i)=>v-origin.getComponent(i)));
 assert.deepEqual(container.quaternion.toArray(),inst.quaternion);assert.deepEqual(container.scale.toArray(),inst.scale);
 let altered=0,dispose=0;
 result.root.traverse(o=>{if(o.isMesh){o.geometry.addEventListener('dispose',()=>dispose++);const list=Array.isArray(o.material)?o.material:[o.material];for(const m of list){if(m.lights)altered++;}}});
 assert.equal(altered,0);result.dispose();assert.ok(dispose>=164);
 console.log(JSON.stringify({cpuOnly:true,textures:'dimension fixtures, not rendered',tiles:25,instances:139,meshNodes:meshes,partBindings:result.parts,lights,
  rejectedForeignAtlas:true,rejectedUnverifiedEnvironment:true,sourceTRSPreserved:true,disposalObserved:true}));
}finally{await fs.rm(temp,{recursive:true,force:true});}
