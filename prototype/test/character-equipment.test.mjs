import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import * as THREE from 'three';
import { createCharacterFactory, setCharacterEquipment, characterEquipmentState, characterAnimationState, updateCharacterAnimation, syncCharacterCombat, disposeCharacterAnimation } from '../public/character-animation.js';
import { validateEquipmentAppearance } from '../public/character-equipment.js';

const allGear = {mainHand:'trainingSword',chest:'linenArmor',feet:'travelerBoots'};
function fixture() {
  const triangle = name => ({name,positions:[0,0,0, .25,0,0, 0,.5,0],normals:[0,0,1,0,0,1,0,0,1],uvs:[0,0,1,0,0,1],indices:[0,1,2],material:0});
  const meshes=['body','foot','head','sword','robe','boots'].map(triangle);
  meshes[3].attachment={node:1,matrix:new THREE.Matrix4().makeTranslation(0,-.02,0).toArray()};
  const skin=mesh=>({mesh,boneNodes:[1],inverseBindMatrices:[new THREE.Matrix4().toArray()],skinIndices:Array(12).fill(0),skinWeights:[1,0,0,0,1,0,0,0,1,0,0,0]});
  return {format:'bdae946-character-v1',meshes,
    rig:{nodes:[{name:'Root',aliases:[],parent:-1,position:[0,0,0],quaternion:[0,0,0,1],scale:[1,1,1]},
      {name:'Hand',aliases:['Weapon_R'],parent:0,position:[0,0,0],quaternion:[0,0,0,1],scale:[1,1,1]}],skins:[0,1,2,4,5].map(skin)},
    clips:[{name:'idle',duration:1,tracks:[]},{name:'walk_forward',duration:1,tracks:[{node:1,type:'quaternion',times:[0,.5,1],values:[0,0,0,1,0,0,Math.SQRT1_2,Math.SQRT1_2,0,0,0,1]}]}],
    appearance:{format:'oc2-equipment-appearance-v1',baseMeshIndices:[0,1,2],items:{
      trainingSword:{slot:'mainHand',meshIndices:[3],hideBaseMeshIndices:[]},
      linenArmor:{slot:'chest',meshIndices:[4],hideBaseMeshIndices:[0]},
      travelerBoots:{slot:'feet',meshIndices:[5],hideBaseMeshIndices:[1]}}}};
}
function objects(root) { const result=[];root.traverse(o=>{if(o.isMesh)result[o.userData.sourceMeshIndex]=o;});return result; }

test('gear changes shared-rig meshes without replacing a character, resetting its walk, or affecting another player',()=>{
  const data=fixture(),material=new THREE.MeshStandardMaterial(),create=createCharacterFactory(THREE,data,[material]),a=create(),b=create();
  const original=objects(a),state=characterAnimationState(a);
  updateCharacterAnimation(a,.1,{moving:true,speed:4.8},1000);
  const time=characterAnimationState(a).walkTime;
  assert(setCharacterEquipment(a,allGear));assert.equal(setCharacterEquipment(a,allGear),false);
  assert.deepEqual(characterEquipmentState(a).visibleMeshIndices,[2,3,4,5]);assert.deepEqual(characterEquipmentState(b).visibleMeshIndices,[0,1,2]);
  assert.equal(characterAnimationState(a).walkTime,time);assert.equal(characterAnimationState(a).bones,state.bones);
  assert.notEqual(objects(b)[4].skeleton.bones[0],original[4].skeleton.bones[0]);
  for(let i=0;i<50;i++){setCharacterEquipment(a,{});setCharacterEquipment(a,allGear);}
  objects(a).forEach((object,index)=>assert.equal(object,original[index]));assert.equal(original[3].parent,state.bones[1]);
  assert.equal(original[4].geometry,objects(b)[4].geometry,'Immutable buffers may be shared');
  assert.deepEqual(data.appearance.baseMeshIndices,[0,1,2]);
  disposeCharacterAnimation(a);disposeCharacterAnimation(b);
});

test('modular skin and rigid grip follow the real animated hand and preserve source skin weights',()=>{
  const data=fixture(),root=createCharacterFactory(THREE,data,[new THREE.MeshStandardMaterial()])();setCharacterEquipment(root,allGear);
  const mesh=objects(root),before=mesh[4].getVertexPosition(2,new THREE.Vector3()).clone();
  const swordBefore=mesh[3].getWorldPosition(new THREE.Vector3());
  updateCharacterAnimation(root,.1,{moving:true,speed:4.8},1000);root.updateMatrixWorld(true);
  for(const skeleton of characterAnimationState(root).skeletons)skeleton.update();
  const after=mesh[4].getVertexPosition(2,new THREE.Vector3());assert(after.distanceTo(before)>.1);
  assert(mesh[3].getWorldPosition(new THREE.Vector3()).distanceTo(swordBefore)>.005);
  const expected=new THREE.Vector3(0,-.02,0).applyMatrix4(characterAnimationState(root).bones[1].matrixWorld);
  assert(mesh[3].getWorldPosition(new THREE.Vector3()).distanceTo(expected)<1e-7);
  assert.deepEqual(Array.from(mesh[4].geometry.attributes.skinWeight.array),data.rig.skins.find(s=>s.mesh===4).skinWeights);
  disposeCharacterAnimation(root);
});

test('invalid appearance references, missing pieces, overlapping base meshes and unknown mounts fail visibly',()=>{
  for(const mutate of [d=>d.appearance.items.linenArmor.meshIndices=[100],d=>d.appearance.items.linenArmor.hideBaseMeshIndices=[5],
    d=>d.appearance.items.trainingSword.meshIndices=[0],d=>delete d.appearance.items.travelerBoots,
    d=>d.meshes[3].attachment.node=999,d=>d.appearance.items.fake={meshIndices:[],hideBaseMeshIndices:[]}]) {
    const data=fixture();mutate(data);assert.throws(()=>validateEquipmentAppearance(data));
  }
});

test('two observers and a late joiner apply the same saved gear independently of animation arrival',()=>{
  const create=createCharacterFactory(THREE,fixture(),[new THREE.MeshStandardMaterial()]);
  const first=create(),second=create();setCharacterEquipment(first,allGear);setCharacterEquipment(second,allGear);
  for(const root of [first,second])updateCharacterAnimation(root,.05,{moving:true,speed:4.8},1000);
  const late=create();setCharacterEquipment(late,allGear);
  assert.deepEqual(characterEquipmentState(first),characterEquipmentState(second));assert.deepEqual(characterEquipmentState(first),characterEquipmentState(late));
  setCharacterEquipment(first,{});assert.deepEqual(characterEquipmentState(second).items.sort(),Object.values(allGear).sort());
  for(const root of [first,second,late])disposeCharacterAnimation(root);
});

const original=new URL('../../game-data/converted/models/elf-female.json',import.meta.url);
test('all original equipment combinations keep real vertices finite through walking, skills, hurt, death and revival',{skip:!existsSync(original)},()=>{
  const data=JSON.parse(readFileSync(original,'utf8')),materials=data.materials.map(()=>new THREE.MeshStandardMaterial());
  const create=createCharacterFactory(THREE,data,materials),root=create();
  const combinations=Array.from({length:8},(_,bits)=>Object.fromEntries(Object.entries(allGear).filter((_,i)=>bits&(1<<i))));
  let now=1000;
  for(const equipment of combinations){
    setCharacterEquipment(root,equipment);
    for(const snapshot of [{hp:100,animation:{}},{hp:100,animation:{attackAt:now}},{hp:100,animation:{hitAt:now}},
      {hp:100,cast:{id:String(now),skillId:'fireball',startedAt:now,releaseAt:now+500},animation:{}},
      {hp:0,animation:{deathAt:now}},{hp:100,animation:{}}]){
      syncCharacterCombat(root,snapshot,now,.7);updateCharacterAnimation(root,.08,{moving:true,speed:4.8},now+80);root.updateMatrixWorld(true);
      for(const skin of characterAnimationState(root).skeletons)skin.update();
      root.traverseVisible(object=>{if(!object.isMesh)return;
        const vertex=object.getVertexPosition(0,new THREE.Vector3()).applyMatrix4(object.matrixWorld);
        assert(vertex.toArray().every(Number.isFinite));assert(vertex.length()<10);
      });now+=1000;
    }
    assert.deepEqual(characterEquipmentState(root).items.sort(),Object.values(equipment).sort());
  }
  disposeCharacterAnimation(root);
});
