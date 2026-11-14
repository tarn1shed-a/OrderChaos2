"""Read-only position persistence audit; executes synthetic memory fixtures only.

The tool opens a fixed allowlist of source files, never any character save.
No server is started, no credentials are read, and no reset request is sent.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/character-position-restore-20261114'
REVIEWED=ROOT/'analysis/raw/showcase-20261110/running-preview'
NODE=shutil.which('node')or'/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
sha=lambda raw:hashlib.sha256(raw).hexdigest()

FIXTURE_JS=r'''
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const cfg=JSON.parse(process.argv[1]);
const {trialRoleManager,entryServer}=await import(cfg.entryManager);
const {trialEntryPosition}=await import(cfg.trialEntry);
const hash=value=>createHash('sha256').update(value).digest('hex');
const token='a'.repeat(64),otherToken='b'.repeat(64),target={x:1053.3333333333333,y:-1280,groundY:135.72999572753906};
function fixture(){
 const own={id:'00000000-0000-0000-0000-000000000001',name:'位置夹具',tokenHash:hash(token),positions:{camp:{x:10,y:11,groundY:4},resources:{x:40,y:50,groundY:172}},level:2,xp:60,gold:7,equipment:{hand:'fixture'},inventory:{fixture:9},updatedAt:123};
 const other={...structuredClone(own),id:'00000000-0000-0000-0000-000000000002',tokenHash:hash(otherToken)};
 const calls=[],backups=[],active=new Map(),store={records:new Map([[own.id,own],[other.id,other]]),saveFile:null,dirty:false,savedAt:5,flush(){calls.push('flush');this.dirty=false;this.savedAt=6;}};
 const manager=trialRoleManager(store,active,{entryPosition:()=>({...target}),backupEntry:record=>{calls.push('backup');backups.push(record);}});
 return {own,other,store,active,calls,backups,manager,identity:{characterId:own.id,resumeToken:token,anchor:'cinematic7'}};
}
const f=fixture(),before=structuredClone(f.own),other=structuredClone(f.other),ref=f.own.positions;
const result=f.manager.returnEntry(f.identity);
assert.deepEqual(f.calls,['backup','flush']);assert.deepEqual(f.backups,[before]);assert.deepEqual(f.other,other);
assert.deepEqual(f.own,{...before,positions:{...before.positions,resources:target}});assert.notEqual(f.own.positions,ref);
const returnSuccess={result,onlyResourcesChanged:true,otherRoleUnchanged:true,backupBeforeWrite:true,calls:f.calls,updatedAtUnchanged:f.own.updatedAt===before.updatedAt};
const negatives=[];
for(const mode of ['wrongToken','wrongId','wrongAnchor','active','closing','backupFailure','flushFailure','missingSupport']){
 const x=fixture(),old=structuredClone(x.own),savedAt=x.store.savedAt,dirty=x.store.dirty;let identity={...x.identity};
 if(mode==='wrongToken')identity.resumeToken=otherToken;
 if(mode==='wrongId')identity.characterId=x.other.id;
 if(mode==='wrongAnchor')identity.anchor='unknown';
 if(mode==='active'||mode==='closing')x.active.set(x.own.id,{readyState:mode==='active'?1:2});
 let manager=x.manager;
 if(['backupFailure','missingSupport'].includes(mode))manager=trialRoleManager(x.store,x.active,{entryPosition:()=>mode==='missingSupport'?{...target,groundY:NaN}:{...target},backupEntry:()=>{throw Error('fixture backup failure');}});
 if(mode==='flushFailure')x.store.flush=()=>{throw Error('fixture write failure');};
 let error;try{manager.returnEntry(identity);}catch(e){error=e.message;}
 assert(error);assert.deepEqual(x.own,old);assert.equal(x.store.savedAt,savedAt);assert.equal(x.store.dirty,dirty);
 negatives.push({mode,rejected:true,recordUnchanged:true,error});
}
const supportCalls=[],entry=trialEntryPosition({logical:()=>({x:target.x,y:target.y}),support:(...args)=>{supportCalls.push(args);return target.groundY;}});
const report={returnSuccess,returnNegatives:negatives,entryTarget:{position:entry,supportCalls,scope:'actual web entry helper; logical/support values are fixtures, not original collision execution'},realRoleFilesOpened:false,networkOrResetRequestsSent:false};
if(cfg.reviewed){
 const {CharacterStore}=await import(cfg.store),{walkable}=await import(cfg.world);
 const store=new CharacterStore(null),a=store.resolveCharacter('位置夹具',undefined,undefined,2),b=store.resolveCharacter('位置夹具',undefined,undefined,3);
 const resumed=store.resolveCharacter('请求名不同',a.record.id,a.resumeToken,5);
 assert.equal(resumed.record,a.record);assert.equal(resumed.record.profession,2);assert.equal(resumed.record.name,'位置夹具');
 assert.notEqual(a.record.id,b.record.id);assert.equal(a.record.name,b.record.name);
 report.identity={credentialRestoreIgnoresRequestNameAndProfession:true,duplicateNamesCreateDifferentIds:true,restoredFlag:resumed.restored,scope:'actual CharacterStore(null), fresh synthetic records only'};
 a.record.positions={camp:{x:1,y:2,groundY:4},resources:{x:40,y:50,groundY:172}};
 const saveCases=[];
 for(const [name,player]of [['falling',{x:44,y:55,worldY:120,grounded:false}],['landed',{x:44,y:55,worldY:132,grounded:true}],['swimming',{x:44,y:55,worldY:130,grounded:false,swimming:true}],['nonfiniteHeight',{x:45,y:55,worldY:NaN,grounded:true}]]){
  const old=structuredClone(a.record.positions.resources);store.savePosition(a.record,'resources',player);saveCases.push({name,before:old,after:structuredClone(a.record.positions.resources)});
 }
 assert.equal(saveCases[0].after.groundY,172);assert.equal(saveCases[0].after.x,44);assert.equal(saveCases[1].after.groundY,132);assert.equal(saveCases[2].after.groundY,130);assert.equal(saveCases[3].after.groundY,130);
 store.dirty=false;store.savePosition(a.record,'resources',{x:45,y:55,worldY:130,grounded:true});assert.equal(store.dirty,false);
 report.savePosition={cases:saveCases,unchangedDoesNotTouch:true,campUnchanged:a.record.positions.camp.groundY===4};
 const raw=readFileSync(cfg.server,'utf8'),effective=entryServer(raw,'file:///explicit-no-execution-audit-trace.mjs');
 function between(text,from,to){assert.equal(text.split(from).length,2);const tail=text.split(from)[1];assert.equal(tail.split(to).length,2);return from+tail.split(to)[0];}
 const join=between(effective,'        const position = ws.character.positions[scene];','        room.set(ws.player.id, ws);');
 const closeGuard=between(effective,'      if (ws.character && activeCharacters.get(ws.character.id) === ws) {','      if (room) {');
 const activeGuard="if (activeCharacters.has(identity.record.id)) return reject(ws, '这个角色已在另一个窗口在线，请先退出原窗口');";assert(effective.includes(activeGuard));
 const joined=[];
 for(const spec of [{name:'savedHeight',saved:{x:44,y:55,groundY:172}},{name:'savedNoHeight',saved:{x:44,y:55}},{name:'dead',saved:{x:44,y:55,groundY:172},hp:0},{name:'outsideBounds',saved:{x:-100,y:55,groundY:172}},{name:'legacyHeightConsumer',saved:{x:44,y:55,groundY:172},camera:false},{name:'fresh',saved:null}]){
  const calls=[],record={id:'fixture',name:'位置夹具',hp:spec.hp??100,maxHp:100,positions:spec.saved?{resources:structuredClone(spec.saved)}:{}},activeCharacters=new Map();
  const motion={sourceCameraCPU:spec.camera!==false,step:.5,place(entity){calls.push({method:'place',x:entity.x,y:entity.y});entity.worldY=10;entity.grounded=true;},restoreHeight(entity,height){calls.push({method:'restoreHeight',height});entity.worldY=height;},point:(x,y)=>({x:x*2,z:y*3}),support(...args){calls.push({method:'support',arguments:args});return 170;}};
  const ws={character:record,motion},context={ws,scene:'resources',roomKey:'resources:source-map:FIXTURE',lab:false,world:{width:1280,height:1280,radius:2,obstacles:[],spawn:{x:9,y:8}},sourceWindow:true,index:2,COLORS:['fixture'],COMBAT:{playerCooldownMs:600},syncPlayerStats:()=>{},walkable,activeCharacters};
  vm.runInNewContext(join,context,{timeout:1000});
  joined.push({name:spec.name,player:JSON.parse(JSON.stringify(ws.player)),calls,identityMarkedActive:activeCharacters.get(record.id)===ws});
 }
 assert.deepEqual(joined[0].calls.map(c=>c.method),['place','restoreHeight']);assert.equal(joined[0].player.worldY,172);
 assert.deepEqual(joined[1].calls.map(c=>c.method),['place']);assert.equal(joined[2].player.x,9);assert.equal(joined[3].player.x,9);assert.equal(joined[5].player.x,9);
 assert.deepEqual(joined[4].calls[1],{method:'support',arguments:[88,165,172.5]});
 report.join={cases:joined,scope:'literal effective join placement statements; native collision/restore consumers are explicit recording fixtures, not original physics'};
 const guardCases=[];
 for(const same of [true,false]){
  const id='guard-id',ws={character:{id},player:{x:700,y:800},scene:'resources'},newer={character:{id}},activeCharacters=new Map([[id,same?ws:newer]]),calls=[];
  vm.runInNewContext(closeGuard,{ws,activeCharacters,savePosition:()=>calls.push('savePosition'),store:{flush:()=>calls.push('flush')},closing:false,storageFailure:()=>{throw Error('unexpected');}},{timeout:1000});
  assert.deepEqual(calls,same?['savePosition','flush']:[]);assert.equal(activeCharacters.has(id),!same);guardCases.push({sameSocket:same,calls,identityStillActive:activeCharacters.has(id)});
 }
 const runActive=new Function('activeCharacters','identity','ws','reject',activeGuard);let rejects=0;
 runActive(new Map([['id',{readyState:2,roomId:'OTHER'}]]),{record:{id:'id'}},{},()=>{rejects++;});
 runActive(new Map([['other',{}]]),{record:{id:'id'}},{},()=>{rejects++;});assert.equal(rejects,1);
 report.sessions={closeCases:guardCases,activeGuardRejectsSameIdAcrossRoomAndClosingState:true,otherIdAllowed:true};
 report.sourceSnippets={join,closeGuard,activeGuard};
}
console.log(JSON.stringify(report));
'''


def run_fixtures(reviewed=REVIEWED,*,include_reviewed=True):
    reviewed=Path(reviewed).resolve();manifest=json.loads((ROOT/'tools/local_mvp_runtime.json').read_text())['files']
    files=['prototype/server.mjs','prototype/game/character-store.mjs','prototype/public/world.js','prototype/game/native-window-collision.mjs']
    available=all((reviewed/rel).is_file()for rel in files)
    if include_reviewed and not available:raise FileNotFoundError('Private reviewed source is unavailable; no save is substituted')
    identities={}
    if include_reviewed:
        for rel in files:
            actual=sha((reviewed/rel).read_bytes())
            if actual!=manifest[rel]:raise ValueError('Reviewed static source differs: '+rel)
            identities[str((reviewed/rel).relative_to(ROOT))]=actual
    cfg={'entryManager':(ROOT/'deploy/entry_manage.mjs').as_uri(),'trialEntry':(ROOT/'deploy/tutorial_entry.mjs').as_uri(),'reviewed':include_reviewed,
        'store':(reviewed/'prototype/game/character-store.mjs').as_uri(),'world':(reviewed/'prototype/public/world.js').as_uri(),'server':str(reviewed/'prototype/server.mjs')}
    result=subprocess.run([NODE,'--input-type=module','-e',FIXTURE_JS,'--',json.dumps(cfg)],capture_output=True,text=True)
    if result.returncode:raise RuntimeError(result.stderr)
    report=json.loads(result.stdout);report['reviewedSourceSHA256']=identities
    return report


def recover(output):
    output=Path(output).resolve()
    if not output.is_relative_to(RAW.resolve())or output.exists():raise ValueError('Choose a new ignored position-audit output directory')
    output.mkdir(parents=True);report=run_fixtures()
    own=['deploy/entry_manage.mjs','deploy/tutorial_entry.mjs','deploy/entry_ui.mjs','deploy/entry_read.mjs','deploy/server.mjs','deploy/admin_server.mjs','tools/source_diving.py','tools/source_physics_worker.py','docs/MAP_ENTRY_AND_FLOOR.md']
    report['sourceSHA256']={rel:sha((ROOT/rel).read_bytes())for rel in own}
    report['format']='oc2-character-position-audit-v1'
    report['boundary']='Actual web store/entry methods and selected literal join/close statements on synthetic memory fixtures only. Original EnterMap consumption is separately documented; no native entry/physics run claimed.'
    (output/'evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (output/'SHA256.json').write_text(json.dumps({p.name:sha(p.read_bytes())for p in output.iterdir()if p.is_file()},indent=2)+'\n')
    return report


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args()
    r=recover(args.output);print(json.dumps({'output':str(args.output/'evidence.json'),'realRoleFilesOpened':r['realRoleFilesOpened'],'networkOrResetRequestsSent':False}))
