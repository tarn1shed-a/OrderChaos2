import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import * as THREE from 'three';
import {TERRAIN_LIGHTING_FORMAT,validateTerrainLighting,terrainVertexLight,terrainFragmentLight,createLitTerrainMaterial,TERRAIN_VERTEX} from '../public/terrain-lighting.js';
import {createSourceTerrain} from '../public/terrain-materials.js';
import {createBakedLighting} from '../public/scene-baked-lighting.js';

function fixture(){
 const terrain={world:'synthetic'},materials={tiles:[{tile:[-41,2]}],sources:{'world/synthetic/tile.trn':{sha256:'a'.repeat(64)}}};
 const state={blendEnabled:false,cullEnabled:true,cullFaceGL:0x405,frontFaceGLBeforeTargetXor:0x901,depthTestEnabled:true,depthWriteEnabled:true,depthFunctionGL:0x201};
 const effect={name:'Terrain',profiles:[32,36].map(field=>({sourcePointerField:field,serializedSamplerDefaults:0,techniques:[{name:'default',index:0,state:{...state},vertex:{defines:{COLOR0:'',LIGHTMAP:''}},fragment:{defines:{COLOR0:'',LIGHTMAP:''}}}]}))};
 const profile={format:TERRAIN_LIGHTING_FORMAT,world:'synthetic',configuration:{phase:0,lightmapEnabled:true,techniqueIndex:0,shadowMap:false,observedOriginalDevice:false},effect,
  vertexColor:{source:'RGB565',current:[255,255,255,255]},tiles:[{tile:[-41,2],source:'world/synthetic/tile.trn',sourceSHA256:'a'.repeat(64),runtimeFlags:Array(64).fill(0),waterClearedByTileMinimumBound:true,
   lightmap:{sourcePath:'original',url:'/assets/original.png',width:128,height:128,encoding:'ETC1',container:'PVR2',fallback:false}}]};
 const lighting={uniforms:{sourceTerrainLight:{value:new THREE.Vector3(.8,.9,1)},sourceModelLight:{value:new THREE.Vector3(100,100,100)},
  sourceToneNear:{value:new THREE.Vector3(1,1,1)},sourceToneFar:{value:new THREE.Vector3(1,1,1)},sourceToneOffsetNear:{value:new THREE.Vector3()},sourceToneOffsetFar:{value:new THREE.Vector3()},
  sourceToneDistance:{value:new THREE.Vector2(0,-1/17)},sourceFogNear:{value:100},sourceFogSpan:{value:100},sourceFogColor:{value:new THREE.Vector3()}}};
 const texture=()=>{const t=new THREE.Texture({width:128,height:128});t.colorSpace=THREE.NoColorSpace;t.flipY=false;return t;};
 return {terrain,materials,profile,lighting,texture};
}
test('terrain binding validates exact source tile hashes and the distinct LESS/default pass',()=>{
 const f=fixture(),tiles=validateTerrainLighting(f.terrain,f.materials,f.profile);
 assert.equal(tiles.size,1);assert.equal(tiles.get('-41,2').lightmap.sourcePath,'original');
 for(const change of [p=>p.format='old',p=>p.configuration.shadowMap=true,p=>p.configuration.techniqueIndex=1,
  p=>p.tiles[0].sourceSHA256='b'.repeat(64),p=>delete p.tiles[0].sourceSHA256,p=>p.tiles[0].runtimeFlags[0]=65536,p=>p.tiles[0].tile=[0,0],p=>p.vertexColor.current[0]=240,
  p=>p.effect.profiles[0].techniques[0].state.depthFunctionGL=0x203,p=>p.effect.profiles[0].techniques[0].vertex.defines.LIGHTING='']){
  const value=structuredClone(f.profile);change(value);assert.throws(()=>validateTerrainLighting(f.terrain,f.materials,value));
 }
});
test('terrain interpolates gain and offset at vertices and adds offset after atlas and generic light',()=>{
 const v=terrainVertexLight(-17,[0,-1/17],[1,.5,0],[0,0,1],[.2,-.2,.4],[0,0,0]);
 assert.deepEqual(v,{color:[.5,.25,.5],offset:[.1,-.1,.2]});
 assert.deepEqual(terrainFragmentLight([1,1,1],[.5,.5,.5],v,[2,2,2]),[.6,.15,.7]);
 assert.deepEqual(terrainFragmentLight([2,2,2],[1,1,1],{color:[1,1,1],offset:[0,0,0]},[2,2,2]),[4,4,4]);
});
test('source terrain material has no Standard lights, normal factor or color-space bridge; source layer5 retains alpha weight',()=>{
 const f=fixture(),textures=Array.from({length:5},f.texture),mask=f.texture(),atlas=f.texture();
 const m=createLitTerrainMaterial(THREE,[0,-1,2,-1,4],textures,mask,atlas,f.lighting);
 assert.equal(m.side,THREE.FrontSide);assert.equal(m.depthFunc,THREE.LessDepth);assert.equal(m.transparent,false);assert.equal(m.lights,false);assert.equal(m.toneMapped,false);
 assert(m.fragmentShader.includes('weights.a*layer4.a'));assert(m.fragmentShader.indexOf('color*=sourceTerrainLight')<m.fragmentShader.indexOf('color+=toneOffset'));
 assert(!/2\.2|sRGB|normal|light_direction|\.75|tonemapping_fragment/.test(m.fragmentShader+TERRAIN_VERTEX));
 assert.equal(m.uniforms.sourceTerrainLight,f.lighting.uniforms.sourceTerrainLight);assert.equal(m.uniforms.terrainLightMap.value,atlas);
 assert.equal(atlas.version,0);assert.equal(textures[0].version,0);
 textures[0].colorSpace=THREE.SRGBColorSpace;assert.throws(()=>createLitTerrainMaterial(THREE,[0,-1,2,-1,4],textures,mask,atlas,f.lighting));
});
test('generic and model multipliers remain independent while sharing the same native tone state',()=>{
 const targets={colors:{light_ambient:[1,1,1],light_diffuse:[0,0,0]},intensities:{intensity_lightMap:.75,model_intensity_lightMap:2},
  tone:{rawDistance:[0,17],gainNear:[1,1,1],gainFar:[1,1,1],offsetTargets:[0,0,0]}};
 const profile={format:'oc2-scene-baked-lighting-v1',world:'tutorial',configuration:{modelSlot:0,forceSingleSlot:true,environmentMode:0,rgbAdds:[0,0],observedOriginalDevice:false},instances:[{}],
  zones:[{id:1,isBase:true,baseId:1,priority:0,bounds:[0,0,1,1],targets}]};
 const context=createBakedLighting(THREE,profile,{});context.update(.5,.5);
 assert.deepEqual(context.state().modelLight,[2,2,2]);assert.deepEqual(context.state().terrainLight,[.75,.75,.75]);
 assert.notEqual(context.uniforms.sourceModelLight,context.uniforms.sourceTerrainLight);
 assert.deepEqual(context.uniforms.sourceToneOffsetNear.value.toArray(),[0,0,0]);
});
const root=new URL('../../game-data/converted/',import.meta.url),manifestFile=new URL('manifest.json',root);
const read=url=>JSON.parse(readFileSync(new URL(url.slice(8),root)));
test('actual terrain profile contains8 tile pages and the native tutorial world fallback',{skip:!existsSync(manifestFile)},()=>{
 const m=JSON.parse(readFileSync(manifestFile)),p=read(m.terrainLighting.url),terrain=read(m.map.url),albedo=read(m.map.materials.url);
 const tiles=validateTerrainLighting(terrain,albedo,p);assert.equal(tiles.size,9);assert.equal(p.tiles.filter(t=>t.lightmap.fallback).length,1);
 const fallback=p.tiles.find(t=>t.lightmap.fallback);assert.deepEqual(fallback.tile,[-43,3]);assert.equal(fallback.lightmap.sourcePath,'texture/terrain_lightmap_tutorial.tga');
});
test('actual terrain meshes keep source albedo geometry, bind their own map and preserve cached textures',{skip:!existsSync(manifestFile)},async()=>{
 const m=JSON.parse(readFileSync(manifestFile)),p=read(m.terrainLighting.url),terrain=read(m.map.url),albedo=read(m.map.materials.url),cache=new Map();
 const lighting=createBakedLighting(THREE,read(m.sceneBakedLighting.url),fixture().lighting.uniforms);
 const loader=async url=>{
  if(!cache.has(url)){const b=readFileSync(new URL(url.slice(8),root)),t=new THREE.Texture({width:b.readUInt32BE(16),height:b.readUInt32BE(20)});t.colorSpace=THREE.NoColorSpace;cache.set(url,t);}return cache.get(url);
 };
 const meshes=await createSourceTerrain(THREE,terrain,albedo,new THREE.Vector3(),loader,{profile:p,context:lighting});
 assert.equal(meshes.length,9);assert.equal(meshes.filter(m=>m.userData.terrainLighting.fallback).length,1);
 let groups=0;
 for(const mesh of meshes){assert.equal(mesh.geometry.getAttribute('position').count,4225);groups+=mesh.material.length;
  for(const mat of mesh.material){assert.equal(mat.isShaderMaterial,true);assert.equal(mat.uniforms.sourceTerrainLight,lighting.uniforms.sourceTerrainLight);assert.equal(mat.depthFunc,THREE.LessDepth);}
 }
 assert.equal(groups,12);assert([...cache.values()].every(t=>t.flipY===true&&t.version===0),'Sampler clones do not modify cached texture state');
});
