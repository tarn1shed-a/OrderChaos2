import test from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import { createCombatEffects } from '../public/combat-effects.js';

function fixture() {
  const names={fireCast:['fire_015','fx_sun'],fireMissile:['jpg_s_fire012e','blur_a'],fireHit:['fire03_xulie4x4','fx_stick'],frostHit:['quan_02','ray045','fx_iceblock01','ice06']};
  const effects={},textures=new Map();
  for(const [key,list]of Object.entries(names)) {
    effects[key]={durationMs:key==='fireHit'?766:key==='frostHit'?633:null,textures:[],textureURLs:{}};
    for(const name of list){const path=`texture/${name}.tga`,url=`/assets/${name}.png`;effects[key].textures.push(path);effects[key].textureURLs[path]=url;textures.set(url,new THREE.Texture());}
  }
  const scene=new THREE.Scene(),views=new Map(['p','wolf'].map((id,index)=>{
    const root=new THREE.Group(),body=new THREE.Group();root.position.set(index*4,0,index*3);root.add(body);scene.add(root);
    return[id,{root,body,alive:true}];
  }));
  const renderer=createCombatEffects(THREE,{scene,data:{format:'oc2-combat-effects-v1',effects},textures,findView:id=>views.get(id),position:(x,y)=>new THREE.Vector3(x,0,y)});
  return {renderer,scene,views};
}
const cast={id:'p:1',skillId:'fireball',startedAt:1000,releaseAt:1500,impactAt:1850,origin:{x:0,y:0},target:{x:4,y:3},targetId:'wolf'};
const event={action:'skill-cast',attackerId:'p',targetId:'wolf',serverTime:1000,cast};
function transforms(scene){const out=[];scene.traverse(n=>{if(n.isSprite||n.isMesh)out.push([n.visible,n.position.toArray(),n.scale.toArray(),n.material.opacity]);});return out;}

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
  const {renderer,scene}=fixture();renderer.handle(event,1000);
  renderer.handle({action:'skill-cancel',castId:cast.id},1100);
  renderer.sync([{id:'p',hp:100,cast}],[],1150);assert.equal(renderer.state().active,0);
  renderer.handle({...event,cast:{...cast,id:'p:2'}},1200);
  renderer.handle({action:'player-hit',targetId:'p',targetHp:0},1250);assert.equal(renderer.state().active,0);
  renderer.handle({action:'skill-hit',skillId:'fireball',castId:'p:3',serverTime:2000,position:{x:8,y:9}},2000);
  renderer.update(2383);
  const effect=scene.children.find(n=>n.name==='combat-effect:fireHit');assert(effect);assert.deepEqual(effect.position.toArray(),[8,0,9]);
  const atlas=effect.children[0].material.map;assert.equal(atlas.repeat.x,.25);assert(atlas.offset.x>=0&&atlas.offset.y>=0);
  let materialsDisposed=0,mapDisposed=0;for(const node of effect.children)node.material.addEventListener('dispose',()=>materialsDisposed++);
  atlas.addEventListener('dispose',()=>mapDisposed++);
  renderer.update(2766);assert.equal(renderer.state().active,0);assert.equal(materialsDisposed,2);assert.equal(mapDisposed,1);
  renderer.dispose();
});

test('frost status follows a living monster and bounded effects clear across room changes',()=>{
  const {renderer,views}=fixture();
  renderer.handle({...event,cast:{...cast,skillId:'frost_blast',releaseAt:1700,impactAt:1700}},1000);
  renderer.handle({action:'skill-hit',skillId:'frost_blast',castId:'ice:1',serverTime:1700,position:{x:4,y:3}},1700);
  renderer.sync([],[{id:'wolf',alive:true,slowUntil:4200,x:4,y:3}],1700);renderer.update(1900);
  assert.deepEqual(renderer.state().types,['frostHit','slow']);
  views.get('wolf').alive=false;renderer.update(1901);assert.deepEqual(renderer.state().types,['frostHit']);
  for(let i=0;i<80;i++)renderer.handle({...event,cast:{...cast,id:`bulk:${i}`}},1200);
  assert.equal(renderer.state().active,48);
  renderer.clear();assert.deepEqual(renderer.state(),{active:0,types:[],seen:0});
  renderer.handle(event,1300);assert.equal(renderer.state().active,1,'New room permits fresh timeline');
  renderer.update(12000);assert.equal(renderer.state().active,0);assert.equal(renderer.state().seen,0);renderer.dispose();
});
