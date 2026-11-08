import test from 'node:test';
import assert from 'node:assert/strict';
import {existsSync,readFileSync} from 'node:fs';
import * as THREE from 'three';
import {BAKED_FORMAT,BAKED_VERTEX,BAKED_FRAGMENT,modelLight,sourceVertexLight,createBakedLighting,createBakedSceneMaterial,bindInstanceLightmap} from '../public/scene-baked-lighting.js';
import {createSceneEnvironment} from '../public/scene-environment.js';

const target=(gain=1,distance=[0,17])=>({colors:{light_ambient:[1,1,1],light_diffuse:[1,.5,.25]},intensities:{model_intensity_lightMap:1.33},tone:{rawDistance:distance,gainNear:[gain,gain,gain],gainFar:[.5,.5,.5]}});
function fixture(){
 const instance={id:8,model:'synthetic',tile:[-41,2]},atlas=new THREE.Texture({width:256,height:256});atlas.colorSpace=THREE.NoColorSpace;atlas.flipY=false;
 const profile={format:BAKED_FORMAT,world:'tutorial',configuration:{modelSlot:0,forceSingleSlot:true,environmentMode:0,rgbAdds:[0,0],observedOriginalDevice:false},
  zones:[{id:1,baseId:1,isBase:true,priority:0,bounds:[-20,-20,20,20],targets:target(1,null)},
   {id:2,baseId:1,isBase:false,priority:1,bounds:[0,0,10,10],targets:target(.25)}],
  instances:[{objectId:8,model:'synthetic',tile:[-41,2],bindings:[{ordinal:0,atlas:'pageA',uvTransform:[.2,.3,.4,.5]}]},
   {objectId:9,model:'synthetic',tile:[-41,2],bindings:[{ordinal:0,atlas:'pageB',uvTransform:[.1,0,.1,.2]}]}]};
 const fog={sourceFogNear:{value:10},sourceFogSpan:{value:100},sourceFogColor:{value:new THREE.Vector3()}};
 const lighting=createBakedLighting(THREE,profile,fog),source={name:'synthetic',diffuse:'synthetic.tga'},map=atlas.clone();
 const data={sceneBakedLighting:{format:BAKED_FORMAT,materials:[{index:0,...source,texture:source.diffuse,sourceLightMap:'texture/lightmap.tga'}]},
  sceneAlpha:{format:'oc2-scene-alpha-v1',materials:[{index:0,name:source.name,texture:source.diffuse,effectPath:'ut_lightmap_solid.bdae',resolvedTechniqueIndex:0,sourceTechnique:{name:'tech0',valueWord0:2},rule:'none',reference:null,sourceAlpha:{mode:'opaque-ETC1',baseAlphaSHA256:'a'.repeat(64),width:256,height:256}}]}};
 return {instance,atlas,profile,lighting,source,map,data};
}
test('float32 lighting includes native byte roundtrip and explicit RGB adds',()=>{
 assert.deepEqual(modelLight([.5,.5,.5],[0,0,0],1),Array(3).fill(Math.fround(128*Math.fround(1/255))));
 assert.deepEqual(modelLight([1,1,1],[1,1,1],1,[.25,.5]),[2,2,2]);
 assert.throws(()=>modelLight([2,0,0],[0,0,0],1));
});
test('vertex tone stays at the vertex stage with encoded diffuse-atlas multiplication and no Standard lighting or transfer',()=>{
 assert.deepEqual(sourceVertexLight(-17,[0,-1/17],[1,1,1],[0,0,0],[2,2,2]),[1,1,1]);
 assert(BAKED_VERTEX.includes('vertexLight=sourceModelLight*mix'));
 assert(BAKED_VERTEX.includes('sourceUVTransform.xy+sourceUV1*sourceUVTransform.zw'));
 assert(BAKED_FRAGMENT.includes('color.rgb*=texture2D(sourceAtlas,atlasUV).rgb'));
 assert(!/normal|light_direction|sRGB|2\.2|colorspace_fragment|tonemapping_fragment/.test(BAKED_VERTEX+BAKED_FRAGMENT));
});
test('native immediate branch uses >500ms selection, raw inclusive float32 bounds and retains tone on skipped writes/no zone',()=>{
 const {lighting}=fixture();
 assert.deepEqual(lighting.update(0,0),{baseId:1,overlayId:2});
 assert.deepEqual(lighting.update(-1,0,500),{baseId:1,overlayId:2});
 assert.deepEqual(lighting.update(-1,0,1),{baseId:1,overlayId:null});
 assert.equal(lighting.state().toneDistance[1],Math.fround(-1/17),'base skipped raw distance retains previous');
 const before=lighting.state().modelLight;
 assert.equal(lighting.update(30,30,501),null);assert.deepEqual(lighting.state().modelLight,before);
 const {lighting:edge}=fixture();assert.equal(edge.update(10,10).overlayId,2);
 assert.equal(edge.update(10.000001,10,501).overlayId,null);
});
test('unsupported packages, quality/slot branches and non-finite inputs fail instead of guessing device state',()=>{
 for(const change of [p=>p.format='old',p=>p.configuration.modelSlot=1,p=>p.configuration.environmentMode=4,
  p=>p.configuration.observedOriginalDevice=true,p=>p.zones[0].bounds[0]=NaN,p=>p.zones.push(p.zones[0])]){
  const {profile}=fixture();change(profile);assert.throws(()=>createBakedLighting(THREE,profile,{}));
 }
 const {lighting}=fixture();assert.throws(()=>lighting.update(0,0,.5));assert.throws(()=>lighting.update(Infinity,0));
});
function template(f){
 const material=createBakedSceneMaterial(THREE,f.map,f.source,0,f.data,f.lighting);
 const geometry=new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute([0,0,0,1,0,0,0,1,0],3))
  .setAttribute('sourceUV1',new THREE.Float32BufferAttribute([0,0,1,0,0,1],2));
 return new THREE.Group().add(new THREE.Mesh(geometry,material));
}
test('shared model instances own UV/atlas materials, keep ordinal fallback and shared live environment values',()=>{
 const f=fixture(),root=template(f),a=root.clone(true),b=root.clone(true),pages=new Map([['pageA',f.atlas],['pageB',f.atlas.clone()]]);
 bindInstanceLightmap(THREE,a,f.instance,f.lighting,pages);
 bindInstanceLightmap(THREE,b,{...f.instance,id:9},f.lighting,pages);
 const ma=a.children[0].material,mb=b.children[0].material;
 assert.notEqual(ma,mb);assert.equal(root.children[0].material.uniforms.sourceAtlas.value,null);
 assert.deepEqual(ma.uniforms.sourceUVTransform.value.toArray(),[.2,.3,.4,.5]);
 assert.deepEqual(mb.uniforms.sourceUVTransform.value.toArray(),[.1,0,.1,.2]);
 assert.equal(ma.uniforms.sourceModelLight,mb.uniforms.sourceModelLight);
 const fallback=root.clone(true);fallback.children[0].material=root.children[0].material.clone();fallback.children[0].material.userData.sceneBakedLighting.index=7;
 bindInstanceLightmap(THREE,fallback,f.instance,f.lighting,pages);
 assert.deepEqual(fallback.children[0].material.uniforms.sourceUVTransform.value.toArray(),[.2,.3,.4,.5],'material ordinal past the binding array uses entry0');
 assert.equal(ma.uniforms.sourceAtlas.value,f.atlas);
 assert.equal(ma.lights,false);assert.equal(ma.toneMapped,false);assert.equal(ma.depthFunc,THREE.LessEqualDepth);
 f.lighting.update(1,1);assert.equal(ma.uniforms.sourceModelLight,f.lighting.uniforms.sourceModelLight);
});
test('wrong tile, duplicate instance, missing UV1/atlas and sparse material keys cannot render stale bindings',()=>{
 for(const mutate of [f=>f.instance.tile=[-42,2],f=>f.profile.instances.push(f.profile.instances[0]),
  f=>f.profile.instances[0].bindings[0].ordinal=1]){
  const f=fixture();mutate(f);assert.throws(()=>bindInstanceLightmap(THREE,template(f),f.instance,f.lighting,new Map([['pageA',f.atlas]])));
 }
 const f=fixture(),root=template(f);root.children[0].geometry.deleteAttribute('sourceUV1');
 assert.throws(()=>bindInstanceLightmap(THREE,root,f.instance,f.lighting,new Map()));
 assert.throws(()=>bindInstanceLightmap(THREE,template(f),f.instance,f.lighting,new Map()));
 f.map.colorSpace=THREE.SRGBColorSpace;assert.throws(()=>template(f));
 const bad=fixture(),badRoot=template(bad);badRoot.children[0].material.userData.sceneBakedLighting.index=-1;
 assert.throws(()=>bindInstanceLightmap(THREE,badRoot,bad.instance,bad.lighting,new Map([['pageA',bad.atlas]])));
});
test('existing Standard fog bridge does not apply an extra gamma encode to source baked ShaderMaterial',()=>{
 const f=fixture(),root=template(f),before=root.children[0].material.onBeforeCompile;
 const env=createSceneEnvironment(THREE,{format:'oc2-scene-render-v1',zones:[{id:1}]});
 env.prepare(root);assert.equal(root.children[0].material.onBeforeCompile,before);
 assert.equal(root.children[0].material.fragmentShader,BAKED_FRAGMENT);
});
const root=new URL('../../game-data/converted/',import.meta.url),manifestFile=new URL('manifest.json',root);
test('actual package supplies 39 unique slot0 instances, three raw atlases and all50 static source materials',{skip:!existsSync(manifestFile)},()=>{
 const m=JSON.parse(readFileSync(manifestFile)),p=JSON.parse(readFileSync(new URL(m.sceneBakedLighting.url.slice(8),root)));
 assert.equal(p.instances.length,39);assert.equal(p.atlases.length,3);let total=0;
 const lighting=createBakedLighting(THREE,p,{});
 assert.deepEqual(lighting.update(-2608,187.3),{baseId:194,overlayId:195});
 for(const item of m.scenery){const data=JSON.parse(readFileSync(new URL(item.url.slice(8),root)));assert.equal(data.sceneBakedLighting.format,BAKED_FORMAT);
  for(const mesh of data.meshes)assert.equal(mesh.sourceUV1.length,mesh.positions.length/3*2);
  total+=data.sceneBakedLighting.materials.length;
 }
 assert.equal(total,50);
 const door=JSON.parse(readFileSync(new URL(m.dynamicModels[0].url.slice(8),root)));assert.equal(door.sceneBakedLighting,undefined);
});
