import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync}from'node:fs';
import * as THREE from 'three';
import {sampleParticleCurve,sampleParticleSystem}from'../public/particle-simulation.js';
import {createParticleRenderer}from'../public/particle-renderer.js';
import {curve,emitter,definition}from'./particle-fixture.mjs';

test('native scalar and UV keys quantize to integer 30 FPS frames and wrap at last frame plus one',()=>{
  const c=curve([0,10],{frames:[0,2]});assert.equal(sampleParticleCurve(c,33),0);assert.equal(sampleParticleCurve(c,34),5);assert.equal(sampleParticleCurve(c,67),10);
  const uv=curve([0,.25,.5,.75],{frames:[0,1,2,3],loop:true});assert.equal(sampleParticleCurve(uv,34),.25);assert.equal(sampleParticleCurve(uv,100),.75);assert.equal(sampleParticleCurve(uv,133),0);
  const color=curve([0,255],{frames:[0,2],kind:'int'});assert.equal(sampleParticleCurve(color,34),127);
});

test('source emission count/quality, finite windows, size curves and deterministic seed replace hardcoded counts',()=>{
  const e=emitter();e.curves.volumeHigh=curve(3);e.curves.volumeLow=curve(1);e.intervalFrames=[1,2,3];
  e.particle.curves.scaleX=curve([1,0],{frames:[0,20]});
  assert.equal(sampleParticleSystem(definition([e]),0,'same').length,3);
  assert.equal(sampleParticleSystem(definition([e]),99,'same').length,12);
  assert.equal(sampleParticleSystem(definition([e]),99,'same',{quality:2}).length,1);
  const before=sampleParticleSystem(definition([e]),34,'same');assert(before[0].size[0]<1);
  assert.equal(sampleParticleSystem(definition([e]),800,'same').length,0);
  e.particle.sizeRandomPercent=35;e.curves.radialSpeed=curve(5);
  assert.deepEqual(sampleParticleSystem(definition([e]),200,'same'),sampleParticleSystem(definition([e]),200,'same'));
  assert.notDeepEqual(sampleParticleSystem(definition([e]),200,'same'),sampleParticleSystem(definition([e]),200,'other'));
  assert(sampleParticleSystem(definition([e]),0,'same').every(p=>p.size[0]>=.65&&p.size[0]<=1));
});

test('native integration uses old velocity before gravity/damping and keeps disk spokes on XZ',()=>{
  const e=emitter();e.curves.directedSpeed=curve(3);e.durationFrames=1;e.particle.lifeFrames=30;
  e.affectors=[{type:0,strength:curve(.15),direction:curve([[0,-1,0]],{kind:'vector3'})},{type:1,strength:curve(.95)}];
  const p=sampleParticleSystem(definition([e]),1000/30,'physics')[0];
  assert(Math.abs(p.position[1]-.1)<1e-8);assert(Math.abs(p.velocity[1]-(3-.15)*.95)<1e-8);
  e.shape=2;e.curves.outerX=curve(2);e.curves.outerZ=curve(2);e.curves.outerY=curve(4);e.curves.volumeHigh=curve(4);e.curves.directedSpeed=curve(0);
  const positions=sampleParticleSystem(definition([e]),0,'disk').map(p=>p.position.map(v=>Math.round(v)||0));
  assert.deepEqual(positions,[[2,0,0],[0,0,2],[-2,0,0],[0,0,-2]]);
});

test('free XZ quads, velocity-aligned streaks, source blend/secondary colors and GPU disposal are preserved',()=>{
  const free=emitter();free.particle.type=1;const streak=emitter();streak.particle.type=3;streak.curves.directedSpeed=curve(3);
  const data={effects:{test:definition([free,streak])}},texture=new THREE.Texture(),textures=new Map([['/assets/test.png',texture]]);
  const camera=new THREE.PerspectiveCamera(),factory=createParticleRenderer(THREE,{data,textures,camera}),group=new THREE.Group();
  const system=factory.create('test','render',group),pose={position:new THREE.Vector3(),quaternion:new THREE.Quaternion()};
  system.update(0,pose);const[a,b]=group.children;
  const widthAxis=new THREE.Vector3(1,0,0).applyQuaternion(a.quaternion),heightAxis=new THREE.Vector3(0,1,0).applyQuaternion(a.quaternion);
  assert(widthAxis.distanceTo(new THREE.Vector3(1,0,0))<1e-6);assert(heightAxis.distanceTo(new THREE.Vector3(0,0,1))<1e-6);
  assert(new THREE.Vector3(0,1,0).applyQuaternion(b.quaternion).distanceTo(new THREE.Vector3(0,1,0))<1e-6);
  assert.equal(a.material.blending,THREE.AdditiveBlending);assert.equal(a.material.uniforms.twoColor.value,1);
  let disposed=0;a.material.addEventListener('dispose',()=>disposed++);system.dispose();assert.equal(disposed,1);assert.equal(group.children.length,0);factory.dispose();
});

const original=new URL('../../game-data/converted/effects/combat.json',import.meta.url);
test('all 15 recovered emitters stay finite, deterministic, within source lifetimes and bounded across repeated samples',{skip:!existsSync(original)},()=>{
  const data=JSON.parse(readFileSync(original,'utf8'));assert.equal(Object.values(data.effects).reduce((n,e)=>n+e.emitters.length,0),15);
  for(const[key,e]of Object.entries(data.effects))for(const time of[0,34,200,400,600,900]){
    const a=sampleParticleSystem(e,time,`cast:${key}`),b=sampleParticleSystem(e,time,`cast:${key}`);assert.deepEqual(a,b);assert(a.length<=256);
    for(const p of a){assert([...p.position,...p.velocity,...p.size,...p.uv,...p.color].every(Number.isFinite));assert(p.age<p.life);assert(p.size.every(v=>v>=0));}
  }
});

test('source follow flags distinguish world particles from emitter-local translation and rotation',()=>{
  const fixed=emitter(),following=emitter();fixed.curves.translateX=curve(1);following.curves.translateX=curve(1);following.particle.followFlags=3;
  const data={effects:{test:definition([fixed,following])}},textures=new Map([['/assets/test.png',new THREE.Texture()]]),camera=new THREE.PerspectiveCamera();
  const factory=createParticleRenderer(THREE,{data,textures,camera}),group=new THREE.Group(),system=factory.create('test','follow',group);
  const birth={position:new THREE.Vector3(),quaternion:new THREE.Quaternion()},current={position:new THREE.Vector3(10,0,0),quaternion:new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),Math.PI/2)};
  system.update(0,current,birth);assert.deepEqual(group.children[0].position.toArray(),[1,0,0]);assert(group.children[1].position.distanceTo(new THREE.Vector3(10,0,-1))<1e-6);
  system.dispose();factory.dispose();
});
