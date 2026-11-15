// Additive original-book closure. The existing world file is not overwritten;
// only a reviewed generated delivery gets the authenticated state wiring.
import {readFile}from'node:fs/promises';
import {resolve}from'node:path';
import {validateJournalProfile}from'./quest_journal_state.mjs';
export const JOURNAL_PROFILE='/assets/source-quest-journal/profile.json';
const PREFIX='/assets/source-quest-journal/';
export function stageQuestJournalWorld(source){
  if(typeof source!=='string'||source.includes('createQuestJournal'))throw Error('Unpatched ordinary world source required');
  const replace=(a,b)=>{if(source.split(a).length!==2)throw Error('Original journal delivery anchor differs');source=source.replace(a,b);};
  replace("import {createQuestUI} from '/__delivery/quest_ui.mjs';","import {createQuestUI} from '/__delivery/quest_ui.mjs';\nimport {createQuestJournal} from '/__delivery/quest_journal.mjs';");
  replace('let npcProjection,','let journal;\nlet npcProjection,');
  replace('const blocked=()=>!connected||skills?.isOpen','const blocked=()=>!connected||journal?.isOpen||skills?.isOpen');
  replace('function openEntry(){skills?.disconnect();entry?.open();}','function openEntry(){journal?.invalidate();skills?.disconnect();entry?.open();}');
  replace("$('field-quests').disabled=!connected||profile.quests.every(q=>completed.has(q.id));","$('field-quests').disabled=!connected||(!journal&&profile.quests.every(q=>completed.has(q.id)));");
  replace('  questTracking?.update(state);','  questTracking?.update(state);journal?.update(state);');
  replace('return;skills?.close();stop();','return;skills?.close();journal?.close();stop();');
  replace('questState=null;skills?.disconnect();stop();questUI?.invalidate();','questState=null;journal?.invalidate();skills?.disconnect();stop();questUI?.invalidate();');
  replace('beforeOpen:()=>{pointer=null;questUI?.close()', 'beforeOpen:()=>{pointer=null;journal?.close();questUI?.close()');
  replace('stop();skills?.dispose();socket?.close();','stop();journal?.dispose();skills?.dispose();socket?.close();');
  const anchor="    action:command=>api('action',{command}),onError:error=>note(error.message)});";
  replace(anchor,anchor+`
  if(document.documentElement.dataset.sourceQuestJournal==='1')journal=await createQuestJournal({
    profile:await json('/assets/source-quest-journal/profile.json'),
    readSession:()=>({connected,characterId:identity?.characterId,epoch:generation}),
    readState:async()=>(await api('state')).state,query:async id=>compatibleInfo((await api('query',{questId:id})).info),
    action:command=>api('action',{command}),readTrackedQuest:()=>questTracking?.currentQuestId??null,
    beforeOpen:()=>{pointer=null;skills?.close();stop();void questUI?.close().catch(()=>{});},
    focusGame:()=>canvas.focus({preventScroll:true}),onError:()=>note('任务资料暂不可用，请重新打开。')});`);
  replace("$('field-quests').addEventListener('click',()=>openQuest());","$('field-quests').addEventListener('click',()=>journal?journal.open().catch(()=>note('任务资料暂不可用，请重新打开。')):openQuest());");
  return source;
}
export async function prepareJournalDelivery(root,files,add){
  if(!files[JOURNAL_PROFILE])return false;
  const p=JSON.parse(await readFile(files[JOURNAL_PROFILE].path,'utf8'));validateJournalProfile(p);
  if(p.methods.onQuestItemSet!=='468ff62dcf0b074b95547e80595f058ecc1739de7d9a3b00193bdc1e537e6a1e')throw Error('Original journal index consumer differs');
  const required=url=>{if(!files[url])throw Error('Original journal delivery incomplete: '+url);return files[url];};
  if(p.artURL!==PREFIX+'journal-art.json'||p.programURL!==PREFIX+'source-program.json'||p.frameURL!=='/assets/ui/igm-frame.json'||
    p.programSHA256!=='fb5f7211e4a9353ed025a30e6beb4863276437fd6adfb395ed93d340fba71c7a')throw Error('Original journal references differ');
  if(required(p.programURL).sha256!==p.programSHA256)throw Error('Original journal question program differs');
  if(p.widgetProgramURL!==PREFIX+'widget-program.json'||p.widgetProgramSHA256!=='4b4c88e6cc7edcc7aaee351dbb01533c4e7f9e2f83fbc17821c7990407492171'||required(p.widgetProgramURL).sha256!==p.widgetProgramSHA256)throw Error('Original journal widget program differs');
  const a=JSON.parse(await readFile(required(p.artURL).path,'utf8'));
  if(a.format!=='oc2-original-quest-journal-art-v2'||a.windows.QuestListHero.sourceSHA256!==p.sourceSHA256||a.gaps.length)throw Error('Original journal drawing source differs');
  for(const v of [...Object.values(a.assets),...Object.values(a.windows),...Object.values(a.stateDrawings)]){
    if(typeof v.file!=='string'||!/^[-\w]+\.(?:json|svg|png)$/.test(v.file)||required(PREFIX+v.file).sha256!==v.sha256)throw Error('Original journal payload differs');
  }
  const f=JSON.parse(await readFile(required(p.frameURL).path,'utf8'));
  if(f.sources['ui/Flash/WindowContainerIGM.swf'].sha256!==p.frameSourceSHA256||
    p.message.sourceSHA256!==a.windows.MessageBox.sourceSHA256||p.message.config.isModal!=='1'||p.question.msgType!==0)throw Error('Original journal frame/question differs');
  for(const url of ['/source-ui-svg.js','/assets/ui/chineseDisplay.woff','/assets/ui/chineseText.woff','/assets/ui/leagueGothic.woff','/assets/source-quest-tracking/tracking.json'])required(url);
  for(const v of Object.values(f.assets))required(v.url);
  for(const name of ['quest_journal.mjs','quest_journal_state.mjs'])await add('/__delivery/'+name,resolve(root,'deploy',name),'text/javascript; charset=utf-8');
  await add('/__delivery/quest_journal.css',resolve(root,'deploy/quest_journal.css'),'text/css; charset=utf-8');
  await add('/__delivery/quest_journal_program.mjs',resolve(root,'tools/preview/quest_journal_program.mjs'),'text/javascript; charset=utf-8');
  await add('/__delivery/quest_journal_widgets.mjs',resolve(root,'tools/preview/quest_journal_widgets.mjs'),'text/javascript; charset=utf-8');
  return true;
}
