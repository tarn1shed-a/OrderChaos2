// Inventory-only fixtures, never original PNG/SWF recovery or a gameplay test.
import test from'node:test';import assert from'node:assert/strict';
import{mkdtemp,writeFile,rm,readFile}from'node:fs/promises';import{tmpdir}from'node:os';import{join}from'node:path';
import{prepareJournalDelivery,stageQuestJournalWorld,JOURNAL_PROFILE}from'../deploy/quest_journal_delivery.mjs';
const prefix='/assets/source-quest-journal/',sha='1'.repeat(64),source='bd5c5a2d392dd63b872104148a74e075f8ec05c887a246015490ed16c95bf851';
async function fixture(fn){
 const root=await mkdtemp(join(tmpdir(),'oc2-journal-gate-')),files={},added=[];
 async function put(url,v,digest=sha){const path=join(root,String(Object.keys(files).length)+'.json');await writeFile(path,JSON.stringify(v));files[url]={path,sha256:digest};}
 const p={format:'oc2-original-ordinary-journal-v1',questId:461,mapId:1,displayLevel:2,questType:2,sourceSHA256:source,
 methods:{getQuestList:'4a61cda6e462fc9916af21bb18b4277491eb015ef5c5c14e9d4dd4260c227f13',onQuestItemSet:'468ff62dcf0b074b95547e80595f058ecc1739de7d9a3b00193bdc1e537e6a1e'},
 steps:[{sourceType:2,total:4,text:'fixture',icon:'ui/icons/quest/task_collect.png'},{sourceType:6,total:0,text:'fixture',icon:'ui/icons/quest/task_talk.png'}],
 reward:{id:20028,count:1,icon:'ui/icons/item/red_skull_plan.png',slotType:9,quality:0},artURL:prefix+'journal-art.json',frameURL:'/assets/ui/igm-frame.json',frameSourceSHA256:sha,
 programURL:prefix+'source-program.json',programSHA256:'fb5f7211e4a9353ed025a30e6beb4863276437fd6adfb395ed93d340fba71c7a',
 widgetProgramURL:prefix+'widget-program.json',widgetProgramSHA256:'4b4c88e6cc7edcc7aaee351dbb01533c4e7f9e2f83fbc17821c7990407492171',message:{sourceSHA256:sha,config:{isModal:'1'}},question:{msgType:0}};
 const art={format:'oc2-original-quest-journal-art-v2',gaps:[],assets:{},stateDrawings:{},windows:{QuestListHero:{file:'book.svg',sha256:sha,sourceSHA256:source},MessageBox:{file:'box.svg',sha256:sha,sourceSHA256:sha}}};
 await put(JOURNAL_PROFILE,p);await put(p.artURL,art);await put(p.frameURL,{sources:{'ui/Flash/WindowContainerIGM.swf':{sha256:sha}},assets:{}});
 for(const name of ['book.svg','box.svg'])files[prefix+name]={sha256:sha};
 files[p.programURL]={sha256:p.programSHA256};files[p.widgetProgramURL]={sha256:p.widgetProgramSHA256};
 for(const url of ['/source-ui-svg.js','/assets/ui/chineseDisplay.woff','/assets/ui/chineseText.woff','/assets/ui/leagueGothic.woff','/assets/source-quest-tracking/tracking.json'])files[url]={sha256:sha};
 try{await fn({root,files,p,art,added,add:async(...v)=>added.push(v),save:async()=>{await writeFile(files[JOURNAL_PROFILE].path,JSON.stringify(p));await writeFile(files[p.artURL].path,JSON.stringify(art));}});}finally{await rm(root,{recursive:true,force:true});}
}
test('old bundles omit the book and register no new browser modules',async()=>{let added=0;assert.equal(await prepareJournalDelivery('/missing',{},()=>added++),false);assert.equal(added,0);});
test('complete inventory adds the two state/render modules, stylesheet and both source helpers',async()=>fixture(async({root,files,add,added})=>{assert.equal(await prepareJournalDelivery(root,files,add),true);assert.deepEqual(added.map(v=>v[0]),['/__delivery/quest_journal.mjs','/__delivery/quest_journal_state.mjs','/__delivery/quest_journal.css','/__delivery/quest_journal_program.mjs','/__delivery/quest_journal_widgets.mjs']);}));
test('partial or altered source dependencies fail before any module registration',async()=>{
 for(const bad of ['widget','program','drawing','frame','font','tracking','foreign','quest','gap'])await fixture(async({root,files,p,art,save,add,added})=>{
  if(bad==='widget')delete files[p.widgetProgramURL];if(bad==='program')files[p.programURL].sha256='0'.repeat(64);
  if(bad==='drawing')files[prefix+'book.svg'].sha256='0'.repeat(64);if(bad==='frame')p.frameSourceSHA256='0'.repeat(64);
  if(bad==='font')delete files['/assets/ui/chineseText.woff'];if(bad==='tracking')delete files['/assets/source-quest-tracking/tracking.json'];
  if(bad==='foreign')p.widgetProgramURL='https://external.invalid/widgets';if(bad==='quest')p.questId=208;if(bad==='gap')art.gaps=['unknown source'];
  await save();await assert.rejects(prepareJournalDelivery(root,files,add));assert.deepEqual(added,[]);
 });
});
test('generated world wires authenticated state and teardown without changing the source file',async()=>{
 const file=new URL('../deploy/quest_world.mjs',import.meta.url),source=await readFile(file,'utf8'),staged=stageQuestJournalWorld(source);
 assert.equal(await readFile(file,'utf8'),source);assert.ok(staged.includes('journal?.dispose()'));assert.ok(staged.includes('characterId:identity?.characterId,epoch:generation'));
 assert.ok(staged.includes('journal?.update(state)'));assert.ok(staged.includes('journal?.invalidate()'));assert.ok(staged.includes('journal?.isOpen'));
 assert.throws(()=>stageQuestJournalWorld(staged));assert.throws(()=>stageQuestJournalWorld('unexpected world'));
});
