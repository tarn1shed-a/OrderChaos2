import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {existsSync,readFileSync} from 'node:fs';
import {sceneDiffuseTexture} from '../public/scene-sampling.js';

function fixture(){
 const material={name:'wall',diffuse:'texture/wall.tga'},texture=new THREE.Texture({width:512,height:256});
 texture.colorSpace=THREE.SRGBColorSpace;texture.anisotropy=4;
 const profile={format:'oc2-scene-sampling-v1',materials:[{index:0,name:material.name,texture:material.diffuse,addressU:0,addressV:0,
  sourceTexture:{width:512,height:256,typeId:1},sourceRequest:{addressU:null,addressV:null,minFilter:null,magFilter:null}}]};
 return {material,texture,profile};
}
test('source scene addressing repeats UV outside 0..1 on an owned sampler, preserving shared textures and other adapters',()=>{
 const {material,texture,profile}=fixture(),owned=sceneDiffuseTexture(THREE,texture,material,0,profile);
 assert.notEqual(owned,texture);assert.equal(owned.image,texture.image);
 assert.equal(owned.wrapS,THREE.RepeatWrapping);assert.equal(owned.wrapT,THREE.RepeatWrapping);
 assert.equal(texture.wrapS,THREE.ClampToEdgeWrapping);assert.equal(texture.wrapT,THREE.ClampToEdgeWrapping);
 for(const key of ['colorSpace','flipY','minFilter','magFilter','generateMipmaps','anisotropy'])assert.equal(owned[key],texture[key],key);
});
test('missing, mismatched, non-POT, explicit-override or wrong-size profiles cannot silently force repeat',()=>{
 for(const change of [p=>p.format='unknown',p=>p.materials[0].name='other',p=>p.materials[0].index=1,
  p=>p.materials[0].texture='other',p=>p.materials[0].addressV=2,p=>p.materials[0].sourceRequest.addressU=0,
  p=>p.materials[0].sourceTexture.typeId=3,p=>p.materials[0].sourceTexture.width=511,p=>p.materials[0].sourceTexture.height=512]){
  const {material,texture,profile}=fixture();change(profile);assert.throws(()=>sceneDiffuseTexture(THREE,texture,material,0,profile));
 }
 const {material,texture}=fixture();assert.throws(()=>sceneDiffuseTexture(THREE,texture,material,0,null));
});
const root=new URL('../../game-data/converted/',import.meta.url),manifestPath=new URL('manifest.json',root);
test('current 39 source instances have checked 2D diffuse profiles with source PNG dimensions',{skip:!existsSync(manifestPath)},()=>{
 const manifest=JSON.parse(readFileSync(manifestPath));assert.equal(manifest.scenery.length,16);
 assert.equal(manifest.scenery.reduce((n,m)=>n+m.instances.length,0),39);
 for(const entry of manifest.scenery){
  const model=JSON.parse(readFileSync(new URL(entry.url.slice('/assets/'.length),root)));
  assert.equal(model.sceneSampling.format,'oc2-scene-sampling-v1');assert.equal(model.sceneSampling.materials.length,model.materials.length);
  for(const [i,material]of model.materials.entries()){
   const png=readFileSync(new URL(manifest.textures[material.diffuse].slice('/assets/'.length),root));
   const texture=new THREE.Texture({width:png.readUInt32BE(16),height:png.readUInt32BE(20)});
   assert.equal(sceneDiffuseTexture(THREE,texture,material,i,model.sceneSampling).wrapS,THREE.RepeatWrapping);
  }
 }
});
