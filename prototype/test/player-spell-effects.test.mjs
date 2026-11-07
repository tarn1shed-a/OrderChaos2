import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync}from'node:fs';
import * as THREE from 'three';
import {hemisphereData,proceduralPose}from'../public/procedural-effects.js';
import {sampleParticleSystem}from'../public/particle-simulation.js';
import {createParticleRenderer}from'../public/particle-renderer.js';
import {curve,emitter,definition}from'./particle-fixture.mjs';
const curves=()=>Object.fromEntries(['translateX','translateY','translateZ','rotateX','rotateY','rotateZ','scaleX','scaleY','scaleZ','red','green','blue','alpha','secondaryRed','secondaryGreen','secondaryBlue','scrollU','scrollV'].map(k=>[k,curve(k.startsWith('scale')?1:k==='scrollU'?.11:k==='scrollV'?-.1:k==='alpha'?255:0)]));
test('native hemisphere uses source ring/radial counts, axes, seam UV and scrolling clock, rejecting corrupt dimensions',()=>{
 const node={radius:2.09,height:.37,radialSegments:15,rings:4,uvRotation:0,startFrame:0,durationFrames:-1,curves:curves(),uvScroll:true},d=hemisphereData(node);
 assert.equal(d.positions.length/3,80);assert.equal(d.indices.length,360);assert.deepEqual(d.uvs.slice(0,2),[1,0]);assert.deepEqual(d.alpha.slice(0,16),Array(16).fill(0));
 assert(Math.abs(d.positions[64*3+1]-.37)<1e-10);assert.deepEqual(proceduralPose(node,1000).scroll,[3.3,-3]);
 assert.throws(()=>hemisphereData({...node,rings:0}));
});
test('source cone rotates directed velocity by its signed angle without changing speed',()=>{
 const e=emitter();e.curves.directedSpeed=curve(4);e.curves.coneAngle=curve(-50);
 const p=sampleParticleSystem(definition([e]),0,'cone')[0];assert(Math.abs(Math.hypot(...p.velocity)-4)<1e-10);assert(Math.abs(p.velocity[1]/4-Math.cos(50*Math.PI/180))<1e-10);
});
const source=new URL('../../game-data/converted/effects/combat.json',import.meta.url);
test('actual player FX layers, hemisphere meshes and linked arcane quads stay finite and release owned GPU objects',{skip:!existsSync(source)},()=>{
 const data=JSON.parse(readFileSync(source,'utf8')),textures=new Map(Object.values(data.effects).flatMap(d=>Object.values(d.textureURLs)).map(url=>[url,new THREE.Texture()])),camera=new THREE.PerspectiveCamera();camera.position.set(0,3,8);
 const renderer=createParticleRenderer(THREE,{data,textures,camera}),pose={position:new THREE.Vector3(),quaternion:new THREE.Quaternion(),scale:new THREE.Vector3(1,1,1),target:new THREE.Vector3(6,1,0)};
 for(const key of Object.keys(data.playerSpells.effects)){
  const group=new THREE.Group(),system=renderer.create(key,key,group);
  for(const at of [34,200,400,600]){system.update(at,pose,pose);group.updateMatrixWorld(true);group.traverse(o=>{if(o.isMesh){assert(o.matrixWorld.elements.every(Number.isFinite));assert(o.scale.toArray().every(Number.isFinite));}});}
  let disposed=0;group.traverse(o=>{if(o.isMesh)o.material.addEventListener('dispose',()=>disposed++);});const count=group.children.length;system.dispose();assert.equal(group.children.length,0);assert.equal(disposed,count);
 }
 renderer.dispose();
});
