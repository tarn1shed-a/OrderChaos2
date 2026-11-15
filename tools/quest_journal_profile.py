"""Private original journal art/metrics for the authorized ordinary ledger.

Exports source UI/data contracts, never a character record or approval. The
browser projection is explicitly separate from native protobuf/Flash runtime.
"""
import argparse,hashlib,json,math,shutil,struct
from pathlib import Path
from quest_journal_art import recover
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from hud_assets import document,named_path,resolve,sprite_frames
from swf_ui_graphics import shape,text_style
from swf_morph_start import morph_start
from ui_assets import Bits,tags
from optimized_abc import parse_abc,extract_abc,named_method
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names

ROOT=Path(__file__).resolve().parents[1]
SHA=lambda p:hashlib.sha256(p).hexdigest()
PROGRAM='fb5f7211e4a9353ed025a30e6beb4863276437fd6adfb395ed93d340fba71c7a'
WIDGET_PROGRAM='4b4c88e6cc7edcc7aaee351dbb01533c4e7f9e2f83fbc17821c7990407492171'

def original_bounds(doc,cid,library,depth=0):
 if depth>24:raise ValueError('Original measurement recursion bound')
 rec=(39,b'')if cid==0 else doc['records'].get(cid)
 if not rec:raise ValueError('Original measurement record absent')
 kind,raw=rec
 if kind==37:
  x0,x1,y0,y1=text_style(kind,raw)['boundsPixels'];return[x0*20,y0*20,x1*20,y1*20]
 if kind in(2,22,32,83):
  x0,x1,y0,y1=shape(kind,raw,extended=True)['boundsTwips'];return[x0,y0,x1,y1]
 if kind==46:
  x0,x1,y0,y1=morph_start(kind,raw,ratio=0)['boundsTwips'];return[x0,y0,x1,y1]
 if kind!=39:raise ValueError('Unrecovered source measuring tag')
 points=[]
 for p in sprite_frames(doc,cid)[0]:
  dd,ii=resolve(doc,p,library);b=original_bounds(dd,ii,library,depth+1)
  if b is None:continue
  a,c0,c,d,tx,ty=p['matrixTwips'];x0,y0,x1,y1=b
  points.extend((a*x+c*y+tx,c0*x+d*y+ty)for x,y in[(x0,y0),(x1,y0),(x0,y1),(x1,y1)])
 if not points:return None
 xs,ys=zip(*points);return[min(xs),min(ys),max(xs),max(ys)]

def export_profile(source,output):
 out=Path(output).resolve();art=recover(source,out);s=Sources(source)
 def doc(name):
  raw=s.read('ui/Flash/'+name+'.swf');d=document(raw,'ui/Flash/'+name+'.swf',name!='library')
  b=Bits(raw,8);b.rect()
  for k,a,n in tags(raw,b.pos()+4,len(raw)):
   if k in(46,84):d['records'][struct.unpack_from('<H',raw,a)[0]]=(k,raw[a:a+n])
  return d
 book,lib,message=doc('QuestListHero'),doc('library'),doc('MessageBox')
 def path(p):return named_path(book,99,p,lib)
 def measured(p):
  v=path(p);d=lib if v['leafSWF']==lib['path']else book;b=original_bounds(d,v['leafCharacterId'],lib)
  if b is None:raise ValueError('Empty source measurement')
  # DisplayObject.width/height are in its parent coordinates. Do not fold
  # the containing pane's small authored scale into bounds.height twice.
  m=v['chain'][-1]['matrixPixels'];return{'path':v,'boundsTwips':b,'width':(b[2]-b[0])/20*abs(m[0]),'height':(b[3]-b[1])/20*abs(m[3])}
 panel=measured('panel_content.mc_bounds');steps=measured('m_ScrollPanel2.mc_bounds')
 panel_path=path('panel_content');reward_path=path('reward_group')
 if any(len(p['chain'])!=1 or p['matrixPixels'][1]or p['matrixPixels'][2]or p['matrixPixels'][0]<=0 or p['matrixPixels'][3]<=0 for p in [panel_path,reward_path]):raise ValueError('Retrace original panel coordinate frame')
 mask1=math.floor(panel['height']);mask2=math.floor(reward_path['matrixPixels'][5]-panel_path['matrixPixels'][5]-2)
 if mask1<=0 or mask2<=mask1:raise ValueError('Original text mask dimensions differ')
 abc=parse_abc(extract_abc(s.read(book['path'])));methods={}
 for name in ['getQuestList','onQuestItemSet','displayCurrQuest','onRewardItemSet','foldText','stretchText','onTextStretchHitzoneClick','onTextStretchDownHitzoneClick','UpdateSelAll','onAbandon','MessageBoxYesNo']:
  m=named_method(abc,'QuestListHero',name);methods[name]=m['codeSHA256']
 stretch=named_method(abc,'QuestListHero','stretchText');separators=[v['args'][0]for v in stretch['instructions']if v['op']=='pushstring']
 if separators!=['\n--------------------------------------------------------\n']:raise ValueError('Original detail separator changed')
 q=next(r for r in decode_ftable(s.read('tables/quests.tbl'),'entry')['rows']if r['entry']==461)
 rows=sorted([r for r in decode_ftable(s.read('tables/quest_objective.tbl'),'id')['rows']if r['quest_id']==461],key=lambda r:r['step'])
 if(q['questlevel'],q['MinLevel'],q['Type'])!=(2,0,2)or[(r['obj_type'],r['value'])for r in rows]!=[(2,4),(6,0)]:raise ValueError('Original ordinary journal scope changed')
 names=decode_localized_names(s.read('tables/String_Quest_zh.tbl'),'SC')['values']
 program_file=ROOT/'analysis/raw/ordinary-quest-journal-20261116/cpu-v3/source-program-v1.json';program=program_file.read_bytes()
 if SHA(program)!=PROGRAM:raise ValueError('Original question program changed')
 (out/'source-program.json').write_bytes(program)
 widgets=(ROOT/'analysis/raw/ordinary-quest-journal-widgets-20261116/source-v1/source-program.json').read_bytes()
 if SHA(widgets)!=WIDGET_PROGRAM:raise ValueError('Original journal widget program changed')
 (out/'widget-program.json').write_bytes(widgets)
 native_file=ROOT/'analysis/raw/ordinary-quest-book-bridge-20261116/cpu-final-v1/native-v1.json'
 native=json.loads(native_file.read_text());question=native['messageCases'][0]['returnedProperties']
 if question['msgType']!=0 or question['fullScreenClose']is not False or question['Icon']!='ui/icons/userinterface/questiontexticon.png':raise ValueError('Original question contract differs')
 frame_raw=s.read('ui/Flash/WindowContainerIGM.swf');frame_doc=document(frame_raw,'ui/Flash/WindowContainerIGM.swf');font_names={}
 for raw in frame_doc['fonts']:
  cid,flags,lang,n=struct.unpack_from('<HBBB',raw);font_names[cid]=raw[5:5+n].rstrip(b'\0').decode()
 frame_font=font_names[6]
 p={'format':'oc2-original-ordinary-journal-v1','questId':461,'mapId':1,'sourceSHA256':book['sourceSHA256'],'methods':methods,
  'displayLevel':q['questlevel'],'questType':q['Type'],'sourceMinLevel':q['MinLevel'],
  'steps':[{'sourceType':r['obj_type'],'total':r['value'],'text':names[r['text']],
    'icon':'ui/icons/quest/'+('task_collect.png'if r['obj_type']==2 else'task_talk.png')}for r in rows],
  'reward':{'id':20028,'count':1,'icon':'ui/icons/item/red_skull_plan.png','slotType':9,'quality':0,
    'provenance':'original same-registry GetActionIDInfo type9 control; no stable ActionID copied'},
  'artURL':'/assets/source-quest-journal/journal-art.json','frameURL':'/assets/ui/igm-frame.json',
  'frameSourceSHA256':SHA(frame_raw),'frameTitleFontName':frame_font,
  'programURL':'/assets/source-quest-journal/source-program.json','programSHA256':PROGRAM,
  'widgetProgramURL':'/assets/source-quest-journal/widget-program.json','widgetProgramSHA256':WIDGET_PROGRAM,
  'question':{k:question[k]for k in ['msg','msgType','btnYesText','btnNoText','Icon','fullScreenClose','enableBtnSound']},
  'nativeQuestionControlSHA256':SHA(native_file.read_bytes()),
  'text':{'maskHeight1':mask1,'maskHeight2':mask2,'detailSeparator':separators[0],'stretchExtraHeight':40,'panel':panel,'steps':steps},
  'message':{'sourceSHA256':message['sourceSHA256'],'config':art['windows']['MessageBox']['config'],
    'authoredBoundsTwips':original_bounds(message,0,lib),'measurement':'source authored first-frame geometry/edit-text rectangles, not initialized original Flash root',
    'textAndInput':'browser host; original movie/modal reachability remains unproven'},
  'boundaries':['Only actual compatible accepted state can supply a displayed task.','No original server receive/approve/learn rule or stable native ActionID is fabricated.','Source static bounds and browser text/scroll/input are explicit host measurements; pixel-identical Flash is not claimed.','Unavailable original map callback is disabled; no new map screen or pathfinding is designed.','Unnamed CItemList.symCurrSel is not assigned to an anonymous source object.']}
 (out/'profile.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n');return p

if __name__=='__main__':
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();p=export_profile(a.source,a.output)
 print(json.dumps({'output':str(a.output),'questId':p['questId'],'maskHeights':[p['text']['maskHeight1'],p['text']['maskHeight2']],'characterOrApprovalCreated':False}))
