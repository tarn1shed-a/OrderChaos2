// CPU-only Three construction using every actual decoded PNG pixel. Does not
// report WebGL compilation, driver upload, browser rendering or original ready.
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {inflateSync} from 'node:zlib';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {selectStageIdentity} from './stage_switch.mjs';
import {buildCreationStageActor} from './actor_v3.mjs';
import {createSourceCreationMaterial} from './material_v2.mjs';
const [directory,contractPath,threeDirectory,shaderDirectory,stagePath,environmentPath,receiptPath]=process.argv.slice(2).map(v=>resolve(v));
if(!receiptPath||!receiptPath.includes('/analysis/raw/'))throw Error('Explicit actor, contract, Three, shader, original stage/environment and ignored receipt path required');
const json=async path=>JSON.parse(await readFile(path,'utf8'));
const manifest=await json(join(directory,'manifest.json'));
// Browser URLs in private candidates are rooted at their own asset directory.
const local=path=>join(directory,path.replace(/^\//,''));
const actorData=await json(local(manifest.model)),contract=await json(contractPath);
const identity=selectStageIdentity(contract,{screen:manifest.screen,race:manifest.race,gender:manifest.gender,professionIndex:manifest.professionIndex});
const THREE=await import(pathToFileURL(join(threeDirectory,'three.module.js')).href),textures=new Map(),attachmentData=new Map();
function png(bytes){
 if(!bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])))throw Error('Expected exact source-converted PNG');
 let width,height,channels,idat=[],header;
 for(let p=8;p<bytes.length;){const size=bytes.readUInt32BE(p),kind=bytes.toString('ascii',p+4,p+8),value=bytes.subarray(p+8,p+8+size);p+=size+12;
  if(kind==='IHDR'){header=value;width=value.readUInt32BE(0);height=value.readUInt32BE(4);channels=value[9]===6?4:value[9]===2?3:null;}
  if(kind==='IDAT')idat.push(value);
 }
 if(!header||header[8]!==8||!channels||header[10]||header[11]||header[12])throw Error('Uncovered source PNG color/filter format');
 const bytesPerRow=width*channels,raw=inflateSync(Buffer.concat(idat));if(raw.length!==(bytesPerRow+1)*height)throw Error('PNG scanline size differs');
 const decoded=Buffer.alloc(bytesPerRow*height),rgba=new Uint8Array(width*height*4);
 const paeth=(a,b,c)=>{const p=a+b-c,pa=Math.abs(p-a),pb=Math.abs(p-b),pc=Math.abs(p-c);return pa<=pb&&pa<=pc?a:pb<=pc?b:c;};
 for(let y=0;y<height;y++)for(let x=0;x<bytesPerRow;x++){
  const at=y*bytesPerRow+x,a=x>=channels?decoded[at-channels]:0,b=y?decoded[at-bytesPerRow]:0,c=y&&x>=channels?decoded[at-bytesPerRow-channels]:0,filter=raw[y*(bytesPerRow+1)];
  const predictor=filter===0?0:filter===1?a:filter===2?b:filter===3?Math.floor((a+b)/2):filter===4?paeth(a,b,c):NaN;
  if(!Number.isFinite(predictor))throw Error('Unknown PNG filter');decoded[at]=(raw[y*(bytesPerRow+1)+1+x]+predictor)&255;
 }
 for(let i=0;i<width*height;i++){rgba[i*4]=decoded[i*channels];rgba[i*4+1]=decoded[i*channels+1];rgba[i*4+2]=decoded[i*channels+2];rgba[i*4+3]=channels===4?decoded[i*channels+3]:255;}
 return {width,height,rgba};
}
const rows=[...manifest.materials,...manifest.attachments.flatMap(a=>a.materials)],images=[];
for(const url of new Set(rows.flatMap(r=>Object.values(r.samplers)))){
 const bytes=await readFile(local(url)),decoded=png(bytes),texture=new THREE.DataTexture(decoded.rgba,decoded.width,decoded.height,THREE.RGBAFormat,THREE.UnsignedByteType);
 texture.flipY=false;texture.colorSpace=THREE.NoColorSpace;texture.needsUpdate=true;textures.set(url,texture);
 images.push({url,width:decoded.width,height:decoded.height,pngSHA256:createHash('sha256').update(bytes).digest('hex'),pixelSHA256:createHash('sha256').update(decoded.rgba).digest('hex')});
}
for(const row of manifest.attachments)attachmentData.set(row.model,await json(local(row.model)));
const stage=await json(stagePath),fresh=await json(environmentPath);
const lighting={uniforms:Object.fromEntries(Object.entries(fresh.uniformInputs).map(([key,v])=>[key,{value:Array.isArray(v)?(v.length===2?new THREE.Vector2(...v):new THREE.Vector3(...v)):v}]))};
const names=['lt_pal_normal_vs.glsl','lt_pal_normal_fs.glsl'];
const programs=await Promise.all(names.map(name=>readFile(join(shaderDirectory,name),'utf8')));
assert.equal(createHash('sha256').update(programs[0]).digest('hex'),'081beacff05e2df94db740331cf0d4b6c7e1b2e8b4cc502ccffabccd3c9733a6');
assert.equal(createHash('sha256').update(programs[1]).digest('hex'),'3d1cc2c7a0eefba6c0dfd40d6948d215bfdb971658b1eaf7f76f1e1c5fca0a2b');
const material=(three,row,maps,colors,object)=>createSourceCreationMaterial(three,row,maps,programs,object,{...colors,eye:stage.transform.freshModelEyeColor},fresh.sourceCharacterLight,lighting,stage.sourceControllerLight.direction);
const actor=buildCreationStageActor({THREE,manifest,data:actorData,identity,textures,attachmentData,createMaterial:material});
for(const object of [...actor.meshes.filter(m=>m.visible),...actor.weapons])for(const row of object.material.filter(Boolean))assert.equal(row.isRawShaderMaterial,true);
actor.update(.1);actor.root.updateMatrixWorld(true);
for(const object of actor.meshes){object.skeleton.update();assert.ok([...object.skeleton.boneMatrices].every(Number.isFinite));}
assert.equal(actor.action.loop,THREE.LoopOnce);
const originalOrder={...manifest,sourceModel:Object.fromEntries(Object.entries(manifest.sourceModel).reverse())};
const reordered=buildCreationStageActor({THREE,manifest:originalOrder,data:actorData,identity,textures,attachmentData,createMaterial:material});reordered.dispose();
let rigidMatrixNegatives=0;
for(const row of manifest.attachments){
 const input=attachmentData.get(row.model),proof=input.sourceRigidMeshTransform;if(!proof)continue;
 const changed=structuredClone(input);changed.sourceRigidMeshTransform.nativeMatrix[12]+=1;
 const replacements=new Map(attachmentData);replacements.set(row.model,changed);
 assert.throws(()=>buildCreationStageActor({THREE,manifest,data:actorData,identity,textures,attachmentData:replacements,createMaterial:material}));rigidMatrixNegatives++;
 const reversed=structuredClone(input);reversed.sourceRigidMeshTransform.sourceNode=Object.fromEntries(Object.entries(reversed.sourceRigidMeshTransform.sourceNode).reverse());
 replacements.set(row.model,reversed);const allowed=buildCreationStageActor({THREE,manifest,data:actorData,identity,textures,attachmentData:replacements,createMaterial:material});allowed.dispose();
}
for(const change of [m=>m.sourceRequest.displayId=2047,m=>m.professionIndex=(m.professionIndex+1)%5,m=>m.panel=manifest.panel===1?2:1]){
 const bad=structuredClone(manifest);change(bad);assert.throws(()=>buildCreationStageActor({THREE,manifest:bad,data:actorData,identity,textures,attachmentData,createMaterial:material}));
}
const receipt={format:'oc2-creation-class-real-material-CPU-v1',display:identity.request.displayId,identity,
 visibleMeshes:actor.meshes.filter(m=>m.visible).length,rigNodes:actor.nodes.length,rigidWeapons:actor.weapons.length,
 materialObjects:actor.root.children.length,images,sourceShaderSHA256:names.map((_,i)=>createHash('sha256').update(programs[i]).digest('hex')),
 actualThreeMaterialsConstructed:true,actualPixelsDecoded:true,finiteOwnInitialIdle:true,originalGPUObserved:false,browserPassed:false,createdRole:false};
receipt.originalRigidMatrixNegativeControls=rigidMatrixNegatives;
let ancestorNegatives=0,legacyChildRejected=0;
for(const row of manifest.attachments){
 const input=attachmentData.get(row.model),proof=input.sourceRigidMeshTransform;if(!proof)continue;
 const reject=value=>{const map=new Map(attachmentData);map.set(row.model,value);assert.throws(()=>buildCreationStageActor({THREE,manifest,data:actorData,identity,textures,attachmentData:map,createMaterial:material}));ancestorNegatives++;};
 const changed=structuredClone(input);const node=changed.sourceNodes[proof.sourceNodeIndex];node.attachments=[];reject(changed);
 if(proof.format==='oc2-original-rigid-mesh-ancestor-transform-v2'){
  const wrong=structuredClone(input);wrong.sourceRigidMeshTransform.sourceAncestorIndices=[proof.sourceNodeIndex];reject(wrong);
  const wrongSource=structuredClone(input);wrongSource.sourceRigidMeshTransform.sourceAncestors[0].node.position[0]+=.5;reject(wrongSource);
  if(proof.sourceAncestorIndices.length>1){const missing=structuredClone(input);delete missing.sourceRigidMeshTransform;reject(missing);legacyChildRejected++;}
 }
}
receipt.actualMeshReferenceNegativeControls=ancestorNegatives;receipt.legacyChildMeshRejected=legacyChildRejected;
actor.dispose();actor.dispose();for(const texture of textures.values())texture.dispose();receipt.disposalIdempotent=true;
await writeFile(receiptPath,JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({display:receipt.display,visibleMeshes:receipt.visibleMeshes,rigNodes:receipt.rigNodes,rigidWeapons:receipt.rigidWeapons,images:images.length,realThreeMaterialCPU:true,GPU:false}));
