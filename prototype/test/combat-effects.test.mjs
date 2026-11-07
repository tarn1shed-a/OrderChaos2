import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createCombatEffects } from '../public/combat-effects.js';
import {emitter,definition,socketCharacter,attachmentProfile}from './particle-fixture.mjs';
import {createCharacterFactory}from '../public/character-animation.js';

function fixture() {
  const effects={},textures=new Map([['/assets/test.png',new THREE.Texture()]]);
  for(const key of ['fireCast','fireMissile','fireHit','frostHit']) {
    const e=emitter();if(key.startsWith('fire')&&!key.endsWith('Hit'))e.durationFrames=-1;
    effects[key]={...definition([e]),durationMs:key==='fireHit'?766:key==='frostHit'?633:null};
  }
  const factory=createCharacterFactory(THREE,socketCharacter(),[new THREE.MeshBasicMaterial()]);
  const scene=new THREE.Scene(),views=new Map(['p','wolf'].map((id,index)=>{
    const root=new THREE.Group(),body=factory();root.position.set(index*4,0,index*3);root.add(body);scene.add(root);
    return[id,{root,body,alive:true}];
  }));
  const camera=new THREE.PerspectiveCamera();
  const renderer=createCombatEffects(THREE,{scene,camera,data:{format:'oc2-combat-effects-v4',effects,attachments:attachmentProfile},textures,findView:id=>views.get(id),position:(x,y)=>new THREE.Vector3(x,0,y)});
  return {renderer,scene,views};
}
const cast={id:'p:1',skillId:'fireball',startedAt:1000,releaseAt:1500,impactAt:1850,origin:{x:0,y:0},target:{x:4,y:3},targetId:'wolf'};
const event={action:'skill-cast',attackerId:'p',targetId:'wolf',serverTime:1000,cast};
function transforms(scene){const out=[];scene.traverse(n=>{if(n.isSprite||n.isMesh)out.push([n.visible,n.position.toArray(),n.scale.toArray(),n.material.uniforms?.primary?.value.toArray()]);});return out;}

test('two views sample confirmed source-texture effects on the same timeline without replaying snapshots',()=>{
  const a=fixture(),b=fixture();
  for(const f of [a,b]){
    f.renderer.handle({action:'attack'},1000);assert.equal(f.renderer.state().active,0);
    f.renderer.handle(event,1000);f.renderer.handle(event,1100);
    f.renderer.sync([{id:'p',hp:100,cast}],[],1100);assert.equal(f.renderer.state().active,1);
    f.renderer.update(1650);
  }
  assert.deepEqual(transforms(a.scene),transforms(b.scene));
  a.renderer.update(1850);assert.equal(a.renderer.state().active,0);
  a.renderer.sync([{id:'p',hp:100,cast}],[],1851);assert.equal(a.renderer.state().active,0,'Old snapshots cannot replay completed effects');
  const late=fixture();late.renderer.sync([{id:'p',hp:100,cast}],[],1650);late.renderer.update(1650);
  assert.deepEqual(transforms(late.scene),transforms(b.scene),'Late observer samples same projectile position');
  for(const f of [a,b,late])f.renderer.dispose();
});

test('cancellation and death remove casts, impact uses confirmed coordinates, and finite effects free GPU materials',()=>{
  const {renderer,scene,views}=fixture();renderer.handle(event,1000);
  renderer.handle({action:'skill-cancel',castId:cast.id},1100);
  renderer.sync([{id:'p',hp:100,cast}],[],1150);assert.equal(renderer.state().active,0);
  renderer.handle({...event,cast:{...cast,id:'p:2'}},1200);
  renderer.handle({action:'player-hit',targetId:'p',targetHp:0},1250);assert.equal(renderer.state().active,0);
  views.get('wolf').root.position.set(8,0,9);
  renderer.handle({action:'skill-hit',skillId:'fireball',castId:'p:3',targetId:'wolf',serverTime:2000,position:{x:8,y:9}},2000);
  renderer.update(2383);
  const effect=scene.children.find(n=>n.name==='combat-effect:fireHit');assert(effect);
  const meshes=[];effect.traverse(n=>{if(n.isMesh)meshes.push(n);});assert(meshes.length>0);
  assert.deepEqual(meshes[0].position.toArray(),[8,.5,9]);
  assert.equal(meshes[0].material.uniforms.rect.value.x,0);
  let materialsDisposed=0;for(const node of meshes)node.material.addEventListener('dispose',()=>materialsDisposed++);
  renderer.update(2766);assert.equal(renderer.state().active,0);assert.equal(materialsDisposed,meshes.length);
  renderer.dispose();
});

test('frost status follows a living monster and bounded effects clear across room changes',()=>{
  const {renderer,views}=fixture();
  renderer.handle({...event,cast:{...cast,skillId:'frost_blast',releaseAt:1700,impactAt:1700}},1000);
  renderer.handle({action:'skill-hit',skillId:'frost_blast',castId:'ice:1',targetId:'wolf',serverTime:1700,position:{x:4,y:3}},1700);
  renderer.sync([],[{id:'wolf',alive:true,slowUntil:4200,x:4,y:3}],1700);renderer.update(1900);
  assert.deepEqual(renderer.state().types,['frostHit','slow']);
  views.get('wolf').alive=false;renderer.update(1901);assert.deepEqual(renderer.state().types,['frostHit']);
  for(let i=0;i<80;i++)renderer.handle({...event,cast:{...cast,id:`bulk:${i}`}},1200);
  assert.equal(renderer.state().active,48);
  renderer.clear();assert.deepEqual(renderer.state(),{active:0,types:[],seen:0});
  renderer.handle(event,1300);assert.equal(renderer.state().active,1,'New room permits fresh timeline');
  renderer.update(12000);assert.equal(renderer.state().active,0);assert.equal(renderer.state().seen,0);renderer.dispose();
});

test('confirmed fire cast creates separate source emitters on both recovered hand slots',()=>{
 const {renderer}=fixture();renderer.handle(event,1000);renderer.update(1200);
 assert(renderer.attachmentState().includes('fireCast:casterRHand'));assert(renderer.attachmentState().includes('fireCast:casterLHand'));
 assert.equal(renderer.particleCount(),14);renderer.dispose();
});
