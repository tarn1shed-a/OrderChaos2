import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import * as THREE from 'three';
import {sourceUV,sourceLayerColor,tileGeometry,sourceTerrainMaterial,createSourceTerrain} from '../public/terrain-materials.js';
import {createSceneEnvironment} from '../public/scene-environment.js';
function fixture(){
 const terrain={world:'test',tileOrigin:[-2,3],tileCount:[2,1],grid:{width:129,height:65},positions:[],normals:[],sourceVertexColorSummary:{white16:true}};
 for(let z=0;z<=64;z++)for(let x=0;x<=128;x++){terrain.positions.push(-128+x,2,192+z);terrain.normals.push(0,1,0);}
 const tile={tile:[-2,3],textures:[{url:'/assets/base.png'}],mask:null,chunks:Array.from({length:64},(_,i)=>({chunk:[i%8,Math.floor(i/8)],effectiveIndices:[0,-1,-1,-1,-1]}))};
 return {terrain,tile};
}
test('native UV0 repeats each eight units and UV1 covers exactly one tile',()=>{
 assert.deepEqual(sourceUV(8,16),{base:[1,2],mask:[.125,.25]});assert.deepEqual(sourceUV(64,64),{base:[8,8],mask:[1,1]});
});
test('source layers mix sequentially in encoded space, with last-layer alpha',()=>{
 const c=[[1,0,0,1],[0,1,0,1],[0,0,1,1],[1,1,1,1],[0,0,0,.5]],m=[.5,.5,0,.5];
 assert.deepEqual(sourceLayerColor(c,m,[0,1,2,-1,4]),[.1875,.1875,.375]);
 assert.deepEqual(sourceLayerColor(c,m,[0,-1,-1,-1,-1]),[1,0,0]);
});
test('material batching preserves every source triangle, seam position and per-tile mask UV',()=>{
 const {terrain,tile}=fixture(),origin={x:-128,y:2,z:192},a=tileGeometry(THREE,terrain,tile,origin);
 const b=tileGeometry(THREE,terrain,{...tile,tile:[-1,3]},origin);
 assert.equal(a.geometry.index.count,64*64*6);assert.equal(a.geometry.groups.length,1);assert.equal(a.geometry.attributes.position.count,4225);
 for(let z=0;z<=64;z++)for(let axis=0;axis<3;axis++)assert.equal(a.geometry.attributes.position.array[(z*65+64)*3+axis],b.geometry.attributes.position.array[z*65*3+axis]);
 assert.equal(a.geometry.attributes.terrainMaskUV.getX(64),1);assert.equal(b.geometry.attributes.terrainMaskUV.getX(0),0);
 assert.equal(a.geometry.attributes.uv.getX(64),8);assert.equal(b.geometry.attributes.uv.getX(0),0);
 assert.throws(()=>tileGeometry(THREE,terrain,{...tile,chunks:tile.chunks.map(()=>tile.chunks[0])},origin));
});
test('source mix remains before Standard lighting and composes with existing recovered fog',()=>{
 const textures=Array.from({length:5},()=>new THREE.Texture()),m=sourceTerrainMaterial(THREE,[0,-1,2,-1,4],textures,new THREE.Texture());
 const env=createSceneEnvironment(THREE,{format:'oc2-scene-render-v1',defaultZoneId:1,zones:[{id:1,priority:0,bounds:[0,0,1,1],fog:{near:1,halfSpan:2,color:[0,0,0]}}]}),scene=new THREE.Scene();scene.add(new THREE.Mesh(new THREE.PlaneGeometry(),m));env.prepare(scene);
 const shader={uniforms:{},vertexShader:THREE.ShaderLib.standard.vertexShader,fragmentShader:THREE.ShaderLib.standard.fragmentShader};m.onBeforeCompile(shader);
 assert(shader.vertexShader.includes('terrainMaskCoord=terrainMaskUV'));assert(shader.fragmentShader.includes('terrainWeights.g'));
 assert(!shader.fragmentShader.includes('terrainWeights.r'));assert(shader.fragmentShader.includes('terrainWeights.a*layer4.a'));assert(shader.fragmentShader.includes('sRGBTransferEOTF'));
 assert(shader.fragmentShader.includes('mix(sourceFogColor'));assert.equal(shader.uniforms.terrainLayer2.value,textures[2]);
});
test('samplers preserve raw source orientation and do not change shared model textures',async()=>{
 const {terrain,tile}=fixture(),source=new THREE.Texture(),profile={format:'oc2-terrain-materials-v1',world:'test',tiles:[tile,{...tile,tile:[-1,3]}],fallback:'/assets/default.png'};
 const meshes=await createSourceTerrain(THREE,terrain,profile,{x:0,y:0,z:0},async()=>source);
 assert.equal(meshes.length,2);const map=meshes[0].material[0].map;assert.notEqual(map,source);assert.equal(map.flipY,false);assert.equal(map.wrapS,THREE.RepeatWrapping);assert.equal(source.flipY,true);
 await assert.rejects(()=>createSourceTerrain(THREE,terrain,{...profile,tiles:[]},{},async()=>source));
 await assert.rejects(()=>createSourceTerrain(THREE,terrain,{...profile,tiles:[tile,tile]},{},async()=>source));
});
const path=new URL('../../game-data/converted/maps/terrain-materials.json',import.meta.url);
test('real converted region uses nine source tiles and one recovered green mask',{skip:!existsSync(path)},()=>{
 const p=JSON.parse(readFileSync(path));assert.equal(p.format,'oc2-terrain-materials-v1');assert.equal(p.tiles.length,9);assert.equal(p.tiles.filter(t=>t.mask).length,1);
 assert.equal(p.coordinates.uv0UnitsPerRepeat,8);assert(p.tiles.every(t=>t.chunks.length===64));
 assert.equal(p.maskUpload.sourceFormatName,'RGBA8');assert.deepEqual(p.maskUpload.channelToByteLane,[0,1,2,3]);assert.equal(p.maskUpload.textureDefaults.appliedAsActiveQualityPreset,false);
});
