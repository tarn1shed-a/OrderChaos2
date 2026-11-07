import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import * as THREE from 'three';
import {createCharacterFactory,characterAttachment} from '../public/character-animation.js';
import {createPortraitScene} from '../public/character-portraits.js';
import {socketCharacter} from './particle-fixture.mjs';

test('portrait has its own skeleton/material and frames the actual source head without moving a fighter',()=>{
  const data=socketCharacter();data.rig.nodes[3].aliases.push('Head');
  const material=new THREE.MeshStandardMaterial(),factory=createCharacterFactory(THREE,data,[material]);
  const fighter=factory();fighter.position.set(5,2,8);fighter.rotation.y=1;
  const before=characterAttachment(fighter,'Head',new THREE.Vector3()).clone();
  const portrait=createPortraitScene(THREE,factory,{headNode:'Head'});
  assert.notEqual(portrait.body,fighter);assert(portrait.head.clone().project(portrait.camera).length()<1);
  const after=characterAttachment(fighter,'Head',new THREE.Vector3());assert(after.distanceTo(before)<1e-8);
  assert.equal(material.toneMapped,true);assert(portrait.span>0);
  let ownMaterial;portrait.body.traverse(o=>{if(o.isMesh)ownMaterial=o.material;});assert.notEqual(ownMaterial,material);
  let count=0;ownMaterial.addEventListener('dispose',()=>count++);portrait.dispose();portrait.dispose();assert.equal(count,1);
  assert.throws(()=>createPortraitScene(THREE,factory,{headNode:'Absent'}),/缺少头部/);
});

for(const[name,headNode]of [['forest-elf','Bip01_Head'],['wolf','Bip001_Head']]){
  const path=new URL(`../../game-data/converted/models/${name}.json`,import.meta.url);
  test(`original ${name} portrait camera centers its own recovered head`,{skip:!existsSync(path)},()=>{
    const data=JSON.parse(readFileSync(path,'utf8')),materials=data.materials.map(()=>new THREE.MeshStandardMaterial());
    const portrait=createPortraitScene(THREE,createCharacterFactory(THREE,data,materials),{headNode});
    const head=portrait.head.clone().project(portrait.camera);assert(Math.abs(head.x)<1e-6&&Math.abs(head.y)<1e-6);
    assert(portrait.span>0&&Number.isFinite(portrait.span));portrait.dispose();
  });
}

test('equipment preview frames an independent whole body without requiring a portrait head alias',()=>{
  const data=socketCharacter(),material=new THREE.MeshStandardMaterial();
  const factory=createCharacterFactory(THREE,data,[material]),fighter=factory();
  const preview=createPortraitScene(THREE,factory,{fullBody:true,frameHeight:1.18,direction:[.22,.02,1]});
  const box=new THREE.Box3().setFromObject(preview.body),center=box.getCenter(new THREE.Vector3());
  assert(preview.head.distanceTo(center)<1e-7);
  const projected=center.clone().project(preview.camera);assert(Math.abs(projected.x)<1e-6&&Math.abs(projected.y)<1e-6);
  assert.notEqual(preview.body,fighter);assert.deepEqual(fighter.position.toArray(),[0,0,0]);preview.dispose();
});
