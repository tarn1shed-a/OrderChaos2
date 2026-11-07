import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import * as THREE from 'three';
import {createSceneMaterial} from '../public/scene-alpha.js';

function fixture(cutout=true){
 const source={name:'synthetic',diffuse:'texture/synthetic.tga'},map=new THREE.Texture({width:256,height:256});
 const profile={format:'oc2-scene-alpha-v1',materials:[{index:0,name:source.name,texture:source.diffuse,
  effectPath:cutout?'ut_lightmap_trans.bdae':'ut_lightmap_solid.bdae',resolvedTechniqueIndex:0,
  sourceTechnique:{name:'tech0',valueWord0:2},rule:cutout?'discard-less-equal':'none',reference:cutout?.5:null,
  sourceAlpha:{mode:cutout?'split-red':'opaque-ETC1',width:256,height:256,baseAlphaSHA256:'a'.repeat(64)}}]};
 return {source,map,profile};
}
test('source cutout discards equality, keeps opaque draw/depth behavior and owns only its material',()=>{
 const {source,map,profile}=fixture(),material=createSceneMaterial(THREE,map,source,0,profile);
 const shader={fragmentShader:THREE.ShaderLib.standard.fragmentShader};material.onBeforeCompile(shader);
 assert(shader.fragmentShader.includes('if ( diffuseColor.a <= 0.5 ) discard;'));
 assert(!shader.fragmentShader.includes('#include <alphatest_fragment>'));
 assert.equal(material.alphaTest,.5);assert.equal(material.opacity,1);assert.equal(material.transparent,false);
 assert.equal(material.depthTest,true);assert.equal(material.depthWrite,true);assert.equal(material.map,map);
 assert.equal(material.side,THREE.DoubleSide,'Existing web sidedness remains an adapter in this branch');
 assert.equal(map.version,0,'Source cached texture is not mutated');
 const second=createSceneMaterial(THREE,map,source,0,profile);assert.notEqual(material,second);
 assert.equal(second.customProgramCacheKey(),material.customProgramCacheKey());
 assert.throws(()=>material.onBeforeCompile({fragmentShader:'missing chunk'}),/接口/);
});
test('solid source FX have no alpha cutout, including the cull variant whose sidedness is still pending',()=>{
 for(const effectPath of ['ut_lightmap_solid.bdae','ut_cull_lightmap_solid.bdae']){
  const {source,map,profile}=fixture(false);profile.materials[0].effectPath=effectPath;
  const material=createSceneMaterial(THREE,map,source,0,profile);
  assert.equal(material.alphaTest,0);assert.equal(material.transparent,false);assert.equal(material.side,THREE.DoubleSide);
  assert.equal(material.userData.sceneAlpha.rule,'none');
 }
});
test('changed rules, named techniques, material identities, alpha planes or old packages fail closed',()=>{
 for(const change of [p=>p.format='old',p=>p.materials[0].index=1,p=>p.materials[0].name='other',
  p=>p.materials[0].texture='other',p=>p.materials[0].rule='none',p=>p.materials[0].reference=.35,
  p=>p.materials[0].effectPath='unknown',p=>p.materials[0].resolvedTechniqueIndex=2,
  p=>p.materials[0].sourceTechnique.name='tech1',p=>p.materials[0].sourceTechnique.valueWord0=0,
  p=>p.materials[0].sourceAlpha.mode='split-blue',p=>p.materials[0].sourceAlpha.baseAlphaSHA256='bad',
  p=>p.materials[0].sourceAlpha.width=128,p=>p.materials[0].sourceAlpha.height=0]){
  const {source,map,profile}=fixture();change(profile);assert.throws(()=>createSceneMaterial(THREE,map,source,0,profile));
 }
 const {source,map}=fixture();assert.throws(()=>createSceneMaterial(THREE,map,source,0,null));
});
const root=new URL('../../game-data/converted/',import.meta.url),manifestFile=new URL('manifest.json',root);
test('all current scenery and the door carry source-bound alpha rules, with only one cutout material',{
 skip:!existsSync(manifestFile)},()=>{
 const manifest=JSON.parse(readFileSync(manifestFile));let cutout=0,opaque=0;
 for(const entry of [...manifest.scenery,...manifest.dynamicModels]){
  const model=JSON.parse(readFileSync(new URL(entry.url.slice('/assets/'.length),root)));
  assert.equal(model.sceneAlpha.format,'oc2-scene-alpha-v1');
  for(const [i,source]of model.materials.entries()){
   const png=readFileSync(new URL(manifest.textures[source.diffuse].slice('/assets/'.length),root));
   const map=new THREE.Texture({width:png.readUInt32BE(16),height:png.readUInt32BE(20)});
   const material=createSceneMaterial(THREE,map,source,i,model.sceneAlpha);
   if(material.alphaTest){cutout++;assert.equal(source.diffuse,'texture/hum_city_big_tree01.tga');}
   else opaque++;
  }
 }
 assert.equal(cutout,1);assert.equal(opaque,51);
});
