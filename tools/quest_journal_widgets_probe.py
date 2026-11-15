"""Export bounded original journal component programs and authored geometry.

No Flash root measurement, artwork redraw, UI/service/save or approval.
"""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
AREA=ROOT/'analysis/raw/ordinary-quest-journal-widgets-20261116'
SHA=lambda raw:hashlib.sha256(raw).hexdigest()
PINS={'mainUI':'e18152cbddf51f335ad764fd57c928a990cb0846de05b2628968050e1dcbc0ac',
      'library':'d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89',
      'QuestListHero':'bd5c5a2d392dd63b872104148a74e075f8ec05c887a246015490ed16c95bf851'}


def recover(output):
    from map_loading_evidence import Sources
    from resource_packs import DEFAULT_SOURCE
    from optimized_abc import parse_abc,extract_named_abc,extract_abc,disassemble
    from hud_assets import document,named_path
    from quest_journal_profile import original_bounds
    out=Path(output)
    if out.exists():raise ValueError('Preserve prior widget export')
    s=Sources(DEFAULT_SOURCE);raw={k:s.read('ui/Flash/'+k+'.swf')for k in PINS}
    if any(SHA(raw[k])!=v for k,v in PINS.items()):raise ValueError('Original widget source differs')
    blocks={'PageIndicator':['Common/gluicEx/components/ui/PageIndicator',['InitPageNum','SetCurrPageNum','RealWidth']],
      'ScrollBarNew':['Common/gluicEx/components/ui/ScrollBarNew',['InitBtnHandleByRange','InitBtnHandle']],
      'ScrollBar':['gluic/components/ui/ScrollBar',['getBoundsAndMoveItAllAround','value','capHandlePos','setInitValue','yScroll']],
      'ScrollPane':['gluic/components/ui/ScrollPane',['positionRatioY']],
      'QuestListHero':[None,['foldText','stretchText','onPanelScroll','onStepInfoScroll','SetCurrPageInfo','subInit']]}
    classes={};methods={};dual=[]
    for label,(block,names)in blocks.items():
        a=parse_abc(extract_named_abc(raw['mainUI'],block)if block else extract_abc(raw['QuestListHero']))
        c=next(c for c in a['classes']if c['name'].split('::')[-1]==label)
        def body(mid):
            b=a['bodies'][mid];return{'signature':a['signatures'][mid],'codeSHA256':SHA(b['code']),'instructions':disassemble(b['code'],a,b['exceptions'])}
        constants={}
        for t in c['traits']+c['staticTraits']:
            if t.get('valueKind')in[3,4,6,10,11]:constants[t['name'].split('::')[-1]]=a['ints'][t['value']]if t['valueKind']in[3,4]else a['doubles'][t['value']]if t['valueKind']==6 else t['valueKind']==11
        classes[label]={'name':c['name'],'base':c['super'],'traits':c['traits'],'constants':constants,'constructor':body(c['iinit'])}
        for t in c['traits']:
            name=t['name'].split('::')[-1]
            if'method'in t and name in names:methods[f'{label}.{name}#{t["kind"]}']=body(t['method'])
        if block:
            aa=parse_abc(extract_named_abc(raw['library'],block));cc=next(x for x in aa['classes']if x['name']==c['name'])
            for t in cc['traits']:
                name=t['name'].split('::')[-1];key=f'{label}.{name}#{t["kind"]}'
                if'method'in t and key in methods:
                    h=SHA(aa['bodies'][t['method']]['code'])
                    if h!=methods[key]['codeSHA256']:raise ValueError('Shared component domain code differs')
                    dual.append({'method':key,'mainUIAndLibrarySameSHA256':h})
    # Preserve source aliases and static rectangles; these are not initialized
    # Flash width/getBounds results or a claim of runtime frame selection.
    book=document(raw['QuestListHero'],'ui/Flash/QuestListHero.swf');lib=document(raw['library'],'ui/Flash/library.swf',False)
    def measure(path):
        row=named_path(book,99,path,lib);doc=lib if row['leafSWF']==lib['path']else book
        b=original_bounds(doc,row['leafCharacterId'],lib)
        if b is None:raise ValueError('Missing authored widget geometry')
        b=[v/20 for v in b];m=row['chain'][-1]['matrixPixels']
        if m[1]or m[2]:raise ValueError('Unrecovered skewed widget measurement')
        points=[(m[0]*x+m[4],m[3]*y+m[5])for x in [b[0],b[2]]for y in [b[1],b[3]]]
        xs,ys=zip(*points);rect={'left':min(xs),'right':max(xs),'top':min(ys),'bottom':max(ys)}
        return{'path':path,'sourcePath':row,'authoredLocalBounds':b,'authoredParentBounds':rect,'width':rect['right']-rect['left'],'height':rect['bottom']-rect['top'],
          'x':m[4],'y':m[5],'measurement':'source-authored-first-frame; explicit substitute for unobserved live DisplayObject measurement'}
    pager=measure('m_PageIndiForReward');indicators=[measure('m_PageIndiForReward.mc_Indi'+str(i))for i in range(10)]
    for r in indicators:r['selectionPath']=r['path']+'.SelState';measure(r['selectionPath'])
    bars={name:{'root':measure(name),'slot':measure(name+'.mc_slot'),'handle':measure(name+'.mc_btn_handle')}for name in ['m_Scroll2','m_Scroll3']}
    result={'format':'oc2-original-journal-widgets-v1','sources':PINS,'classes':classes,'methods':methods,'sharedCodeEquality':dual,
      'aliases':{'pager':'mc_Indi0..9 / SelState','scrollbar':{'btn_handle':'mc_btn_handle','slot':'mc_slot','btn_dec':'mc_btn_dec (optional)','btn_inc':'mc_btn_inc (optional)'}},
      'authoredMeasurements':{'pager':pager,'indicators':indicators,'bars':bars},'sourceProofs':s.proofs,
      'limits':['No full original MovieClip initialization/getBounds/textHeight measured','No timer, drag/input, display-list or source event dispatch is implemented','All pure control dimensions use explicit host/source-authored measurement inputs; no new art or task state']}
    out.mkdir(parents=True);p=out/'source-program.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return{'path':str(p),'sha256':SHA(p.read_bytes()),'methods':len(methods),'classes':len(classes),'sharedMethodsMatched':len(dual)}


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=AREA/'source-v1')
    print(json.dumps(recover(p.parse_args().output),ensure_ascii=False,indent=2))
