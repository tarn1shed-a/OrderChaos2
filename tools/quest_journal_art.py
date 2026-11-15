"""Read original accepted-book/MessageBox artwork into a private SVG candidate.

No quest state, character store, network, new art or replacement UI is created.
Unsupported morphs are named gaps, never silently replaced with rectangles.
"""
import argparse, hashlib, io, json, re, struct
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image
from hud_assets import document, sprite_frames, resolve, compose, named_path, _ini_blocks
from swf_ui_graphics import shape, text_style
from optimized_abc import parse_abc, extract_abc, extract_named_abc, named_method, disassemble
from ui_assets import parse_font3, tags, Bits
from login_ui_assets import element, matrix, rgba
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from skill_icons import decode_localized_names
from swf_morph_start import morph_start

ROOT=Path(__file__).resolve().parents[1]
PINS={
 'QuestListHero':'bd5c5a2d392dd63b872104148a74e075f8ec05c887a246015490ed16c95bf851',
 'MessageBox':'a4e85f3e7677caf292ab0f5d404f153d46d4886220c078e3667b568893b5e9c0',
 'library':'d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89',
}
BASE='/assets/source-quest-journal/'
SHA=lambda value:hashlib.sha256(value).hexdigest()

def recover(source, output):
 out=Path(output).resolve()
 if not out.is_relative_to(ROOT/'analysis/raw') or out.exists():
  raise ValueError('Use a new ignored artwork directory')
 out.mkdir(parents=True);s=Sources(source);loaded={};docs={};fonts={};selections={}
 def load(path):
  if path not in loaded:
   if path=='ui/icons/item/gold_coin.png':
    # Reuse the already executed original UI registration/merge/name lookup;
    # this is the same Common Icon consumer, not an arbitrary pack preference.
    from resource_packs import read_entry
    receipt=ROOT/'analysis/raw/tutorial-npc-mission-resources-20261115/selection-v3.json'
    proof=json.loads(receipt.read_text());row=proof['lookups'][0]['selected']
    if row['member']!=path or row['pack']!='ui_icons_upd14.bin' or not row['nativeAliasSelectorExecuted'] or not proof['scope']['nativeUIRegistrationMergeSortLookupExecuted']:
     raise ValueError('Original UI icon selection unavailable')
    value=read_entry(row['entry'],source)
    if SHA(value)!=row['decodedHostBytes']['sha256']:raise ValueError('Selected original UI icon changed')
    loaded[path]=value;selections[path]={'receiptSHA256':SHA(receipt.read_bytes()),'pack':row['pack'],'scope':'original UI group, cold original pack set; no hot external cache claim'}
   else:loaded[path]=s.read(path)
  return loaded[path]
 for name,pin in PINS.items():
  path='ui/Flash/'+name+'.swf';raw=load(path)
  if SHA(raw)!=pin:raise ValueError('Original drawing source differs: '+name)
  doc=docs[name]=document(raw,path,name!='library');fonts[path]={}
  # Keep the original morph record kind as a gap rather than misreporting it
  # as an absent source asset (the older artwork reader inventories no46).
  data=b'FWS'+raw[3:8]+__import__('zlib').decompress(raw[8:]) if raw[:3]==b'CWS' else raw
  header=Bits(data,8);header.rect()
  for kind,at,size in tags(data,header.pos()+4,len(data)):
   if kind in (46,84):doc['records'][struct.unpack_from('<H',data,at)[0]]=(kind,data[at:at+size])
  for rawfont in doc['fonts']:
   cid,flags,lang,n=struct.unpack_from('<HBBB',rawfont);namefont=rawfont[5:5+n].rstrip(b'\0').decode()
   count=struct.unpack_from('<H',rawfont,5+n)[0]
   fonts[path][cid]=parse_font3(rawfont) if flags&128 and count else {'id':cid,'name':namefont,'metadataOnly':True}
 lib=docs['library'];assets={};gaps=[];filters=[];serial=0
 def unique():
  nonlocal serial
  serial+=1;return 'journal-'+str(serial)
 def png(path):
  if path not in assets:
   raw=load(path);image=Image.open(io.BytesIO(raw));image.verify();name=SHA(raw)+'.png';(out/name).write_bytes(raw)
   assets[path]={'file':name,'sha256':SHA(raw),'bytes':len(raw),'size':list(image.size)}
  return BASE+assets[path]['file']
 def draw(doc,cid,path,defs,depth=0,ratio=0,frame=1):
  if depth>24:raise ValueError('Original drawing recursion exceeds bound')
  rec=(39,b'') if cid==0 else doc['records'].get(cid)
  if not rec:raise ValueError('Original drawing record missing: '+str((doc['path'],cid,path)))
  kind,raw=rec;node=element('g',{'data-source-path':path,'data-source-id':cid,'data-source-file':doc['path']})
  if kind==46:
   spec=morph_start(kind,raw,ratio=ratio)
   node.set('data-source-morph-ratio','0')
   for p in spec['fills']:
    if p['paint']['kind']!='solid':raise ValueError('Original morph fill differs')
    color=p['paint']['color'];node.append(element('path',{'d':p['path'],'fill':rgba(color),'fill-opacity':color[3]/255,'fill-rule':spec['fillRule']}))
   for p in spec['lines']:
    color=p['paint']['color'];node.append(element('path',{'d':p['path'],'fill':'none','stroke':rgba(color),'stroke-opacity':color[3]/255,'stroke-width':p['width']}))
   return node
  if kind==84:
   gaps.append({'path':path,'kind':kind,'id':cid,'file':doc['path'],'reason':'Original morph record exists; ratio/cooldown consumer not recovered here'})
   node.set('data-unrestored','original-morph-ratio');return node
  if kind==39:
   masks=[]
   frames=sprite_frames(doc,cid)
   if type(frame)is not int or not 1<=frame<=len(frames):raise ValueError('Original frame outside timeline: '+path)
   node.set('data-source-frame',str(frame))
   for p in frames[frame-1]:
    dd,ii=resolve(doc,p,lib);child=draw(dd,ii,path+'.'+p.get('name',str(ii)),defs,depth+1,p.get('ratio',0))
    child.set('transform',matrix(p['matrixTwips']));child.set('data-source-depth',str(p['depth']))
    ct=p['colorTransform']
    if ct!={'multiply':[256]*4,'add':[0]*4}:
     key=unique();f=element('filter',{'id':key,'color-interpolation-filters':'sRGB'});v=[]
     for r in range(4):v.extend([ct['multiply'][r]/256 if r==j else 0 for j in range(4)]+[ct['add'][r]/255])
     f.append(element('feColorMatrix',{'type':'matrix','values':' '.join(map(str,v))}));defs.append(f);child.set('filter','url(#'+key+')')
    if p.get('filters'):filters.append({'path':path,'filters':p['filters'],'renderedAsFlashFilter':False})
    if p.get('blendMode',1) not in (0,1):raise ValueError('Unrecovered source blend mode')
    if 'clipDepth' in p:
     key=unique();clip=element('clipPath',{'id':key,'clipPathUnits':'userSpaceOnUse'})
     def flatten(n,parent=(1,0,0,1,0,0)):
      local=n.get('transform');m=compose(parent,list(map(float,local[7:-1].split()))) if local else parent
      if n.tag.rsplit('}',1)[-1]=='path':
       leaf=ET.fromstring(ET.tostring(n));leaf.set('transform',matrix(m));leaf.set('fill-opacity','1');leaf.set('clip-rule',leaf.get('fill-rule','nonzero'));clip.append(leaf)
      else:
       for item in n:flatten(item,m)
     flatten(child)
     if not len(clip):raise ValueError('Original mask has no resolved geometry: '+path)
     defs.append(clip);masks.append((p['clipDepth'],key));continue
    masks=[v for v in masks if p['depth']<=v[0]]
    for _,key in masks:
     wrapper=element('g',{'clip-path':'url(#'+key+')'});wrapper.append(child);child=wrapper
    node.append(child)
  elif kind in (2,22,32,83):
   spec=shape(kind,raw,extended=True)
   def paint(p):
    if p['kind']=='solid':return rgba(p['color']),p['color'][3]/255
    key=unique()
    if p['kind']=='bitmap':
     bid=p['bitmapId'];names=[n for n,c in doc['symbols'].items() if c==bid]
     if len(names)!=1 or Path(names[0]).name!=names[0]:raise ValueError('Ambiguous original bitmap')
     path='ui/Texture/'+names[0];url=png(path);size=assets[path]['size']
     if tuple(size)!=doc['bitmaps'][bid]:raise ValueError('Original bitmap metadata differs')
     value=element('pattern',{'id':key,'patternUnits':'userSpaceOnUse','width':size[0],'height':size[1],'patternTransform':matrix(p['matrix'])})
     value.append(element('image',{'href':url,'width':size[0],'height':size[1],'image-rendering':'auto' if p['sourceType']<66 else 'pixelated'}))
    elif p['kind'] in ('linear','radial'):
     value=element('linearGradient' if p['kind']=='linear' else 'radialGradient',{'id':key,'gradientUnits':'userSpaceOnUse','gradientTransform':matrix(p['matrix']),'spreadMethod':['pad','reflect','repeat'][p['spread']],'color-interpolation':'linearRGB' if p['interpolation'] else 'sRGB',**({'x1':-16384,'y1':0,'x2':16384,'y2':0} if p['kind']=='linear' else {'cx':0,'cy':0,'r':16384})})
     for stop in p['stops']:value.append(element('stop',{'offset':stop['ratio']/255,'stop-color':rgba(stop['color']),'stop-opacity':stop['color'][3]/255}))
    else:raise ValueError('Unrecovered source paint')
    defs.append(value);return 'url(#'+key+')',1
   for p in spec['fills']:
    color,alpha=paint(p['paint']);node.append(element('path',{'d':p['path'],'fill':color,'fill-opacity':alpha,'fill-rule':spec['fillRule']}))
   for p in spec['lines']:
    color,alpha=paint(p['paint']);node.append(element('path',{'d':p['path'],'fill':'none','stroke':color,'stroke-opacity':alpha,'stroke-width':p['width'],'stroke-linecap':['round','butt','square'][p['cap']],'stroke-linejoin':['round','bevel','miter'][p['join']]}))
  elif kind==37:
   st=text_style(kind,raw);font=fonts[doc['path']][st['fontId']];x0,x1,y0,y1=[x*20 for x in st['boundsPixels']];left,right,indent=st['marginsPixels'][:3];align=st['align']
   x=x0+(left+indent)*20 if align==0 else x1-right*20 if align==1 else (x0+x1)/2
   family='EntryDisplay' if 'Alegreya' in font['name'] else 'EntryGothic' if 'League' in font['name'] else 'EntryText'
   baseline={'y':y0+st['fontHeight']*font['ascent']/1024} if 'ascent'in font else {'y':y0,'dominant-baseline':'text-before-edge'}
   value=element('text',{'x':x,**baseline,'font-family':family,'font-size':st['fontHeight']*20,'fill':rgba(st['colorRGBA']),'fill-opacity':st['colorRGBA'][3]/255,'text-anchor':['start','end','middle','start'][align],'data-entry-text':'true','data-font-source':font['name'],'data-entry-bounds':' '.join(map(str,[x0,y0,x1-x0,y1-y0]))})
   value.text=re.sub('<[^>]+>','',st['initialHTML']);node.append(value)
  else:raise ValueError('Unrecovered original tag '+str(kind))
  return node
 rows=_ini_blocks(load('ui/Config/interface_common_2.ini'));windows={}
 for name,cid in [('QuestListHero',99),('MessageBox',0)]:
  d=docs[name];svg=element('svg',{'viewBox':'0 0 1136 640','preserveAspectRatio':'xMidYMid meet'});defs=element('defs');svg.append(defs)
  wrapper=element('g',{'transform':'scale(0.05)','data-journal-window':name});wrapper.append(draw(d,cid,'',defs));svg.append(wrapper)
  raw=ET.tostring(svg,encoding='utf-8');(out/(name+'.svg')).write_bytes(raw)
  abc=parse_abc(extract_abc(load(d['path'])));cls=next(c for c in abc['classes'] if c['name']==name)
  methods={}
  for trait in cls['traits']:
   if 'method'in trait:
    m=named_method(abc,name,trait['name']);methods[trait['name']]={k:v for k,v in m.items() if k!='instructions'}
  windows[name]={'file':name+'.svg','sha256':SHA(raw),'sourceSHA256':d['sourceSHA256'],'sourceRoot':cid,'config':next(v for v in rows if v.get('name')==name),'methods':methods,'svgNodes':sum(1 for _ in svg.iter())}
 en=decode_localized_names(load('tables/String_General_.tbl'),'EN')['values'];zh=decode_localized_names(load('tables/String_General_zh.tbl'),'SC')['values']
 strings={key:{'id':idx,'text':zh[idx]} for idx,key in en.items() if key.startswith('GENERAL_QUESTBOOK_') or key in ['GENERAL_FREEBAR_QUESTBOOK','GENERAL_QUESTHUD_NOQUEST','GENERAL_OK','GENERAL_CANCEL']}
 for path in ['ui/icons/head_obj/quest_unfinished.png','ui/icons/head_obj/quest_complete.png','ui/icons/quest/quest_fail.png','ui/icons/item/gold_coin.png','ui/icons/item/exp.png','ui/icons/userinterface/fever_coin.png','ui/icons/userinterface/questiontexticon.png','ui/icons/item/red_skull_plan.png','ui/icons/quest/task_collect.png','ui/icons/quest/task_talk.png','ui/icons/userinterface/location.png']:
  # Paths here are literal original callback/AS references. Do not search for
  # a similarly named replacement if the specific original resource is absent.
  try:png(path)
  except (KeyError,FileNotFoundError):gaps.append({'path':path,'reason':'Specific original icon unavailable'})
 # Separate authored state fragments. Nothing selects a live state here. The
 # parent must use original consumers plus actual compatible quest state.
 variants={}
 requests=[('tracked-row','QuestListHero',99,'.panel_list.item_1.btnBlink',5),
  ('active-disabled','QuestListHero',99,'.m_btnSetActive',11),
  ('abandon-disabled','QuestListHero',99,'.m_btnAbandon',11),
  ('map-disabled','QuestListHero',99,'.m_btnMap',11),
  ('yes-disabled','MessageBox',0,'.OkButton',11),
  ('no-disabled','MessageBox',0,'.CancelButton',11)]
 for key,name,root,path,number in requests:
  d=docs[name];target=named_path(d,root,path[1:],lib)
  dd=next(v for v in docs.values() if v['path']==target['leafSWF'])
  svg=element('svg',{'viewBox':'0 0 1136 640'});defs=element('defs');svg.append(defs)
  g=draw(dd,target['leafCharacterId'],path,defs,frame=number);g.set('data-state-root',key);svg.append(g)
  raw=ET.tostring(svg,encoding='utf-8');filename=key+'.svg';(out/filename).write_bytes(raw)
  variants[key]={'file':filename,'sha256':SHA(raw),'window':name,'path':path,'frame':number,'placement':target,'appliedToRuntime':False}
 main=load('ui/Flash/mainUI.swf')
 if SHA(main)!='e18152cbddf51f335ad764fd57c928a990cb0846de05b2628968050e1dcbc0ac':raise ValueError('Original UI methods changed')
 method_proofs={}
 for block in ['Common/gluicEx/components/ui/Icon','Common/gluicEx/components/ui/ItemSlot','Common/Window/WindowManager']:
  abc=parse_abc(extract_named_abc(main,block));cls=abc['classes'][0]
  code=abc['bodies'][cls['iinit']]['code'];method_proofs[block+'.constructor']={'codeSHA256':SHA(code),'codeBytes':len(code)}
  if block.endswith('/Icon'):
   code=disassemble(code,abc)
   if not any(v['op']=='pushbyte' and v['args']==[96] for v in code):raise ValueError('Original icon measuring input changed')
  if block.endswith('/WindowManager'):
   m=named_method(abc,cls['name'],'Common.Window:WindowManager::resetUI')
   if m['codeSHA256']!='09e6cd50d37111dd0ea42b6c9e51cccea9a521ac28dc39d04f891e4812b84544':raise ValueError('Original window placement changed')
   method_proofs[block+'.resetUI']={k:v for k,v in m.items() if k!='instructions'}
 result={'format':'oc2-original-quest-journal-art-v2','stage':[1136,640],'windows':windows,'stateDrawings':variants,'supportMethods':method_proofs,'assets':assets,'strings':strings,'gaps':gaps,'flashFilters':filters,'nativeResourceSelections':selections,'sources':{p:{'sha256':SHA(v),'bytes':len(v)}for p,v in loaded.items()},'boundaries':['Artwork only; no accepted task, callback, activity, network or save is created.','All original selected-frame placements/matrices/clips retained. Browser text/filter rendering is not pixel-identical Flash.','Only solid DefineMorphShape ratio zero is read. Runtime progress/interpolation and source enabled-state are not invented.','State fragments are exact authored frames, not proof of their live selection. MessageBox root measurement/full native movie remains a separate boundary.']}
 (out/'journal-art.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result

if __name__=='__main__':
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();result=recover(a.source,a.output)
 print(json.dumps({'output':str(a.output),'windows':list(result['windows']),'assets':len(result['assets']),'gaps':len(result['gaps']),'noGameOrSaveChanges':True}))
