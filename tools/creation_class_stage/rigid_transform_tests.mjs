// Real six-source matrices and honest frozen root-proof compatibility only.
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
import {checkedRigidTransform} from './actor_v3.mjs';
const [base,threePath]=process.argv.slice(2).map(v=>resolve(v));
if(!threePath)throw Error('Exact candidate root and original Three directory required');
const THREE=await import(pathToFileURL(join(threePath,'three.module.js')).href);
const json=async p=>JSON.parse(await readFile(p,'utf8'));
const audit=await json(join(base,'rigid-ancestor-audit-v1.json'));
let matrices=0,rejections=0,rootCompatibility=0;
for(const row of audit.records){
 const directory=join(base,row.candidate),manifest=await json(join(directory,'manifest.json'));
 const attachment=manifest.attachments.find(a=>a.slot===row.slot),source=await json(join(directory,attachment.model));
 const mesh=source.meshes[0],verify=(value,proof)=>checkedRigidTransform(THREE,value,mesh,proof);
 const actual=verify(source,row.proof);
 assert.ok(actual.elements.every((v,i)=>Math.abs(v-row.proof.nativeMatrix[i])<=2e-6));matrices++;
 if(row.frozenPayloadNeedsNewVersion){assert.throws(()=>verify(source,source.sourceRigidMeshTransform));rejections++;}
 else{verify(source,source.sourceRigidMeshTransform);rootCompatibility++;}
 const wrongRef=structuredClone(source);wrongRef.sourceNodes[row.proof.sourceNodeIndex].attachments=[];
 assert.throws(()=>verify(wrongRef,row.proof));rejections++;
 const wrongParent=structuredClone(source);wrongParent.sourceNodes[row.proof.sourceNodeIndex].parent=row.proof.sourceNodeIndex;
 assert.throws(()=>verify(wrongParent,row.proof));rejections++;
 const wrongMatrix=structuredClone(row.proof);wrongMatrix.nativeMatrix[12]+=.25;
 assert.throws(()=>verify(source,wrongMatrix));rejections++;
 const sorted=structuredClone(row.proof);
 sorted.sourceNode=Object.fromEntries(Object.entries(sorted.sourceNode).reverse());
 sorted.sourceAncestors=sorted.sourceAncestors.map(x=>({node:Object.fromEntries(Object.entries(x.node).reverse()),index:x.index}));
 verify(source,sorted);
}
assert.equal(matrices,6);assert.equal(rootCompatibility,5);assert.equal(rejections,19);
console.log(JSON.stringify({matrices,rootCompatibility,rejections,sourcePixelsOrGeometryChanged:false,GPU:false}));
