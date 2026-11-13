"""Verify the original tutorial menu gate and real character-page route.

No new interface, font/color choice, or original name renderer is generated.
Original bytecode and full layouts remain local.
"""
import hashlib
from hud_assets import _ini_blocks,document,named_path
from optimized_abc import extract_abc,parse_abc,named_method

PINS={
 'ui/Flash/IGMEntrance.swf':'8b97da95ba21ce835dd2833a290fe0d35a6c4b480ae7fbe4438de285f0aad051',
 'ui/Flash/AttributePage.swf':'e7ad9fc9b9fd8c1749113c1ca2fa9e9ec00e1261bdaca282cae943a2d38bdc76',
}
def evidence(read):
 loaded={}
 def load(path):
  raw=read(path)
  if path in PINS and hashlib.sha256(raw).hexdigest()!=PINS[path]:raise ValueError('Original role UI source changed')
  loaded[path]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()};return raw
 raw=load('ui/Flash/IGMEntrance.swf');abc=parse_abc(extract_abc(raw));m=named_method(abc,'IGMEntrance','onShow')
 if m['codeSHA256']!='df3b257b933a91860487f8488a10286d0d7a21914b6c6348b41024ca7594e57b':raise ValueError('Original tutorial gate changed')
 ins=[(v['op'],v['args'])for v in m['instructions']]
 if ('pushstring',['Map_GetHeroMapId'])not in ins or ('pushbyte',[5])not in ins or ('pushfalse',[])not in ins or ('callpropvoid',['setShow',1])not in ins:raise ValueError('Original map-5 hiding condition differs')
 rows=_ini_blocks(load('ui/Config/interface_common_2.ini'));route=[]
 for name,url,parent in [('AttributePage','AttributePage.swf','BaseInfo'),('BaseInfo','WindowStack.swf','IGMContainer'),('IGMContainer','WindowContainerIGM.swf','')]:
  row=next(v for v in rows if v.get('name')==name)
  if row.get('url')!=url or row.get('parent')!=parent:raise ValueError('Original character page route differs')
  route.append({'name':name,'url':url,'parent':parent})
 doc=document(load('ui/Flash/AttributePage.swf'),'ui/Flash/AttributePage.swf');lib=document(load('ui/Flash/library.swf'),'ui/Flash/library.swf',False)
 if doc['symbols']['Window_AttributePageInfo']!=106:raise ValueError('Original attribute root differs')
 fields={name:named_path(doc,106,name,lib)for name in ['player_name','player_level','CharacterDisplay','CharacterAttrPanel','CombatScorePanel']}
 return {'format':'oc2-role-ui-retirement-evidence-v1','tutorialMenuEntranceHiddenOnMap':5,'gateMethodSHA256':m['codeSHA256'],'characterRoute':route,'characterFields':fields,'sources':loaded,'originalCharacterPageRendered':False,'originalHeadNameStyleKnown':False,'replacementArtGenerated':False}
