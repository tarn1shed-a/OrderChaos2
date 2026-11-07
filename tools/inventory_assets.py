"""Recover bounded original bag/equipment artwork and named display lists.

No ActionScript is run. Common_2 configuration distinguishes EquipmentPage
(wearing items) from Equipment (crafting). Named slot numbers/positions are
source evidence; body-part names, local capacity and responsive reflow are not.
"""
import hashlib
import io
import json
import math
import struct
from pathlib import Path

from hud_assets import (Bits, _art_bounds, _ini_blocks,
                        document, named_path, rectangle_bitmap, sprite_frames)
from ui_assets import shape_edges, sprite_references

CONFIG = 'ui/Config/interface_common_2.ini'
SWFS = ('library', 'Bag', 'EquipmentPage', 'ItemDetail')
ART = {
    'slotBackground': ('IGMequipmenticoninput4', 466, 465),
    'selectedFrame': ('IGMequipmenticoninput3', 468, 467),
    'qualityGreen': ('Character_green', 470, 469),
    'qualityBlue': ('Character_blue', 472, 471),
    'qualityViolet': ('Character_violet', 474, 473),
    'qualityOrange': ('Character_orange', 476, 475),
    'qualityGold': ('character_gold', 479, 478),
    'goldCoin': ('goldcoin', 2041, 2040),
    'bagIcon': ('igm_bag1', 1446, 1445),
    'equipmentIcon': ('igm_equipment1', 1428, 1427),
    'attackStat': ('iconequipmentinfoatteck', 1305, 1304),
    'lifeStat': ('iconequipmentinfolife', 1303, 1302),
    'armorStat': ('iconequipmentinfoshield', 1301, 1300),
}


def _single_bitmap_rectangle(payload):
    """Read a rectangle whose source bitmap matrix may resample original art."""
    bits = Bits(payload, 2)
    bounds = bits.rect()
    at = bits.pos()
    if payload[at:at+1] != b'\x01' or payload[at+1] not in (64, 65, 66, 67):
        raise ValueError('Inventory texture needs one bitmap fill')
    bitmap, = struct.unpack_from('<H', payload, at+2)
    bits = Bits(payload, at+4)
    matrix = bits.matrix()
    at = bits.pos()
    if payload[at] != 0:
        raise ValueError('Inventory texture cannot contain line styles')
    edges = shape_edges(payload[at+1:])
    xmin, xmax, ymin, ymax = bounds
    expected = {frozenset(pair) for pair in [
        ((xmin, ymin), (xmax, ymin)), ((xmax, ymin), (xmax, ymax)),
        ((xmax, ymax), (xmin, ymax)), ((xmin, ymax), (xmin, ymin))]}
    if (len(edges) != 4 or any(edge[1] is not None for edge in edges) or
            {frozenset((edge[0], edge[2])) for edge in edges} != expected):
        raise ValueError('Inventory texture must be a complete four-edge rectangle')
    a, b, c, d, tx, ty = matrix
    if not a or not d or b or c:
        raise ValueError('Inventory texture requires a nonzero axis-aligned matrix')
    xs, ys = [(xmin-tx)/a, (xmax-tx)/a], [(ymin-ty)/d, (ymax-ty)/d]
    return bitmap, [min(xs), min(ys), max(xs), max(ys)], matrix, bounds


def _source_affine_texture(image, matrix, bounds):
    """Rasterize the proven source rectangle, retaining fractional edge alpha.

    Only the veins source needs this path: its bitmap matrix scales by roughly
    .993 and .991. Calling this a lossless crop would conceal that fact.
    """
    from PIL import Image
    a, b, c, d, tx, ty = matrix
    if not a or not d or b or c:
        raise ValueError('Inventory texture requires a nonzero axis-aligned matrix')
    left, right, top, bottom = [value/20 for value in bounds]
    width, height = math.ceil(right-left), math.ceil(bottom-top)
    if not 0 < width <= 4096 or not 0 < height <= 4096:
        raise ValueError('Inventory texture output dimensions exceed reader bounds')
    result = image.transform((width, height), Image.Transform.AFFINE,
        (20/a, 0, (left*20-tx)/a, 0, 20/d, (top*20-ty)/d),
        resample=Image.Resampling.BICUBIC)
    # Clip the fractional right/bottom edges to the original shape extent.
    alpha = result.getchannel('A')
    pixels = alpha.load()
    x_extent, y_extent = right-left, bottom-top
    for y in range(height):
        y_coverage = min(1, max(0, y_extent-y))
        for x in range(width):
            coverage = min(1, max(0, x_extent-x))*y_coverage
            if coverage < 1:
                pixels[x,y] = round(pixels[x,y]*coverage)
    result.putalpha(alpha)
    return result


def _asset(extract, library, key, symbol, owner, shape_id, output, affine=False):
    from PIL import Image
    if symbol not in library['symbols']:
        raise ValueError('Missing original inventory bitmap SymbolClass')
    if owner not in sprite_references(library,library['symbols'][symbol]):
        raise ValueError('Original inventory symbol does not reference its bitmap owner')
    if shape_id not in [row.get('characterId') for row in sprite_frames(library, owner)[0]]:
        raise ValueError('Original inventory Sprite/shape link changed')
    kind, payload = library['records'][shape_id]
    if kind != 2:
        raise ValueError('Original inventory atlas shape type changed')
    if affine:
        bitmap, rect, matrix, bounds = _single_bitmap_rectangle(payload)
        segments = 4
    else:
        bitmap, rect, matrix, bounds, segments = rectangle_bitmap(payload)
    names = [name for name, cid in library['symbols'].items() if cid == bitmap]
    if len(names) != 1 or Path(names[0]).name != names[0]:
        raise ValueError('Unsafe or ambiguous inventory atlas bitmap symbol')
    path = 'ui/Texture/'+names[0]
    raw = extract(path)
    atlas = Image.open(io.BytesIO(raw))
    if atlas.mode != 'RGBA' or atlas.size != library['bitmaps'][bitmap]:
        raise ValueError('Inventory atlas differs from original bitmap metadata')
    left, top, right, bottom = rect
    if not 0 <= left < right <= atlas.width or not 0 <= top < bottom <= atlas.height:
        raise ValueError('Original inventory crop exceeds source atlas bounds')
    if affine:
        image = _source_affine_texture(atlas, matrix, bounds)
    else:
        image = atlas.crop(rect)
        if matrix[0] < 0: image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if matrix[3] < 0: image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    filename = 'inventory'+key[0].upper()+key[1:]+'.png'
    image.save(output/filename)
    return {'url':'/assets/ui/'+filename,'width':image.width,'height':image.height,
        'sourceSWF':library['path'],'sourceSWFSHA256':library['sourceSHA256'],
        'sourceSymbol':symbol,'sourceSpriteId':owner,'sourceShapeId':shape_id,
        'sourceBitmapId':bitmap,'sourceAtlas':path,
        'sourceAtlasSHA256':hashlib.sha256(raw).hexdigest(),
        'sourceRect':rect,'sourceMatrixTwips':matrix,'sourceBoundsTwips':bounds,
        'sourcePerimeterSegments':segments,
        'sourceScalingGridTwips':library['scalingGrids'].get(owner),
        'sourceFlipX':matrix[0]<0,'sourceFlipY':matrix[3]<0,
        'mode':'source-bitmap-affine-render' if affine else 'lossless-source-atlas-crop',
        'resampling':'bicubic-to-source-shape-pixel-size' if affine else None,
        'colorTransformBaked':False}


def _layout(doc, symbol, fields, library):
    cid = doc['symbols'][symbol]
    return {'sourceSWF':doc['path'],'sourceSWFSHA256':doc['sourceSHA256'],
        'sourceSymbol':symbol,'sourceSpriteId':cid,'stagePixels':doc['stagePixels'],
        'instances':sprite_frames(doc,cid)[0],
        'fields':{path:named_path(doc,cid,path,library) for path in fields}}


def recover_inventory_assets(extract, output):
    """extract(path)->Path/bytes; write ui/inventory.json and 14 PNGs."""
    cache = {}
    def load(path):
        if path not in cache:
            value = extract(path)
            cache[path] = value if isinstance(value,bytes) else Path(value).read_bytes()
        return cache[path]
    docs = {stem:document(load('ui/Flash/'+stem+'.swf'), 'ui/Flash/'+stem+'.swf',root=stem!='library')
            for stem in SWFS}
    library = docs['library']
    output = Path(output)/'ui'
    output.mkdir(parents=True,exist_ok=True)
    assets = {key:_asset(load,library,key,symbol,owner,shape,output)
              for key,(symbol,owner,shape) in ART.items()}
    assets['panelTexture'] = _asset(load,library,'panelTexture','veins',1217,1216,output,affine=True)
    bag = _layout(docs['Bag'],'Window_Bag',
        ['bagPagePlane','bagPagePlane.Mask','bagCapacity','_FilterTitle','_FilterList'],library)
    bag.update(sourceRole='self-bag',columns=8,visibleRows=5,
               visibleRowsAreNotTotalCapacity=True,slots=[])
    for row in range(5):
        for column in range(8):
            path=f'bagPagePlane.item_{row}.Item{column}'
            field=named_path(docs['Bag'],bag['sourceSpriteId'],path,library)
            if field['leafSWF']!=library['path'] or field['leafCharacterId']!=503:
                raise ValueError('Original bag slot class differs from expected source art')
            bag['slots'].append({'index':row*8+column,'row':row,'column':column,
                'path':path,'asset':'slotBackground',**field,
                **_art_bounds(field['matrixTwips'],96,96),
                'x':field['matrixPixels'][4],'y':field['matrixPixels'][5],
                'width':96,'height':96})
    equip_ids = [0,1,2,4,6,7,8,9,13,21]
    equip = _layout(docs['EquipmentPage'],'EquipmentPage_MC',
        ['cnt','cnt.EquipDisplay','cnt.EquipDisplay.objImage','cnt.EquipBaglist','cnt.title_name']+
        ['cnt.EquipSlot'+str(cid) for cid in equip_ids],library)
    equip.update(sourceRole='self-worn-equipment',slots=[],
                 sourceSlotBodyPartMappingRecovered=False,
                 modelPlaceholderIsNotCharacterArtwork=True)
    for cid in equip_ids:
        field=equip['fields']['cnt.EquipSlot'+str(cid)]
        if field['leafSWF']!=library['path'] or field['leafCharacterId']!=1643:
            raise ValueError('Original equipment slot class differs from expected source art')
        equip['slots'].append({'index':cid,'sourceSlotId':cid,'asset':'slotBackground',
            **field,**_art_bounds(field['matrixTwips'],96,96),
            'x':field['matrixPixels'][4],'y':field['matrixPixels'][5],
            'width':96,'height':96})
    model=equip['fields']['cnt.EquipDisplay.objImage']
    shape=docs['EquipmentPage']['records'][27]
    if shape[0]!=32:
        raise ValueError('Original HeroEquip model placeholder shape changed')
    placeholder=Bits(shape[1],2).rect()
    if placeholder!=[0,5081,0,8643]:
        raise ValueError('Original HeroEquip model placeholder bounds changed')
    equip['modelViewport']={'sourceShapeId':27,'sourceBoundsTwips':placeholder,
        'placeholderGeometryOnly':True,
        **_art_bounds(model['matrixTwips'],254.05,432.15)}
    border_kind,border_payload=library['records'][1352]
    if border_kind!=83:
        raise ValueError('Original equipment panel border shape type changed')
    xmin,xmax,ymin,ymax=Bits(border_payload,2).rect()
    equip['backgroundViewport']={'sourceShapeId':1352,'sourceSWF':library['path'],
        'boundsPixels':[xmin/20,ymin/20,(xmax-xmin)/20,(ymax-ymin)/20],
        'meaning':'Source new_big_bg Shape4 border bounds, not whole SWF stage.'}
    detail = _layout(docs['ItemDetail'],'symWindowItemDetail',
        ['txtName','txtBound','txtThirdCat','txtUnique','txtLevel','txtPrice','buttonList','spScroll'],library)
    quality=[]
    for index,frame in enumerate(sprite_frames(library,480),1):
        quality.append({'frame':index,'instances':frame})
    if [[row.get('characterId') for row in frame['instances']] for frame in quality]!=[[],[],[470],[472],[474],[476],[479]]:
        raise ValueError('Original inventory quality frame artwork mapping changed')
    anchors=[block for block in _ini_blocks(load(CONFIG)) if block.get('name') in
             {'BagMenu','Bag','EquipmentPage','BaseInfo','ItemDetail'}]
    expected={'BagMenu':'Bag.swf','Bag':'WindowStack.swf','EquipmentPage':'EquipmentPage.swf',
              'BaseInfo':'WindowStack.swf','ItemDetail':'ItemDetail.swf'}
    if len(anchors)!=5 or {row['name']:row.get('url') for row in anchors}!=expected:
        raise ValueError('Original common_2 bag/equipment component configuration changed')
    profile={'format':'oc2-original-inventory-v1','assets':assets,
        'layouts':{'bag':bag,'equipment':equip,'itemDetail':detail},
        'slotInternals':{
            'bag':{'sourceSWF':library['path'],'sourceSpriteId':503,'instances':sprite_frames(library,503)[0]},
            'equipment':{'sourceSWF':library['path'],'sourceSpriteId':1643,'instances':sprite_frames(library,1643)[0]},
            'quality':{'sourceSWF':library['path'],'sourceSpriteId':480,'frames':quality,
                'sourceFrameArtwork':{'1':None,'2':None,'3':'qualityGreen','4':'qualityBlue',
                                      '5':'qualityViolet','6':'qualityOrange','7':'qualityGold'}}},
        'panel':{'sourceSWF':library['path'],'sourceSymbol':'new_big_bg','sourceSpriteId':1353,
                 'instances':sprite_frames(library,1353)[0],
                 'completePanelRendered':False,
                 'limitation':'Texture is recovered; Shape4 border and gradient fill are retained as source IDs, not rendered as a complete native window.'},
        'anchors':{'source':CONFIG,'sections':anchors},
        'semantics':{'bagCapacity':'Five visible rows are scroll-list viewport rows, not proof of total bag capacity.',
            'equipmentPage':'EquipmentPage_MC.cnt has ten taskitemWithIconequip slots and HeroEquip.objImage; Equipment.swf is crafting UI and excluded.',
            'slotBodyParts':'Only source numeric slot IDs are proven here. Local named equipment slots require an explicit web-game mapping.',
            'localInventoryRulesRecovered':False,'localItemStatsRecovered':False,
            'unusedSourceControlsAreNotImplementedGameplay':True},
        'provenance':{'sources':{path:{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                                 for path,raw in cache.items()},
            'swfScriptExecution':False,
            'limitations':['Common_2 selects self bag and wearing-equipment components; no original server inventory protocol is implemented.',
                'Source numeric equipment IDs do not prove body-part names without separate native/data-table evidence.',
                'Item counts, item names/stats, bag capacity, equip rules and responsive placement belong to the local prototype.',
                'Panel texture is resampled using the original bitmap matrix; it is not a lossless crop or a full native window export.',
                'Original locks, decomposing, expansions, quick-equipment and equipment schemes are recorded but not functional gameplay.']}}
    (output/'inventory.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2))
    return profile
