"""Export only the authored original BreakAway Disable overlay.

This never changes the frozen v5 UI, installs a menu or supplies cooldown/map
state. --check validates the original timeline/shape/alpha without writing art.
The output SVG uses exactly the frozen button group's local viewBox.
"""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from tutorial_map_geometry import local_output

SOURCE_SHA='8aa3a2cfdbd9d55dc7e2414b78f57c2f2b1e844d0209d6d62d9b6622cc6d9c4b'
DISABLE_MATRIX=[1.073272705078125,0,0,0.9881744384765625,40,263]
CHILD_MATRIX=[0.427154541015625,0,0,0.213043212890625,0,0]
SHAPE_PATH='M 13000 9120 L 0 9120 L 0 0 L 13000 0 L 13000 9120 Z'

def check_source(source):
    from map_loading_evidence import Sources
    from hud_assets import document,sprite_frames
    from swf_ui_graphics import shape
    s=Sources(source);path='ui/Flash/SettingInfo.swf';raw=s.read(path)
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise ValueError('Original SettingInfo source changed')
    doc=document(raw,path);group=sprite_frames(doc,25)[0];layer=next(p for p in group if p.get('name')=='_Disable');child=sprite_frames(doc,24)[0]
    expected={'multiply':[256,256,256,77],'add':[0,0,0,0]}
    if layer.get('characterId')!=24 or layer['depth']!=5 or layer['matrixTwips']!=DISABLE_MATRIX or layer['colorTransform']!=expected:raise ValueError('Original Disable placement/alpha differs')
    button=next(p for p in group if p.get('name')=='_Button')
    if button.get('characterId')!=12 or button['depth']!=1:raise ValueError('Original overlay/button stacking differs')
    if len(child)!=1 or child[0].get('characterId')!=23 or child[0]['matrixTwips']!=CHILD_MATRIX or child[0]['colorTransform']!={'multiply':[256]*4,'add':[0]*4}:raise ValueError('Original Disable child differs')
    spec=shape(*doc['records'][23],extended=True)
    if doc['records'][23][0]!=2 or spec['boundsTwips']!=[0,13000,0,9120] or spec['fills']!=[{'paint':{'kind':'solid','color':[0,0,0,255]},'path':SHAPE_PATH}]or spec['lines']:raise ValueError('Original Disable shape differs')
    return doc,layer,child[0],spec,s.proofs

def export(source,output):
    from hud_assets import named_path,compose
    from login_ui_assets import element,matrix
    out=local_output(output)
    if out.exists()and any(out.iterdir()):raise ValueError('Existing standalone overlay evidence stays frozen')
    doc,p,child,spec,proofs=check_source(source);out.mkdir(parents=True,exist_ok=True)
    svg=element('svg',{'viewBox':'-10 -15 300 130','width':300,'height':130});root=element('g',{'transform':'scale(0.05)','data-source-swf':doc['path'],'data-source-parent-id':25});layer=element('g',{'transform':matrix(p['matrixTwips']),'opacity':p['colorTransform']['multiply'][3]/256,'data-source-path':'_GroupBtn._Disable','data-source-id':24});g=element('g',{'transform':matrix(child['matrixTwips'])});g.append(element('path',{'d':spec['fills'][0]['path'],'fill':'black','fill-rule':spec['fillRule']}));layer.append(g);root.append(layer);svg.append(root)
    raw=ET.tostring(svg,encoding='utf-8');ET.fromstring(raw);name='source-unstuck-disabled.svg';(out/name).write_bytes(raw)
    m=compose(p['matrixPixels'],child['matrixPixels']);a,b,c,d,x,y=m;points=[(a*xx+c*yy+x,b*xx+d*yy+y)for xx,yy in((0,0),(650,0),(0,456),(650,456))]
    chain=named_path(doc,41,'m_HelpPanel.mc_content.m_BreakAway._GroupBtn._Disable',None)
    receipt={'format':'oc2-original-unstuck-disable-receipt-v1','file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'viewBox':[-10,-15,300,130],'groupLocalBoundsPixels':[min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points)],'boundsOrder':'xmin,ymin,xmax,ymax','shape':spec,'groupPlacement':p,'childPlacement':child,'authoredWindowParentChain':chain,'authoredParentYIsRuntimeOverridden':'_GroupBtn.y = _Detail.y + _Detail.textHeight; do not bake authoredGroupY78.85 into Chinese layout','mount':'Overlay this SVG above the existing button-group SVG at the same element box/viewBox; it already contains the original _Disable local transforms. Do not reapply its placement a second time.','alphaMultiplier':77/256,'originalStaticTimelineNode':True,'dynamicCreation':False,'visibilityConsumer':'SettingInfo.subInit initializes true; GetBreakAwayInfo toggles by received mapType and CanBreakAway result; onTapBreakAway tests visible','stateIncluded':False,'oldV5AndPackagesChanged':False,'originalAssetChecks':1,'sourceProofs':proofs}
    (out/'manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');return receipt

if __name__=='__main__':
    from resource_packs import DEFAULT_SOURCE
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=DEFAULT_SOURCE);p.add_argument('--output',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.output is not None:
        r=export(a.source,a.output);print(json.dumps({'output':str(a.output),'file':r['file'],'bytes':r['bytes'],'sha256':r['sha256'],'originalAssetChecks':1,'stateIncluded':False}))
    elif a.check:check_source(a.source);print(json.dumps({'originalAssetChecks':1,'source':'SettingInfo.swf cid25/24/23','stateIncluded':False}))
    else:p.error('Use --check or --output in an ignored directory')
