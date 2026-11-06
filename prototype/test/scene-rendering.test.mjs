import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync}from'node:fs';
import * as THREE from 'three';
import {selectSceneZone,fogVisibility,sourceTonemap,sourceBloom,sourceLUTCoordinate,createSceneEnvironment,BLOOM_WEIGHTS}from'../public/scene-environment.js';
import {createRecoveredHDR}from'../public/hdr-renderer.js';
const profile={format:'oc2-scene-render-v1',defaultZoneId:194,hdr:{exposure:1,whitePoint:1.2,brightness:0,contrast:1,scale:1.3,thresholdOffset:.64,downscale:.5,blurWidth:2,blurIterations:2},zones:[
  {id:194,priority:0,bounds:[-3200,-448,-2176,320],fog:{color:[166/255,202/255,240/255],near:45,halfSpan:89},bloom:{decrease:0,intensity:.5}},
  {id:195,priority:14,bounds:[-2624,-272,-2284,251],fog:{color:[78/255,71/255,86/255],near:89,halfSpan:101},bloom:{decrease:.3945,intensity:1.2617}},
]};

test('original overlapping zone priority and exponential half-span select source fog without linear approximation',()=>{
  assert.equal(selectSceneZone(profile,-2617,182).id,195);assert.equal(selectSceneZone(profile,-2700,182).id,194);assert.equal(selectSceneZone(profile,-2617,252).id,194);
  const fog=profile.zones[1].fog;assert.equal(fogVisibility(89,fog),1);assert.equal(fogVisibility(190,fog),.5);assert.equal(fogVisibility(291,fog),.25);assert.equal(fogVisibility(10000,{...fog,rate:0}),1);
});

test('recovered Reinhardt, raw bloom and exact LUT indexing keep black finite and match source constants',()=>{
  assert.deepEqual(sourceTonemap([0,0,0],profile.hdr),[0,0,0]);
  const expected=(1+1/1.44)/2;assert(sourceTonemap([1,1,1],profile.hdr).every(v=>Math.abs(v-expected)<1e-6));
  assert.deepEqual(sourceBloom([[1,1,1],[1,1,1],[1,1,1],[1,1,1]],1.3,1,.5),[.15000000000000002,.15000000000000002,.15000000000000002]);
  assert.deepEqual(sourceLUTCoordinate([1,1,1]),[510.5/512,15.5/16]);assert(Math.abs(BLOOM_WEIGHTS.reduce((a,b)=>a+b,0)-1)<1e-10);
});

test('fog patch survives material cloning and uses skinned vertex view depth before gamma-space blending',()=>{
  const env=createSceneEnvironment(THREE,profile),scene=new THREE.Scene(),m=new THREE.MeshStandardMaterial(),clone=m.clone();
  scene.add(new THREE.Mesh(new THREE.BoxGeometry(),m),new THREE.Mesh(new THREE.BoxGeometry(),clone));env.update(-2617,182,scene);env.prepare(scene);
  for(const mat of [m,clone]){const shader={uniforms:{},vertexShader:'#include <fog_vertex>',fragmentShader:'#include <fog_fragment>'};mat.onBeforeCompile(shader);
    assert(shader.vertexShader.includes('-mvPosition.z'));assert(shader.fragmentShader.includes('1.0/2.2'));assert(shader.fragmentShader.includes('mix(sourceFogColor'));
    assert.equal(shader.uniforms.sourceFogNear.value,89);env.update(-2700,182,scene);assert.equal(shader.uniforms.sourceFogNear.value,45);env.update(-2617,182,scene);
  }
  assert.equal(scene.fog,null);
});

test('HDR uses half-size bloom, two H/V blur rounds, correct LUT orientation and frees targets',()=>{
  const calls=[],renderer={toneMapping:THREE.ACESFilmicToneMapping,getRenderTarget:()=>null,setRenderTarget:t=>calls.push(['target',t]),render:(s,c)=>calls.push(['draw',s,c])};
  const lut=new THREE.Texture(),hdr=createRecoveredHDR(THREE,renderer,profile,lut);hdr.setSize(1280,720);hdr.render(new THREE.Scene(),new THREE.PerspectiveCamera(),profile.zones[1]);
  assert.equal(renderer.toneMapping,THREE.NoToneMapping);assert.equal(lut.flipY,false);assert.equal(lut.colorSpace,THREE.NoColorSpace);
  assert.deepEqual(hdr.state(),{width:1280,height:720,bloomW:640,bloomH:360,passes:7,precision:'half-float'});assert.equal(calls.filter(c=>c[0]==='draw').length,7);
  const targets=new Set(calls.filter(c=>c[0]==='target'&&c[1]).map(c=>c[1]));let disposed=0;for(const t of targets)t.addEventListener('dispose',()=>disposed++);
  hdr.dispose();hdr.dispose();assert.equal(disposed,3);
});
const original=new URL('../../game-data/converted/rendering/tutorial.json',import.meta.url);
test('source tutorial profile has verified default HDR, both zones and matching LUT pixel rows',{skip:!existsSync(original)},()=>{
  const data=JSON.parse(readFileSync(original,'utf8'));assert.equal(data.world.mapId,5);assert.deepEqual(data.hdr.blurWidths,[2,4]);assert.equal(data.hdr.downscale,.5);
  assert.equal(selectSceneZone(data,-2617,182).id,195);assert.deepEqual(data.zones.find(z=>z.id===195).fog.color,[78/255,71/255,86/255]);assert.equal(data.lut.flipY,false);
});
