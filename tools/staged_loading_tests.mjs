import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {stageEntry} from '../deploy/stage_runtime.mjs';
import {preparationWindow} from '../deploy/streaming_window.mjs';
const source=(await readFile(new URL('../deploy/staged_scene.mjs',import.meta.url),'utf8')).replace(/^import[^\n]+\n/gm,'').replace('export function createSceneStages','function createSceneStages');
function fixture({fail=false}={}){
  const context={performance,Date,setTimeout,preparationWindow,sourceArchiveWindow:()=>({update:()=>({center:[0,0],resident:new Set(['0,0'])})})};
  vm.createContext(context);vm.runInContext(source+';this.factory=createSceneStages;',context);
  const tiles=[0,1,2].map(x=>({tile:[x,0],original:'same-geometry-'+x}));
  const canvas={dataset:{}},scene={children:[],add(root){this.children.push(root);}},archiveObjects=[];
  const terrain={sourceTiles:tiles,grid:{width:193},tileOrigin:[0,0],tileCount:[3,1]};
  const stages=context.factory({canvas,scene,archiveObjects,terrain,initial:{x:0,z:0},offsets:[[0,0]],radius:0});
  let release;const gate=new Promise(resolve=>release=resolve),created=[];
  async function create(T,data,mats,origin,texture,light){
    assert.equal(data.grid,terrain.grid);assert.equal(data.tileOrigin,terrain.tileOrigin);
    assert.deepEqual(JSON.parse(JSON.stringify(data.sourceTiles)),JSON.parse(JSON.stringify(mats.tiles)));
    assert.deepEqual(JSON.parse(JSON.stringify(light.profile.tiles)),JSON.parse(JSON.stringify(mats.tiles)));
    if(data.sourceTiles.some(t=>t.tile[0]>0)){await gate;if(fail&&data.sourceTiles[0].tile[0]===1)throw Error('deliberate missing resource');}
    return data.sourceTiles.map(t=>{created.push(t);return{visible:true,userData:{sourceTile:t.tile}};});
  }
  return{stages,canvas,scene,archiveObjects,terrain,tiles,created,create,release};
}
async function setup(f){
  f.roots=await f.stages.terrain(f.create,null,f.terrain,{tiles:f.tiles},{},()=>{},{profile:{tiles:f.tiles}});
  for(const root of f.roots){f.scene.add(root);f.archiveObjects.push({root,tile:root.userData.sourceTile});}
  const row={model:'original-model',instances:f.tiles.map((t,i)=>({tile:t.tile,id:i,position:[i,5,0]}))};f.instances=[];
  await f.stages.scenery([row],async(item,rows)=>{assert.equal(item,row);f.instances.push(...rows);for(const inst of rows){const root={visible:false};f.scene.add(root);f.archiveObjects.push({root,tile:inst.tile});}});
}
async function settle(f){for(let i=0;i<100&&f.canvas.dataset.loadingBackgroundDone!==f.canvas.dataset.loadingBackgroundTotal;i++)await new Promise(r=>setTimeout(r,2));}
test('entry prepares only existing nearby tiles; background reuses exact records and complete coverage',async()=>{
  const f=fixture();await setup(f);assert.equal(f.created.length,1);assert.equal(f.instances.length,1);assert.equal(f.roots.length,1);
  assert.equal(f.stages.present({center:[0,0],resident:new Set(['0,0'])}),true);f.stages.start();
  assert.equal(f.stages.present({center:[1,0],resident:new Set(['1,0'])}),false);
  assert.equal(f.canvas.dataset.loadingPresentation,'waiting-for-complete-window');
  f.release();await settle(f);assert.equal(f.created.length,3);assert.equal(f.roots.length,3);assert.equal(f.instances.length,3);
  assert.equal(new Set(f.created).size,3);assert(f.created.every(t=>f.tiles.includes(t)));
  assert.equal(f.stages.present(null),true);
  for(const row of f.archiveObjects)assert.equal(row.root.visible,row.tile[0]===1);
  assert.equal(f.canvas.dataset.loadingStage,'complete');
});
test('returning to a complete window does not wait for unrelated background tiles',async()=>{
  const f=fixture();await setup(f);f.stages.start();assert.equal(f.stages.present({center:[2,0],resident:new Set(['2,0'])}),false);
  assert.equal(f.stages.present({center:[0,0],resident:new Set(['0,0'])}),true);f.release();await settle(f);
});
test('failed background resources never unlock an incomplete window or draw placeholders',async()=>{
  const f=fixture({fail:true});await setup(f);f.stages.start();f.release();await new Promise(r=>setTimeout(r,20));
  assert.equal(f.stages.present({center:[1,0],resident:new Set(['1,0'])}),false);assert.equal(f.canvas.dataset.loadingBackgroundError,'deliberate missing resource');
  assert.equal(f.roots.length,2);assert.equal(f.created.length,2);assert.notEqual(f.canvas.dataset.loadingStage,'complete');
});
test('loader overlay refuses unknown or modified game source',()=>assert.throws(()=>stageEntry('unverified source'),/identity differs/));
test('verified private entry overlay changes loading sections only',async t=>{
  let original;try{original=await readFile(new URL('../analysis/raw/showcase-20261110/running-preview/prototype/public/explore-map.js',import.meta.url),'utf8');}catch{t.skip('Private historical runtime not in Git');return;}
  const changed=stageEntry(original);assert(changed.includes('sceneStages.start()'));
  for(const [start,end]of [['function updateCharacter(', 'async function texture('],['function updateRoster()', 'function inputBlocked()']])assert.equal(changed.slice(changed.indexOf(start),changed.indexOf(end)),original.slice(original.indexOf(start),original.indexOf(end)));
  const calculation=original.slice(original.indexOf('  if (!connected || document.hidden) return;',original.indexOf('setInterval(() => {')),original.indexOf('}, 50);\nsetInterval(() => { if(connected&&!document.hidden)'));
  assert(changed.includes(calculation));assert(changed.includes('setInterval(publishMovement,50)'));assert(changed.includes('createSourceFramePresentation({delayMs:50})'));
});
test('prepare adjacent request windows without expanding the visible window',()=>{
  const offsets=Array.from({length:25},(_,i)=>[i%5-2,Math.floor(i/5)-2]),tiles=Array.from({length:81},(_,i)=>[i%9-4,Math.floor(i/9)-4]);
  const {entry,prepared}=preparationWindow(tiles,offsets,[0,0]);assert.equal(entry.size,25);assert.equal(prepared.size,49);
  for(const center of [[1,0],[-1,0],[0,1],[0,-1]])for(const key of preparationWindow(tiles,offsets,center).entry)assert(prepared.has(key));
});
test('50ms transport buffer preserves paired source coordinates and camera, without prediction',async t=>{
  let module;try{module=await import('../analysis/raw/showcase-20261110/running-preview/prototype/public/source-frame-presentation.js');}catch{t.skip('Private historical runtime not in Git');return;}
  const fast=module.createSourceFramePresentation({delayMs:50}),old=module.createSourceFramePresentation({delayMs:100});
  for(let i=0;i<10;i++){const player={id:'fixture',x:i,y:i*2,worldY:i*3,sourceCamera:{nativeCPU:true,yaw:i,position:[i,4,6],target:[i,0,2]}};fast.push([player],i*50,i*50+20);old.push([player],i*50,i*50+20);}
  for(let now=100;now<400;now+=16){const a=fast.sample(now).get('fixture'),b=old.sample(now+50).get('fixture');delete a.presentation;delete b.presentation;assert.deepEqual(a,b);}
});
