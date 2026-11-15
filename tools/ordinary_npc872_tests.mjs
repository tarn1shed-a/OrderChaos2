// Actual Three CPU objects/material builder; no browser, GL context or server.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {loadNPC872Assets} from './preview/source-ordinary-npc872.mjs';
const root=path.resolve(import.meta.dirname,'..'),area=path.join(root,'analysis/raw/ordinary-npc872-candidate-20261116');
const option=k=>{const i=process.argv.indexOf(k);return i<0?null:process.argv[i+1];};
const candidate=path.resolve(root,option('--candidate')||'analysis/raw/ordinary-npc872-candidate-20261116/candidate-v2');
const sha=raw=>crypto.createHash('sha256').update(raw).digest('hex');let assertions=0;
const ok=(v,m)=>{assert.ok(v,m);assertions++;},eq=(a,b)=>{assert.deepEqual(a,b);assertions++;},reject=async f=>{await assert.rejects(f);assertions++;};
await reject(()=>loadNPC872Assets({}, {json:async()=>({format:'different-source'})}));
const profileFile=path.join(candidate,'assets/source-ordinary-npc872/profile.json');
const available=await fs.access(profileFile).then(()=>true,()=>false);
if(process.argv.includes('--public-only')||!available){console.log(JSON.stringify({assertions,privateCases:'skipped: original assets unavailable or public-only',browser:false,GPU:false,server:false}));process.exit(0);}
const output=path.resolve(root,option('--output')||'analysis/raw/ordinary-npc872-candidate-20261116/node-checks-v1.json');
if(!output.startsWith(area+path.sep)||await fs.access(output).then(()=>true,()=>false))throw Error('New owned ignored check output required');
const THREE=await import(pathToFileURL(path.join(candidate,'three.module.js'))),{finalPairMaterial}=await import(pathToFileURL(path.join(candidate,'source-npc-final-pair-material.js')));
const json=async file=>JSON.parse(await fs.readFile(file,'utf8'));
const profile=await json(profileFile),data=await json(path.join(candidate,profile.model.slice(1)));
const rows=new Map(Object.values(profile.textures).map(r=>[r.url,r]));
const fileURL=u=>{ok(u.startsWith('/assets/source-ordinary-npc872/'));return path.join(candidate,u.slice(1));};
const readJSON=async u=>json(fileURL(u));
async function decodedTexture(u){const r=rows.get(u);ok(r);const raw=await fs.readFile(fileURL(r.rgbaURL));eq(sha(raw),r.rgbaSHA256);eq(raw.length,r.size[0]*r.size[1]*4);
  return new THREE.DataTexture(new Uint8Array(raw),...r.size,THREE.RGBAFormat);}
const assets=await loadNPC872Assets(THREE,{json:readJSON,texture:decodedTexture});
const disposals=[],tracked=new WeakSet();
function track(object,kind){if(tracked.has(object))return;tracked.add(object);const record={kind,count:0};disposals.push(record);object.addEventListener('dispose',()=>record.count++);}
function materialFactory({THREE,record,textures,colors}){
  const m=finalPairMaterial(THREE,record,textures,colors,'source');track(m,'material');for(const t of new Set(textures.values()))track(t,'texture');
  // Exercise the real existing adapter's source rewrite on actual Three
  // ShaderLib programs; this does not compile them or claim GPU success.
  const shader={uniforms:{},vertexShader:THREE.ShaderLib.standard.vertexShader,fragmentShader:THREE.ShaderLib.standard.fragmentShader};
  m.onBeforeCompile(shader);for(const[key,value]of Object.entries(record.scalars))eq(shader.uniforms['npc_'+key].value,value);
  ok(shader.vertexShader.includes('sourceTangent'));return m;
}
const a=assets.createNPC872({materialFactory}),b=assets.createNPC872({materialFactory});
for(const actor of[a,b])for(const g of actor.geometries)track(g,'geometry');
eq(a.inspect().visibleMeshIndices,profile.visibleMeshIndices);eq(a.inspect().boneCount,116);eq(a.inspect().meshCount,16);
eq(a.inspect().actorGUID,null);eq(a.inspect().questState,null);eq(a.inspect().worldPlacement,null);
ok(a.root!==b.root);ok(a.bones.every((x,i)=>x!==b.bones[i]));ok(a.materials.every((x,i)=>x!==b.materials[i]));
for(const actor of[a,b])for(const[i,m]of actor.meshes.entries()){
  eq(m.visible,profile.visibleMeshIndices.includes(i));ok(m.geometry.boundingSphere.radius>=0);ok(m.geometry.boundingBox.isBox3);
  const skin=data.rig.skins.find(s=>s.mesh===i);eq(Array.from(m.geometry.attributes.skinWeight.array),skin.skinWeights.map(Math.fround));
}
const beforeB=b.bones.map(n=>n.matrixWorld.toArray());a.sampleIdle(.5);eq(b.bones.map(n=>n.matrixWorld.toArray()),beforeB);
const reference=await json(path.join(candidate,'pose-reference-private.json')),poseChecks=[];
for(const sample of reference.samples){
  a.sampleIdle(sample.time);let worldError=0,paletteError=0;
  a.bones.forEach((b,i)=>b.matrixWorld.elements.forEach((v,j)=>{worldError=Math.max(worldError,Math.abs(v-sample.world[i][j]));}));
  a.meshes.forEach((mesh,i)=>{const s=data.rig.skins.findIndex(s=>s.mesh===i),flat=sample.palettes[s].flat();
    mesh.skeleton.boneMatrices.forEach((v,j)=>{paletteError=Math.max(paletteError,Math.abs(v-flat[j]));});});
  ok(Number.isFinite(worldError)&&worldError<.002,'Original source world pose mismatch');ok(Number.isFinite(paletteError)&&paletteError<.002,'Original source palette mismatch');
  poseChecks.push({time:sample.time,worldError,paletteError});
}
const state=a.inspect();for(const value of[-1,NaN,profile.idleDuration+1]){assert.throws(()=>a.sampleIdle(value));assertions++;eq(a.inspect(),state);}
// A foreign material cannot be disposed when a second creation is rejected.
assert.throws(()=>assets.createNPC872({materialFactory:({record})=>a.materials[record.index]}));assertions++;
ok(disposals.filter(r=>r.kind==='material').every(r=>r.count===0));
a.dispose();a.dispose();ok(a.inspect().disposed);eq(assets.inspect().instances,1);eq(b.inspect().disposed,false);
assert.throws(()=>a.sampleIdle(0));assertions++;
assets.dispose();assets.dispose();b.dispose();eq(assets.inspect().instances,0);ok(assets.inspect().released);ok(disposals.every(r=>r.count===1));
assert.throws(()=>assets.createNPC872({materialFactory}));assertions++;
const failures=[];
await reject(()=>loadNPC872Assets(THREE,{json:readJSON,texture:async u=>{const t=await decodedTexture(u),r={count:0};failures.push(r);t.addEventListener('dispose',()=>r.count++);
  if(u===[...rows.keys()][0])t.image.width++;return t;}}));
eq(failures.length,rows.size);ok(failures.every(r=>r.count===1));
let unexpectedTextureLoads=0;
await reject(()=>loadNPC872Assets(THREE,{json:async u=>u.endsWith('profile.json')?profile:{...data,sourceNPC872:{...data.sourceNPC872,actualGUID:'not-an-asset'}},texture:async()=>{unexpectedTextureLoads++;throw Error('Must not load');}}));
eq(unexpectedTextureLoads,0);
const result={format:'oc2-npc872-real-three-host-check-v1',assertions,poseChecks,independentInstances:2,meshCount:16,boneCount:116,
  materials:profile.materials.length,textures:rows.size,visible:profile.visibleMeshIndices,disposals:disposals.length,allDisposedExactlyOnce:true,
  wrongTextureFailureReleasedAll:true,sharedMaterialRejected:true,sourceAssetOnly:true,browser:false,GPU:false,server:false,actorGUID:null,questState:null,
  inputs:Object.fromEntries(await Promise.all([profileFile,path.join(candidate,profile.model.slice(1)),path.join(root,'tools/preview/source-ordinary-npc872.mjs')].map(async f=>[path.relative(root,f),sha(await fs.readFile(f))])))};
await fs.mkdir(path.dirname(output),{recursive:true});await fs.writeFile(output,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({output:path.relative(root,output),assertions,poseChecks,GPU:false}));
