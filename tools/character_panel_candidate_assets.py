"""Build a separate source-drawn character/skill panel candidate for local QA.

No existing runtime, role or deployment is changed. All original drawings,
icons, localization and generated browser artifacts stay in ignored output.
"""
import argparse
import hashlib
import io
import json
import shutil
from pathlib import Path

from PIL import Image
from attribute_page import source_bounds
from character_panel_candidate_svg import SourcePanelSVG
from character_progression_evidence import TABLES,profession_catalog
from hud_assets import document,resolve,sprite_frames,_ini_blocks
from igm_frame_assets import recover_igm_frame
from login_ui_assets import recover_login_ui
from optimized_abc import extract_abc,parse_abc,named_method
from resource_packs import ResourceArchive,DEFAULT_SOURCE,index,normalize_resource_name
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names

ROOT=Path(__file__).resolve().parents[1]
SOURCE_PINS={
    'ui/Flash/library.swf':'d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89',
    'ui/Flash/AttributePage.swf':'e7ad9fc9b9fd8c1749113c1ca2fa9e9ec00e1261bdaca282cae943a2d38bdc76',
    'ui/Flash/SkillSetting.swf':'3ffab64df48454250c71871c94796a4409af719ca72e6fc6afcc1e2d00ab12bc',
    'ui/Flash/SkillPassive.swf':'93d7ab055dbdd4ae4cd424023d06d0a46b5f5d8bd793cefcc69df68827f3af9d',
    'ui/Flash/WindowStack.swf':'39f53d816b06f9573e8cc0a6b107ac9428f239c7a80bcaaeb63626bc1803dd33',
    'ui/Config/interface_common_2.ini':'08557d51933e3824d77bddbb324d0179be51be01133c1c5ee802ecc5b9fefca0',
    'tables/String_Skill_zh.tbl':'3f27ebc3d3c192fc99c886249a94c91465a12cefd90611809c2a973053e8811b',
    'tables/String_General_.tbl':'fa295450826581bfdf59c4d4b4fecde3e88fdfacbc815d81a31e4cbbe2fefa97',
    'tables/String_General_zh.tbl':'e865387db222af45ff34631b57785c416cf3718590477098ec9fdf9abe0aeb1f',
}


def build(output,source=DEFAULT_SOURCE,runtime=ROOT/'analysis/raw/showcase-20261110/running-preview'):
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'analysis/raw').resolve()):raise ValueError('Original panel candidates stay in ignored analysis/raw/')
    if output.exists():raise ValueError('Refusing to overwrite an existing candidate')
    public=output/'public';assets=public/'assets/character-source';assets.mkdir(parents=True)
    archives={};loaded={};locations={}
    for record in index(source):
        locations.setdefault(normalize_resource_name(record['path']),[]).append(record['pack'])
    def read(path):
        if path not in loaded:
            found=locations.get(normalize_resource_name(path),[])
            if not found:raise KeyError('Missing original resource: '+path)
            copies=[]
            for pack in found:
                if pack not in archives:archives[pack]=ResourceArchive(Path(source)/pack)
                copies.append(archives[pack].read(path))
            if any(raw!=copies[0]for raw in copies):raise ValueError('Ambiguous original resource: '+path)
            loaded[path]=copies[0]
            if path in SOURCE_PINS and hashlib.sha256(loaded[path]).hexdigest()!=SOURCE_PINS[path]:raise ValueError('Pinned original panel source changed: '+path)
        return loaded[path]
    tables={}
    for name,(key,expected)in TABLES.items():
        raw=read('tables/'+name+'.tbl')
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Original panel table changed: '+name)
        tables[name]=decode_ftable(raw,key)
    names=decode_localized_names(read('tables/String_Skill_zh.tbl'),'SC')['values']
    english=decode_localized_names(read('tables/String_General_.tbl'),'EN')['values']
    chinese=decode_localized_names(read('tables/String_General_zh.tbl'),'SC')['values'];ids={v:k for k,v in english.items()}
    general={key:chinese[idx]for key,idx in ids.items()if idx in chinese}
    entry=recover_login_ui(read,public/'assets/source-entry',attributes=True)
    frame=recover_igm_frame(read,public/'assets')
    lib=document(read('ui/Flash/library.swf'),'ui/Flash/library.swf',False)
    docs={name:document(read('ui/Flash/'+name+'.swf'),'ui/Flash/'+name+'.swf')for name in('SkillSetting','SkillPassive','WindowStack')}
    renderer=SourcePanelSVG(read,lib,assets);windows={};methods={};measurements={}
    for name,symbol in [('SkillSetting','symWindowSkillSetting'),('SkillPassive','symWindowSkillPassive'),('WindowStack',None)]:
        doc=docs[name];root=doc['symbols'][symbol]if symbol else 23
        windows[name]=renderer.export(doc,root,name)
        if name!='WindowStack':
            p=next(v for v in sprite_frames(doc,0)[0]if v.get('name')=='emptybtn');dd,cid=resolve(doc,p,lib);b=source_bounds(dd,cid,lib)
            measurements[name]=[(b[2]-b[0])/20*p['matrixPixels'][0],(b[3]-b[1])/20*p['matrixPixels'][3]]
        abc=parse_abc(extract_abc(read('ui/Flash/'+name+'.swf')))
        for method in({'SkillSetting':['initString','initMembers','onShow','ShowSkillDetail','ShowRuneDetail','MakeBtnVariable'],
                        'SkillPassive':['initString','ShowSkillDetail'],
                        'WindowStack':['init','onItemSet','SwitchTab']}[name]):
            methods[name+'.'+method]=named_method(abc,name,method)
    skill_abc=parse_abc(extract_abc(read('ui/Flash/SkillSetting.swf')))
    skill_class=next(c for c in skill_abc['classes']if c['name']=='SkillSetting')
    count_trait=next(t for t in skill_class['traits']if t['name']=='SKILL_COUNT')
    if count_trait['valueKind']!=3:raise ValueError('Original skill count is no longer an int constant')
    skill_count=skill_abc['ints'][count_trait['value']]
    rune_factor=next(i['args'][0]for i in methods['SkillSetting.onShow']['instructions']if i['at']==126 and i['op']=='pushbyte')
    if(skill_count,rune_factor)!=(9,3):raise ValueError('Original skill display capacities changed')
    # SetAttributeValueExp @290..301 first stops its *parent* valueBar on
    # totalFrames. Its child exp has one frame and is then scaled by the ratio.
    # Exporting parent frame 1 clips even a half-full bar to a narrow sliver.
    attr=document(read('ui/Flash/AttributePage.swf'),'ui/Flash/AttributePage.swf')
    prefix='.CharacterAttrPanel.CharacterPanel.mc_content.'
    selected={**entry['attributePage']['iconFrames'],prefix+'Exp.valueBar':60}
    windows['AttributePage']=renderer.export(attr,106,'AttributePage',selected,entry['attributePage']['animatedFrames'])
    entry['windows']['AttributePage'].update(windows['AttributePage'])
    abc=parse_abc(extract_abc(read('ui/Flash/AttributePage.swf')))
    for method in ['SetAttributeValueExp','setMcToPercent','setAttributePlayerClass']:
        methods['AttributePage.'+method]=named_method(abc,'AttributePage',method)
    p=next(v for v in sprite_frames(docs['WindowStack'],23)[0]if v.get('name')=='TabBoard')
    dd,cid=resolve(docs['WindowStack'],p,lib);b=source_bounds(dd,cid,lib)
    sidebar_runtime={'boardPath':'.TabBoard','sourceMatrix':p['matrixTwips'],'sourceBoundsTwips':b,
                     'height':565,'matrix':[1,0,0,565*20/(b[3]-b[1]),0,0],'sourceMethod':'WindowStack.init @296..302'}
    protos={r['skillId']:r for r in tables['skill_proto']['rows']};runes={r['id']:r for r in tables['skill_runes']['rows']}
    icon_assets={}
    def icon(path):
        if path in icon_assets:return icon_assets[path]
        if not path.startswith('ui/icons/')or '..'in path.split('/'):raise ValueError('Unsafe original panel icon path')
        raw=read(path);image=Image.open(io.BytesIO(raw));image.verify()
        if image.size not in((96,96),(48,48)):raise ValueError('Original panel icon dimensions changed')
        digest=hashlib.sha256(raw).hexdigest();filename='icon-'+digest[:20]+'.png';(assets/filename).write_bytes(raw)
        icon_assets[path]={'url':'/assets/character-source/'+filename,'sha256':digest,'bytes':len(raw),
                           'width':image.width,'height':image.height,'sourcePath':path}
        return icon_assets[path]
    catalogs={}
    for profession in range(1,6):
        catalog=profession_catalog(tables,names,profession)
        for skill in catalog:
            proto=protos[skill['skillId']];skill['powerType']=proto['powerType']
            for rune in skill['runes']:
                row=runes[rune['sourceRuneId']]
                rune['description']=names.get(row['descStrId'],'')
                rune['iconAsset']=icon('ui/icons/'+row['icon'])
                rune['stats']={key:row[key]for key in('powerCost','minCastRange','maxCastRange','chantTime','coolDownTime','channelTime','effectRadius')}
        catalogs[str(profession)]=catalog
    configs=_ini_blocks(read('ui/Config/interface_common_2.ini'))
    tabs=[]
    for row in configs:
        if row.get('parent')=='Skill':tabs.append({'name':row['name'],'title':general[row['title']],
                                                 'icon':icon('ui/icons/userinterface/'+row['icon'])})
    class_icons={str(i):icon('ui/icons/userinterface/class_'+name+'.png')for i,name in
                 [(1,'warrior'),(2,'mage'),(3,'ranger'),(4,'monk'),(5,'demonslayer')]}
    attribute_tabs=[{**row,'iconAsset':icon('ui/icons/userinterface/'+row['icon'])}for row in entry['attributePage']['tabs']]
    manifest={'format':'oc2-character-source-panel-candidate-v1','stage':[1136,640],
        'windows':windows,'entry':entry,'frame':frame,'pageSizes':measurements,'catalogs':catalogs,
        'attributeXP':{'parentPath':prefix+'Exp.valueBar','sourceParentSprite':70,'sourceParentFrames':60,'selectedParentFrame':60,'childFrames':1,'sourceMethod':'SetAttributeValueExp @290..301; setMcToPercent @13..32'},
        'skillDisplayCounts':{'active':skill_count,'runes':skill_count*rune_factor,'sourceMethod':'SkillSetting.SKILL_COUNT resolved int pool; onShow @123..144'},
        'classIcons':class_icons,'tabs':tabs,'attributeTabs':attribute_tabs,'general':general,'textFields':renderer.text_fields,'sidebarRuntime':sidebar_runtime,
        'methods':{key:{'codeSHA256':m['codeSHA256']}for key,m in methods.items()},
        'sources':{p:{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}for p,raw in loaded.items()},
        'assets':{**renderer.assets,**icon_assets},'drawingBoundaries':renderer.warnings,
        'boundaries':['Source drawings/positions/text/icons and five-profession catalog only; browser SVG rasterization and text wrapping are adapters.',
                      'Trial role fields remain trial fields. Unknown original XP/skill-point/learning/equipped data stay blank; no progression or learning is granted.',
                      'Prepared preview callback remains caller-owned. This candidate never reads saves, sends skill/cast requests or changes hotkeys.']}
    (assets/'panels.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    pinned=json.loads((ROOT/'tools/local_mvp_runtime.json').read_text())['files']
    module='prototype/public/source-ui-svg.js';raw=(Path(runtime)/module).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pinned[module]:raise ValueError('Reviewed SVG interface source changed')
    (public/'source-ui-svg.js').write_bytes(raw)
    for name in('chineseText.woff','chineseDisplay.woff','leagueGothic.woff'):
        shutil.copyfile(Path(runtime)/'game-data/converted/ui'/name,public/'assets/ui'/name)
    for name in('character-source-panels.mjs','character-source-state.mjs','character-source-panels.css','character-source-qa.mjs'):
        shutil.copyfile(ROOT/'tools/preview'/name,public/name)
    (public/'panel-candidate.html').write_text('<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>混沌与秩序2</title><link rel="stylesheet" href="/character-source-panels.css"><body><script type="module" src="/character-source-qa.mjs"></script></body></html>')
    checksum={str(p.relative_to(public)):hashlib.sha256(p.read_bytes()).hexdigest()for p in public.rglob('*')if p.is_file()}
    (output/'SHA256.json').write_text(json.dumps(checksum,indent=2)+'\n')
    return {'output':str(output),'public':str(public),'catalogs':{k:len(v)for k,v in catalogs.items()},'icons':len(icon_assets),'warnings':len(renderer.warnings)}


def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--output',type=Path,required=True)
    cli.add_argument('--source',type=Path,default=DEFAULT_SOURCE);cli.add_argument('--runtime',type=Path,default=ROOT/'analysis/raw/showcase-20261110/running-preview')
    args=cli.parse_args();print(json.dumps(build(args.output,args.source,args.runtime),ensure_ascii=False))


if __name__=='__main__':main()
