import {test} from 'node:test';import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync,existsSync,rmSync} from 'node:fs';import {tmpdir} from 'node:os';import {join} from 'node:path';
import {createHash} from 'node:crypto';import {spawnSync} from 'node:child_process';
import {createMapInspector,stageInspectorServer} from '../deploy/map_inspector.mjs';
import {applyPositionRepair} from '../deploy/role_position_repair.mjs';import {stageInspectorEntry} from '../deploy/map_inspector_ui.mjs';
import {entryServer} from '../deploy/entry_manage.mjs';import {stageEntry} from '../deploy/stage_runtime.mjs';
import {stageInsideEntry} from './preview/map-runtime-inside-overlay.mjs';import {stageCharacterPanelsEntry} from './preview/character-panel-runtime-overlay.mjs';import {stageCharacterHotbarEntry} from './preview/character-hotbar-overlay.mjs';import {stageSceneEffectsEntry} from './preview/source-scene-effect-overlay.mjs';import {stageFire10Entry} from './preview/source-scene-effect-fire10-overlay.mjs';import {stageUnstuckEntry} from '../deploy/unstuck_entry.mjs';
const digest=v=>createHash('sha256').update(v).digest('hex');
const target={x:2,y:3,groundY:136};
test('only server-issued UUID and stored object receive noclip; input timeout, bounds, home and elevation work',()=>{
 const dir=mkdtempSync(join(tmpdir(),'inspector-'));let time=0;const records=new Map(),token='a'.repeat(64);
 const store={records,resolveCharacter(name,id,value){if(id){const record=records.get(id);assert(record&&value===token);return{record};}const record={id:'issued',name,tokenHash:digest(token)};records.set(record.id,record);return{record,resumeToken:token};}};
 try{const inspector=createMapInspector({identityFile:join(dir,'identity.json'),entryPosition:()=>target,now:()=>time});inspector.bind(store);
 const ordinary={character:{id:'issued',name:'地图管理员'},player:{x:10,y:10,worldY:10}};inspector.attach(ordinary,true);assert(!inspector.enabled(ordinary));
 const identity=inspector.identity();assert.equal(identity.characterId,'issued');const ws={character:records.get('issued'),player:{},motion:{point:(x,y)=>({x,z:y}),logical:p=>({x:p.x,y:p.z})},world:{bounds:{minX:-50,maxX:50,minY:-50,maxY:50}}};
 inspector.attach(ws,true);assert(inspector.enabled(ws));const motion={type:'map-inspect',x:1,y:0,z:1,yaw:0,pitch:25,distance:5,fast:false};assert(!inspector.input(ordinary,motion));assert(inspector.input(ws,motion));assert(inspector.move(ws,.5));assert(ws.player.worldY>136);assert(!ws.player.sourceCamera);assert(ws.player.inspectionCamera.webAdmin);
 const before=structuredClone(ws.player);time=400;inspector.move(ws,.5);assert.equal(ws.player.x,before.x);assert.equal(ws.player.worldY,before.worldY);
 assert(!inspector.input(ws,{...motion,z:NaN,home:true}));assert.equal(ws.player.worldY,before.worldY);
 assert(inspector.input(ws,{...motion,x:0,z:0,home:true}));assert.equal(ws.player.worldY,136);
 const again=createMapInspector({identityFile:join(dir,'identity.json'),entryPosition:()=>target});again.bind(store);assert.equal(again.identity().characterId,identity.characterId);assert.equal(records.size,1);
 }finally{rmSync(dir,{recursive:true,force:true});}
});
test('startup repair changes only the named UUID position, is one-shot, and refuses stale input',()=>{
 const dir=mkdtempSync(join(tmpdir(),'position-')),file=join(dir,'request.json');
 const original={id:'selected',name:'2',xp:75,equipment:{x:'y'},positions:{camp:{x:8,y:9},resources:{x:10,y:11,groundY:132}}},other={id:'other',name:'2',xp:11};
 const store={records:new Map([['selected',structuredClone(original)],['other',other]]),flush(){this.flushed=true;}};
 try{writeFileSync(file,JSON.stringify({format:'oc2-position-repair-v1',characterId:'selected',name:'2',anchor:'cinematic7',expectedPosition:original.positions.resources}));
 applyPositionRepair(store,file,()=>target);assert.deepEqual(store.records.get('selected'),{...original,positions:{...original.positions,resources:target}});assert.equal(store.records.get('other'),other);assert(store.flushed);assert(existsSync(file+'.applied'));assert.equal(applyPositionRepair(store,file,()=>target),null);
 writeFileSync(file,JSON.stringify({format:'oc2-position-repair-v1',characterId:'selected',name:'2',anchor:'cinematic7',expectedPosition:{x:1}}));assert.throws(()=>applyPositionRepair(store,file,()=>({...target,x:5})),/changed/);
 }finally{rmSync(dir,{recursive:true,force:true});}
});
const root=new URL('../analysis/raw/showcase-20261110/running-preview/prototype/',import.meta.url);
test('complete immutable server and entry overlay compile and keep normal physics and source UI',{skip:!existsSync(new URL('server.mjs',root))},()=>{
 const server=stageInspectorServer(entryServer(readFileSync(new URL('server.mjs',root),'utf8'),'file:///tmp/trace.mjs'));
 assert(server.includes('mapInspector:inspector?.enabled(ws)===true'));assert(server.includes('ws.motion.move(ws.player,input,.05,ws.world)'));assert(server.includes('if(!ws.lab&&!inspector?.enabled(ws))store.savePosition'));
 const entry=stageInspectorEntry(stageUnstuckEntry(stageFire10Entry(stageSceneEffectsEntry(stageCharacterHotbarEntry(stageCharacterPanelsEntry(stageInsideEntry(stageEntry(readFileSync(new URL('public/explore-map.js',root),'utf8'),{entryUI:true}))))))));
 for(const source of [entry,server]){const checked=spawnSync(process.execPath,['--check','--input-type=module'],{input:source,encoding:'utf8'});assert.equal(checked.status,0,checked.stderr);}
 assert(entry.includes('applySourceCamera(THREE,camera,origin,nativeCamera)'));assert(entry.includes('mapInspector?.keyDown(e)'));assert.throws(()=>stageInspectorServer(server),/anchor differs/);
});
