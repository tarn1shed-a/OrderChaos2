"""Export original QuestHudNew current-objective artwork and its branch program.

Only the compatible executor's real accepted quest is bound. This does not
recover original task approval, automatic routing, or the tutorial202 script.
Original drawings, text and full instructions remain in an ignored package.
"""
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

from analyze_native_resources import NativeImage
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from optimized_abc import extract_abc, extract_named_abc, parse_abc, named_method
from tutorial_quest_ui_assets import recover, PINS
from skill_attachments import decode_ftable
from skill_icons import decode_localized_names
from tutorial_map_geometry import local_output

SO = Path(__file__).resolve().parents[1]/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
METHOD_SHA = 'b510e0688ce1cb5e7371ba2ddd1bc495c8c673d247c3cf7f62a06055e41041d5'
ICON_INIT_SHA = '08c5dc8d4346fc4fab2f731db1d510d9e55f6b3bc0d30de637bf562a507b1fd4'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def export(output, source=DEFAULT_SOURCE, library=SO):
    out = local_output(output)
    if out.exists():
        raise ValueError('Preserve previous original-HUD exports')
    s = Sources(source)
    raw = s.read('ui/Flash/QuestHudNew.swf')
    if sha(raw) != PINS['QuestHudNew']:
        raise ValueError('Original QuestHudNew changed')
    abc = parse_abc(extract_abc(raw))
    cls = next(c for c in abc['classes'] if c['name'] == 'QuestHudNew')
    constants = {t['name']: abc['ints'][t['value']] for t in cls['traits']
                 if t['kind'] == 6 and t.get('valueKind') == 3}
    definitions = parse_abc(extract_named_abc(s.read('ui/Flash/mainUI.swf'),'Common/ASDefines'))
    definitions_class = next(c for c in definitions['classes'] if c['name']=='Common::ASDefines')
    languages = {t['name']:definitions['ints'][t['value']] for t in definitions_class['staticTraits']
                 if t['name'] in ('LANG_SC','LANG_AR') and t.get('valueKind')==3}
    method = named_method(abc, 'QuestHudNew', 'SetCurQuestItem')
    if method['codeSHA256'] != METHOD_SHA:
        raise ValueError('Original objective formatting changed')
    image = NativeImage(Path(library).read_bytes())
    if sha(image.read(0x2a6174, 0xbc)) != ICON_INIT_SHA:
        raise ValueError('Original objective-icon initialization changed')
    # Original 2a6174..2a6230 initializes nine consecutive pointer strings;
    # 672d84..672e2c indexes this table by objective type minus one.
    icon_offsets = [0xe22,0xe3f,0xe5f,0xe7b,0xe9f,0xebe,0xedb,0xef9,0xf1a]
    icons = {i+1: image.read(0x1e02000+off,128).split(b'\0')[0].decode()
             for i,off in enumerate(icon_offsets)}
    names = decode_localized_names(s.read('tables/String_Quest_zh.tbl'),'SC')['values']
    rows = sorted([r for r in decode_ftable(s.read('tables/quest_objective.tbl'),'id')['rows']
                   if r['quest_id'] == 461], key=lambda r:r['step'])
    if [(r['obj_type'],r['value']) for r in rows] != [(2,4),(6,0)]:
        raise ValueError('Retrace original ordinary objective sequence')
    generated = out/'source-export'
    profile = recover(s.read, generated, sprite_frames_by_path={'.m_CurQuestPanel.m_LowShap':2})
    target = out/'assets/source-quest-tracking'
    target.mkdir(parents=True)
    drawing = ET.fromstring((generated/'QuestHudNew.svg').read_bytes())
    wrapper = next(n for n in drawing.iter() if n.get('data-quest-window') == 'QuestHudNew')
    window_root = next(n for n in wrapper if n.get('data-source-path') == '')
    # This bounded adapter shows the original current-objective panel only.
    # Unsupported switch/list/pathfinding controls are not replaced or rebound.
    current = next(n for n in window_root if n.get('data-source-path') == '.m_CurQuestPanel')
    for n in list(window_root):
        if n is not current: window_root.remove(n)
    retained = {'.m_CurQuestPanel.m_LowShap','.m_CurQuestPanel.m_QuestItem0'}
    for n in list(current):
        if n.get('data-source-path') not in retained: current.remove(n)
    assets = {}
    xml = ET.tostring(drawing, encoding='utf-8').decode()
    for path, row in profile['assets'].items():
        if row['url'] not in xml: continue
        name = Path(row['url']).name
        new_url = '/assets/source-quest-tracking/'+name
        xml = xml.replace(row['url'], new_url)
        raw = (generated/name).read_bytes()
        (target/name).write_bytes(raw)
        assets[path] = {'url':new_url,'sourceSHA256':sha(raw)}
    steps = []
    for r in rows:
        path = icons[r['obj_type']]; raw=s.read(path); name=sha(raw)[:20]+'.png'
        (target/name).write_bytes(raw)
        assets[path]={'url':'/assets/source-quest-tracking/'+name,'sourceSHA256':sha(raw)}
        steps.append({'sourceId':r['id'],'sourceIndex':r['obj_idx'],'sourceType':r['obj_type'],
                      'step':r['step'],'total':r['value'],'text':names[r['text']],
                      'pathFinding':r['pathfinding'],'icon':path})
    (target/'QuestHudNew.svg').write_text(xml)
    spec=profile['windows']['QuestHudNew']
    result={'format':'oc2-original-ordinary-tracking-v1','sourceSHA256':PINS['QuestHudNew'],
            'questId':461,'window':{k:spec[k]for k in ['config','measuredSize','sourceRoot']},
            'url':'/assets/source-quest-tracking/QuestHudNew.svg','assets':assets,
            'constants':constants,'languages':languages,'method':method,'steps':steps,
            'boundaries':['Actual compatible per-role accepted progress, not original native task messages.',
                          'Original current panel, font metrics, coordinates and SetCurQuestItem branches; browser text bounds are an explicit host boundary.',
                          'Other quest modes, lists, switch buttons, tracking clicks and automatic routing are not attached.'],
            'sources':{'QuestHudNew':sha(s.read('ui/Flash/QuestHudNew.swf')),
                       'objectiveIconInitialization':{'address':'0x2a6174','size':188,'sha256':ICON_INIT_SHA},
                       'nativeLibrary':sha(image.data)},'sourceProofs':s.proofs}
    (target/'tracking.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--source',type=Path,default=DEFAULT_SOURCE)
    p.add_argument('--library',type=Path,default=SO);a=p.parse_args()
    result=export(a.output,a.source,a.library)
    print(json.dumps({'output':str(a.output),'questId':result['questId'],'steps':len(result['steps']),
                      'methodSHA256':result['method']['codeSHA256']},ensure_ascii=False))
