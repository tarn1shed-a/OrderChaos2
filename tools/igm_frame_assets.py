"""Verified WindowContainerIGM frame, source drawings and QuestListHero mounting."""
import hashlib,io,json
from pathlib import Path
from PIL import Image
from hud_assets import document,sprite_frames,named_path,_ini_blocks
from optimized_abc import extract_abc,parse_abc,named_method
from swf_ui_graphics import display_tree,bounds,text_style

METHODS={
 'init':'5f5d815ae3ece2aabc726e45b756b6ca2de2cc99f688cc24b9c51a153874599a',
 'onShow':'05b02533674ea94ebb8f9b097bafd8afc4ec592803aead552996c82e4072ed3f',
 'onClose':'983ee1d46fb7e3bac12c6da1cd945dd50f3d7fdbc6c18b78d8e837dcd63ee3a5',
 'getElementSize':'2e84e142a7cee35fd109325ef2b28441a291f9900c6b532e26926477ea333d3f',
 'onSubLoadComlete':'72d84c712812bfb70fc77272a034ea53f4326fd21fa3c29708f19853ea3dc22f',
 'SetCurrentSelect':'98ac1e490cf85532027698c6b796a0b39beb9fabe5e35a6a37050e6c220579d1',
}
def recover_igm_frame(extract,output):
    loaded={}
    def load(path):
        if path not in loaded:
            value=extract(path);loaded[path]=bytes(value) if isinstance(value,(bytes,bytearray)) else Path(value).read_bytes()
        return loaded[path]
    lib=document(load('ui/Flash/library.swf'),'ui/Flash/library.swf',False)
    doc=document(load('ui/Flash/WindowContainerIGM.swf'),'ui/Flash/WindowContainerIGM.swf')
    page=document(load('ui/Flash/QuestListHero.swf'),'ui/Flash/QuestListHero.swf')
    abc=parse_abc(extract_abc(load(doc['path'])));methods={}
    for name,digest in METHODS.items():
        m=named_method(abc,'WindowContainerIGM',name)
        if m['codeSHA256']!=digest:raise ValueError('IGM frame method changed; retrace required')
        methods[name]={k:v for k,v in m.items() if k!='instructions'}
    rows=_ini_blocks(load('ui/Config/interface_common_2.ini'))
    container=next(v for v in rows if v.get('name')=='IGMContainer');child=next(v for v in rows if v.get('name')=='QuestListHero')
    if container['url']!='WindowContainerIGM.swf' or child['parent']!='IGMContainer' or float(container['scale'])!=1 or float(child['scale'])!=1:raise ValueError('IGM frame config changed')
    if lib['symbols']['new_big_bg']!=1353 or lib['symbols']['button_igmlittlelisticonback']!=2770:raise ValueError('IGM source art links changed')
    # These placements connect the drawings to this particular empty-list page.
    # Unknown transforms cannot silently become a newly designed web layout.
    placements={'pageRoot':sprite_frames(page,100)[0][0],
        'pageBackground':sprite_frames(page,99)[0][0],
        'back':next(p for p in sprite_frames(doc,12)[0] if p.get('name')=='m_RealBtn'),
        'separator':next(p for p in sprite_frames(doc,12)[0] if p.get('characterId')==10)}
    if any(p['matrixPixels']!=[1,0,0,1,0,0] for p in placements.values()):raise ValueError('IGM drawing placement changed')
    if placements['pageBackground'].get('className')!='new_big_bg' or placements['back'].get('className')!='button_igmlittlelisticonback':raise ValueError('IGM drawing binding changed')
    drawings={'background':display_tree(lib,1353,lib),'back':display_tree(lib,2770,lib),'topbar':display_tree(doc,5,lib),'separator':display_tree(doc,10,lib)}
    bitmaps=set()
    def collect(n):
        if n['kind']=='group':
            for c in n['children']:collect(c['node'])
        else:
            for p in [v['paint'] for v in n['fills']]+[v['paint'] for v in n['lines']]:
                if p['kind']=='bitmap':
                    if p['sourceType']!=66:raise ValueError('IGM bitmap mode needs renderer recovery')
                    bitmaps.add(p['bitmapId'])
    for n in drawings.values():collect(n)
    assets={};destination=Path(output)/'ui';destination.mkdir(parents=True,exist_ok=True)
    for identifier in sorted(bitmaps):
        names=[name for name,cid in lib['symbols'].items() if cid==identifier]
        if len(names)!=1 or Path(names[0]).name!=names[0]:raise ValueError('Unknown IGM bitmap namespace')
        path='ui/Texture/'+names[0];raw=load(path);im=Image.open(io.BytesIO(raw))
        if im.size!=lib['bitmaps'][identifier] or im.mode!='RGBA':raise ValueError('IGM atlas metadata mismatch')
        im.verify();filename=f'igm-atlas-{identifier}.png';(destination/filename).write_bytes(raw)
        assets[str(identifier)]={'url':'/assets/ui/'+filename,'width':im.width,'height':im.height,'sourcePath':path,
            'sourceSHA256':hashlib.sha256(raw).hexdigest(),'mode':'unchanged-full-source-png'}
    empty=named_path(page,0,'emptybtn',lib);box=bounds(display_tree(page,empty['leafCharacterId'],lib));m=empty['matrixPixels']
    if m[1] or m[2]:raise ValueError('Rotated IGM measuring box not supported')
    page_size=[(box[2]-box[0])/20*m[0],(box[3]-box[1])/20*m[3]]
    title=named_path(doc,0,'closeButton.m_BtnName',lib);title_local=named_path(doc,12,'m_BtnName',lib)
    title_style=text_style(*doc['records'][title['leafCharacterId']])
    result={'format':'oc2-source-igm-frame-v1','methods':methods,'placements':placements,'drawings':drawings,'assets':assets,
        'drawingBounds':{k:bounds(v) for k,v in drawings.items()},'title':{'placement':title_local,'style':title_style},
        'layout':{'containerScale':float(container['scale']),'pageScale':float(child['scale']),'pageSize':page_size,
            'closeX':0,'closeY':-5,'closeSize':[120,72],'topbarX':-100,'topbarHeight':62,'topbarExtraWidth':100,
            'modalAlpha':float(container['modalBgAlpha']),'pagePlacement':'x=(screenWidth-pageWidth)/2; y=(screenHeight-topbarHeight-pageHeight)/2+topbarHeight',
            'runtimeOverridesAuthoredClosePosition':True,'sourceStagePixels':doc['stagePixels']},
        'sources':{k:{'bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()} for k,v in loaded.items()},
        'limitations':['Source vectors, bitmap matrices, gradients and color transforms are retained. SVG rasterization, font fallback and source text shadow filters are not proven pixel-identical to Flash.',
            'Configuration scale=1 and source placement equations are used literally. Runtime DPI scaling and Player_EnableBlur kernel remain unresolved; no guessed CSS blur or responsive reflow.',
            'Only the current direct QuestListHero empty-list branch is mounted. Other IGM pages/navigation history and source UI sounds remain pending.']}
    (destination/'igm-frame.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
