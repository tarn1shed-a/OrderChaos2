"""Read the original AttributePage layout and bytecode; never execute SWF.

The result describes source artwork/fields. It supplies no missing server stats,
power score, original account GUID, model camera, or world-name appearance.
"""
import hashlib
from hud_assets import document, sprite_frames, resolve, named_path, _ini_blocks
from optimized_abc import extract_abc, extract_named_abc, parse_abc, named_method, disassemble
from swf_ui_graphics import shape, text_style

PIN='e7ad9fc9b9fd8c1749113c1ca2fa9e9ec00e1261bdaca282cae943a2d38bdc76'
METHODS={
 'onCreate':'80ff06d850f0ff837489258ff207292fae33fd35636f52195b68e1e40f333544',
 'refreshState':'1c964da620c6ebcb48f275e34fd16a4de41f03264b787b6c24f5c986c712e156',
 'InitAttribute':'c2e602041a257d73239111c9009109205f0be6683a146ca75de72b378100c97d',
 'SetAttributeValueHp':'09fa57d057e1ff09e80c47fa206c49e862423bd5c67f4320bfc5205ccfb8ac77',
 'ModelRefresh':'a58ebb49964d2fefeb4a06320403ca4b96160b70b282036a785d924d23395ba4',
 'SetAttrCombatScoreString':'bd76da082ba169de54b26eca4040024fd6463bebd7446f052cb19e4aabfedd13',
}
PREFIX='.CharacterAttrPanel.CharacterPanel.mc_content.'

def source_bounds(doc,cid,lib,depth=0):
 if depth>20:raise ValueError('Attribute measuring tree too deep')
 rec=doc['records'][cid]
 if rec[0]==37:
  x0,x1,y0,y1=text_style(*rec)['boundsPixels'];return [x0*20,y0*20,x1*20,y1*20]
 if rec[0]!=39:
  x0,x1,y0,y1=shape(*rec,extended=True)['boundsTwips'];return [x0,y0,x1,y1]
 points=[]
 for p in sprite_frames(doc,cid)[0]:
  dd,cc=resolve(doc,p,lib);x0,y0,x1,y1=source_bounds(dd,cc,lib,depth+1);a,b,c,d,tx,ty=p['matrixTwips']
  points.extend((a*x+c*y+tx,b*x+d*y+ty)for x,y in [(x0,y0),(x0,y1),(x1,y0),(x1,y1)])
 if not points:raise ValueError('Empty attribute measuring tree')
 xs,ys=zip(*points);return [min(xs),min(ys),max(xs),max(ys)]

def recover_attribute_profile(load,docs,strings,english,chinese):
 raw=load('ui/Flash/AttributePage.swf')
 if hashlib.sha256(raw).hexdigest()!=PIN:raise ValueError('Original AttributePage changed')
 doc,lib=docs['AttributePage'],docs['library'];abc=parse_abc(extract_abc(raw));methods={}
 for name in ['onCreate','onShow','subInit','refreshState','InitAttribute','InitCombatScore','SetAttrCombatScoreString','SetAttribute','SetAttributeValueHp','SetAttributeValueExp','ModelRefresh','setAttributePlayerClass','scrollUp_ac','scrollDown_ac','scrollRS']:
  method=named_method(abc,'AttributePage',name)
  if name in METHODS and method['codeSHA256']!=METHODS[name]:raise ValueError('Original attribute method changed: '+name)
  methods[name]=method
 defs=parse_abc(extract_named_abc(load('ui/Flash/mainUI.swf'),'Common/ASDefines'))
 cls=next(c for c in defs['classes']if c['name']=='Common::ASDefines')
 constants={t['name']:defs['ints'][t['value']]for t in cls['staticTraits']if t['name'].startswith('PROPERTY_BAR_ICON_')and t.get('valueKind')==3}
 for name in ['isDynamicLoadUI','isAndroidDevice']:
  t=next(t for t in cls['staticTraits']if t['name']==name)
  if [(i['op'],i['args'])for i in disassemble(defs['bodies'][t['method']]['code'],defs)]!=[('getlocal0',[]),('pushscope',[]),('pushfalse',[]),('returnvalue',[])]:raise ValueError('Original attribute container branch differs')
 ids={v:k for k,v in english.items()}
 def word(key):
  if key not in ids or ids[key]not in chinese:raise ValueError('Missing attribute translation: '+key)
  strings[key]={'id':ids[key],'text':chinese[ids[key]]};return chinese[ids[key]]
 labels={};frames={};ins=methods['InitAttribute']['instructions']
 for at,i in enumerate(ins):
  if i['at']>=832:break
  if i['op']=='callpropvoid'and i['args']==['SetAttribute',3]:
   span=ins[max(0,at-18):at];props=[v['args'][0]for v in span if v['op']=='getproperty'and v['args'][0]!='<runtime-name>']
   field,constant=props[-2:];key=next(v['args'][0]for v in reversed(span)if v['op']=='pushstring'and v['args'][0].startswith('GENERAL_'))
   path=PREFIX+field;labels[path+'.title_name']=word(key);frames[path+'.item_icon']=constants[constant]
  if i['op']=='setproperty'and i['args']==['text']:
   span=ins[max(0,at-12):at];props=[v['args'][0]for v in span if v['op']=='getproperty'and v['args'][0]!='<runtime-name>']
   key=next((v['args'][0]for v in reversed(span)if v['op']=='pushstring'and v['args'][0].startswith('GENERAL_')),None)
   if props and key:labels[PREFIX+props[0]]=word(key)
 labels['.NormalVigorPanel.title_name']=word('GENERAL_VIGOR_NORMAL')
 frames['.powerIcon.power_icon']=constants['PROPERTY_BAR_ICON_POWER']
 for path,key in [('.tabTxtCharactor','GENERAL_ATTRIBUTE_DETAIL'),('.tabTxtCombatScore','GENERAL_COMBAT_SCORE_SUM'),('.txtCombatScore','GENERAL_COMBAT_SCORE')]:labels[path]=word(key)
 ins=methods['InitCombatScore']['instructions']
 for at,i in enumerate(ins):
  if i['op']=='callpropvoid'and i['args']==['SetAttrCombatScoreString',2]:
   span=ins[max(0,at-5):at];field=next(v['args'][0]for v in span if v['op']=='getproperty');key=next(v['args'][0]for v in span if v['op']=='pushstring')
   desc=next(v['args'][0]for v in methods['SetAttrCombatScoreString']['instructions']if v['op']=='getproperty')
   labels['.CombatScorePanel.CSAttrPanel.'+field+'.'+desc]=word(key)
 rows=_ini_blocks(load('ui/Config/interface_common_2.ini'));sizes=[];tabs=[]
 for row in rows:
  if row.get('parent')!='BaseInfo':continue
  other=document(load('ui/Flash/'+row['url']),row['url']);p=next(p for p in sprite_frames(other,0)[0]if p.get('name')=='emptybtn');dd,cid=resolve(other,p,lib)
  x0,y0,x1,y1=source_bounds(dd,cid,lib);m=p['matrixPixels'];size=[(x1-x0)/20*m[0]*float(row['scale']),(y1-y0)/20*m[3]*float(row['scale'])]
  sizes.append(size);tabs.append({'name':row['name'],'title':word(row['title']),'icon':row['icon'],'measuredSize':size})
 window=next(r for r in rows if r.get('name')=='BaseInfo')
 if window['url']!='WindowStack.swf'or window['parent']!='IGMContainer':raise ValueError('Original attribute parent changed')
 # The non-dynamic WindowStack.init branch measures every BaseInfo child.
 size=[max(s[i]for s in sizes)for i in range(2)]
 animated={}
 for path in [PREFIX+'Hp.valueBar',PREFIX+'Exp.valueBar.exp']:
  leaf=named_path(doc,106,path[1:],lib);dd=next(d for d in docs.values()if d['path']==leaf['leafSWF']);animated[path]=len(sprite_frames(dd,leaf['leafCharacterId']))
 mask=named_path(doc,106,'CharacterAttrPanel.CharacterPanel.mc_bounds',lib);content=named_path(doc,106,'CharacterAttrPanel.CharacterPanel.mc_content',lib)
 box=source_bounds(doc,mask['leafCharacterId'],lib);m=mask['chain'][-1]['matrixTwips'];a,b,c,d,tx,ty=m
 points=[(a*x+c*y+tx,b*x+d*y+ty)for x,y in [(box[0],box[1]),(box[2],box[3])]]
 cb=source_bounds(doc,content['leafCharacterId'],lib)
 return {'format':'oc2-source-attribute-page-v1','pageSize':size,'sourceStage':[1136,640],'tabs':tabs,'selectedTab':next(i for i,t in enumerate(tabs)if t['name']=='AttributePage'),
   'labels':labels,'iconFrames':frames,'animatedFrames':animated,'defaultPane':'attributes',
   'powerTitles':{str(i):word(k)for i,k in enumerate(['GENERAL_PLAYERINFO_RAGE','GENERAL_PLAYERINFO_MANA','GENERAL_PLAYERINFO_ENERGY','GENERAL_PLAYERINFO_YINYANG','GENERAL_PLAYERINFO_EXTRAHP','GENERAL_PLAYERINFO_ENERGY'],1)},
   'scroll':{'bounds':[points[0][0]/20,points[0][1]/20,points[1][0]/20,points[1][1]/20],'contentBounds':[v/20 for v in cb],'step':0.1},
   'methods':{k:{'codeSHA256':v['codeSHA256'],'codeBytes':v.get('codeBytes')}for k,v in methods.items()},
   'unrestored':['original native GUID/model camera','original server attributes, vigor, energy, combat/power scores','full WindowStack navigation','world-name renderer and visibility/color inputs','Flash filter rasterization and runtime DPI']}
