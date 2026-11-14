"""Export a bounded original settings/BreakAway resource inspector.

Original artwork and all converted output belong only in ignored local folders.
No menu is installed in the game; browser typography is an explicit adapter.
"""
import argparse
import base64
import hashlib
import html
import io
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET
from PIL import Image
from map_loading_evidence import Sources,DEFAULT_SOURCE
from hud_assets import document,sprite_frames,resolve,named_path,_ini_blocks,compose
from ui_assets import Bits
from optimized_abc import extract_abc,parse_abc,named_method,disassemble
from swf_ui_graphics import shape,text_style
from login_ui_assets import element,matrix,rgba
from skill_icons import decode_localized_names
from tutorial_map_geometry import local_output

PINNED={
 'SettingInfo':'8aa3a2cfdbd9d55dc7e2414b78f57c2f2b1e844d0209d6d62d9b6622cc6d9c4b',
 'IGMBottomBar':'21bc8a592ca5af0c75db44ceee0e9651ad31cfec75f752d0751a82c127ba9a8d',
 'library':'d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89',
}
METHODS={'SettingInfo':['initString','subInit','onShow','SwitchPanel','SwitchTitle','onTapHelp','onTapBreakAway','GetBreakAwayInfo','SwitchBreakAwayTimer','InitHelpPanelPos'],
 'IGMBottomBar':['InitMembers','onIgmBtnTap','onShow','AddWindow'],
 'WindowStack':['init','onItemSet','onItemSelect','SwitchTab','onSubLoadComlete'],
 'WindowContainerIGM':['init','onShow','SetCurrentSelect']}

def recover(source,output):
    out=local_output(output);out.mkdir(parents=True,exist_ok=True);s=Sources(source);loaded={};docs={};assets={};warnings=[];methods={}
    def load(path):
        if path not in loaded:loaded[path]=s.read(path)
        return loaded[path]
    for n in ('library','SettingInfo','IGMBottomBar','WindowStack','WindowContainerIGM','IGM'):
        p='ui/Flash/'+n+'.swf';raw=load(p)
        if n in PINNED and hashlib.sha256(raw).hexdigest()!=PINNED[n]:raise ValueError('Original settings resource differs')
        docs[n]=document(raw,p,n!='library')
        if n in METHODS:
            a=parse_abc(extract_abc(raw))
            methods[n]={m:named_method(a,n,m)for m in METHODS[n]}
            if n=='SettingInfo':methods[n]['SettingBtn.SetTitle']=named_method(a,'SettingBtn','SetTitle')
    lib=docs['library'];counter=0
    def uid():
        nonlocal counter
        counter+=1;return 'original-'+str(counter)
    def bitmap(path):
        raw=load(path);im=Image.open(io.BytesIO(raw));im.verify();name=hashlib.sha256(raw).hexdigest()[:24]+'.png';(out/name).write_bytes(raw)
        assets[path]={'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)};return name
    def draw(doc,cid,defs,*,omit_names=(),path=''):
        rec=doc['records'].get(cid)
        if rec is None:raise ValueError('Missing original display record')
        g=element('g',{'data-source-swf':doc['path'],'data-source-id':cid,'data-source-path':path})
        if rec[0]==39:
            for p in sprite_frames(doc,cid)[0]:
                if p.get('name')in omit_names:continue
                if 'clipDepth'in p:raise ValueError('Minimal candidate must not flatten masks')
                dd,cc=resolve(doc,p,lib);sub=draw(dd,cc,defs,omit_names=omit_names,path=path+'.'+p.get('name',str(cc)));sub.set('transform',matrix(p['matrixTwips']))
                c=p['colorTransform']
                if c['multiply']!=[256]*4 or c['add']!=[0]*4:
                    key=uid();f=element('filter',{'id':key,'color-interpolation-filters':'sRGB'});v=[]
                    for row in range(4):v.extend([c['multiply'][row]/256 if row==col else 0 for col in range(4)]+[c['add'][row]/255])
                    f.append(element('feColorMatrix',{'type':'matrix','values':' '.join(map(str,v))}));defs.append(f);sub.set('filter','url(#'+key+')')
                if p.get('filters'):warnings.append({'source':doc['path'],'path':path,'unrestored':'Flash filter rasterization','filters':p['filters']})
                if p.get('blendMode',1)not in(0,1):raise ValueError('Unsupported original blend mode')
                g.append(sub)
        elif rec[0]in(2,22,32,83):
            spec=shape(*rec,extended=True)
            def paint(p):
                if p['kind']=='solid':return rgba(p['color']),p['color'][3]/255
                key=uid()
                if p['kind']=='bitmap':
                    names=[n for n,c in doc['symbols'].items()if c==p['bitmapId']]
                    if len(names)!=1:raise ValueError('Ambiguous original bitmap namespace')
                    url=bitmap('ui/Texture/'+names[0]);im=Image.open(io.BytesIO(load('ui/Texture/'+names[0])));w,h=im.size
                    if (w,h)!=doc['bitmaps'][p['bitmapId']]:raise ValueError('Original bitmap size mismatch')
                    node=element('pattern',{'id':key,'patternUnits':'userSpaceOnUse','width':w,'height':h,'patternTransform':matrix(p['matrix'])});node.append(element('image',{'href':'data:image/png;base64,'+base64.b64encode(load('ui/Texture/'+names[0])).decode(),'width':w,'height':h}))
                elif p['kind']in('linear','radial'):
                    node=element('linearGradient'if p['kind']=='linear'else'radialGradient',{'id':key,'gradientUnits':'userSpaceOnUse','gradientTransform':matrix(p['matrix']),'spreadMethod':['pad','reflect','repeat'][p['spread']],'color-interpolation':'linearRGB'if p['interpolation']else'sRGB',**({'x1':-16384,'y1':0,'x2':16384,'y2':0}if p['kind']=='linear'else{'cx':0,'cy':0,'r':16384})})
                    for stop in p['stops']:node.append(element('stop',{'offset':stop['ratio']/255,'stop-color':rgba(stop['color']),'stop-opacity':stop['color'][3]/255}))
                else:raise ValueError('Unsupported original paint')
                defs.append(node);return 'url(#'+key+')',1
            for v in spec['fills']:
                c,a=paint(v['paint']);g.append(element('path',{'d':v['path'],'fill':c,'fill-opacity':a,'fill-rule':spec['fillRule']}))
            for v in spec['lines']:
                c,a=paint(v['paint']);g.append(element('path',{'d':v['path'],'fill':'none','stroke':c,'stroke-opacity':a,'stroke-width':v['width'],'stroke-linecap':['round','butt','square'][v['cap']],'stroke-linejoin':['round','bevel','miter'][v['join']]}))
        elif rec[0]==37:
            spec=text_style(*rec);g.set('data-source-text-style',json.dumps(spec,ensure_ascii=False));warnings.append({'source':doc['path'],'id':cid,'unrestored':'Text fields exported as metadata; no substitute original font metrics claimed'})
        else:raise ValueError('Unsupported original display tag '+str(rec[0]))
        return g
    drawings={}
    # These are individual source components, never a newly designed game menu.
    selections=[('settings-entry','IGMBottomBar',18,(-10,-15,100,100),('notifMC',)),
                ('setting-help-button','SettingInfo',12,(-10,0,330,130),('_Hit',)),
                ('breakaway-button-group','SettingInfo',25,(-10,-15,300,130),('_Disable','_Hit')),
                ('settings-background','library',lib['symbols']['new_big_bg'],(0,0,880,560),()),
                ('settings-tabs-board','WindowStack',19,(0,0,100,500),()),
                ('settings-tab-component-frame1','library',lib['symbols']['IGM_LJ_STACK_1'],(-10,-10,100,100),('SelectedEff','NewTag'))]
    for name,n,cid,box,omit in selections:
        svg=element('svg',{'viewBox':' '.join(map(str,box)),'width':box[2],'height':box[3]});defs=element('defs');svg.append(defs);wrap=element('g',{'transform':'scale(0.05)'});wrap.append(draw(docs[n],cid,defs,omit_names=omit));svg.append(wrap)
        filename=name+'.svg';(out/filename).write_bytes(ET.tostring(svg,encoding='utf-8'));drawings[name]={'file':filename,'sourceSWF':docs[n]['path'],'sourceId':cid,'viewBox':box,'omitted':list(omit)}
    configs=_ini_blocks(load('ui/Config/interface_common_2.ini'));selected=[v for v in configs if v.get('name')in('IGMContainer','IGMBottomBar','IGMEntrance','SettingHouse','Setting','LanguageSetting','SettingScreen','SettingInfo')]
    keys=['GENERAL_FREEBAR_SETTING','GENERAL_SET_INFO_TITLE','GENERAL_SET_INFO_BTN_HELP','GENERAL_SET_INFO_BTN_BREAK','GENERAL_SET_INFO_BREAKAWAY','GENERAL_SET_INFO_TIP_BREAK','GENERAL_DUNGEON_ASK_QUIT','GENERAL_DEATH_QUIT_SOLO_DUNGEON','GENERAL_BREAK_AWAY_WARNING','GENERAL_TIPS_MAP_3_113']
    en=decode_localized_names(load('tables/String_General_.tbl'),'EN')['values'];zh=decode_localized_names(load('tables/String_General_zh.tbl'),'SC')['values'];ids={v:k for k,v in en.items()};strings={k:{'id':ids[k],'text':zh[ids[k]]}for k in keys}
    def text_metadata(doc,cid):
        kind,raw=doc['records'][cid];style=text_style(kind,raw);bits=Bits(raw,2);bits.rect();at=bits.pos();flags=int.from_bytes(raw[at:at+2],'big')
        font=next((r for r in doc['fonts']if int.from_bytes(r[:2],'little')==style['fontId']),None)
        if font is None:raise ValueError('Original text font declaration absent')
        font_flags=font[2];count=font[4];font_name=font[5:5+count].rstrip(b'\0').decode()
        return {**style,'flagsHex':hex(flags),'wordWrap':bool(flags&0x4000),'multiline':bool(flags&0x2000),'readOnly':bool(flags&0x800),'autoSize':bool(flags&0x40),'noSelect':bool(flags&0x10),'html':bool(flags&2),'useOutlines':bool(flags&1),'fontName':font_name,'fontBold':bool(font_flags&1),'fontItalic':bool(font_flags&2),'runtimeGlobalFontReplacementProven':False}
    def graphic_bounds(doc,cid,omit=(),transform=(1,0,0,1,0,0)):
        kind,raw=doc['records'][cid];points=[]
        if kind==39:
            for p in sprite_frames(doc,cid)[0]:
                if p.get('name')in omit or p['colorTransform']['multiply'][3]==0:continue
                dd,cc=resolve(doc,p,lib);b=graphic_bounds(dd,cc,omit,compose(transform,p['matrixTwips']))
                if b:points.extend([(b[0],b[1]),(b[2],b[3])])
        elif kind in(2,22,32,83):
            x0,x1,y0,y1=shape(kind,raw,extended=True)['boundsTwips'];a,b,c,d,x,y=transform
            points=[(a*xx+c*yy+x,b*xx+d*yy+y)for xx,yy in((x0,y0),(x0,y1),(x1,y0),(x1,y1))]
        if not points:return None
        return [min(p[0]for p in points),min(p[1]for p in points),max(p[0]for p in points),max(p[1]for p in points)]
    fields={}
    for root,doc,paths in[(27,docs['IGMBottomBar'],['_settingBtn']),(41,docs['SettingInfo'],['m_Title','m_MainPanel.m_Help','m_MainPanel.m_Help._Title','m_MainPanel.m_Help._Hit','m_HelpPanel.mc_bounds','m_HelpPanel.mc_content.m_BreakAway','m_HelpPanel.mc_content.m_BreakAway._Title._Text','m_HelpPanel.mc_content.m_BreakAway._Detail','m_HelpPanel.mc_content.m_BreakAway._Tip','m_HelpPanel.mc_content.m_BreakAway._GroupBtn._Button','m_HelpPanel.mc_content.m_BreakAway._GroupBtn._Button._Title','m_HelpPanel.mc_content.m_BreakAway._GroupBtn._Button._Hit'])]:
        for p in paths:
            q=named_path(doc,root,p,lib);leaf=next(v for v in docs.values()if v['path']==q['leafSWF'])
            if leaf['records'][q['leafCharacterId']][0]==37:q['textStyle']=text_metadata(leaf,q['leafCharacterId'])
            fields[doc['path']+':'+p]=q
    gear=graphic_bounds(docs['IGMBottomBar'],18,('notifMC',));gear_pixels=[v/20 for v in gear]
    tab_graphic=graphic_bounds(lib,lib['symbols']['IGM_LJ_STACK_1'],('SelectedEff','NewTag'))
    for filename in('option_info.png','option_setting.png','option_language.png','option_account.png'):
        bitmap('ui/icons/userinterface/'+filename)
    a=parse_abc(extract_abc(load('ui/Flash/IGM.swf')));cls=next(c for c in a['classes']if c['name']=='IGM');b=a['bodies'][cls['iinit']];igm_init=disassemble(b['code'],a,b['exceptions'])
    result={'format':'oc2-original-unstuck-ui-v1','sourceStage':[1136,640],'drawings':drawings,'assets':assets,'strings':strings,'configs':selected,'fields':fields,'methods':methods,'igmInitializer':igm_init,
        'sourceTabs':{'order':['Setting','LanguageSetting','SettingScreen','SettingInfo'],'informationIndex':3,'authoredOrigin':[0,222.3],'localScale':[1,1],'component':'library.swf:IGM_LJ_STACK_1','componentFrame1GraphicBoundsTwips':tab_graphic,'textLabelPresentInOnItemSet':False,'runtimeSelection':'WindowStack.onItemSelect -> SwitchTab; original list/controller/device transforms remain inputs'},
        'gearBounds':{'componentGraphicPixelsWithoutNotification':gear_pixels,'bottomBarGraphicPixelsWithoutNotification':[gear_pixels[0]+50.5,gear_pixels[1]+48.65,gear_pixels[2]+50.5,gear_pixels[3]+48.65],'boundsOrder':'xmin,ymin,xmax,ymax','filtersExpandBounds':False,'bottomBarGlobalPosition':'config relativepos(1,1): (screenWidth-measuredWidth,screenHeight-measuredHeight); requires original measuring object/device scale; not a fixed HUD position','visibility':'IGMBottomBar.onShow -> onCreate; onHide -> onDestory; actual show/event input and notification state not supplied'},
        'windowPositionEquations':{'container':'IGMContainer config origin(0,0),scale1,modalAlpha0.35; WindowContainerIGM.onShow determines child position','settingHouse':'child.x=(screenWidth-measuredScaledWidth)/2; child.y=(screenHeight-TopBar.height-measuredScaledHeight)/2+TopBar.height','settingHouseDynamicMeasure':'WindowStack.init uses first child scale*880 by scale*560; original list/bounds measurement retained in full methods','settingInfoChild':'WindowStack.onSubLoadComlete sets child scale from config(1),x=0,y=0; calls init/initString','tabsBoard':'_TabsForStack authored x=0,y=0; WindowStack.init sets TabBoard.height=565; original frame1/tab item placement is retained, not recentered','background':'SettingInfo Window_SettingInfoInfo: library new_big_bg authored identity at(0,0); original drawing bounds retained'} ,
        'layoutBoundary':{'helpAuthoredOrigin':[101.25,102.35],'breakAwayAuthoredOrigin':[75.8,76], 'breakAwayButtonAuthoredOrigin':[309.65,143.65],'actualButtonY':'m_BreakAway._GroupBtn.y = m_BreakAway._Detail.y + m_BreakAway._Detail.textHeight','buttonLabelY':'SettingBtn.SetTitle sets height=textHeight+10; y=_Hit.y+(_Hit.height-height)*0.5','finalChineseFlashTextHeightKnown':False},
        'warnings':warnings,'limits':['This is an isolated original-component inspector, not a restored game menu or Flash runtime.','Source artwork/affine transforms are retained; text fields stay metadata. Font rasterization, localized textHeight, controller/list movement and device scaling remain unresolved.','No invented final button coordinates, confirmation for map5, destination, cooldown or eligibility policy.','Notification visibility/state and original bottom-bar show/hide inputs are not supplied.'], 'sourceProofs':s.proofs}
    (out/'unstuck-ui.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    cards=''.join('<figure><figcaption>'+html.escape(n)+'</figcaption><img src="'+v['file']+'" alt="'+n+'"></figure>'for n,v in drawings.items())
    (out/'index.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><title>原脱离卡死 UI 资源取证</title><style>body{background:#222;color:#ddd;font:16px sans-serif}figure{border:1px solid #555;padding:12px}img{max-width:880px;display:block}pre{white-space:pre-wrap}</style><h1>原脱离卡死 UI 资源取证</h1><p>只读组件；文字保留元数据，未重建运行菜单或传送规则。</p>'+cards+'<pre>'+html.escape(json.dumps({'strings':strings,'layoutBoundary':result['layoutBoundary']},ensure_ascii=False,indent=2))+'</pre></html>')
    files=[{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in sorted(out.rglob('*'))if p.is_file()and p.name!='files.json'];(out/'files.json').write_text(json.dumps(files,indent=2)+'\n');return result

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--output',type=Path,required=True);a=cli.parse_args();r=recover(a.source,a.output);print(json.dumps({'output':str(a.output),'drawings':list(r['drawings']),'sourceFiles':len(r['sourceProofs']),'finalChineseFlashTextHeightKnown':False}))
if __name__=='__main__':main()
