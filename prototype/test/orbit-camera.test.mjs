import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {createOrbitCameraCollision} from '../public/orbit-camera.js';

test('camera retracts before a source building wall from either side and preserves the rendered material',()=>{
  const wall=new THREE.Mesh(new THREE.BoxGeometry(10,10,.2),new THREE.MeshBasicMaterial());wall.position.z=3;
  const camera=new THREE.PerspectiveCamera(48,16/9,.1,900),focus=new THREE.Vector3(0,1,0),desired=new THREE.Vector3(0,1,8);
  const collision=createOrbitCameraCollision(THREE,[wall]),material=wall.material;
  const result=collision.resolve(focus,desired,camera);
  assert(result.blocked);assert(Math.abs(desired.z-2.8)<1e-6);assert.equal(wall.material,material);assert.equal(material.side,THREE.FrontSide);
  focus.set(0,1,8);desired.set(0,1,0);assert(collision.resolve(focus,desired,camera).blocked);assert(desired.z>3.1);
  focus.set(8,1,0);desired.set(8,1,8);assert.equal(collision.resolve(focus,desired,camera).blocked,false);assert.equal(desired.z,8);
  collision.dispose();
});

test('near-plane corner catches a pillar missed by the camera centre ray; moving geometry is refreshed',()=>{
  const wall=new THREE.Mesh(new THREE.BoxGeometry(.05,10,.2),new THREE.MeshBasicMaterial());wall.position.set(.09,0,3);
  const camera=new THREE.PerspectiveCamera(48,2,.1,900),focus=new THREE.Vector3(0,1,0),desired=new THREE.Vector3(0,1,8);
  const collision=createOrbitCameraCollision(THREE,[wall]);assert(collision.resolve(focus,desired,camera).blocked);
  wall.position.x=5;desired.set(0,1,8);assert.equal(collision.resolve(focus,desired,camera).blocked,false);collision.dispose();
});

test('camera looks over a low ledge rather than retracting into the avatar',()=>{
  const ledge=new THREE.Mesh(new THREE.BoxGeometry(10,1.4,10),new THREE.MeshBasicMaterial());ledge.position.set(0,0,5.6);
  const camera=new THREE.PerspectiveCamera(48,16/9,.1,900),focus=new THREE.Vector3(0,0,0),desired=new THREE.Vector3(0,2,8);
  const collision=createOrbitCameraCollision(THREE,[ledge]);
  const result=collision.resolve(focus,desired,camera,{minDistance:3});assert(result.raised);assert(result.distance>=3);assert(desired.y>2);collision.dispose();
});
