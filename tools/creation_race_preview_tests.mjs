import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import vm from 'node:vm';
import {createHash} from 'node:crypto';
import {buildCreationRacePreview,checkedCreationPreview,CREATION_RACE_IDENTITIES} from './preview/character_creation_preview_proposal.mjs';
import * as previewAPI from './preview/character_creation_preview_proposal.mjs';
import {applyCreationStageTransform,createCreationStageCamera} from './preview/source-creation-stage.mjs';
import {webGLSource,paletteGlobals} from './preview/source-scene-palette.js';

const ROOT=resolve(fileURLToPath(new URL('../',import.meta.url)));
const json=p=>JSON.parse(readFileSync(p,'utf8'));
const hash=b=>createHash('sha256').update(b).digest('hex');
const stageSource=readFileSync(join(ROOT,'deploy/creation_preview.mjs'),'utf8');
const scope={};vm.createContext(scope);
vm.runInContext(stageSource.replace(/^import[^\n]*\n/gm,'').replaceAll('export ','')+';this.validate=validateCreationDelivery;',scope);
const qa=join(ROOT,'analysis/raw/creation-race-preview-20261115/qa-static-elf-female-v1');

test('new costume stage is optional and old human-only versions retain their admission',t=>{
 if(!existsSync(join(qa,'game-data/converted/source-creation-stage/manifest-races-v1.json'))){t.skip('Private candidate absent');return;}
 const p=json(join(qa,'game-data/converted/source-creation-stage/manifest-races-v1.json'));
 assert.equal(scope.validate(p),p);
 for(const bad of [{...p,format:'oc2-source-creation-preview-delivery-v3'},
  {...p,allNineRacePreviewsRestored:true},{...p,sourceRaceTraceSHA256:'0'.repeat(64)},
  {...p,additionalOriginalPreviews:[{...p.additionalOriginalPreviews[0],display:2053}]},
  {...p,previews:{...p.previews,'2:0':p.previews['2:1']}}])assert.throws(()=>scope.validate(bad));
 for(const path of ['/assets/source-creation-stage/%2e%2e/%2e%2e/outside.json','/assets/source-x/%2foutside.json',
  '/assets/source-x/a\\b.json','/assets/source-x/stage.json?next=outside','/assets/source-x/a//b.json'])
  assert.throws(()=>scope.validate({...p,stage:path}));
});

test('actual loadActor rejects escaped references and wrong identities before following them',async()=>{
 const base=join(ROOT,'analysis/raw/creation-race-preview-20261115/candidate-v1/elf-female');
 if(!existsSync(join(base,'manifest.json')))return;
 const manifest=json(join(base,'manifest.json')),data=json(join(base,'assets/character.json'));
 const source=stageSource.slice(stageSource.indexOf(' async function loadActor(e,race,gender){'),stageSource.indexOf('\n function frame(time){'));
 for(const change of [m=>({...m,model:'../../outside.json'}),m=>({...m,model:'/%2e%2e/outside.json'}),
  m=>({...m,model:'https://outside.invalid/a.json'}),m=>({...m,race:0}),
  m=>({...m,materials:m.materials.map((row,i)=>i?row:{...row,samplers:{...row.samplers,texture:'../../outside.png'}})})]){
  const requests=[],images=[],ctx={racePreviewAPI:async()=>previewAPI,legacyCreationPreview:previewAPI,
   CREATION_RACES_FORMAT:'oc2-source-creation-preview-delivery-v4',
   json:async url=>{requests.push(url);return url.endsWith('/manifest.json')?change(structuredClone(manifest)):data;}};
  vm.createContext(ctx);vm.runInContext(source+';this.load=loadActor;',ctx);
  globalThis.location={href:'http://127.0.0.1:62000/'};
  try{await assert.rejects(ctx.load({p:{format:ctx.CREATION_RACES_FORMAT,previews:{'2:1':{baseURL:'/assets/source-test/'}}},texture:async url=>{images.push(url);}},2,1));}
  finally{delete globalThis.location;}
  assert.deepEqual(requests,['http://127.0.0.1:62000/assets/source-test/manifest.json']);assert.equal(images.length,0);
 }
 const requests=[],images=[],ctx={racePreviewAPI:async()=>previewAPI,legacyCreationPreview:previewAPI,
  CREATION_RACES_FORMAT:'oc2-source-creation-preview-delivery-v4',json:async url=>{requests.push(url);return url.endsWith('/manifest.json')?manifest:
   {...data,source:'model/npc/character/human/male/oc2_human_m_body_01.bdae',sourceCreation:{...data.sourceCreation,displayId:2053,race:0,gender:0,sourceModelId:1}};}};
 vm.createContext(ctx);vm.runInContext(source+';this.load=loadActor;',ctx);globalThis.location={href:'http://127.0.0.1:62000/'};
 try{await assert.rejects(ctx.load({p:{format:ctx.CREATION_RACES_FORMAT,previews:{'2:1':{baseURL:'/assets/source-test/'}}},texture:async url=>images.push(url)},2,1));}
 finally{delete globalThis.location;}
 assert.equal(requests.length,2);assert.equal(images.length,0);
 for(const value of [
  {...data,source:'model/npc/character/human/male/oc2_human_m_body_01.bdae'},
  {...data,sourceCreation:{...data.sourceCreation,displayId:2053}},
  {...data,sourceCreation:{...data.sourceCreation,race:0}},
  {...data,sourceCreation:{...data.sourceCreation,gender:0}},
  {...data,sourceCreation:{...data.sourceCreation,sourceModelId:1}},
  {...data,sourceCreation:{...data.sourceCreation,visibleMeshIndices:[]}},
 ])assert.throws(()=>previewAPI.checkedCreationModel(manifest,value,{race:2,gender:1}));
});

test('legacy actual loadActor validates its human model without importing the new private module',async t=>{
 const folder=join(ROOT,'analysis/raw/character-addressing-correction-20261114/male-corrected');
 if(!existsSync(join(folder,'manifest.json'))){t.skip('Private legacy source candidate absent');return;}
 const manifest=json(join(folder,'manifest.json')),data=json(join(folder,'assets/character.json'));
 const prefix=stageSource.slice(0,stageSource.indexOf('export function createSourceCreationPreview')).replace(/^import[^\n]*\n/gm,'').replaceAll('export ','');
 const load=stageSource.slice(stageSource.indexOf(' async function loadActor(e,race,gender){'),stageSource.indexOf('\n function frame(time){'));
 for(const format of ['oc2-source-creation-preview-delivery-v1','oc2-source-creation-preview-delivery-v2','oc2-source-creation-preview-delivery-v3']){
  const requests=[],images=[],context={URL,legacyCreationPreview:previewAPI,location:{href:'http://127.0.0.1:62000/'},
   json:async url=>{requests.push(url);return url.endsWith('/manifest.json')?manifest:{...data,sourceCreation:{...data.sourceCreation,displayId:2047}};}};
  vm.createContext(context);vm.runInContext(prefix+load+';this.load=loadActor;',context);
  // No importModuleDynamically callback is installed: any accidental dynamic
  // import fails before json(). Two actual requests prove the legacy route.
  await assert.rejects(context.load({p:{format,previews:{'0:0':{baseURL:'/assets/source-legacy/'}}},texture:async url=>images.push(url)},0,0));
  assert.deepEqual(requests,['http://127.0.0.1:62000/assets/source-legacy/manifest.json','http://127.0.0.1:62000/assets/source-legacy/assets/character.json']);
  assert.equal(images.length,0);
 }
});

test('actual original costume assembly and raw source-material factory retain own rig/idle, never write a role',async t=>{
 const folder=join(ROOT,'analysis/raw/creation-race-preview-20261115/candidate-v1/elf-female');
 if(!existsSync(join(folder,'manifest.json'))){t.skip('Private original stage-0 candidate absent');return;}
 const THREE=await import(pathToFileURL(join(ROOT,'analysis/raw/character-human-male-20261114/candidate-v1/three.module.js')));
 const m=json(join(folder,'manifest.json')),data=json(join(folder,m.model.replace(/^\//,'')));
 assert.equal(m.originalDisplayId,2047);assert.equal(m.sourceModelId,2);assert.equal(data.sourceCreation.displayId,2047);
 const checked=json(join(folder,'package-files.json')).files;
 for(const name of new Set(['manifest.json',m.model.replace(/^\//,''),...m.materials.flatMap(r=>Object.values(r.samplers).map(p=>p.replace(/^\//,'')))])){
  const b=readFileSync(join(folder,name));assert.deepEqual(checked[name],{bytes:b.length,sha256:hash(b)});
 }
 const visibility=json(join(folder,'visibility-private.json'));
 assert.deepEqual(visibility.garments.map(g=>g.itemKey),[100342,100354]);
 assert(visibility.garments.every(g=>g.model.ModelPath.includes('oc2_elf_f_light_sunken_')));
 assert.equal(json(join(folder,'binding-private.json')).length,18);
 for(const bad of [{...m,creationPreviewAdmitted:false},{...m,appearanceComplete:false},{...m,originalDisplayId:2046},
  {...m,sourceModelId:1},{...m,sourceTraceSHA256:'0'.repeat(64)},{...m,liveActor:true}])assert.throws(()=>checkedCreationPreview(bad,{race:2,gender:1}));
 const textures=new Map(m.materials.flatMap(r=>Object.values(r.samplers)).map(p=>{const texture=new THREE.Texture();texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;return[p,texture];}));
 const stage=json(join(qa,'game-data/converted/source-creation-stage/stage.json'));
 const fresh=json(join(qa,'game-data/converted/source-creation-stage/environment.json'));
 const programs=['lt_pal_normal_vs.glsl','lt_pal_normal_fs.glsl'].map(name=>readFileSync(join(qa,'game-data/converted/source-map-palette',name),'utf8'));
 const context={webGLSource,paletteGlobals};vm.createContext(context);
 // Evaluate the actual production material function. Imports unrelated to
 // this factory are outside this CPU constructor test; no fake GPU is used.
 const source=readFileSync(join(ROOT,'deploy/attribute_preview.mjs'),'utf8').replace(/^import[^\n]*\n/gm,'').replace(/^export \{[^\n]*\n/gm,'').replaceAll('export ','');
 vm.runInContext(source+';this.make=material;',context);
 const lighting={uniforms:Object.fromEntries(Object.entries(fresh.uniformInputs).map(([key,value])=>[key,{value:Array.isArray(value)?new THREE.Vector3(...value):value}]))};
 const preview=buildCreationRacePreview({THREE,createMaterial:()=>new THREE.MeshBasicMaterial(),manifest:m,data,textures,race:2,gender:1});
 const originalMaterials=new Set(preview.meshes.flatMap(o=>o.material).filter(Boolean)),materials=[];
 for(const [index,object]of preview.meshes.entries()){
  assert.deepEqual(Array.from(object.geometry.getAttribute('skinWeight').array),data.rig.skins.find(s=>s.mesh===index).skinWeights.map(Math.fround));
  if(!object.visible)continue;
  const list=[];
  for(const i of new Set(data.meshes[index].groups.map(g=>g.material))){
   const row=m.materials.find(r=>r.index===i);
   const material=context.make(THREE,row,textures,programs,object,{...m.colors,eye:stage.transform.freshModelEyeColor},fresh.sourceCharacterLight,lighting,stage.sourceControllerLight.direction);
   assert(material.isRawShaderMaterial);assert.equal(material.defines.HARDWARE_SKINNING_CUSTOM_BONE_COUNT,object.skeleton.bones.length);
   assert.equal(material.depthFunc,THREE.LessEqualDepth);assert.equal(material.blending,THREE.NoBlending);
   list[i]=material;materials.push(material);
  }
  object.material=list;
 }
 applyCreationStageTransform(preview.root,stage);assert.deepEqual(preview.root.matrix.elements,stage.transform.matrix);
 const actualScale=new THREE.Vector3().setFromMatrixScale(preview.root.matrix);
 assert(actualScale.toArray().every(v=>Math.abs(v-5)<1e-6));assert.deepEqual(new THREE.Vector3().setFromMatrixPosition(preview.root.matrix).toArray(),[-2572,139,-30]);
 const before=preview.nodes.map(n=>n.quaternion.toArray());preview.update(.1);preview.root.updateMatrixWorld(true);
 assert(preview.nodes.some((node,i)=>node.quaternion.toArray().some((v,j)=>Math.abs(v-before[i][j])>1e-5)));
 const camera=createCreationStageCamera(THREE,stage,{width:1136,height:640});
 for(const object of preview.meshes.filter(o=>o.visible)){
  object.skeleton.update();
  for(const material of object.material.filter(Boolean)){material.onBeforeRender(null,null,camera.camera);assert(material.uniforms.BoneMatrices.value.every(v=>v.elements.every(Number.isFinite)));}
  const vertex=object.getVertexPosition(0,new THREE.Vector3());assert(vertex.toArray().every(Number.isFinite));
 }
 preview.dispose();preview.dispose();for(const material of materials)material.dispose();for(const material of originalMaterials)material.dispose();
 assert.equal(Object.keys(CREATION_RACE_IDENTITIES).includes('2:0'),false);
});

test('each additional body uses its own real stage costume, material programs and literal source skeleton',async t=>{
 const base=join(ROOT,'analysis/raw/creation-race-preview-20261115');
 const rows=[['elf-female','candidate-v1',2047,18,72],['mendel-male','candidate-v1',2048,20,80],
  ['mendel-female','candidate-v2',2049,18,72],['orc-male','candidate-v1',2050,18,72],
  ['orc-female','candidate-v1',2051,16,64],['kartan','candidate-v3',2052,17,68]];
 if(rows.some(([key,version])=>!existsSync(join(base,version,key,'manifest.json')))){t.skip('Private complete six-body source candidates absent');return;}
 const THREE=await import(pathToFileURL(join(ROOT,'analysis/raw/character-human-male-20261114/candidate-v1/three.module.js')));
 const stage=json(join(qa,'game-data/converted/source-creation-stage/stage.json')),fresh=json(join(qa,'game-data/converted/source-creation-stage/environment.json'));
 const programs=['lt_pal_normal_vs.glsl','lt_pal_normal_fs.glsl'].map(n=>readFileSync(join(qa,'game-data/converted/source-map-palette',n),'utf8'));
 const context={webGLSource,paletteGlobals};vm.createContext(context);
 vm.runInContext(readFileSync(join(ROOT,'deploy/attribute_preview.mjs'),'utf8').replace(/^import[^\n]*\n/gm,'').replace(/^export \{[^\n]*\n/gm,'').replaceAll('export ','')+';this.make=material;',context);
 const lighting={uniforms:Object.fromEntries(Object.entries(fresh.uniformInputs).map(([key,value])=>[key,{value:Array.isArray(value)?new THREE.Vector3(...value):value}]))};
 let count=0;
 for(const [key,version,display,controllers,cases]of rows){
  const folder=join(base,version,key),manifest=json(join(folder,'manifest.json')),data=json(join(folder,'assets/character.json'));
  const proofs=json(join(folder,'binding-private.json'));
  assert.equal(proofs.length,controllers);assert.equal(proofs.reduce((n,p)=>n+p.nativeIdleSamplesAndPaletteAndVertices.length,0),cases);
  for(const p of proofs){assert(p.nativeNamedBoneInverseConsumersExecuted);assert(p.nativeIdleSamplesAndPaletteAndVertices.every(c=>Math.max(c.maximumSampleError,c.maximumPaletteError,c.maximumVertexError)<=.002));}
  const garments=json(join(folder,'visibility-private.json')).garments;
  assert(garments.every(g=>!g.model.ModelPath.includes('/oc2_human_')),'Never borrow human stage garments');
  assert.equal(manifest.originalDisplayId,display);assert.equal(data.sourceCreation.displayId,display);
  const source=CREATION_RACE_IDENTITIES[manifest.race+':'+manifest.gender];assert.equal(source.key,key);
  const textures=new Map(manifest.materials.flatMap(r=>Object.values(r.samplers)).map(p=>{const texture=new THREE.Texture();texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;return[p,texture];}));
  const preview=buildCreationRacePreview({THREE,createMaterial:()=>new THREE.MeshBasicMaterial(),manifest,data,textures,race:manifest.race,gender:manifest.gender});
  assert.equal(preview.meshes.filter(o=>o.visible).length,manifest.visibleMeshIndices.length);
  const owned=[];
  for(const [i,object]of preview.meshes.entries())if(object.visible){
   for(const index of new Set(data.meshes[i].groups.map(g=>g.material))){
    const row=manifest.materials.find(r=>r.index===index),material=context.make(THREE,row,textures,programs,object,
     {...manifest.colors,eye:stage.transform.freshModelEyeColor},fresh.sourceCharacterLight,lighting,stage.sourceControllerLight.direction);
    owned.push(material);assert(material.isRawShaderMaterial);assert.equal(material.defines.HARDWARE_SKINNING_CUSTOM_BONE_COUNT,object.skeleton.bones.length);
   }
  }
  const before=preview.nodes.map(n=>n.quaternion.toArray());preview.update(.1);preview.root.updateMatrixWorld(true);
  assert(preview.nodes.some((n,i)=>n.quaternion.toArray().some((v,j)=>Math.abs(v-before[i][j])>1e-5)));
  for(const object of preview.meshes.filter(o=>o.visible)){object.skeleton.update();assert(object.getVertexPosition(0,new THREE.Vector3()).toArray().every(Number.isFinite));}
  if(key==='mendel-female')assert.equal(proofs.find(p=>p.exactSourceTailProof).exactSourceTailProof.span.sourceHeaderModified,false);
  if(key==='kartan')assert.deepEqual(json(join(folder,'visibility-private.json')).unmappedSourceGeometry,['the_tail']);
  if(key.startsWith('mendel-'))assert(json(join(folder,'overrides-private.json')).every(p=>p.path==='texture/oc2_human_m_tramp_feet_d.tga'));
  preview.dispose();for(const material of owned)material.dispose();count++;
 }
 assert.equal(count,6);
});
