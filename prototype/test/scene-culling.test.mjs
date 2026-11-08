import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import * as THREE from 'three';
import {applySceneCulling,assertSceneOrientation,guardSceneOrientation} from '../public/scene-culling.js';

function fixture(effectPath='ut_cull_lightmap_solid.bdae'){
 const source={name:'synthetic',diffuse:'texture/synthetic.tga'},material=new THREE.MeshStandardMaterial({side:THREE.DoubleSide,alphaTest:.5});
 const profile={format:'oc2-scene-culling-v1',projectionRule:'target-y-inversion-compensated-by-front-face-xor',
  transformScope:'positive-affine-source-nodes-and-world-instances',materials:[{index:0,...source,texture:source.diffuse,
   effectPath,cullEnabled:effectPath==='ut_cull_lightmap_solid.bdae',cullFace:'BACK',frontFaceBeforeTarget:'CCW',technique:'tech0'}]};
 return {source,material,profile};
}
test('original cull FX maps to FrontSide, unculled FX stay double sided and web shadows are preserved',()=>{
 for(const effect of ['ut_cull_lightmap_solid.bdae','ut_lightmap_solid.bdae','ut_lightmap_trans.bdae']){
  const {source,material,profile}=fixture(effect);
  assert.equal(applySceneCulling(THREE,material,source,0,profile),material);
  assert.equal(material.side,effect==='ut_cull_lightmap_solid.bdae'?THREE.FrontSide:THREE.DoubleSide);
  assert.equal(material.shadowSide,THREE.DoubleSide);assert.equal(material.alphaTest,.5);
  assert.equal(material.depthTest,true);assert.equal(material.depthWrite,true);assert.equal(material.transparent,false);
 }
});
test('unverified cull direction, technique, target compensation or old metadata fail closed',()=>{
 for(const change of [p=>p.format='old',p=>p.projectionRule='copy-native-flip',p=>p.transformScope='all',
  p=>p.materials[0].index=1,p=>p.materials[0].name='other',p=>p.materials[0].texture='other',
  p=>p.materials[0].effectPath='unknown',p=>p.materials[0].cullEnabled=false,
  p=>p.materials[0].cullFace='FRONT',p=>p.materials[0].frontFaceBeforeTarget='CW',p=>p.materials[0].technique='tech1']){
  const {source,material,profile}=fixture();change(profile);
  assert.throws(()=>applySceneCulling(THREE,material,source,0,profile));
 }
 const {source,material}=fixture();assert.throws(()=>applySceneCulling(THREE,material,source,0,null));
});
test('final cloned instances validate their own world transform, including reflected parents',()=>{
 const {source,material,profile}=fixture();applySceneCulling(THREE,material,source,0,profile);
 const template=new THREE.Group();template.add(new THREE.Mesh(new THREE.BufferGeometry(),material));
 const instance=template.clone(true);let draws=0;guardSceneOrientation(instance,()=>draws++);
 instance.rotation.y=1.7;instance.position.set(20,30,40);instance.updateMatrixWorld(true);
 const mesh=instance.children[0];mesh.onBeforeRender();assert.equal(draws,1);
 assert.notEqual(mesh.onBeforeRender,template.children[0].onBeforeRender);
 instance.scale.x=-1;instance.updateMatrixWorld(true);assert.throws(()=>mesh.onBeforeRender(),/镜像/);
 instance.scale.set(-1,1,-1);instance.updateMatrixWorld(true);assert.doesNotThrow(()=>mesh.onBeforeRender());
 instance.scale.x=0;instance.updateMatrixWorld(true);assert.throws(()=>assertSceneOrientation(mesh),/退化/);
 mesh.matrixWorld.elements[0]=NaN;assert.throws(()=>assertSceneOrientation(mesh));
});
const root=new URL('../../game-data/converted/',import.meta.url),manifestFile=new URL('manifest.json',root);
test('current map and door source cull bindings and all instance determinants agree', {skip:!existsSync(manifestFile)},()=>{
 const manifest=JSON.parse(readFileSync(manifestFile));let culled=0,unculled=0,instances=0;
 for(const entry of [...manifest.scenery,...manifest.dynamicModels]){
  const model=JSON.parse(readFileSync(new URL(entry.url.slice('/assets/'.length),root)));
  for(const [i,source]of model.materials.entries()){
   const material=applySceneCulling(THREE,new THREE.MeshStandardMaterial(),source,i,model.sceneCulling);
   if(material.side===THREE.FrontSide)culled++;else unculled++;
  }
  for(const mesh of model.meshes){
   const object=new THREE.Object3D();object.matrixWorld.fromArray(mesh.sourceNodeTransform.matrix);assertSceneOrientation(object);
  }
  for(const inst of entry.instances||[]){
   const object=new THREE.Object3D();object.position.fromArray(inst.position);object.quaternion.fromArray(inst.quaternion);object.scale.fromArray(inst.scale);
   object.updateMatrixWorld(true);assertSceneOrientation(object);instances++;
  }
 }
 assert.equal(culled,27);assert.equal(unculled,25);assert.equal(instances,39);
});
