import test from'node:test';
import assert from'node:assert/strict';
import{existsSync,readFileSync}from'node:fs';
import * as THREE from'three';
import{createCharacterFactory,playCharacterSkill,updateCharacterAnimation,characterAttachmentTransform}from'../public/character-animation.js';
import{resolveSkillAttachment}from'../public/skill-attachments.js';
import{socketCharacter,attachmentProfile}from'./particle-fixture.mjs';
const target=()=>({position:new THREE.Vector3(),quaternion:new THREE.Quaternion(),scale:new THREE.Vector3()});

test('source hand slots inherit dummy TRS while chest and ground use owner facing and exact terrain offset',()=>{
 const data=socketCharacter();data.rig.nodes[1].scale=[1.1,1.1,1.1];data.rig.nodes[3].quaternion=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0),1).toArray();
 const body=createCharacterFactory(THREE,data,[new THREE.MeshBasicMaterial()])(),root=new THREE.Group();root.position.set(3,2,4);body.rotation.y=Math.PI/2;root.add(body);
 const view={root,body};const hand=resolveSkillAttachment(THREE,attachmentProfile.slots.casterRHand,view,new THREE.Vector3());
 assert(hand.scale.distanceTo(new THREE.Vector3(1.1,1.1,1.1))<1e-5);
 const chest=resolveSkillAttachment(THREE,attachmentProfile.slots.targetChest,view,new THREE.Vector3());assert.equal(chest.position.y,2.5);
 assert(new THREE.Vector3(0,1,0).applyQuaternion(chest.quaternion).distanceTo(new THREE.Vector3(0,1,0))<1e-5);
 const ground=resolveSkillAttachment(THREE,attachmentProfile.slots.targetGround,view,new THREE.Vector3(5,2,7));assert.deepEqual(ground.position.toArray(),[5,2.1,7]);
 assert.equal(resolveSkillAttachment(THREE,attachmentProfile.slots.casterRHand,null,new THREE.Vector3()),null);
});
const path=new URL('../../game-data/converted/models/forest-elf.json',import.meta.url);
test('recovered player dummies have original animated channels and change real world hand transforms',{skip:!existsSync(path)},()=>{
 const data=JSON.parse(readFileSync(path,'utf8')),factory=createCharacterFactory(THREE,data,data.materials.map(()=>new THREE.MeshStandardMaterial())),body=factory();
 const indices=['Dummy_R_Hand','Dummy_L_Hand','Dummy_Chest'].map(name=>data.rig.nodes.findIndex(n=>n.aliases.includes(name)));
 assert(indices.every(i=>i>=52));for(const i of indices.slice(0,2))assert(data.clips.find(c=>c.name==='skill_fireball').tracks.some(t=>t.node===i));
 playCharacterSkill(body,{id:'socket',skillId:'fireball',startedAt:1000,releaseAt:1500},{now:1000});updateCharacterAnimation(body,.1,{moving:false},1100);
 const first=characterAttachmentTransform(body,'Dummy_R_Hand',target());updateCharacterAnimation(body,.1,{moving:false},1350);
 const last=characterAttachmentTransform(body,'Dummy_R_Hand',target());assert(first.position.distanceTo(last.position)>.005||first.quaternion.angleTo(last.quaternion)>.05);
 assert([...last.position.toArray(),...last.quaternion.toArray(),...last.scale.toArray()].every(Number.isFinite));
});
