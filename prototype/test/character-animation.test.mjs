import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import * as THREE from 'three';
import { createCharacterFactory, updateCharacterAnimation, characterAnimationState, disposeCharacterAnimation, snapshotMotion } from '../public/character-animation.js';

function fixture() {
  const track = values => ({ node: 1, type: 'quaternion', times: [0, .5, 1], values });
  const identity = new THREE.Matrix4().toArray();
  return { format: 'bdae946-character-v1',
    meshes: [{ positions: [0,0,0, 1,0,0, 0,1,0], normals: [0,0,1, 0,0,1, 0,0,1], uvs: [0,0, 1,0, 0,1], indices: [0,1,2], material: 0, groups: [{start:0,count:3,material:0}] }],
    rig: { nodes: [
      { parent: -1, position: [0,0,0], quaternion: [0,0,0,1], scale: [1,1,1] },
      { parent: 0, position: [0,0,0], quaternion: [0,0,0,1], scale: [1,1,1] }],
      skins: [{mesh:0,boneNodes:[1],inverseBindMatrices:[identity],skinIndices:[0,0,0,0, 0,0,0,0, 0,0,0,0],skinWeights:[1,0,0,0, 1,0,0,0, 1,0,0,0]}] },
    clips: [{name:'idle',duration:1,tracks:[track([0,0,0,1, 0,0,0,1, 0,0,0,1])]},
      {name:'walk_forward',duration:1,tracks:[track([0,0,0,1, 0,0,Math.SQRT1_2,Math.SQRT1_2, 0,0,0,1])]}] };
}
const materials = () => [new THREE.MeshStandardMaterial()];
function skinnedMeshes(root) { const result = []; root.traverse(object => { if(object.isSkinnedMesh)result.push(object); }); return result; }

test('characters have independent skeletons, real vertex deformation, and an idle transition', () => {
  const create = createCharacterFactory(THREE, fixture(), materials());
  const a = create(), b = create();
  const sa = characterAnimationState(a), sb = characterAnimationState(b);
  assert.notEqual(sa.bones[1], sb.bones[1]);
  assert.notEqual(sa.skeletons[0], sb.skeletons[0]);
  const mesh = skinnedMeshes(a)[0], initial = mesh.getVertexPosition(1,new THREE.Vector3()).clone();
  for(let frame=0;frame<20;frame++) {
    updateCharacterAnimation(a,1/60,{moving:true,speed:4.8});
    updateCharacterAnimation(b,1/60,{moving:false,speed:0});
  }
  a.updateMatrixWorld(true);b.updateMatrixWorld(true);
  assert(mesh.getVertexPosition(1,new THREE.Vector3()).distanceTo(initial)>.5);
  assert(sa.bones[1].quaternion.angleTo(sb.bones[1].quaternion)>.5);
  assert.equal(characterAnimationState(b).walkWeight,0);
  const rootPosition = a.position.clone();
  for(let frame=0;frame<90;frame++)updateCharacterAnimation(a,1/60,{moving:false,speed:0});
  assert.equal(characterAnimationState(a).walkWeight,0);
  assert(sa.bones[1].quaternion.angleTo(new THREE.Quaternion())<1e-5);
  assert.deepEqual(a.position,rootPosition);
  disposeCharacterAnimation(a);
  assert.equal(characterAnimationState(a),null);
  updateCharacterAnimation(b,1/30,{moving:true,speed:4.8});
  assert(characterAnimationState(b).walkWeight>0);
  disposeCharacterAnimation(b);
});

test('both views derive walking from server displacement and stop on idle, death or teleport', () => {
  const before={x:900,y:360,hp:100}, after={x:899.031702,y:358.726266,hp:100};
  const viewA=snapshotMotion(before,after,.05,.15),viewB=snapshotMotion({...before},{...after},.05,.15);
  assert.deepEqual(viewA,viewB);assert(viewA.moving);assert(Math.abs(viewA.speed-4.8)<.00001);
  assert.equal(snapshotMotion(after,after,.05,.15).moving,false);
  assert.equal(snapshotMotion(before,{...after,hp:0},.05,.15).moving,false);
  assert.equal(snapshotMotion(before,{x:20,y:20,hp:100},.05,.15).moving,false);
  assert.equal(snapshotMotion(null,after,.05,.15).moving,false);
});

const original = new URL('../../game-data/converted/models/forest-elf.json',import.meta.url);
test('original recovered character stays finite through repeated walk/idle cycles with no root drift', {skip: !existsSync(original)}, () => {
  const data=JSON.parse(readFileSync(original,'utf8'));
  assert.equal(data.format,'bdae946-character-v1');
  const create=createCharacterFactory(THREE,data,data.materials.map(()=>new THREE.MeshStandardMaterial()));
  const character=create(),state=characterAnimationState(character),meshes=skinnedMeshes(character);
  assert.equal(state.bones.length,52);assert.equal(meshes.length,2);
  let greatestMovement=0;
  const previous=state.bones.map(bone=>bone.quaternion.clone());
  for(let frame=0;frame<360;frame++) {
    updateCharacterAnimation(character,1/30,{moving:frame<240,speed:4.8});character.updateMatrixWorld(true);
    for(const [index,bone]of state.bones.entries()) {
      greatestMovement=Math.max(greatestMovement,bone.quaternion.angleTo(previous[index]));
      assert(bone.matrixWorld.elements.every(Number.isFinite));
    }
    if(frame%30===0)for(const mesh of meshes)for(let vertex=0;vertex<mesh.geometry.attributes.position.count;vertex++) {
      const point=mesh.getVertexPosition(vertex,new THREE.Vector3());
      assert(point.toArray().every(Number.isFinite));assert(point.length()<10);
    }
  }
  assert(greatestMovement>.5);assert.equal(characterAnimationState(character).walkWeight,0);
  assert.deepEqual(character.position.toArray(),[0,0,0]);
  disposeCharacterAnimation(character);
});
