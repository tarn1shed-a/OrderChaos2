// Same pinned source branches as the frozen Node control; no GUI/server/Flash.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {createOriginalJournalControls}from'./preview/quest_journal_program.mjs';
const root=new URL('../',import.meta.url),args=process.argv.slice(2),cases=[];
let assertions=0;const eq=(a,b)=>{assert.deepEqual(a,b);assertions++;};
await assert.rejects(()=>createOriginalJournalControls('{}'));assertions++;
await assert.rejects(()=>createOriginalJournalControls(null));assertions++;
const oldURL=new URL('tools/ordinary_quest_journal_program.mjs',root),webURL=new URL('tools/preview/quest_journal_program.mjs',root);
let exactBodyParity=false;
if(fs.existsSync(oldURL)){
  const before="  if(typeof sourceJSON!=='string'||createHash('sha256').update(sourceJSON).digest('hex')!==SOURCE)throw TypeError('Pinned private original journal program required');";
  const after="  if(typeof sourceJSON!=='string')throw TypeError('Pinned private original journal program required');\n  if(!globalThis.crypto?.subtle)throw TypeError('WebCrypto SHA-256 required');\n  const digest=await globalThis.crypto.subtle.digest('SHA-256',new TextEncoder().encode(sourceJSON));\n  if(Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,'0')).join('')!==SOURCE)throw TypeError('Pinned private original journal program required');";
  const expected=fs.readFileSync(oldURL,'utf8').replace("import {createHash} from 'node:crypto';\n",'').replace('export function createOriginalJournalControls(','export async function createOriginalJournalControls(').replace(before,after);
  eq(fs.readFileSync(webURL,'utf8'),expected);exactBodyParity=true;
}
const p=new URL('analysis/raw/ordinary-quest-journal-20261116/cpu-v3/source-program-v1.json',root);
const hasPrivate=!args.includes('--public-only')&&fs.existsSync(p);
async function branches(create,source,program){
  const cases=[];
  const fresh=options=>create(source,{rows:[{questId:461},{questId:462}],selectedIndex:0,isPUB:false,paramsStringCallback:true,...options});
  await assert.rejects(()=>fresh({isPUB:undefined}));assertions++;
  await assert.rejects(()=>fresh({paramsStringCallback:undefined}));assertions++;
  await assert.rejects(()=>create(source+' '));assertions++;
  eq(program.msgboxParams.constants.CLK_ST_YES,0);eq(program.msgboxParams.constants.CLK_ST_NO,1);
  eq(program.msgboxParams.resolvedOptionalInputs,['',1,0,0,0]);
  for(const platform of [false,true]){
    const c=await fresh({isPUB:platform}),initial=c.abandon(),a=initial.actions[0];
    eq(a.boundary,'ShowMsg');eq(a.arguments.slice(0,3),['MessageBoxYesNo','Test',5]);
    const params=a.arguments[3];
    eq(params.msg,program.strings.GENERAL_QUESTBOOK_CONFIRM.text);eq(params.msgType,0);
    eq([params.btnYesText,params.btnNoText],[program.strings.GENERAL_OK.text,program.strings.GENERAL_CANCEL.text]);
    eq([params.btnYesType,params.btnNoType,params.btnMidType],[1,1,-1]);eq(params.fullScreenClose,false);
    eq(params.enableBtnSound,true);eq(params.countdown,0);eq(Object.hasOwn(params,'isNeedRestart'),platform);
    eq(initial.actions.filter(x=>x.boundary==='Hero_AbandonQuest'),[]);
    const result=c.messageButton('onOkClick',{enableSound:true,fullScreenClose:false,forwardToBook:true});
    eq(result.shown,false);eq(result.actions.at(-1).arguments,[461]);eq(result.actions.at(-1).boundary,'Hero_AbandonQuest');
    eq(result.actions.find(x=>x.boundary==='MessageBox.OnBtnClick').arguments,[0]);
    cases.push({name:'original-question-and-yes',explicitIsPUB:platform,result});
  }
  for(const button of ['onCancelClick','onFullScreenClick']){
    const c=await fresh();c.abandon();const v=c.messageButton(button,{enableSound:true,fullScreenClose:false,forwardToBook:true});
    eq(v.actions.filter(x=>x.boundary==='Hero_AbandonQuest'),[]);eq(v.shown,button==='onFullScreenClick');
    cases.push({name:button,result:v});
  }
  for(const click of [1,2,3,4,5,6,7,8,9]){
    const c=await fresh();c.abandon();eq(c.confirm(click).actions.filter(x=>x.boundary==='Hero_AbandonQuest'),[]);
  }
  eq((await fresh({selectedIndex:-1})).abandon().actions,[]);
  const absent=await fresh({abandonCallback:false});absent.abandon();eq(absent.confirm(0).actions.filter(x=>x.boundary==='Hero_AbandonQuest'),[]);
  const changed=await fresh();changed.abandon();changed.select(1);eq(changed.confirm(0).actions.at(-1).arguments,[462]);
  cases.push({name:'explicit-confirmation-current-selection-not-normal-modal-reachability',result:changed.inspect()});
  const noParamString=await fresh({paramsStringCallback:false});eq(Object.hasOwn(noParamString.abandon().actions[0].arguments[3],'btnYesText'),false);
  const closing=await fresh();closing.abandon();const close=closing.messageButton('onFullScreenClick',{enableSound:false,fullScreenClose:true,forwardToBook:true});
  eq(close.shown,false);eq(close.actions.at(-1).arguments,[1]);eq(close.actions.filter(x=>x.boundary==='Hero_AbandonQuest'),[]);
  for(const key of ['QuestListHero.onListItemClick','QuestListHero.displayCurrQuest'])eq(program.methods[key].instructions.some(x=>x.args.includes('EventQuestDetail')||x.args.includes('Hero_SendAcceptQuestN')),false);
  return cases;
}
if(hasPrivate){
  const source=fs.readFileSync(p,'utf8'),program=JSON.parse(source);
  cases.push(...await branches(createOriginalJournalControls,source,program));
  if(fs.existsSync(oldURL)){
    const old=(await import(oldURL)).createOriginalJournalControls;
    const original=await branches(async(...args)=>old(...args),source,program);
    eq(cases,original);
  }
}
const report={format:'oc2-original-journal-webcrypto-controls-v1',assertions,sourcePresent:hasPrivate,exactBodyParity,cases,
  browserModuleSHA256:crypto.createHash('sha256').update(fs.readFileSync(webURL)).digest('hex'),
  originalProgramSHA256:hasPrivate?crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'):null,
  asyncHashOnly:true,originalFlashExecuted:false,networkOrUI:false,
  remaining:['Original modal reachability/ShowMsg native window delivery not supplied','Explicit currSel changes are control inputs, not normal GUI actions','No ActionID16 or other process-local handle is transported']};
if(args.includes('--report')){
  const out=new URL('analysis/raw/ordinary-quest-journal-web-20261116/webcrypto-controls-v1.json',root);
  if(fs.existsSync(out))throw Error('Preserve frozen receipt');fs.writeFileSync(out,JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify({assertions,privateOriginalProgram:hasPrivate,exactBodyParity,cases:cases.length,originalFlash:false,networkOrUI:false}));
