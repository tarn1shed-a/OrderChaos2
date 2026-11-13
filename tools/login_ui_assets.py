"""Read the pinned original login/selection drawings and bytecode, never run SWF.

Exports artwork to ignored assets. The web identity bridge is a separate adapter;
original account authentication, list ownership and selection world are not fabricated.
"""
import argparse, hashlib, io, json, re, struct
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image
from resource_packs import ResourceArchive, DEFAULT_SOURCE
from hud_assets import document, sprite_frames, resolve, _ini_blocks, compose
from optimized_abc import extract_abc, extract_named_abc, parse_abc, named_method
from swf_ui_graphics import shape, text_style, display_tree, bounds
from ui_assets import parse_font3
from skill_icons import decode_localized_names

PINS={
 'ui/Flash/library.swf':'d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89',
 'ui/Flash/mainUI.swf':'e18152cbddf51f335ad764fd57c928a990cb0846de05b2628968050e1dcbc0ac',
 'ui/Flash/QuickLogin.swf':'955ba936c5e98073b0ad740570683b09ded75c30a4ef7dca89fd58d70cb5034b',
 'ui/Flash/CharacterChooseCharacter.swf':'3e055b2c07f6098664fadab44be0498aebcedf17d7520805d1948130c89db587',
 'ui/Flash/LoginMsgBox.swf':'96298c44e0be0fc9ec51c1fba9bc0df1c9a071f00de44b9756995f5886c14134',
 'ui/Flash/CharacterChooseRace.swf':'14af412f5c44f4a91d1a14bed9273cfc04128674f4788472f100288eca676940',
 'ui/Flash/CharacterChooseClass.swf':'83f552329ad0ab1b1967f17371d7ff4e58fba8d7c5bcac5d5f7f04aae7839bb1',
 'ui/Flash/CharacterChoosePart.swf':'45bee25667edb845471b73cf94677b095c1479c0fa4c490ec2af68cef7c4d716',
 'ui/Flash/CharacterChooseVillage.swf':'5b5a93eab1fc25ff3259e89e1ca71e1542e9904f3ee268954e29fb6785593c85',
}
NS='http://www.w3.org/2000/svg';ET.register_namespace('',NS)
def element(tag,attrs=None):return ET.Element('{'+NS+'}'+tag,{k:str(v) for k,v in (attrs or {}).items()})
def digest(raw):return hashlib.sha256(raw).hexdigest()
def matrix(m):return 'matrix('+ ' '.join(map(str,m))+')'
def rgba(c):return 'rgb('+','.join(map(str,c[:3]))+')'

def recover_login_ui(extract,output,management=False):
 out=Path(output);out.mkdir(parents=True,exist_ok=True);loaded={};assets={};warnings=[]
 def load(path):
  if path not in loaded:
   loaded[path]=extract(path)
   if path in PINS and PINS[path] and digest(loaded[path])!=PINS[path]:raise ValueError('Original entry source changed: '+path)
  return loaded[path]
 names=['library','QuickLogin','CharacterChooseCharacter','LoginMsgBox']
 if management:names+=['CharacterChooseRace','CharacterChooseClass','CharacterChoosePart','CharacterChooseVillage']
 docs={n:document(load('ui/Flash/'+n+'.swf'),'ui/Flash/'+n+'.swf',n!='library') for n in names};lib=docs['library']
 rows=_ini_blocks(load('ui/Config/interface_common_2.ini'))
 configs={n:next(v for v in rows if v.get('name')==n)for n in ['QuickLogin','ChooseCharacter','LoginMsgBox']}
 if management:configs.update({n:next(v for v in rows if v.get('name')==n)for n in ['CharacterSelection','CharacterChooseClass','CharacterChoosePart','CharacterChooseVillage']})
 if any(float(v['scale'])!=1 for v in configs.values()):raise ValueError('Original entry scale changed')
 main=load('ui/Flash/mainUI.swf');manager=parse_abc(extract_named_abc(main,'Common/Window/WindowManager'))
 reset=named_method(manager,'Common.Window::WindowManager','Common.Window:WindowManager::resetUI')
 if reset['codeSHA256']!='09e6cd50d37111dd0ea42b6c9e51cccea9a521ac28dc39d04f891e4812b84544':raise ValueError('Original window placement changed')
 methods={'WindowManager.resetUI':{k:v for k,v in reset.items()if k!='instructions'}}
 definitions=parse_abc(extract_named_abc(main,'Common/ASDefines'));cls=next(c for c in definitions['classes']if c['name']=='Common::ASDefines');trait=next(t for t in cls['staticTraits']if t['name']=='isPUB')
 from optimized_abc import disassemble
 body=definitions['bodies'][trait['method']]['code']
 if [(i['op'],i['args'])for i in disassemble(body,definitions)]!=[('getlocal0',[]),('pushscope',[]),('pushfalse',[]),('returnvalue',[])]:raise ValueError('Source entry platform visibility changed')
 methods['ASDefines.isPUB']={'codeSHA256':digest(body),'constantReturn':False}
 checkbox=parse_abc(extract_named_abc(main,'Common/gluicEx/components/ui/CheckBox'));cls=next(c for c in checkbox['classes']if c['name']=='Common.gluicEx.components.ui::CheckBox');setter=next(t for t in cls['traits']if t['name']=='Selected'and t['kind']==3)
 methods['CheckBox.Selected.setter']={'codeSHA256':digest(checkbox['bodies'][setter['method']]['code']),'selectedDrawing':'SelectedEff'}
 strings={};english=decode_localized_names(load('tables/String_General_.tbl'),'EN')['values'];chinese=decode_localized_names(load('tables/String_General_zh.tbl'),'SC')['values'];ids={v:k for k,v in english.items()}
 for key in ['GENERAL_QUICK_LOGIN','GENERAL_ACCOUNT_QUICK_LOGIN','GENERAL_LOGIN_FACEBOOK_BTN','GENERAL_LOGIN_GAMECENTER_BTN','GENERAL_LOGIN_GOOGLE_BTN_FOR_ANDROID','GENERAL_LOAD_SPLASH_VERSION','GENERAL_MC_SELECT_BTN_PLAY','GENERAL_MC_SELECT_LV','GENERAL_MC_SELECT_CREATE','GENERAL_OK','GENERAL_CANCEL']:
  if key not in ids or ids[key]not in chinese:raise ValueError('Source entry translation missing: '+key)
  strings[key]={'id':ids[key],'text':chinese[ids[key]]}
 if management:
  # Only creation/deletion UI strings, not a dump of the full original table.
  for key,idx in ids.items():
   if (key=='GENERAL_ERROR_GUILD_NAME_ILLEGAL'or key.startswith(('GENERAL_CH_SELEC_','GENERAL_ROLESELECT_REMOVE','GENERAL_ROLECREATE_','GENERAL_CREATION_','GENERAL_CHARACTER_','GENERAL_MC_SELECT_','GENERAL_ERROR_CREATION_')))and idx in chinese:
    strings[key]={'id':idx,'text':chinese[idx]}
 for name in ['QuickLogin','CharacterChooseCharacter','LoginMsgBox']:
  abc=parse_abc(extract_abc(load(docs[name]['path'])))
  for cls in abc['classes']:
   if cls['name'] not in ['QuickLogin','Window_ChooseCharacter','character_list_mc','delete_char_mc','LoginMsgBox']:continue
   for trait in cls['traits']:
    if 'method' not in trait:continue
    m=named_method(abc,cls['name'],trait['name']);methods[cls['name']+'.'+trait['name']]={k:v for k,v in m.items()if k!='instructions'}
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
  counter+=1;return 'entry-'+str(counter)
 def export_asset(path):
  raw=load(path);im=Image.open(io.BytesIO(raw));im.verify();filename=digest(raw)[:20]+'.png';(out/filename).write_bytes(raw)
  assets[path]={'url':'/assets/source-entry/'+filename,'sourceSHA256':digest(raw),'bytes':len(raw)}
  return assets[path]['url']
 def draw(doc,cid,path,defs,depth=0):
  if depth>20:raise ValueError('Entry drawing recursion exceeds bound')
  record=doc['records'].get(cid)
  if not record:raise ValueError('Missing original entry character')
  g=element('g',{'data-source-path':path,'data-source-id':cid,'data-source-file':doc['path']})
  if record[0]==39:
   placements=sprite_frames(doc,cid)[0];active=[]
   for p in placements:
    dd,ii=resolve(doc,p,lib);sub=draw(dd,ii,path+'.'+p.get('name',str(ii)),defs,depth+1);sub.set('transform',matrix(p['matrixTwips']))
    c=p['colorTransform']
    if c['multiply']!=[256]*4 or c['add']!=[0]*4:
     fid=unique();f=element('filter',{'id':fid,'color-interpolation-filters':'sRGB'});v=[]
     for r in range(4):v.extend([c['multiply'][r]/256 if r==j else 0 for j in range(4)]+[c['add'][r]/255])
     f.append(element('feColorMatrix',{'type':'matrix','values':' '.join(map(str,v))}));defs.append(f);sub.set('filter','url(#'+fid+')')
    if 'filters'in p:warnings.append({'path':path,'unrestored':'source Flash text/bitmap filter rasterization','filters':p['filters']})
    if p.get('blendMode',1)not in (0,1):raise ValueError('Unsupported source entry blend mode')
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
     if not len(clip):raise ValueError('Entry clipping geometry unavailable')
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
     if len(names)!=1 or Path(names[0]).name!=names[0]:raise ValueError('Entry bitmap namespace missing')
     source='ui/Texture/'+names[0];url=export_asset(source);im=Image.open(io.BytesIO(load(source)));width,height=im.size
     if (width,height)!=doc['bitmaps'][bid]:raise ValueError('Entry atlas dimensions differ')
     node=element('pattern',{'id':key,'patternUnits':'userSpaceOnUse','width':width,'height':height,'patternTransform':matrix(p['matrix'])});node.append(element('image',{'href':url,'width':width,'height':height,'image-rendering':'auto' if p['sourceType']<66 else 'pixelated'}))
    elif p['kind']in ('linear','radial'):
     node=element('linearGradient'if p['kind']=='linear'else'radialGradient',{'id':key,'gradientUnits':'userSpaceOnUse','gradientTransform':matrix(p['matrix']),'spreadMethod':['pad','reflect','repeat'][p['spread']],'color-interpolation':'linearRGB'if p['interpolation']else'sRGB',**({'x1':-16384,'y1':0,'x2':16384,'y2':0}if p['kind']=='linear'else{'cx':0,'cy':0,'r':16384})})
     for stop in p['stops']:node.append(element('stop',{'offset':stop['ratio']/255,'stop-color':rgba(stop['color']),'stop-opacity':stop['color'][3]/255}))
    else:raise ValueError('Unsupported entry paint')
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
  else:raise ValueError('Unsupported entry display tag '+str(record[0]))
  return g
 windows={}
 window_specs=[('QuickLogin',18,'QuickLogin'),('CharacterChooseCharacter',35,'ChooseCharacter'),('LoginMsgBox',24,'LoginMsgBox')]
 if management:window_specs += [('CharacterChooseRace',27,'CharacterSelection'),('CharacterChooseClass',34,'CharacterChooseClass'),('CharacterChoosePart',22,'CharacterChoosePart'),('CharacterChooseVillage',32,'CharacterChooseVillage')]
 for name,cid,config in window_specs:
  doc=docs[name];svg=element('svg',{'viewBox':'0 0 1136 640','preserveAspectRatio':'xMidYMid meet'});defs=element('defs');svg.append(defs)
  wrapper=element('g',{'transform':'scale(0.05)','data-entry-window':name});wrapper.append(draw(doc,cid,'',defs));svg.append(wrapper)
  (out/(name+'.svg')).write_bytes(ET.tostring(svg,encoding='utf-8'))
  windows[name]={'url':'/assets/source-entry/'+name+'.svg','config':configs[config],'sourceSHA256':doc['sourceSHA256'],'sourceRoot':cid}
 # Exact root hit rectangle supplies resetUI dimensions; authored X/Y are not guessed.
 for name,_,_ in window_specs:
  doc=docs[name];p=next((v for v in sprite_frames(doc,0)[0]if v.get('name')=='emptybtn'),None)
  if not p:
   cfg=windows[name]['config']
   if float(cfg['relativeposX']) or float(cfg['relativeposY']):raise ValueError('Entry measuring rectangle missing')
   windows[name]['measuredSize']=None;continue # zero-relative placement does not consume width/height
  dd,ii=resolve(doc,p,lib);box=bounds(display_tree(dd,ii,lib));m=p['matrixPixels'];windows[name]['measuredSize']=[(box[2]-box[0])/20*m[0],(box[3]-box[1])/20*m[3]]
 logo=export_asset('ui/icons/specialimage/logo_cn.png')
 # These icons are set by QuickLogin.onCreate and onCharacterListSet, not chosen art.
 for icon in ['google','facebook','gamecenter','class_warrior','class_mage','class_monk','class_ranger','class_demonslayer']:
  source='ui/icons/userinterface/'+icon+'_0.5x.png'
  export_asset(source)
 if management:
  for icon in ['icon_characteradd','icon_deleteplayer','race_human','race_mender','race_elf','race_orc','race_kartan','female','male','class_warrior','class_ranger','class_mage','class_demonslayer','class_monk']:
   export_asset('ui/icons/userinterface/'+icon+'_0.5x.png')
 result={'format':'oc2-source-entry-ui-v1','stage':[1136,640],'windows':windows,'strings':strings,'assets':assets,'logo':logo,'methods':methods,
  'limits':['Original account services unavailable. Web role credentials and connection are a separate, authorized adapter.','Original selection-world background, full character preview, creation/slot purchase/transfer/deletion and original account responses are not restored.','SVG text/filter rasterization and browser scaling are not proven pixel-identical to Flash. No substitute background artwork is generated.'],
  'warnings':warnings,'sources':{p:{'bytes':len(b),'sha256':digest(b)}for p,b in loaded.items()}}
 (out/'entry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result

def main():
 cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True);cli.add_argument('--management',action='store_true');args=cli.parse_args();root=Path(__file__).resolve().parents[1]
 if not any(args.output.resolve().is_relative_to(root/p)for p in ['analysis/raw','game-data','backups']):cli.error('Original entry assets must stay in ignored folders')
 archives={}
 def read(path):
  pack='conf.bin'if path.startswith('ui/Config/')else'tables.bin'if path.startswith('tables/')else'ui.bin'
  if pack not in archives:archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
  return archives[pack].read(path)
 r=recover_login_ui(read,args.output,management=args.management);print(json.dumps({'windows':list(r['windows']),'assets':len(r['assets']),'sources':len(r['sources']),'output':str(args.output)},ensure_ascii=False))
if __name__=='__main__':main()
