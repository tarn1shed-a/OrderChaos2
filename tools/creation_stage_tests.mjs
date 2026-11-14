import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {validateCreationStage,createCreationCameraTrack,createCreationStageCamera,applyCreationStageTransform} from './preview/source-creation-stage.mjs';
const path='analysis/raw/creation-stage-transform-20261115/source-stage.json';
const threePath='analysis/raw/character-addressing-correction-20261114/male-corrected/three.module.js';
test('missing source stage/current camera state cannot create a camera/character',()=>{
 for(const value of [null,{}, {format:'oc2-source-creation-stage-v1'}]){
  assert.throws(()=>validateCreationStage(value));assert.throws(()=>createCreationCameraTrack(value));assert.throws(()=>applyCreationStageTransform({},value));
 }
});
test('actual original camera track matches all 25 native pose sequences', {skip:!existsSync(path)},()=>{
 const p=JSON.parse(readFileSync(path));
 for(const row of p.cameraGroups){
  const track=createCreationCameraTrack(p,{pose:p.configuredInitialPose,group:-1});track.select(row.group,row.race);
  for(const frame of row.frames){const actual=track.update();assert.deepEqual(actual.eye,frame.eye);assert.deepEqual(actual.target,frame.target);assert.equal(actual.moving,frame.moving);}
  assert.equal(track.state().moving,false);const settled=track.state();track.select(row.group,4-row.race);assert.deepEqual(track.state(),settled);
 }
 assert.throws(()=>createCreationCameraTrack(p));
 const duplicate=structuredClone(p);duplicate.cameraGroups[1]=duplicate.cameraGroups[0];assert.throws(()=>validateCreationStage(duplicate));
});
test('Three transform/projection/view bridge agrees with original CPU matrices', {skip:!existsSync(path)||!existsSync(threePath)},async()=>{
 const p=JSON.parse(readFileSync(path)),THREE=await import(pathToFileURL(process.cwd()+'/'+threePath));
 const root=new THREE.Group();const result=applyCreationStageTransform(root,p);assert.deepEqual(root.matrix.elements,p.transform.matrix);assert.equal(result.createsPlayableRole,false);
 const bridge=createCreationStageCamera(THREE,p,{width:1136,height:640});
 for(let i=0;i<16;i++)assert(Math.abs(bridge.camera.projectionMatrix.elements[i]-p.projection[i])<2e-6);
 let maxDifference=0;
 for(const row of p.cameraGroups)for(const frame of row.frames){
  bridge.setPose(frame);for(let i=0;i<16;i++)maxDifference=Math.max(maxDifference,Math.abs(bridge.camera.matrixWorldInverse.elements[i]-frame.view[i]));
 }
 // Translation around original X=-2500 admits four source float32 ULPs;
 // the bridge is not described as a pixel-identical Android GPU frame.
 assert(maxDifference<.000977,`Original/Three view difference ${maxDifference}`);
 assert.throws(()=>bridge.resize(0,640));
});
