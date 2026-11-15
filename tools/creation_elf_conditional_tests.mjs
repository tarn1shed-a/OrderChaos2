import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync,existsSync,writeFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import * as API from './preview/character_creation_preview_proposal.mjs';
import {ELF_SAMPLERS,ELF_CONDITIONAL_FORMAT,ELF_CONTRACT_SHA,ELF_FAILURE_SHA,ELF_SOURCE_PACKET_SHA,ELF_MISSING_PATH,ELF_PART,ELF_PART_SHA,completeElfConditionalPreview} from './preview/creation_elf_source_ready.mjs';
import {webGLSource,paletteGlobals} from './preview/source-scene-palette.js';
import {applyCreationStageTransform} from './preview/source-creation-stage.mjs';

const ROOT=resolve(fileURLToPath(new URL('../',import.meta.url))),raw=join(ROOT,'analysis/raw/creation-elf-conditional-20261115');
const candidate=join(raw,'candidate-v1/elf-male'),read=p=>JSON.parse(readFileSync(p,'utf8'));
const host='http://127.0.0.1:62100/',base='/assets/source-creation-elf-conditional-v1/';
const hash=b=>createHash('sha256').update(b).digest('hex');
const stageSource=readFileSync(join(ROOT,'deploy/creation_preview.mjs'),'utf8');
const sourceManifest=()=>read(join(candidate,'manifest.json'));
const sourceData=()=>read(join(candidate,'assets/character.json'));
const available=()=>existsSync(join(candidate,'manifest.json'))&&existsSync(join(raw,'host-decoded-v1/inputs.json'));

test('public conditional schema cannot turn a missing texture into complete original appearance',()=>{
 // This is a schema fixture only: it supplies no model, textures or ready receipt.
 const manifest={format:ELF_CONDITIONAL_FORMAT,key:'elf-male',race:2,gender:0,originalDisplayId:2046,sourceModelId:33,
  sourceTraceSHA256:ELF_SOURCE_PACKET_SHA,creationPreviewAdmitted:false,appearanceComplete:false,hostConditionalDisplay:true,
  originalAndroidFinalAppearanceKnown:false,originalGPUObserved:false,createdRole:false,initialServerAttributes:null,liveActor:false,
  visibleMeshIndices:[],materials:[{index:2,sourceMaterialName:'st222',sourceModel:ELF_PART,effectPath:'lt_pal_normal_trans.bdae',
   samplers:Object.fromEntries(Object.entries(ELF_SAMPLERS).map(([key,v])=>[key,v.url])),
   addressing:Object.fromEntries(Object.entries(ELF_SAMPLERS).map(([key,v])=>[key,{source:v.sourcePath,sourceSHA256:v.sourceSHA256}]))}],
  retainedSourceMaterial:{format:'oc2-exact-elf-st222-missing-stream-policy-v1',contractSHA256:ELF_CONTRACT_SHA,
   originalFailureEvidenceSHA256:ELF_FAILURE_SHA,materialIndex:2,sourceMaterialName:'st222',sourcePartPath:ELF_PART,sourcePartSHA256:ELF_PART_SHA,
   requestedOverride:{channel:0,path:ELF_MISSING_PATH,availableOriginalPayloads:0,overrideApplied:false,overrideCacheWritten:false},
   samplers:structuredClone(ELF_SAMPLERS),hostSourceMaterialReadyRequired:true,originalAndroidFinalAppearanceKnown:false},
  missingSourceOverrides:[{slot:11,material:'st222',requestedPath:ELF_MISSING_PATH,availableOriginalPayloads:0,overrideApplied:false,
   overrideCacheWritten:false,originalMissingStreamEvidenceSHA256:ELF_FAILURE_SHA,permittedOnlyAfterRealHostSourceMaterialReady:true}]};
 assert.equal(API.checkedCreationPreview(manifest,{race:2,gender:0}).grantsEquipment,false);
 for(const bad of [{...manifest,appearanceComplete:true},{...manifest,creationPreviewAdmitted:true},
  {...manifest,sourceTraceSHA256:'0'.repeat(64)},{...manifest,originalGPUObserved:true},
  {...manifest,originalAndroidFinalAppearanceKnown:true},{...manifest,missingSourceOverrides:[]}])
  assert.throws(()=>API.checkedCreationPreview(bad,{race:2,gender:0}));
 assert.throws(()=>completeElfConditionalPreview({}, {manifest,data:{materials:[]},preview:{hostReady:true}}));
 const old={format:'oc2-source-creation-preview-delivery-v5',mapId:7,sourceSelectionRegion:211,freshStartOnly:true,
  wholeCreationRestored:false,createsPlayableRole:false,stages:['CharacterChooseRace'],
  stage:'/assets/source-creation-stage/stage.json',environment:'/assets/source-creation-stage/environment.json',
  scene:'/assets/source-selection-scene/manifest.json',inside:'/assets/source-selection-inside/overlay.json',stones:'/assets/source-selection-stones/overlay.json',
  previews:{'0:0':{baseURL:'/assets/source-creation-human-male/'},'0:1':{baseURL:'/assets/source-creation-human-female/'},
   ...Object.fromEntries(Object.entries(API.CREATION_RACE_IDENTITIES).map(([key,s])=>[key,{baseURL:'/assets/source-test-'+s.key+'/'}]))},
  sourceRaceTraceSHA256:ELF_SOURCE_PACKET_SHA,allNineRacePreviewsRestored:false,originalAndroidFinalAppearanceKnown:false,
  additionalOriginalPreviews:Object.entries(API.CREATION_RACE_IDENTITIES).map(([key,s])=>({key,bodyKey:s.key,display:s.display,model:s.model})),
  conditionalOriginalPreviews:[{key:'2:0',contractSHA256:ELF_CONTRACT_SHA,appearanceComplete:false,sourceRequestSucceeded:false,displayOnlyAfterHostReady:true}],
  originalStaticInstances:151,originalDryChunks:192,originalWaterSurfaceChunks:152,originalWetFloorRestored:true,originalGroupRepresentativeMaterialCopies:true,
  extensions:[['dry','water'],['flowers','flowers'],['grass','grass'],['waterfalls','waterfalls'],['waterSurface','water-surface'],['wetFloor','water-floor-groups']].map(([kind,ns])=>({kind,url:'/assets/source-selection-'+ns+'/overlay.json'}))};
 const context={};vm.createContext(context);vm.runInContext(stageSource.replace(/^import[^\n]*\n/gm,'').replaceAll('export ','')+';this.validate=validateCreationDelivery;',context);
 assert.equal(context.validate(old),old);
 for(const invalid of [{...old,format:'oc2-source-creation-preview-delivery-v4'},{...old,allNineRacePreviewsRestored:true},
  {...old,conditionalOriginalPreviews:[{...old.conditionalOriginalPreviews[0],sourceRequestSucceeded:true}]}])assert.throws(()=>context.validate(invalid));
});

test('Elf2046 is conditional, never a completed missing override or another missing-source fallback',t=>{
 if(!available()){t.skip('Private original conditional source candidate absent');return;}
 const manifest=sourceManifest();assert.equal(API.checkedCreationPreview(manifest,{race:2,gender:0}).key,'2:0');
 assert.equal(manifest.creationPreviewAdmitted,false);assert.equal(manifest.appearanceComplete,false);
 for(const mutate of [m=>({...m,appearanceComplete:true}),m=>({...m,creationPreviewAdmitted:true}),
  m=>({...m,originalAndroidFinalAppearanceKnown:true}),m=>({...m,sourceModelId:2}),
  m=>({...m,missingSourceOverrides:[]}),m=>({...m,retainedSourceMaterial:{...m.retainedSourceMaterial,sourceMaterialName:'other'}}),
  m=>({...m,retainedSourceMaterial:{...m.retainedSourceMaterial,requestedOverride:{...m.retainedSourceMaterial.requestedOverride,overrideApplied:true}}}),
  m=>({...m,retainedSourceMaterial:{...m.retainedSourceMaterial,samplers:{...m.retainedSourceMaterial.samplers,normalMap:{...m.retainedSourceMaterial.samplers.normalMap,pngSHA256:'0'.repeat(64)}}}})
 ])assert.throws(()=>API.checkedCreationPreview(mutate(structuredClone(manifest)),{race:2,gender:0}));
 const data=sourceData();assert.equal(API.checkedCreationModel(manifest,data,{race:2,gender:0}).writesCharacter,false);
 assert.throws(()=>API.checkedCreationModel(manifest,{...data,sourceCreation:{...data.sourceCreation,sourceModelId:2}},{race:2,gender:0}));
});

test('v5 envelope cannot enable Elf2046 on old profiles or claim complete original appearance',t=>{
 const path=join(raw,'qa-static-v1/game-data/converted/source-creation-stage/manifest-conditional-v1.json');
 if(!existsSync(path)){t.skip('Private v5 source profile absent');return;}
 const context={};vm.createContext(context);
 vm.runInContext(stageSource.replace(/^import[^\n]*\n/gm,'').replaceAll('export ','')+';this.validate=validateCreationDelivery;',context);
 const profile=read(path);assert.equal(context.validate(profile),profile);
 for(const change of [
  {...profile,format:'oc2-source-creation-preview-delivery-v4'},
  {...profile,conditionalOriginalPreviews:[]},{...profile,allNineRacePreviewsRestored:true},
  {...profile,originalAndroidFinalAppearanceKnown:true},
  {...profile,conditionalOriginalPreviews:profile.conditionalOriginalPreviews.map(c=>({...c,sourceRequestSucceeded:true}))},
  {...profile,conditionalOriginalPreviews:profile.conditionalOriginalPreviews.map(c=>({...c,appearanceComplete:true}))},
  {...profile,conditionalOriginalPreviews:profile.conditionalOriginalPreviews.map(c=>({...c,contractSHA256:'0'.repeat(64)}))},
  {...profile,previews:Object.fromEntries(Object.entries(profile.previews).filter(([key])=>key!=='2:0'))},
 ])assert.throws(()=>context.validate(change));
});

async function setup(){
 const THREE=await import(pathToFileURL(join(ROOT,'analysis/raw/character-human-male-20261114/candidate-v1/three.module.js')));
 const manifest=sourceManifest(),data=sourceData(),pixels=read(join(raw,'host-decoded-v1/inputs.json')).inputs;
 const staticRoot=join(ROOT,'analysis/raw/creation-race-preview-20261115/qa-static-eight-v2/game-data/converted');
 const stage=read(join(staticRoot,'source-creation-stage/stage.json')),fresh=read(join(staticRoot,'source-creation-stage/environment.json'));
 const programs=['lt_pal_normal_vs.glsl','lt_pal_normal_fs.glsl'].map(name=>readFileSync(join(staticRoot,'source-map-palette',name),'utf8'));
 const materialContext={webGLSource,paletteGlobals};vm.createContext(materialContext);
 vm.runInContext(readFileSync(join(ROOT,'deploy/attribute_preview.mjs'),'utf8').replace(/^import[^\n]*\n/gm,'').replace(/^export \{[^\n]*\n/gm,'').replaceAll('export ','')+';this.make=material;',materialContext);
 const textures=[],requests=[],events=[];
 const inputURL=url=>'/assets/'+new URL(url,host).pathname.split('/').at(-1);
 const imageTexture=(T,url)=>{
  const key=inputURL(url),entry=pixels[key];assert(entry,'Exact source PNG required');
  const png=readFileSync(join(candidate,key.slice(1))),rgba=readFileSync(join(raw,'host-decoded-v1',entry.rgba));
  assert.equal(hash(png),entry.pngSHA256);assert.equal(hash(rgba),entry.rgbaSHA256);
  const texture=new T.DataTexture(new Uint8Array(rgba),entry.width,entry.height,T.RGBAFormat,T.UnsignedByteType);
  texture.flipY=false;texture.colorSpace=T.NoColorSpace;texture.needsUpdate=true;textures.push(texture);return texture;
 };
 const fetcher=async url=>{requests.push(url);const path=inputURL(url);return new Response(readFileSync(join(candidate,path.slice(1))),{status:200});};
 const decode=async(T,bytes,sampler)=>{
  assert.equal(hash(Buffer.from(bytes)),ELF_SAMPLERS[sampler].pngSHA256);
  events.push('decoded:'+sampler);return imageTexture(T,host+base.slice(1)+ELF_SAMPLERS[sampler].url.slice(1));
 };
 let builds=0;
 const api={...API,buildCreationRacePreview(options){builds++;events.push('actual-geometry-factory');return API.buildCreationRacePreview(options);},
  loadElfConditionalTexture:(T,url,sampler)=>API.loadElfConditionalTexture(T,url,sampler,{fetcher,decodeForHost:decode,documentURL:host})};
 const e={p:{format:'oc2-source-creation-preview-delivery-v5',previews:{'2:0':{baseURL:base}}},THREE,profile:stage,fresh,
  lighting:{uniforms:Object.fromEntries(Object.entries(fresh.uniformInputs).map(([key,value])=>[key,{value:Array.isArray(value)?new THREE.Vector3(...value):value}]))},
  texture:async url=>imageTexture(THREE,url)};
 const context={racePreviewAPI:async()=>api,legacyCreationPreview:API,CREATION_RACES_FORMAT:'oc2-source-creation-preview-delivery-v4',
  json:async url=>{events.push('json:'+url);return url.endsWith('/manifest.json')?manifest:data;},
  attributes:[['Vertex','position'],['Normal','normal'],['TexCoord0','uv'],['Tangent','sourceTangent'],['Binormal','sourceBinormal'],['SkinWeights','skinWeight'],['SkinIndices','skinIndex']],
  loadSourceCharacterPrograms:async()=>programs,createSourceCharacterMaterial:materialContext.make,applyCreationStageTransform};
 vm.createContext(context);
 const start=stageSource.indexOf(' async function loadActor(e,race,gender){'),end=stageSource.indexOf('\n function frame(time){');
 vm.runInContext(stageSource.slice(start,end)+';this.load=loadActor;',context);
 return{THREE,manifest,data,e,api,context,requests,events,decode,fetcher,textures,get builds(){return builds;}};
}

test('actual production loadActor creates source material only after six checked real image inputs',async t=>{
 if(!available()){t.skip('Private original source pixels absent');return;}
 const p=await setup();globalThis.location={href:host};
 let preview;
 try{
  preview=await p.context.load(p.e,2,0);
  assert.equal(p.builds,1);assert.equal(p.requests.length,6);
  assert.equal(p.events.filter(x=>x.startsWith('decoded:')).length,6);
  assert(p.events.slice(0,p.events.indexOf('actual-geometry-factory')).filter(x=>x.startsWith('decoded:')).length===6);
  const receipt=preview.conditionalReady;
  assert.equal(receipt.hostSourceMaterialReady,true);assert.equal(receipt.existingBindingsUnchanged,6);
  assert.equal(receipt.overrideApplied,false);assert.equal(receipt.overrideCacheWritten,false);
  assert.equal(receipt.appearanceComplete,false);assert.equal(receipt.originalAndroidFinalAppearanceKnown,false);assert.equal(receipt.originalGPUObserved,false);
  assert.equal(receipt.verifiedSamplers.length,6);
  const target=preview.meshes.find((o,i)=>o.visible&&p.data.meshes[i].groups.some(g=>g.material===2));
  const material=target.material[2],before=Object.fromEntries(Object.keys(ELF_SAMPLERS).map(k=>[k,material.uniforms[k==='texture'?'sourceTexture':k].value]));
  completeElfConditionalPreview(p.THREE,{manifest:p.manifest,data:p.data,preview});
  for(const [key,texture]of Object.entries(before))assert.equal(material.uniforms[key==='texture'?'sourceTexture':key].value,texture);
  const original=material.uniforms.normalMap.value,unregistered=original.clone();unregistered.userData.hostReady=true;
  material.uniforms.normalMap.value=unregistered;
  assert.throws(()=>completeElfConditionalPreview(p.THREE,{manifest:p.manifest,data:p.data,preview}));
  material.uniforms.normalMap.value=original;unregistered.dispose();
  const checks=read(join(candidate,'binding-private.json'));
  assert.equal(checks.length,16);assert.equal(checks.reduce((n,c)=>n+c.nativeIdleSamplesAndPaletteAndVertices.length,0),64);
  if(process.env.OC2_ELF_HOST_REPORT){const reportPath=resolve(process.env.OC2_ELF_HOST_REPORT);
   assert(reportPath.startsWith(join(ROOT,'analysis/raw')+'/'));assert(!existsSync(reportPath),'Preserve frozen evidence');
   writeFileSync(reportPath,JSON.stringify({format:'oc2-elf-st222-actual-host-construct-v1',
   productionLoadActorExecuted:true,actualRawShaderMaterial:material.isRawShaderMaterial,
   decoder:'Actual PNG SHA checked, Pillow RGBA input through real Three.DataTexture CPU constructor; browser/GPU pending',
   receipt,requests:p.requests,events:p.events,ownIdleNativeCPUCases:64,characterWrites:false},null,2)+'\n',{flag:'wx'});}
 }finally{delete globalThis.location;preview?.dispose();for(const texture of p.textures)texture.dispose();}
});

test('pending, missing or changed source image cannot reach production material-ready',async t=>{
 if(!available()){t.skip('Private original source pixels absent');return;}
 const p=await setup();let release;const gate=new Promise(ok=>release=ok);let complete=false;
 p.api.loadElfConditionalTexture=(T,url,sampler)=>API.loadElfConditionalTexture(T,url,sampler,{fetcher:p.fetcher,documentURL:host,
  decodeForHost:async(...args)=>{if(sampler==='normalMap')await gate;return p.decode(...args);}});
 globalThis.location={href:host};let preview;
 try{
  const loading=p.context.load(p.e,2,0).then(value=>{complete=true;return value;});
  await new Promise(ok=>setTimeout(ok,20));assert.equal(complete,false);assert.equal(p.builds,0);release();preview=await loading;
  assert(preview.conditionalReady.hostSourceMaterialReady);
 }finally{delete globalThis.location;release();preview?.dispose();for(const texture of p.textures)texture.dispose();}
 for(const response of [()=>new Response('absent',{status:404}),()=>new Response(new Uint8Array([1,2,3]),{status:200})]){
  const q=await setup();q.api.loadElfConditionalTexture=(T,url,sampler)=>API.loadElfConditionalTexture(T,url,sampler,{fetcher:response,decodeForHost:q.decode,documentURL:host});
  globalThis.location={href:host};try{await assert.rejects(q.context.load(q.e,2,0));assert.equal(q.builds,0);}
  finally{delete globalThis.location;for(const texture of q.textures)texture.dispose();}
 }
});
