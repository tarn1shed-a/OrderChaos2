import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import * as THREE from 'three';
import { createCharacterFactory, updateCharacterAnimation, characterAnimationState, disposeCharacterAnimation, snapshotMotion, playCharacterAction, syncCharacterCombat, respawnCharacterAnimation, playCharacterSkill, cancelCharacterSkill, characterAttachment } from '../public/character-animation.js';
import { applyCombatAnimations } from '../public/combat-animation.js';

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

function combatFixture() {
  const data=fixture();
  data.clips.push({name:'attack',duration:1,tracks:[{node:1,type:'quaternion',times:[0,.5,1],values:[0,0,0,1, 0,0,Math.SQRT1_2,Math.SQRT1_2, 0,0,0,1]}]},
    {name:'hurt',duration:.5,tracks:[{node:1,type:'quaternion',times:[0,.25,.5],values:[0,0,0,1, .6,0,0,.8, 0,0,0,1]}]},
    {name:'death',duration:1,tracks:[{node:1,type:'quaternion',times:[0,1],values:[0,0,0,1, Math.SQRT1_2,0,0,Math.SQRT1_2]}]});
  return data;
}

test('confirmed attack and additive hurt coexist without restarting on repeated state snapshots', () => {
  const create=createCharacterFactory(THREE,combatFixture(),materials()),a=create(),baseline=create();
  assert(playCharacterAction(a,'attack',{at:1000,now:1000,attackSeconds:.7}));
  playCharacterAction(baseline,'attack',{at:1000,now:1000,attackSeconds:.7});
  playCharacterAction(a,'hurt',{at:1050,now:1050});
  for(let i=0;i<10;i++){
    const now=1100+i*10;
    syncCharacterCombat(a,{hp:100,animation:{attackAt:1000,hitAt:1050}},now,.7);
    updateCharacterAnimation(a,.01,{moving:false},now);updateCharacterAnimation(baseline,.01,{moving:false},now);
  }
  const state=characterAnimationState(a);
  assert.equal(state.phase,'attack');assert(state.attackTime>.2);assert(state.hurtWeight>0);
  assert(state.bones[1].quaternion.angleTo(characterAnimationState(baseline).bones[1].quaternion)>.1);
  updateCharacterAnimation(a,.1,{moving:false},1900);
  assert.equal(characterAnimationState(a).phase,'idle');
  assert.equal(characterAnimationState(a).hurtWeight,0);
  disposeCharacterAnimation(a);disposeCharacterAnimation(baseline);
});

test('death overrides attacks, holds its final pose, survives late snapshots and resets only on revival', () => {
  const body=createCharacterFactory(THREE,combatFixture(),materials())();
  playCharacterAction(body,'attack',{at:900,now:1000});
  playCharacterAction(body,'death',{at:1000,now:1000});
  updateCharacterAnimation(body,.1,{moving:true,speed:4.8},1500);
  assert.equal(characterAnimationState(body).phase,'death');
  assert.equal(characterAnimationState(body).attackWeight,0);
  assert.equal(characterAnimationState(body).walkWeight,0);
  assert.equal(playCharacterAction(body,'hurt',{at:1600,now:1600}),false);
  assert.equal(playCharacterAction(body,'attack',{at:1600,now:1600}),false);
  updateCharacterAnimation(body,.1,{moving:true,speed:4.8},2200);
  const held=characterAnimationState(body).bones[1].quaternion.clone();
  assert.equal(characterAnimationState(body).phase,'dead');
  syncCharacterCombat(body,{hp:0,animation:{deathAt:1000}},3000,.7);
  playCharacterAction(body,'death',{at:3100,now:3100});
  updateCharacterAnimation(body,.1,{moving:false},4800);
  assert.deepEqual(characterAnimationState(body).bones[1].quaternion.toArray(),held.toArray());
  respawnCharacterAnimation(body,{at:5000,now:5000});
  syncCharacterCombat(body,{hp:0,animation:{deathAt:1000}},4900,.7);
  assert.equal(characterAnimationState(body).dead,false);
  updateCharacterAnimation(body,.1,{moving:false},5100);
  assert.equal(characterAnimationState(body).phase,'idle');
  playCharacterAction(body,'attack',{at:5100,now:5100});
  respawnCharacterAnimation(body,{at:5000,now:5200});
  updateCharacterAnimation(body,.1,{moving:false},5200);
  assert.equal(characterAnimationState(body).phase,'attack');
  disposeCharacterAnimation(body);
});

test('two views route confirmed hits identically; late observers see held corpses and no predicted attacks', () => {
  const create=createCharacterFactory(THREE,combatFixture(),materials());
  const worlds=[0,1].map(()=>new Map(['player','wolf'].map((id,index)=>[id,{body:create(),root:{position:{x:index,z:0}},target:{x:index,z:0},attackSeconds:.7}])));
  for(const world of worlds)for(const view of world.values())updateCharacterAnimation(view.body,.05,{moving:false},1000);
  for(const world of worlds)assert.equal(characterAnimationState(world.get('player').body).phase,'idle');
  const event={type:'combat',action:'hit',attackerId:'player',targetId:'wolf',targetHp:40,serverTime:1100};
  for(const world of worlds){applyCombatAnimations(event,id=>world.get(id),1150);for(const view of world.values())updateCharacterAnimation(view.body,.05,{moving:false},1200);}
  assert.equal(characterAnimationState(worlds[0].get('player').body).phase,'attack');
  assert.equal(characterAnimationState(worlds[0].get('wolf').body).phase,'hurt');
  assert.deepEqual(characterAnimationState(worlds[0].get('player').body).bones[1].quaternion.toArray(),characterAnimationState(worlds[1].get('player').body).bones[1].quaternion.toArray());
  for(const world of worlds){applyCombatAnimations({...event,targetHp:0,serverTime:1300},id=>world.get(id),1300);updateCharacterAnimation(world.get('wolf').body,.05,{moving:false},2500);assert.equal(characterAnimationState(world.get('wolf').body).phase,'dead');}
  const late=create();syncCharacterCombat(late,{hp:0,alive:false,animation:{deathAt:1300}},3000,1);updateCharacterAnimation(late,.05,{moving:false},3000);
  assert.equal(characterAnimationState(late).phase,'dead');
  for(const world of worlds)for(const view of world.values())disposeCharacterAnimation(view.body);
  disposeCharacterAnimation(late);
});

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
const originalWolf = new URL('../../game-data/converted/models/wolf.json',import.meta.url);
test('original recovered skill clips deform vertices, follow hand bones and agree for late observers', {skip: !existsSync(original)},()=>{
  const data=JSON.parse(readFileSync(original,'utf8'));
  assert.equal(data.clips.find(c=>c.name==='skill_fireball').duration,.5);
  assert.equal(data.clips.find(c=>c.name==='skill_frost_blast').duration,.7);
  const create=createCharacterFactory(THREE,data,data.materials.map(()=>new THREE.MeshStandardMaterial()));
  for(const [skillId,duration]of [['fireball',500],['frost_blast',700]]) {
    const a=create(),b=create(),cast={id:skillId,skillId,startedAt:1000,releaseAt:1000+duration};
    playCharacterSkill(a,cast,{now:1000});updateCharacterAnimation(a,.1,{moving:false},1000+duration*.4);
    syncCharacterCombat(b,{hp:100,cast},1000+duration*.4,.7);updateCharacterAnimation(b,.1,{moving:false},1000+duration*.4);
    assert.equal(characterAnimationState(a).phase,`skill_${skillId}`);
    assert.equal(characterAnimationState(a).skillTime,characterAnimationState(b).skillTime);
    a.updateMatrixWorld(true);b.updateMatrixWorld(true);
    // Untouched source helpers keep float32 rest quaternions; comparing their raw
    // angle assumes exact unit length even when both poses are byte-for-byte equal.
    for(let i=0;i<data.rig.nodes.length;i++)assert.deepEqual(characterAnimationState(a).bones[i].quaternion.toArray(),characterAnimationState(b).bones[i].quaternion.toArray());
    const hand=characterAttachment(a,'Bip01_R_Hand',new THREE.Vector3());assert(hand&&hand.toArray().every(Number.isFinite));
    for(const mesh of skinnedMeshes(a))for(let vertex=0;vertex<mesh.geometry.attributes.position.count;vertex++) {
      const point=mesh.getVertexPosition(vertex,new THREE.Vector3());assert(point.toArray().every(Number.isFinite));assert(point.length()<10);
    }
    cancelCharacterSkill(a,cast.id);updateCharacterAnimation(a,.1,{moving:false},1200);assert.equal(characterAnimationState(a).skillWeight,0);
    syncCharacterCombat(a,{hp:100,cast},1250,.7);assert.equal(characterAnimationState(a).castId,undefined,'Cancelled cast does not replay from stale state');
    playCharacterAction(b,'death',{at:1250,now:1250});updateCharacterAnimation(b,.1,{moving:false},1300);assert.equal(characterAnimationState(b).skillWeight,0);
    respawnCharacterAnimation(b,{at:5000,now:5000});assert.equal(playCharacterSkill(b,cast,{now:5000}),false,'Old-life casts cannot revive');
    disposeCharacterAnimation(a);disposeCharacterAnimation(b);
  }
});
test('original player and wolf combat deform real vertices, hold corpses, and reset on authoritative revival', {skip: !existsSync(original)||!existsSync(originalWolf)}, () => {
  for(const path of [original,originalWolf]) {
    const data=JSON.parse(readFileSync(path,'utf8'));
    const body=createCharacterFactory(THREE,data,data.materials.map(()=>new THREE.MeshStandardMaterial()))();
    playCharacterAction(body,'attack',{at:1000,now:1000,attackSeconds:.7});
    playCharacterAction(body,'hurt',{at:1100,now:1100});
    for(let frame=0;frame<20;frame++)updateCharacterAnimation(body,1/30,{moving:false},1100+frame*30);
    assert(characterAnimationState(body).combatEnabled);
    playCharacterAction(body,'death',{at:2000,now:2000});
    for(let frame=0;frame<60;frame++) {
      updateCharacterAnimation(body,1/30,{moving:true,speed:4.8},2000+frame*50);body.updateMatrixWorld(true);
      if(frame%15===0)for(const mesh of skinnedMeshes(body))for(let vertex=0;vertex<mesh.geometry.attributes.position.count;vertex++) {
        const point=mesh.getVertexPosition(vertex,new THREE.Vector3());
        assert(point.toArray().every(Number.isFinite));assert(point.length()<10);
      }
    }
    const state=characterAnimationState(body);assert.equal(state.phase,'dead');
    const pose=state.bones.map(bone=>bone.quaternion.toArray());
    updateCharacterAnimation(body,.1,{moving:false},5500);
    assert.deepEqual(characterAnimationState(body).bones.map(bone=>bone.quaternion.toArray()),pose);
    syncCharacterCombat(body,{hp:100,alive:true,animation:{attackAt:null,hitAt:null,deathAt:null}},6000,.7);
    updateCharacterAnimation(body,.1,{moving:false},6000);assert.equal(characterAnimationState(body).phase,'idle');
    assert.deepEqual(body.position.toArray(),[0,0,0]);disposeCharacterAnimation(body);
  }
});
test('original recovered character stays finite through repeated walk/idle cycles with no root drift', {skip: !existsSync(original)}, () => {
  const data=JSON.parse(readFileSync(original,'utf8'));
  assert.equal(data.format,'bdae946-character-v1');
  const create=createCharacterFactory(THREE,data,data.materials.map(()=>new THREE.MeshStandardMaterial()));
  const character=create(),state=characterAnimationState(character),meshes=skinnedMeshes(character);
  assert.equal(state.bones.length,55);assert.equal(meshes.length,2);
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

test('confirmed source jump phases deform bones consistently in both views and death returns height to zero',()=>{
  const data=combatFixture();
  for(const [name,duration] of [['jump_start',.5],['jump_air',2/3],['jump_land',13/15]])data.clips.push({name,duration,tracks:[{node:1,type:'quaternion',times:[0,duration],values:[0,0,0,1,0,.6,0,.8]}]});
  const create=createCharacterFactory(THREE,data,materials()),bodies=[create(),create()];
  const jump={startedAt:1000,takeoffAt:1500,landAt:2166.6666666666665,endsAt:3033.333333333333};
  for(const body of bodies){
    syncCharacterCombat(body,{hp:100,jump,animation:{}},1000,.7);
    updateCharacterAnimation(body,.1,{moving:true,speed:4.8},1750);
    const state=characterAnimationState(body);assert.equal(state.phase,'jump_air');assert(state.jumpHeight>0);assert.equal(state.walkWeight,0);
  }
  assert.deepEqual(characterAnimationState(bodies[0]).bones[1].quaternion.toArray(),characterAnimationState(bodies[1]).bones[1].quaternion.toArray());
  for(const body of bodies){
    syncCharacterCombat(body,{hp:0,jump:null,animation:{deathAt:1800}},1800,.7);
    updateCharacterAnimation(body,.1,{moving:true},1850);assert.equal(characterAnimationState(body).phase,'death');assert.equal(characterAnimationState(body).jumpHeight,0);
    disposeCharacterAnimation(body);
  }
});

const originalPlayer=new URL('../../game-data/converted/models/elf-female.json',import.meta.url);
test('actual player jump clips preserve source lengths, deform real vertices and finish without root drift',{skip:!existsSync(originalPlayer)},()=>{
  const data=JSON.parse(readFileSync(originalPlayer,'utf8'));
  for(const [name,duration] of [['jump_start',.5],['jump_air',2/3],['jump_land',13/15]])assert(Math.abs(data.clips.find(c=>c.name===name).duration-duration)<1e-8);
  const body=createCharacterFactory(THREE,data,data.materials.map(()=>new THREE.MeshStandardMaterial()))();
  const meshes=skinnedMeshes(body),before=meshes[0].getVertexPosition(0,new THREE.Vector3()).clone();
  const jump={startedAt:1000,takeoffAt:1500,landAt:2166.6666666666665,endsAt:3033.333333333333};
  syncCharacterCombat(body,{hp:100,jump,animation:{}},1000,.7);
  for(const [now,phase] of [[1250,'jump_start'],[1800,'jump_air'],[2500,'jump_land']]){
    updateCharacterAnimation(body,.1,{moving:false},now);body.updateMatrixWorld(true);assert.equal(characterAnimationState(body).phase,phase);
    for(const mesh of meshes)for(let i=0;i<mesh.geometry.attributes.position.count;i++){
      const point=mesh.getVertexPosition(i,new THREE.Vector3());assert(point.toArray().every(Number.isFinite));assert(point.length()<10);
    }
  }
  assert(meshes[0].getVertexPosition(0,new THREE.Vector3()).distanceTo(before)>1e-5);
  syncCharacterCombat(body,{hp:100,jump:null,animation:{}},3200,.7);updateCharacterAnimation(body,.1,{moving:false},3200);
  assert.equal(characterAnimationState(body).phase,'idle');assert.equal(characterAnimationState(body).jumpHeight,0);assert.deepEqual(body.position.toArray(),[0,0,0]);
  disposeCharacterAnimation(body);
});
