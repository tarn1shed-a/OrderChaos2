"""Read-only journal source/data mapping audit. No DOM/server/save execution."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
AREA=ROOT/'analysis/raw/ordinary-quest-journal-render-audit-20261116'
SHA=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()


def compatible_views(ordinary,profile):
    node=shutil.which('node')or'/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
    script="""
import {OrdinaryQuestLedger}from'./deploy/ordinary_quests.mjs';
import {journalRows,journalDetail}from'./deploy/quest_journal_state.mjs';
let text='';for await(const data of process.stdin)text+=data;
const {ordinary,profile}=JSON.parse(text),ledger=new OrdinaryQuestLedger(ordinary,{clock:()=>0,saveFile:null,write:null});
const q=ordinary.quests.find(q=>q.id===461),actor=ordinary.actors.find(a=>a.id===q.startActor),id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
const context={characterId:id,mapId:1,level:0,alive:true,inspector:false,position:actor.position},outputs={};
const inspect=()=>{const state=ledger.snapshot(id),info=ledger.query(context,461);return{state,info,rows:journalRows(profile,state),detail:state.quests.length?journalDetail(profile,state,info,461):null};};
const act=(type,extra={})=>ledger.act(context,{type,questId:461,revision:ledger.snapshot(id).revision,...extra});
outputs.empty=inspect();act('accept');
for(let i=0;i<4;i++){const object=ordinary.objects.find(o=>o.id===q.collect.objectIds[i]);context.position=object.position;act('collect',{objectId:object.id});if(i===0)outputs.collected=inspect();}
context.position=actor.position;outputs.ready=inspect();act('complete');outputs.completedEmpty=inspect();
console.log(JSON.stringify({outputs,scope:'existing compatible461 ledger, isolated in-memory fixture; no server/save/account',saveFile:ledger.saveFile,writeCallback:ledger.write,realOriginalApproval:false}));
"""
    r=subprocess.run([node,'--input-type=module','-e',script],cwd=ROOT,input=json.dumps({'ordinary':ordinary,'profile':profile}),capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr)
    return json.loads(r.stdout)


def audit(profile_path,*,public=False):
    renderer=ROOT/'deploy/quest_journal.mjs';builder=ROOT/'tools/quest_journal_profile.py'
    public_inputs={name:{'path':str(path.relative_to(ROOT)),'sha256':SHA(path)}for name,path in {
      'renderer':renderer,'profileBuilder':builder,'compatibleLedger':ROOT/'deploy/ordinary_quests.mjs',
      'journalState':ROOT/'deploy/quest_journal_state.mjs','stylesheet':ROOT/'deploy/quest_journal.css'}.items()}
    if public:return{'format':'oc2-journal-render-audit-v1','publicInputs':public_inputs,'privateSourceRead':False,'privateChecksSkipped':True,'noUIServiceOrSave':True}
    from optimized_abc import parse_abc,extract_abc,named_method
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    source=Sources(DEFAULT_SOURCE);raw=source.read('ui/Flash/QuestListHero.swf')
    if hashlib.sha256(raw).hexdigest()!='bd5c5a2d392dd63b872104148a74e075f8ec05c887a246015490ed16c95bf851':raise ValueError('Original journal differs')
    abc=parse_abc(extract_abc(raw));methods={n:named_method(abc,'QuestListHero',n)for n in ['onQuestItemSet','initString','SwitchRewardLeftRightBtn']}
    original=ROOT/'analysis/raw/ordinary-quest-journal-20261116/cpu-v3/source-program-v1.json'
    reward_path=ROOT/'analysis/raw/ordinary-quest-reward-slot-20261116/cpu-final-v3/program.json'
    widget_path=ROOT/'analysis/raw/ordinary-quest-journal-widgets-20261116/source-v1/source-program.json'
    native_path=ROOT/'analysis/raw/ordinary-quest-book-bridge-20261116/cpu-final-v1/native-v1.json'
    state_path=ROOT/'analysis/raw/ordinary-quest-book-state-20261116/cpu-final-v1/native-v1.json'
    ordinary_path=ROOT/'analysis/raw/ordinary-quest-journal-art-20261116/existing-quest-profile.json'
    svg_path=ROOT/'analysis/raw/ordinary-quest-journal-art-20261116/export-v4/QuestListHero.svg'
    native=json.loads(native_path.read_text());native_state=json.loads(state_path.read_text());profile=json.loads(profile_path.read_text());ordinary=json.loads(ordinary_path.read_text())
    program=json.loads(original.read_text());reward_program=json.loads(reward_path.read_text());widget_program=json.loads(widget_path.read_text())
    code=renderer.read_text();compact=''.join(code.split());svg=ET.fromstring(svg_path.read_bytes())
    checks=[]
    def check(name,value,**evidence):
        checks.append({'name':name,'passed':bool(value),**evidence})
    def contains(text):return ''.join(text.split())in compact
    def text_fill(path):
        n=next(n for n in svg.iter()if n.get('data-source-path')==path)
        return next(n.get('fill')for n in n.iter()if n.get('data-entry-text')is not None)
    views=compatible_views(ordinary,profile);out=views['outputs'];q=ordinary['quests'][0]
    source_accepted=native['bookCases']['accepted']['book']['properties'];source_ready=native['bookCases']['ready']['book']['properties']
    for mode in ['collected','ready']:
        dto=source_accepted if mode=='collected'else source_ready;d=out[mode]['detail']
        check(mode+' original full title/objective/detail retained',all(d[k.lower()]==dto[k]for k in ['Title','Objective','Detail']),sourceNativeCase='accepted'if mode=='collected'else'ready',originalChars={k:len(dto[k])for k in ['Title','Objective','Detail']})
        check(mode+' original numeric/item reward amounts retained',d['rewards']=={'money':9,'xp':512,'favor':5,'items':[{'id':20028,'count':1,'icon':'ui/icons/item/red_skull_plan.png','quality':0,'slotType':9,'nativeActionID':None}]})
    check('collected compatible actual1/4 maps original collect objective',out['collected']['detail']['step']['current']==1 and out['collected']['detail']['step']['total']==4 and out['collected']['detail']['step']['sourceType']==2)
    check('ready compatible actual4/4 maps original no-ratio talk objective',out['ready']['detail']['step']['sourceType']==6 and out['ready']['detail']['step']['total']==0 and source_ready['stepSubHasPb0']is False)
    for mode in ['empty','completedEmpty']:check(mode+' contains no accepted rows/detail',out[mode]['rows']==[] and out[mode]['detail']is None)
    check('renderer formats same source level2 title and source normal header',contains("'['+d.displayLevel+'] '+d.title")and contains("word('GENERAL_QUESTBOOK_NORMAL')")and all(out[m]['detail']['displayLevel']==2 for m in ['collected','ready']))
    check('collected/ready icon paths use original4/9 consumer mapping',contains("d.status===9?'ui/icons/head_obj/quest_complete.png':'ui/icons/head_obj/quest_unfinished.png'"))
    check('collected source white text and ready original authored green retained',contains("d.step.sourceType===2?\"<font color='#FFFFFF'>\"+d.step.text+'</font>':d.step.text")and source_accepted['stepSubText0']=="<font color='#FFFFFF'>"+out['collected']['detail']['step']['text']+'</font>'and source_ready['stepSubText0']==out['ready']['detail']['step']['text']and text_fill('.m_ScrollPanel2.mc_content.m_QuestStep0.m_StepSubText')=='rgb(64,237,31)',originalAuthoredReadyFill=text_fill('.m_ScrollPanel2.mc_content.m_QuestStep0.m_StepSubText'))
    check('renderer goal ratio only visible for collect and writes current/total',contains("show(screen,p+'.m_StepSubRatio',d.step.total>0)")and contains("d.step.current+'/'+d.step.total"))
    check('original text prompt key used for empty list',contains("text(screen,'.m_TextPrompt',word('GENERAL_QUESTHUD_NOQUEST'))")and any(i['args']==['GENERAL_QUESTHUD_NOQUEST']for i in methods['initString']['instructions']))
    check('renderer hides content/reward list when detail empty',contains("const has=!!view.detail")and contains("show(screen,p,has)")and contains("show(screen,'.m_TextPrompt',!has)"))
    check('current compatible row index1 fixes original number/backplate omission',all(out[m]['detail'].get('displayIndex')==native_state['state']['beforeView']['properties']['questIndex0']==1 for m in ['collected','ready'])and contains("text(screen,'.panel_list.item_1.iconWithIndex.indexQuest',d.displayIndex)")and contains("show(screen,'.panel_list.item_1.iconWithIndex.indexBack',d.displayIndex>0)"),originalIndex=1,projection='compatible accepted list ordinal, not general native index algorithm')
    check('source onQuestItemSet pin is exported by current builder',"'onQuestItemSet'"in builder.read_text(),expectedSHA256=methods['onQuestItemSet']['codeSHA256'],profileHasPin=profile['methods'].get('onQuestItemSet'))
    source_method_pins={name:program['methods']['QuestListHero.'+name]['codeSHA256']for name in ['getQuestList','displayCurrQuest']}
    source_method_pins['onRewardItemSet']=reward_program['methods']['QuestListHero.onRewardItemSet#1']['codeSHA256']
    source_method_pins.update({name:widget_program['methods']['QuestListHero.'+name+'#1']['codeSHA256']for name in ['foldText','stretchText']})
    check('all five requested original consumer hashes match audited profile',all(profile['methods'].get(name)==value for name,value in source_method_pins.items()),sourceMethodSHA256=source_method_pins)
    check('one fixed reward page and no optional reward count',contains('{pages:1}')and all(out[m]['info']['NumItem']==1 and out[m]['info']['NumItemOp']==0 for m in ['collected','ready']))
    check('fixed reward label and three positive numeric icons retained',contains("word('GENERAL_QUESTBOOK_REWARD_BIXUAN')")and contains("[['money','ui/icons/item/gold_coin.png'],['xp','ui/icons/item/exp.png'],['favor','ui/icons/userinterface/fever_coin.png']]"))
    check('single reward stack hidden and selected/lock/gem disabled fields cleared',contains('!!item&&item.count>1')and contains("['SelectedMark','_GemIcon','IsLocked','NewPromo','Disable']"))
    check('fold/stretch uses pinned pure widget input and original separator',contains('widgets.bodyLayout({expanded,summary:d.objective,detail:d.detail,textHeight:')and contains('d.objective+profile.text.detailSeparator+d.detail')and profile['text']['detailSeparator']=='\n--------------------------------------------------------\n')
    check('body ratio never fed back from rounded display thumb',contains('ratio=bodyText.scrollTop/Math.max(1,bodyText.scrollHeight-bodyText.clientHeight)')and'actualRatio'not in code)
    check('no filesystem ledger path or write callback used',views['saveFile']is None and views['writeCallback']is None)
    return{'format':'oc2-journal-render-audit-v1','publicInputs':public_inputs,
      'privateInputs':{str(p.relative_to(ROOT)):SHA(p)for p in [profile_path,ordinary_path,original,reward_path,widget_path,native_path,state_path,svg_path]},
      'checks':checks,'passed':sum(v['passed']for v in checks),'failed':sum(not v['passed']for v in checks),'sourceMethods':methods,'originalPinnedProgramMethods':{k:program['methods'][k]['codeSHA256']for k in ['QuestListHero.getQuestList','QuestListHero.displayCurrQuest']},
      'views':views,'sourceProofs':source.proofs,'originalFieldColors':{'collect':'#FFFFFF','readySourceAuthoredFill':text_fill('.m_ScrollPanel2.mc_content.m_QuestStep0.m_StepSubText'),'listTitleAuthoredFill':text_fill('.panel_list.item_1.btnScrollText.m_TheText')},
      'bounds':['Static source/renderer assignment audit, not DOM, browser or Flash execution','Actual compatible ledger exercised only in a fresh in-memory fixture; no file/save/account/server','Original source frame size/text metrics, animation and modality remain separate boundaries','Only current authorized461 is audited; no208/202 approval or all-task index algorithm'],
      'knownScopeLimits':['Parent input priorStepBarVisible=false is scoped to this one short461 objective; no general overflow inference','Native IsNew/isNew case gap is not silently repaired into a badge','Map/tracking input callbacks remain disabled instead of invented'],
      'profileOnQuestItemSetPinStatus':'Present'if profile['methods'].get('onQuestItemSet')==methods['onQuestItemSet']['codeSHA256']else'Input profile predates added method pin; current builder exports it. No frozen profile rewritten.',
      'noSharedCodeBrowserServiceSaveOrDeployment':True}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',type=Path,default=ROOT/'analysis/raw/ordinary-quest-journal-live-20261116/assets-v5/profile.json');p.add_argument('--output',type=Path,default=AREA/'audit-v1.json');p.add_argument('--public-only',action='store_true');a=p.parse_args()
    if a.output.exists():raise ValueError('Preserve prior audit receipt')
    report=audit(a.profile,public=a.public_only);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'output':str(a.output),'sha256':SHA(a.output),'passed':report.get('passed'),'failed':report.get('failed'),'sourceRead':not a.public_only},ensure_ascii=False))
    if report.get('failed'):raise SystemExit(1)
