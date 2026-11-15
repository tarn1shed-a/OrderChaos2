// Synthetic interface controls only; original CPU/source checks stay private.
import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from '../deploy/node_modules/three/build/three.module.js';
import {checkedRigidTransform} from './creation_class_stage/actor_v3.mjs';
const mesh={name:'fixture-mesh'};
const node=(parent,attachments=[])=>({parent,position:[0,0,0],quaternion:[0,0,0,1],scale:[1,1,1],controllerRelative:0,attachments});
const reference={kind:3,reference:'#fixture-mesh'};
function fixture(){
 const root=node(-1),child=node(0,[reference]);child.position=[.02,.003,-.04];
 const source={sourceNodes:[root,child]};
 const proof={format:'oc2-original-rigid-mesh-ancestor-transform-v2',sourceMeshName:mesh.name,sourceNodeIndex:1,sourceNode:structuredClone(child),
  nativeCPUExecuted:true,originalGPUObserved:false,originalModelLoaderExecuted:false,sourceLiteralMeshAttachmentVerified:true,
  originalEmptyNodeHierarchyConstructed:true,sourceAncestorIndices:[0,1],sourceAncestors:[{index:0,node:structuredClone(root)},{index:1,node:structuredClone(child)}],
  nativeMatrix:[1,0,0,0,0,1,0,0,0,0,1,0,.02,.003,-.04,1]};
 return {source,proof};
}
test('actual mesh reference preserves its complete static ancestor transform',()=>{
 const {source,proof}=fixture();assert.deepEqual(checkedRigidTransform(THREE,source,mesh,proof).elements,proof.nativeMatrix);
 const reversed=structuredClone(proof);reversed.sourceNode=Object.fromEntries(Object.entries(reversed.sourceNode).reverse());
 assert.deepEqual(checkedRigidTransform(THREE,source,mesh,reversed).elements,proof.nativeMatrix);
});
test('an identity alias cannot hide a child mesh or replace its proof',()=>{
 const {source,proof}=fixture();source.sourceNodes[0].aliases=['fixture'];
 assert.throws(()=>checkedRigidTransform(THREE,source,mesh,undefined),/actual identity mesh root/);
 assert.throws(()=>checkedRigidTransform(THREE,source,mesh,{...proof,format:'oc2-original-rigid-root-mesh-transform-v1'}),/Root-only/);
 const identity={sourceNodes:[node(-1,[reference])]};
 assert.deepEqual(checkedRigidTransform(THREE,identity,mesh,undefined).elements,new THREE.Matrix4().elements);
});
test('missing, duplicated, cyclic, animated and nonfinite source hierarchies are refused',()=>{
 for(const mutate of [
  s=>s.sourceNodes[1].attachments=[],s=>s.sourceNodes[0].attachments=[reference],
  s=>s.sourceNodes[1].parent=1,s=>s.sourceNodes[1].parent=7,s=>s.sourceNodes[0].parent=1,
  s=>s.sourceNodes[0].controllerRelative=12,s=>s.sourceNodes[0].position[0]=NaN
 ]){const {source,proof}=fixture();mutate(source);assert.throws(()=>checkedRigidTransform(THREE,source,mesh,proof));}
});
test('proof cannot omit, reorder or alter source nodes, complete matrices or completion scope',()=>{
 for(const mutate of [
  p=>p.sourceAncestorIndices.reverse(),p=>p.sourceAncestors.pop(),p=>p.sourceNodeIndex=0,
  p=>p.nativeMatrix[12]=0,p=>p.sourceNode.position[0]=0,p=>p.nativeCPUExecuted=false,
  p=>p.originalGPUObserved=true,p=>p.originalModelLoaderExecuted=true,p=>p.originalEmptyNodeHierarchyConstructed=false,
  p=>p.sourceLiteralMeshAttachmentVerified=false,p=>p.format='unknown'
 ]){const {source,proof}=fixture();mutate(proof);assert.throws(()=>checkedRigidTransform(THREE,source,mesh,proof));}
});
