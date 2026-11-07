import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { sourceSkinColor, sourceCharacterLighting, createCharacterMaterial, setCharacterMaterialLook } from '../public/character-materials.js';
import { createSceneEnvironment } from '../public/scene-environment.js';

function fixture(){
  const samplers=Object.fromEntries(['texture','normalMap','maskMap','diffusePal','specularPal','specularPalBack','skinColorMask'].map(key=>[key,`/assets/${key}.png`]));
  const entry={samplers,defines:['RIM_LIGHT','SKIN_COLOR','ALPHA_TEST'],alphaTest:.5,doubleSided:true,
    scalars:{ambientIntensity:.7,diffuseIntensity:.5,specularIntensity:.6,rim_spec_pow:2,rim_intensity:1.5,rim_fresnel_pow:2}};
  const colors={hair:{},skin:{}};
  for(let i=1;i<=6;i++){colors.hair[`color${i}`]={primaryRGB:[i/6,.2,.3]};colors.skin[`color${i}`]={primaryRGB:[.8,i/6,.6]};}
  const textures=new Map(Object.values(samplers).map(url=>[url,new THREE.Texture()]));return{entry,colors,textures};
}
test('source tint channels multiply hair/skin and neutral eye zero preserves the original eye texture',()=>{
  assert.deepEqual(sourceSkinColor([.4,.3,.2],[1,0,0],[1,.5,.2],[1,1,1]),[.4,.15,.04000000000000001]);
  assert.deepEqual(sourceSkinColor([.4,.3,.2],[0,1,0],[1,1,1],[.5,1,.5]),[.2,.3,.1]);
  assert.deepEqual(sourceSkinColor([.4,.3,.2],[0,0,1],[1,1,1],[1,1,1]),[.4,.3,.2]);
});
test('palette lighting keeps distinct front/back specular, mask channels and native rim powers',()=>{
  const {entry}=fixture();let sampled=[];
  const result=sourceCharacterLighting({color:[.5,.5,.5],normal:[0,0,1],light:[0,0,1],view:[0,0,1],mask:[.5,0],ambient:[1,1,1],diffuse:[1,1,1],specular:[1,1,1],scalars:entry.scalars,
    palette:(name,coordinate)=>{sampled.push([name,coordinate]);return name==='diffusePal'?[.2,.4,.6]:name==='specularPal'?[.3,.3,.3]:[.1,.1,.1];}});
  [.52,.57,.62].forEach((expected,i)=>assert(Math.abs(result[i]-expected)<1e-7));
  assert.deepEqual(sampled,[['diffusePal',1],['specularPal',1],['specularPalBack',0]]);
  const rim=sourceCharacterLighting({color:[0,0,0],normal:[0,0,1],light:[0,0,1],view:[1,0,0],mask:[0,1],ambient:[0,0,0],diffuse:[0,0,0],specular:[0,0,0],scalars:entry.scalars,palette:()=>[0,0,0]});
  assert(Math.abs(rim[0]-.6525)<1e-6);assert(Math.abs(rim[2]-.75)<1e-6);
});
test('native material cloning preserves tint but owns its uniforms; shader composes source TBN, cutout, shadows and recovered fog',()=>{
  const {entry,colors,textures}=fixture(),material=createCharacterMaterial(THREE,entry,textures,colors);
  setCharacterMaterialLook(material,{hair:'hair2',hairColor:'color2',skinColor:'color3'});
  const clone=material.clone();setCharacterMaterialLook(material,{hair:'hair3',hairColor:'color5',skinColor:'color1'});
  const env=createSceneEnvironment(THREE,{format:'oc2-scene-render-v1',defaultZoneId:1,zones:[{id:1,priority:1,bounds:[0,0,1,1],fog:{color:[.1,.2,.3],near:1,halfSpan:2}}]}),scene=new THREE.Scene();
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(),material),new THREE.Mesh(new THREE.BoxGeometry(),clone));env.update(.5,.5,scene);env.prepare(scene);
  const compile=mat=>{const shader={uniforms:{},vertexShader:THREE.ShaderLib.standard.vertexShader,fragmentShader:THREE.ShaderLib.standard.fragmentShader};mat.onBeforeCompile(shader);return shader;};
  const a=compile(material),b=compile(clone);
  assert.notEqual(a.uniforms.nativeHair.value,b.uniforms.nativeHair.value);
  assert.deepEqual(a.uniforms.nativeHair.value.toArray(),colors.hair.color5.primaryRGB);assert.deepEqual(b.uniforms.nativeHair.value.toArray(),colors.hair.color2.primaryRGB);
  assert(a.vertexShader.includes('sourceB=-sourceBinormal'));assert(a.vertexShader.includes('skinMatrix*vec4(sourceT,0.0)'));
  assert(a.fragmentShader.includes('diffuseColor.a<=0.500000'));assert(a.fragmentShader.includes('pow(max(nRGB'));
  assert(a.fragmentShader.includes('mix(sourceFogColor'));assert(a.fragmentShader.includes('getShadowMask()'));
  assert(a.fragmentShader.indexOf('#include <shadowmap_pars_fragment>')<a.fragmentShader.indexOf('#include <shadowmask_pars_fragment>'));
  assert.equal(material.side,THREE.DoubleSide);assert.equal(material.transparent,false);
});
