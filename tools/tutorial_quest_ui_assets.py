"""Recover bounded original task windows for a read-only web adapter.

This exports drawings/text, not a Flash runtime or server task state. All source
bytes and converted artwork must stay in ignored folders. No saves are read.
"""
import argparse, hashlib, io, json, re, struct
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from hud_assets import document, sprite_frames, resolve, _ini_blocks, compose, named_path
from optimized_abc import extract_abc, parse_abc, named_method
from swf_ui_graphics import shape, text_style, display_tree, bounds
from ui_assets import parse_font3
from skill_icons import decode_localized_names
from skill_attachments import decode_ftable
from login_ui_assets import element, digest, matrix, rgba

PINS={
 'MissionDialog':'1ca086266a17e5a12a46bcc6b5a37f1e3714dae6f66772f71256ea8161ca1236',
 'QuestHudNew':'760866b49cbd948764e93183c7ba5cc32605d408e91b7f052f52856837cdfe2c',
 'NPCInteraction':'b2e220f6511c01b692c5173245407d8a1c7577e2d339bcd0760f82e8cbc76493',
 'library':'d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89',
}
METHODS={
 'MissionDialog':['onCreate','subInit','initString','ShowQuestInfo','RePosDetail','RePosReward','onEventQuestOpen','onOkClick','onCloseClick'],
 'QuestHudNew':['onCreate','onHitQuestTrack','CheckEmptyQuest','SetCurQuestItem'],
 'NPCInteraction':['initButton','onBtnClick','updateInteractPos'],
}

def placement(config,measured,stage=(1136,640)):
    """Original WindowManager.resetUI arithmetic, supplied measurement only."""
    if len(measured)!=2 or len(stage)!=2 or any(type(v)not in(int,float)or not __import__('math').isfinite(v)or v<0 for v in [*measured,*stage]):
        raise ValueError('Invalid source window measurement')
    return [float(config['relativeposX'])*(stage[0]-measured[0])+float(config['offsetX']),
            float(config['relativeposY'])*(stage[1]-measured[1])+float(config['offsetY'])]

def recover(extract,output,*,sprite_frames_by_path=None):
 frames_by_path=dict(sprite_frames_by_path or {})
 out=Path(output);out.mkdir(parents=True,exist_ok=True);loaded={};assets={};warnings=[]
 def load(path):
  if path not in loaded:loaded[path]=extract(path)
  return loaded[path]
 docs={}
 for name,sha in PINS.items():
  path='ui/Flash/'+name+'.swf';raw=load(path)
  if digest(raw)!=sha:raise ValueError('Source task drawing changed: '+name)
  docs[name]=document(raw,path,name!='library')
 lib=docs['library'];methods={};constants={}
 for name,names in METHODS.items():
  abc=parse_abc(extract_abc(load(docs[name]['path'])))
  if name=='MissionDialog':
   cls=next(c for c in abc['classes']if c['name']==name);trait=next(t for t in cls['traits']if t['name']=='_Dist1')
   if trait['valueKind']!=3:raise ValueError('Unknown source text inset kind')
   constants['detailInset']=abc['ints'][trait['value']]
  for method in names:
   value=named_method(abc,name,method);methods[name+'.'+method]={k:v for k,v in value.items()if k!='instructions'}
 fonts={}
 for doc in docs.values():
  fonts[doc['path']]={}
  for raw in doc['fonts']:
   cid,flags,lang,n=struct.unpack_from('<HBBB',raw);name=raw[5:5+n].rstrip(b'\0').decode();count=struct.unpack_from('<H',raw,5+n)[0]
   f=parse_font3(raw)if flags&128 and count else {'id':cid,'name':name,'metadataOnly':True}
   fonts[doc['path']][f['id']]=f
 counter=0
 def unique():
  nonlocal counter
  counter+=1;return 'quest-'+str(counter)
 def export_asset(path):
  raw=load(path);im=Image.open(io.BytesIO(raw));im.verify();filename=digest(raw)[:20]+'.png';(out/filename).write_bytes(raw)
  assets[path]={'url':'/assets/source-quest/'+filename,'sourceSHA256':digest(raw),'bytes':len(raw)}
  return assets[path]['url']
 def draw(doc,cid,path,defs,depth=0,frame=None):
  if depth>20:raise ValueError('Quest drawing recursion exceeds bound')
  record=(39,b'')if cid==0 else doc['records'].get(cid)
  if path in ('.MainWin._RewardBoard','.MainWin._GroupBtn.btn_gray'):
   warnings.append({'path':path,'unrestored':'Read-only candidate omits reward subtree and missing local gray-button bitmap; no replacement artwork'})
   return element('g',{'data-source-path':path,'data-source-id':cid,'data-source-file':doc['path']})
  if not record:raise ValueError(f'Missing original quest character: {doc["path"]} {cid} {path}')
  g=element('g',{'data-source-path':path,'data-source-id':cid,'data-source-file':doc['path']})
  if record[0]==39:
   selected=frame or frames_by_path.get(path,1)
   if type(selected)is not int or not 1<=selected<=len(sprite_frames(doc,cid)):
    raise ValueError('Original quest sprite frame unavailable: '+path)
   placements=sprite_frames(doc,cid)[selected-1];active=[]
   for p in placements:
    dd,ii=resolve(doc,p,lib);sub=draw(dd,ii,path+'.'+p.get('name',str(ii)),defs,depth+1);sub.set('transform',matrix(p['matrixTwips']))
    c=p['colorTransform']
    if c['multiply']!=[256]*4 or c['add']!=[0]*4:
     fid=unique();f=element('filter',{'id':fid,'color-interpolation-filters':'sRGB'});v=[]
     for r in range(4):v.extend([c['multiply'][r]/256 if r==j else 0 for j in range(4)]+[c['add'][r]/255])
     f.append(element('feColorMatrix',{'type':'matrix','values':' '.join(map(str,v))}));defs.append(f);sub.set('filter','url(#'+fid+')')
    if 'filters'in p:warnings.append({'path':path,'unrestored':'source Flash text/bitmap filter rasterization','filters':p['filters']})
    if p.get('blendMode',1)not in (0,1):raise ValueError('Unsupported source quest blend mode')
    if 'clipDepth'in p:
     key=unique();clip=element('clipPath',{'id':key,'clipPathUnits':'userSpaceOnUse'})
     # SVG clipPath accepts direct geometry; nested display-list groups are
     # flattened with their exact affine matrices, never replaced by a new box.
     def clipping(node,parent=(1,0,0,1,0,0)):
      local=node.get('transform');m=compose(parent,list(map(float,local[7:-1].split())))if local else parent
      if node.tag.rsplit('}',1)[-1]=='path':
       leaf=ET.fromstring(ET.tostring(node));leaf.set('transform',matrix(m));leaf.set('fill-opacity','1');leaf.set('clip-rule',leaf.get('fill-rule','nonzero'));clip.append(leaf)
      else:
       for child in node:clipping(child,m)
     clipping(sub)
     if not len(clip):raise ValueError('Quest clipping geometry unavailable')
     defs.append(clip);active.append((p['clipDepth'],key));continue
    active=[v for v in active if p['depth']<=v[0]]
    for _,key in active:
     wrap=element('g',{'clip-path':'url(#'+key+')'});wrap.append(sub);sub=wrap
    g.append(sub)
  elif record[0] in (2,22,32,83):
   spec=shape(*record,extended=True)
   def paint(p):
    if p['kind']=='solid':return rgba(p['color']),p['color'][3]/255
    key=unique()
    if p['kind']=='bitmap':
     bid=p['bitmapId'];names=[n for n,v in doc['symbols'].items()if v==bid]
     if len(names)!=1 or Path(names[0]).name!=names[0]:raise ValueError('Quest bitmap namespace missing')
     source='ui/Texture/'+names[0];url=export_asset(source);im=Image.open(io.BytesIO(load(source)));width,height=im.size
     if (width,height)!=doc['bitmaps'][bid]:raise ValueError('Quest atlas dimensions differ')
     node=element('pattern',{'id':key,'patternUnits':'userSpaceOnUse','width':width,'height':height,'patternTransform':matrix(p['matrix'])});node.append(element('image',{'href':url,'width':width,'height':height,'image-rendering':'auto' if p['sourceType']<66 else 'pixelated'}))
    elif p['kind']in ('linear','radial'):
     node=element('linearGradient'if p['kind']=='linear'else'radialGradient',{'id':key,'gradientUnits':'userSpaceOnUse','gradientTransform':matrix(p['matrix']),'spreadMethod':['pad','reflect','repeat'][p['spread']],'color-interpolation':'linearRGB'if p['interpolation']else'sRGB',**({'x1':-16384,'y1':0,'x2':16384,'y2':0}if p['kind']=='linear'else{'cx':0,'cy':0,'r':16384})})
     for stop in p['stops']:node.append(element('stop',{'offset':stop['ratio']/255,'stop-color':rgba(stop['color']),'stop-opacity':stop['color'][3]/255}))
    else:raise ValueError('Unsupported quest paint')
    defs.append(node);return'url(#'+key+')',1
   for f in spec['fills']:
    color,alpha=paint(f['paint']);g.append(element('path',{'d':f['path'],'fill':color,'fill-opacity':alpha,'fill-rule':spec['fillRule']}))
   for line in spec['lines']:
    color,alpha=paint(line['paint']);g.append(element('path',{'d':line['path'],'fill':'none','stroke':color,'stroke-opacity':alpha,'stroke-width':line['width'],'stroke-linecap':['round','butt','square'][line['cap']],'stroke-linejoin':['round','bevel','miter'][line['join']]}))
  elif record[0]==37:
   style=text_style(*record);f=fonts[doc['path']][style['fontId']];x0,x1,y0,y1=[v*20 for v in style['boundsPixels']];left,right,indent=style['marginsPixels'][:3]
   align=style['align'];x=x0+(left+indent)*20 if align==0 else x1-right*20 if align==1 else(x0+x1)/2
   family='EntryDisplay'if'Alegreya'in f['name']else'EntryGothic'if'League'in f['name']else'EntryText'
   metric={'y':y0+style['fontHeight']*f['ascent']/1024}if'ascent'in f else{'y':y0,'dominant-baseline':'text-before-edge'}
   text=element('text',{'x':x,**metric,'font-family':family,'font-size':style['fontHeight']*20,'fill':rgba(style['colorRGBA']),'fill-opacity':style['colorRGBA'][3]/255,'text-anchor':['start','end','middle','start'][align],'data-entry-text':'true','data-font-source':f['name'],'data-entry-bounds':' '.join(map(str,[x0,y0,x1-x0,y1-y0]))})
   text.text=re.sub('<[^>]+>','',style['initialHTML']);g.append(text)
  else:raise ValueError('Unsupported quest display tag '+str(record[0]))
  return g
 windows={};rows=_ini_blocks(load('ui/Config/interface_common_2.ini'))
 fields={
  'MissionDialog':['MainWin.txt_title','MainWin.txt_summ','MainWin.txt_sub_title','MainWin._ScrollPanel.mc_content.txt_detail','MainWin._GroupBtn.btn_ok','MainWin._GroupBtn.btn_gray','MainWin._RewardBoard','MainWin._watermark1','MainWin._detailBar'],
  'QuestHudNew':['m_CurQuestPanel','m_QuestListPanel','m_QuestIconBtn'],
  'NPCInteraction':['interact_'+str(i)for i in range(6)]+['interact_mid'],
 }
 for name,cid,cfg_name in [('MissionDialog',56,'MissionDialog'),('QuestHudNew',152,'QuestHud'),('NPCInteraction',0,'NPCInteraction')]:
  doc=docs[name];config=next(v for v in rows if v.get('name')==cfg_name)
  svg=element('svg',{'viewBox':'0 0 1136 640','preserveAspectRatio':'xMidYMid meet'});defs=element('defs');svg.append(defs)
  wrapper=element('g',{'transform':'scale(0.05)','data-quest-window':name});wrapper.append(draw(doc,cid,'',defs));svg.append(wrapper)
  (out/(name+'.svg')).write_bytes(ET.tostring(svg,encoding='utf-8'))
  p=next((v for v in sprite_frames(doc,0)[0]if v.get('name')=='emptybtn'),None)
  size=[0,0]
  if p:
   dd,ii=resolve(doc,p,lib);box=bounds(display_tree(dd,ii,lib));m=p['matrixPixels'];size=[(box[2]-box[0])/20*m[0],(box[3]-box[1])/20*m[3]]
  elif float(config['relativeposX'])or float(config['relativeposY']):raise ValueError('Source window measurement unavailable')
  windows[name]={'url':'/assets/source-quest/'+name+'.svg','config':config,'sourceRoot':cid,'sourceSHA256':doc['sourceSHA256'],'measuredSize':size,'position':placement(config,size),'fields':{f:named_path(doc,cid,f,lib)for f in fields[name]}}
 english=decode_localized_names(load('tables/String_General_.tbl'),'EN')['values'];chinese=decode_localized_names(load('tables/String_General_zh.tbl'),'SC')['values'];ids={v:k for k,v in english.items()}
 keys=['GENERAL_OK','GENERAL_NOTHING','GENERAL_MISSIONDLG_01','GENERAL_MISSIONDLG_NORMAL_REWARD','GENERAL_MISSIONDLG_CHOOSE_REWARD','GENERAL_QUESTHUD_NOQUEST','GENERAL_QUEST_UNFINISHED','GENERAL_QUEST_CHOOSE_ITEM','GENERAL_QUEST_NO_ENOUGH_LEVEL','GENERAL_QUEST_LIMITED_TIME','GENERAL_QUEST_LACK_ITEM']
 strings={k:{'id':ids[k],'text':chinese[ids[k]]}for k in keys}
 quest=next(r for r in decode_ftable(load('tables/quests.tbl'),'entry')['rows']if r['entry']==202)
 qtext=decode_localized_names(load('tables/String_Quest_zh.tbl'),'SC')['values']
 static={'questId':202,'title':qtext[quest['Title']],'detail':qtext[quest['Details']],'objective':qtext[quest['Objectives']],'provenance':'original-static-table-only','accepted':False,'status':None,'sourceTextIds':{k:quest[k]for k in ['Title','Details','Objectives']}}
 result={'format':'oc2-source-quest-ui-v1','stage':[1136,640],'constants':constants,'windows':windows,'strings':strings,'staticQuest':static,'assets':assets,'methods':methods,'warnings':warnings,
  'boundaries':{'staticDetail':'Read-only host adaptation; no cached status, request, reward or accepted-HUD insertion.','liveDetail':'Requires original query cache + Hero_GetQuestInfoNPC fields from received GS2C data, not this static table.','tracking':'Requires original accepted cache and initialized hero/controller/position; callback Hero_UpdateQuestTrack(type,true).','interaction':'Requires actual target guid, NamePosX/Y, original interaction button list; static spawn is not an interaction response.','rendering':'Source vector/bitmap hierarchy and text metrics; browser text/filter rasterization is not pixel-identical Flash.'},
  'sources':{p:{'bytes':len(b),'sha256':digest(b)}for p,b in loaded.items()}}
 (out/'quest-ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

def main():
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);args=cli.parse_args();root=Path(__file__).resolve().parents[1]
 if not any(args.output.resolve().is_relative_to(root/p)for p in ['analysis/raw','game-data','backups']):cli.error('Original task artwork must remain ignored')
 if args.output.exists():cli.error('Refusing to overwrite an existing candidate')
 source=Sources(args.source);r=recover(source.read,args.output)
 print(json.dumps({'windows':list(r['windows']),'assets':len(r['assets']),'sources':len(r['sources']),'staticQuest':r['staticQuest']['questId'],'accepted':False,'output':str(args.output)},ensure_ascii=False))
if __name__=='__main__':main()
