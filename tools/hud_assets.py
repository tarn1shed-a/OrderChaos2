"""Recover bounded original HUD art, display-list transforms and vector masks.

This is a static reader, not a Flash runtime. Only observed PlaceObject2/3
fields and simple solid/bitmap shapes are supported; unknown placement options
fail rather than being skipped. Frontend anchoring and percentage-to-frame
selection remain explicit web adaptations. Original files stay in game-data.
"""
import copy
import hashlib
import io
import json
import math
import re
import struct
import zlib
from pathlib import Path

from ui_assets import Bits, read_swf, tags, rectangular_bitmap, shape_edges

IDENTITY = [1, 0, 0, 1, 0, 0]
IDENTITY_COLOR = {'multiply': [256] * 4, 'add': [0] * 4}
SWFS = ('library', 'Gauges2', 'PlayerGauges', 'EnemyGauges', 'OperationPanel2', 'ShortCutBar2', 'ExpBar')
CONFIG = 'ui/Config/interface_common_2.ini'
TUTORIAL = 'ui/Config/tuto_display.ini'
# Source library Sprite -> exact source shape. The colors below are original
# PlaceObject CXFORMWITHALPHA values, not chosen web palette replacements.
ART = {
    'selfHealthArc': ('hud_blood', 2399, None),
    'selfCenterBackground': ('hud_exp_black', 2382, None),
    'playerInteractionButton': ('PlayerGaugesbutton1', 2621, None),
    'healthArcBackground': ('hud_blood_black', 2557, None),
    'healthRingGreen': ('hud_blood_CIRCLE', 1108, None),
    'healthRingRed': ('hud_blood_CIRCLE', 1108,
                      {'multiply': [256] * 4, 'add': [255, -100, 0, 0]}),
    'skillSlotBackground': ('pic_hudsmallcircleskill', 2453, None),
    'skillSelectedFrame': ('IGMequipmenticoninput3', 467, None),
    'attackBackground': ('pic_hudbigcircleattack_2', 2294, None),
    'interactionBackground': ('pic_hudhalfcirclejump_new', 2284, None),
    'skillTrack': ('button_track', 2287, None),
    'experienceFill': ('expbar_blue', 2388,
                       {'multiply': [256, 256, 0, 256], 'add': [255, 0, 0, 0]}),
    'experienceGlow': ('Exp_yellow', 2384, None),
}


def compose(parent, child):
    """Column-vector affine matrices, retaining SWF twip translations."""
    a, b, c, d, x, y = parent
    e, f, g, h, u, v = child
    return [a*e+c*f, b*e+d*f, a*g+c*h, b*g+d*h, a*u+c*v+x, b*u+d*v+y]


def pixels(matrix):
    return matrix[:4] + [matrix[4] / 20, matrix[5] / 20]


def _u16(data, at):
    if at + 2 > len(data):
        raise ValueError('Truncated SWF uint16')
    return struct.unpack_from('<H', data, at)[0]


def _string(data, at):
    try:
        end = data.index(0, at)
        value = data[at:end].decode('utf-8')
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError('Invalid SWF terminated UTF-8 string') from error
    return value, end + 1


def _color(bits):
    add, multiply, size = bits.u(1), bits.u(1), bits.u(4)
    result = {'multiply': [bits.s(size) for _ in range(4)] if multiply else [256]*4,
              'add': [bits.s(size) for _ in range(4)] if add else [0]*4}
    bits.align()
    return result


def placement(kind, data):
    """Parse known PlaceObject2/3 fields with strict extents and filter sizes."""
    if kind not in (26, 70) or len(data) < (4 if kind == 70 else 3):
        raise ValueError('Unsupported/truncated HUD placement')
    flags, extra = data[0], data[1] if kind == 70 else 0
    if flags & 128 or extra & ~15:
        # This deliberately excludes the modified HasImage record on the unused
        # library root. Its omitted class string must not shift our field reads.
        raise ValueError('Unsupported HUD clip actions/image/placement flags')
    at = 2 if kind == 70 else 1
    result = {'tag': kind, 'depth': _u16(data, at), 'move': bool(flags & 1)}
    at += 2
    if extra & 8:
        result['className'], at = _string(data, at)
    if flags & 2:
        result['characterId'] = _u16(data, at)
        at += 2
    if flags & 4:
        bits = Bits(data, at)
        result['matrixTwips'] = bits.matrix()
        at = bits.pos()
    if flags & 8:
        bits = Bits(data, at)
        result['colorTransform'] = _color(bits)
        at = bits.pos()
    if flags & 16:
        result['ratio'] = _u16(data, at)
        at += 2
    if flags & 32:
        result['name'], at = _string(data, at)
    if flags & 64:
        result['clipDepth'] = _u16(data, at)
        at += 2
        if result['clipDepth'] <= result['depth']:
            raise ValueError('Invalid HUD mask clip depth')
    if extra & 1:
        if at >= len(data):
            raise ValueError('Truncated HUD filter count')
        count, at = data[at], at + 1
        filters = []
        for _ in range(count):
            if at >= len(data):
                raise ValueError('Truncated HUD filter ID')
            fid, at = data[at], at + 1
            size = {0: 23, 1: 9, 2: 15}.get(fid)
            if size is None or at + size > len(data):
                raise ValueError('Unsupported/truncated HUD filter layout')
            filters.append({'id': fid, 'sourceBytes': data[at:at+size].hex()})
            at += size
        result['filters'] = filters
    for flag, name in ((2, 'blendMode'), (4, 'bitmapCache')):
        if extra & flag:
            if at >= len(data):
                raise ValueError('Truncated HUD placement option')
            result[name], at = data[at], at + 1
    if at != len(data):
        raise ValueError('Unknown trailing HUD placement data')
    return result


def timeline(data, start, frame_count):
    if not 1 <= frame_count <= 1024:
        raise ValueError('HUD frame count outside bounded reader')
    state, frames = {}, []
    ended = False
    for kind, at, size in tags(data, start, len(data)):
        payload = data[at:at+size]
        if kind in (26, 70):
            update = placement(kind, payload)
            depth = update['depth']
            if update['move']:
                if depth not in state:
                    raise ValueError('HUD placement moves an absent depth')
                item = copy.deepcopy(state[depth])
            else:
                item = {'matrixTwips': list(IDENTITY), 'colorTransform': copy.deepcopy(IDENTITY_COLOR)}
            item.update(update)
            item['matrixPixels'] = pixels(item['matrixTwips'])
            state[depth] = item
        elif kind == 28:
            if size != 2:
                raise ValueError('Invalid HUD RemoveObject2 extent')
            state.pop(_u16(payload, 0), None)
        elif kind in (4, 5):
            raise ValueError('Legacy HUD placement/removal is not supported')
        elif kind == 1:
            if size or len(frames) >= frame_count:
                raise ValueError('HUD ShowFrame count/extent mismatch')
            frames.append(copy.deepcopy([state[key] for key in sorted(state)]))
        elif kind == 0:
            if size or at != len(data):
                raise ValueError('Invalid HUD End tag extent')
            ended = True
    if not ended or len(frames) != frame_count:
        raise ValueError('HUD timeline does not match declared frame count')
    return frames


def document(raw, path, root=True):
    source = read_swf(raw)
    data = raw if raw[:3] == b'FWS' else b'FWS' + raw[3:8] + zlib.decompress(raw[8:])
    bits = Bits(data, 8)
    stage = bits.rect()
    at = bits.pos()
    if at + 4 > len(data):
        raise ValueError('Truncated HUD SWF movie header')
    rate, count = struct.unpack_from('<HH', data, at)
    at += 4
    source.update(path=path, sourceSHA256=hashlib.sha256(raw).hexdigest(),
                  stageTwips=stage, stagePixels=[value/20 for value in stage],
                  frameRate=rate/256, frameCount=count, timelines={}, scalingGrids={})
    source['root'] = timeline(data, at, count) if root else None
    # read_swf intentionally inventories only artwork records. Keep EditText
    # bounds here so named target/name fields retain their original rectangles.
    for kind, pos, size in tags(data, at, len(data)):
        payload = data[pos:pos+size]
        if kind == 37:
            source['records'][_u16(payload, 0)] = (kind, payload)
        elif kind == 78:
            bits = Bits(payload, 2)
            rect = bits.rect()
            if bits.pos() != len(payload):
                raise ValueError('Unknown HUD ScalingGrid trailing data')
            source['scalingGrids'][_u16(payload, 0)] = rect
    return source


def sprite_frames(doc, cid):
    if cid == 0:
        if doc['root'] is None:
            raise ValueError('Unused library root is intentionally not parsed')
        return doc['root']
    if cid not in doc['timelines']:
        kind, payload = doc['records'].get(cid, (None, None))
        if kind != 39 or len(payload) < 4:
            raise ValueError('Expected a defined original HUD Sprite')
        doc['timelines'][cid] = timeline(payload, 4, _u16(payload, 2))
    return doc['timelines'][cid]


def resolve(doc, item, library):
    if 'characterId' in item:
        return doc, item['characterId']
    name = item.get('className')
    if name in doc['symbols']:
        return doc, doc['symbols'][name]
    if name in library['symbols']:
        return library, library['symbols'][name]
    raise ValueError(f'Unresolved original HUD class: {name}')


def named_path(doc, cid, name, library):
    chain, combined = [], list(IDENTITY)
    for segment in name.split('.'):
        items = [item for item in sprite_frames(doc, cid)[0] if item.get('name') == segment]
        if len(items) != 1:
            raise ValueError(f'Missing/ambiguous original HUD named path: {name}')
        item = items[0]
        combined = compose(combined, item['matrixTwips'])
        chain.append({'sourceSWF': doc['path'], 'sourceSpriteId': cid, **item})
        doc, cid = resolve(doc, item, library)
    bounds = None
    record = doc['records'].get(cid)
    if record and record[0] in (2, 22, 32, 37, 83):
        bounds = Bits(record[1], 2).rect()
    return {'path': name, 'sourceSWF': chain[0]['sourceSWF'], 'chain': chain,
            'matrixTwips': combined, 'matrixPixels': pixels(combined),
            'leafSWF': doc['path'], 'leafCharacterId': cid,
            'leafBoundsTwips': bounds, 'leafBoundsPixels': [v/20 for v in bounds] if bounds else None}


def rectangle_bitmap(payload):
    """Accept exact rectangles subdivided by a source ScalingGrid as well."""
    try:
        return (*rectangular_bitmap(payload), 4)
    except ValueError:
        pass
    bits = Bits(payload, 2)
    bounds = bits.rect()
    at = bits.pos()
    if at + 4 > len(payload) or payload[at] != 1 or payload[at+1] not in (64,65,66,67):
        raise ValueError('HUD crop needs exactly one original bitmap fill')
    bitmap = _u16(payload, at+2)
    bits = Bits(payload, at+4)
    matrix = bits.matrix()
    at = bits.pos()
    if at >= len(payload) or payload[at] != 0:
        raise ValueError('HUD rectangular crop cannot contain line styles')
    edges = shape_edges(payload[at+1:])
    xmin, xmax, ymin, ymax = bounds
    sides = [[], [], [], []]
    for start, control, end in edges:
        x, y = start
        u, v = end
        if control is not None or start == end:
            raise ValueError('HUD crop is not an axis-aligned rectangular perimeter')
        if y == v == ymin: index, low, high = 0, min(x,u), max(x,u)
        elif y == v == ymax: index, low, high = 1, min(x,u), max(x,u)
        elif x == u == xmin: index, low, high = 2, min(y,v), max(y,v)
        elif x == u == xmax: index, low, high = 3, min(y,v), max(y,v)
        else: raise ValueError('HUD crop contains a non-perimeter edge')
        sides[index].append((low, high))
    for index, side in enumerate(sides):
        expected_low, expected_high = (xmin,xmax) if index < 2 else (ymin,ymax)
        previous = expected_low
        for low, high in sorted(side):
            if low != previous or high <= low:
                raise ValueError('HUD crop perimeter has gaps or overlaps')
            previous = high
        if previous != expected_high:
            raise ValueError('HUD crop perimeter is incomplete')
    a,b,c,d,tx,ty = matrix
    if abs(a) != 20 or abs(d) != 20 or b or c:
        raise ValueError('HUD atlas crop would resample or rotate original pixels')
    xs, ys = [(xmin-tx)/a,(xmax-tx)/a], [(ymin-ty)/d,(ymax-ty)/d]
    rect = [min(xs),min(ys),max(xs),max(ys)]
    if any(value != round(value) for value in rect):
        raise ValueError('HUD atlas crop has a fractional pixel boundary')
    return bitmap, [int(v) for v in rect], matrix, bounds, len(edges)


def vector_shape(kind, payload, bitmap_as_mask=False):
    if kind not in (2, 22, 32):
        raise ValueError('HUD mask is not a supported solid vector shape')
    bits = Bits(payload, 2)
    bounds = bits.rect()
    at = bits.pos()
    channels = 4 if kind == 32 else 3
    if at + 3 + channels > len(payload) or payload[at] != 1:
        raise ValueError('HUD mask needs one fill')
    fill = payload[at+1]
    metadata = {}
    if fill == 0:
        metadata['sourceFillRGBA'] = list(payload[at+2:at+2+channels]) + ([] if channels==4 else [255])
        at += 2 + channels
    elif fill in (64,65,66,67) and bitmap_as_mask:
        metadata['sourceBitmapId'] = _u16(payload,at+2)
        bits = Bits(payload,at+4)
        metadata['sourceBitmapMatrixTwips'] = bits.matrix()
        at = bits.pos()
    else:
        raise ValueError('HUD mask fill style is unsupported')
    if payload[at] != 0:
        raise ValueError('HUD mask line styles are unsupported')
    edges = shape_edges(payload[at+1:])
    paths = []
    while edges:
        edge = edges.pop(0)
        start, position = edge[0], edge[2]
        contour = [('M', start)]
        for _ in range(10000):
            contour.append(('L', position) if edge[1] is None else ('Q', edge[1], position))
            if position == start:
                break
            index = next((i for i,e in enumerate(edges) if e[0] == position), None)
            if index is None:
                raise ValueError('Original HUD mask has an open fill contour')
            edge = edges.pop(index)
            position = edge[2]
        else:
            raise ValueError('HUD vector contour limit exceeded')
        contour.append(('Z',))
        paths.append(contour)
    def svg(divisor):
        return ' '.join(command[0] + (' ' + ' '.join(f'{v/divisor:g}' for point in command[1:] for v in point)
                                      if len(command)>1 else '') for contour in paths for command in contour)
    return {**metadata, 'pathPixels': svg(20), 'pathTwips': svg(1), 'boundsTwips': bounds,
            'boundsPixels': [v/20 for v in bounds], 'fillRule': 'nonzero'}


def mask_shapes(doc, item, library, parent=None, depth=0):
    if depth > 8:
        raise ValueError('HUD mask hierarchy limit exceeded')
    matrix = compose(parent or IDENTITY, item['matrixTwips'])
    doc, cid = resolve(doc, item, library)
    kind, payload = doc['records'].get(cid, (None, None))
    if kind == 39:
        leaves = []
        for child in sprite_frames(doc, cid)[0]:
            leaves.extend(mask_shapes(doc, child, library, matrix, depth+1))
        return leaves
    result = vector_shape(kind, payload)
    return [{'sourceSWF': doc['path'], 'sourceShapeId': cid,
             'matrixTwips': matrix, 'matrixPixels': pixels(matrix), **result}]


def progress_clip(doc, cid, library):
    frames = sprite_frames(doc, cid)
    recovered = []
    for number, frame in enumerate(frames, 1):
        masks = []
        for item in frame:
            if 'clipDepth' in item:
                masks.extend(mask_shapes(doc, item, library))
        recovered.append({'frame': number, 'masks': masks})
    return {'sourceSWF': doc['path'], 'sourceSpriteId': cid,
            'frameCount': len(frames), 'frames': recovered,
            'sourceTimelineOnly': True, 'scriptExecuted': False}


def self_health_clip(library, color):
    """Equivalent clip of original animated bitmap geometry, not an invented arc."""
    frames = sprite_frames(library,2448)
    recovered, reference = [], None
    for number, frame in enumerate(frames,1):
        if len(frame) != 1 or frame[0]['matrixTwips'] != IDENTITY:
            raise ValueError('Self HP bitmap timeline layout changed')
        item = frame[0]
        kind,payload = library['records'][item['characterId']]
        shape = vector_shape(kind,payload,bitmap_as_mask=True)
        bitmap = (shape['sourceBitmapId'],shape['sourceBitmapMatrixTwips'])
        if reference is None: reference = bitmap
        if bitmap != reference:
            raise ValueError('Self HP frames do not share the same source bitmap mapping')
        recovered.append({'frame':number,'masks':[{'sourceSWF':library['path'],
            'sourceShapeId':item['characterId'], 'matrixTwips':IDENTITY,
            'matrixPixels':pixels(IDENTITY), **shape}]})
    return {'sourceSWF':library['path'],'sourceSpriteId':2448,'sourceRole':'self-health',
        'sourceOwnerSWF':'ui/Flash/Gauges2.swf','sourceOwnerPath':'HP.HP_instance',
        'frameCount':len(frames),'viewBox':[0,0,125,125],
        'content':{'asset':'selfHealthArc','width':59,'height':125,'matrixPixels':pixels(IDENTITY),
            'colorTransform':{**color,'multiplyUnit':256,'colorSpace':'sRGB'}},
        'frames':recovered,'sourceTimelineOnly':True,'sourceTimelineGeometryAsClip':True,
        'scriptExecuted':False,'webMapping':{'mode':'nearest-source-frame',
            'formula':'1+round((1-clamp(ratio,0,1))*49)','zeroBehavior':'hide-all-color',
            'ratioOrder':'descending',
            'sourceFirstFrame':'full left half arc','sourceLastFrame':'near-empty bottom sliver',
            'mappingIsWebAdaptation':True}}


def _art_bounds(matrix, width, height):
    a,b,c,d,x,y = pixels(matrix)
    points = [(a*u+c*v+x,b*u+d*v+y) for u,v in [(0,0),(width,0),(0,height),(width,height)]]
    xs,ys = zip(*points)
    bounds = [min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys)]
    return {'boundsPixels':bounds,'centerPixels':[bounds[0]+bounds[2]/2,bounds[1]+bounds[3]/2],
            'matrixPixels':pixels(matrix)}


def _ini_blocks(raw):
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError('Invalid HUD INI encoding') from error
    blocks, current = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith((';','#')):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = {'section': line[1:-1]}
            blocks.append(current)
        elif '=' in line and current is not None:
            key, value = (v.strip() for v in line.split('=',1))
            if key in current:
                raise ValueError('Duplicate HUD INI field')
            current[key] = value
        else:
            raise ValueError('Unsupported HUD INI layout')
    return blocks


def _tint(image, color):
    if color is None:
        return image
    from PIL import Image
    bands = []
    for band, multiply, add in zip(image.split(), color['multiply'], color['add']):
        table = [max(0,min(255,math.floor(value*multiply/256+add))) for value in range(256)]
        bands.append(band.point(table))
    return Image.merge('RGBA', bands)


def recover_hud_assets(extract, output):
    """extract(path)->Path/bytes; output is the converted-assets root."""
    from PIL import Image
    cache = {}
    def load(path):
        if path not in cache:
            value = extract(path)
            cache[path] = value if isinstance(value, bytes) else Path(value).read_bytes()
        return cache[path]
    docs = {stem: document(load('ui/Flash/'+stem+'.swf'), 'ui/Flash/'+stem+'.swf', root=stem!='library')
            for stem in SWFS}
    library = docs['library']
    output = Path(output)/'ui'
    output.mkdir(parents=True, exist_ok=True)
    bitmap_names = {cid:name for name,cid in library['symbols'].items() if cid in library['bitmaps']}
    assets = {}
    for key,(symbol,shape_id,color) in ART.items():
        owner = library['symbols'].get(symbol)
        if owner is None or shape_id not in [item.get('characterId') for item in sprite_frames(library,owner)[0]]:
            raise ValueError('Original HUD bitmap Sprite/shape link mismatch')
        kind, payload = library['records'][shape_id]
        if kind != 2:
            raise ValueError('Original HUD atlas shape type changed')
        bitmap, rect, matrix, bounds, segments = rectangle_bitmap(payload)
        atlas_name = bitmap_names.get(bitmap)
        if not atlas_name or Path(atlas_name).name != atlas_name:
            raise ValueError('Unsafe or missing HUD atlas bitmap symbol')
        path = 'ui/Texture/'+atlas_name
        raw = load(path)
        atlas = Image.open(io.BytesIO(raw))
        if atlas.mode != 'RGBA' or atlas.size != library['bitmaps'][bitmap]:
            raise ValueError('HUD atlas differs from original bitmap metadata')
        left,top,right,bottom = rect
        if not 0 <= left < right <= atlas.width or not 0 <= top < bottom <= atlas.height:
            raise ValueError('Original HUD crop exceeds atlas bounds')
        image = atlas.crop(rect)
        if matrix[0] < 0: image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if matrix[3] < 0: image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        filename = 'hud'+key[0].upper()+key[1:]+'.png'
        image.save(output/filename)
        assets[key] = {'url':'/assets/ui/'+filename, 'width':image.width, 'height':image.height,
            'sourceSWF':library['path'], 'sourceSWFSHA256':library['sourceSHA256'],
            'sourceSymbol':symbol, 'sourceSpriteId':owner, 'sourceShapeId':shape_id,
            'sourceBitmapId':bitmap, 'sourceAtlas':path, 'sourceAtlasSHA256':hashlib.sha256(raw).hexdigest(),
            'sourceRect':rect, 'sourceMatrixTwips':matrix, 'sourceBoundsTwips':bounds,
            'sourcePerimeterSegments':segments, 'sourceScalingGridTwips':library['scalingGrids'].get(owner),
            'sourceColorTransform':color,'colorTransformBaked':False,
            'sourceFlipX':matrix[0]<0,'sourceFlipY':matrix[3]<0,
            'mode':'lossless-source-atlas-crop-flipped' if matrix[0]<0 or matrix[3]<0 else 'lossless-source-atlas-crop'}
    fields = {
        'self': ('Gauges2',0,['HP','HP.HP_instance','MP_Default','MP_Mage','MP_Warrior','MP_Slayer','MP_Monk','enterMap']),
        'player': ('PlayerGauges',114,['playerIcon','hpGreenProgressBar','hpRedProgressBar','targetNameTextField','targetLevelTextField','PlayerInteractionBtn']),
        'target': ('EnemyGauges',17,['m_enemyIcon','TargetName','hpYellow','hpRed','hpGreen']),
        'operations': ('OperationPanel2',0,['Spellbtn.SpellSlot0']+['Spellbtn.spellSlots.SpellSlot'+str(i) for i in range(1,5)]+['Interactionbtn']),
        'shortcuts': ('ShortCutBar2',0,['shortcutlist.item_0.item'+str(i) for i in range(6)]),
        'experience': ('ExpBar',0,['expMc']),
    }
    layouts = {}
    for key,(stem,cid,names) in fields.items():
        doc = docs[stem]
        layouts[key] = {'sourceSWF':doc['path'], 'sourceSWFSHA256':doc['sourceSHA256'],
            'sourceSpriteId':cid, 'stageTwips':doc['stageTwips'], 'stagePixels':doc['stagePixels'],
            'frameRate':doc['frameRate'], 'instances':sprite_frames(doc,cid)[0],
            'fields':{name:named_path(doc,cid,name,library) for name in names}}
    layouts['self']['sourceRole'] = 'self-gauges-with-map-center-and-class-resource-arcs'
    layouts['self']['portraitIsWebAdaptation'] = True
    layouts['self']['omittedLocalGameplay'] = ['MP_Default','MP_Mage','MP_Warrior','MP_Slayer','MP_Monk','enterMap']
    layouts['player']['sourceRole'] = 'selected-player-target'
    layouts['player']['portraitSlot'] = _art_bounds(layouts['player']['fields']['playerIcon']['matrixTwips'],48,48)
    operation_slots = {}
    for index in range(5):
        name = 'Spellbtn.SpellSlot0' if index==0 else 'Spellbtn.spellSlots.SpellSlot'+str(index)
        leaf = named_path(docs['OperationPanel2'],0,name+'.slotBtn',library)
        source_cid = leaf['leafCharacterId']
        expected = 2307 if index==0 else 2613
        if source_cid != expected:
            raise ValueError('Original operation slot class differs from expected source art')
        first = sprite_frames(library,source_cid)[0][0]
        matrix = compose(leaf['matrixTwips'],first['matrixTwips'])
        asset = 'attackBackground' if index==0 else 'skillSlotBackground'
        art = assets[asset]
        operation_slots[str(index)] = {'path':name,'asset':asset,**_art_bounds(matrix,art['width'],art['height'])}
    layouts['operations']['slots'] = operation_slots
    track = named_path(docs['OperationPanel2'],0,'Spellbtn.spellSlots.bg',library)
    layouts['operations']['track'] = {'asset':'skillTrack',**_art_bounds(track['matrixTwips'],259,212)}
    rectangles = [slot['boundsPixels'] for slot in operation_slots.values()] + [layouts['operations']['track']['boundsPixels']]
    x,y = math.floor(min(r[0] for r in rectangles)),math.floor(min(r[1] for r in rectangles))
    layouts['operations']['suggestedViewportPixels'] = [x,y,
        math.ceil(max(r[0]+r[2] for r in rectangles))-x,
        math.ceil(max(r[1]+r[3] for r in rectangles))-y]
    layouts['operations']['viewportIsWebCrop'] = True
    # Slot internals establish the icon/cooldown/lock semantics independently of
    # any guesses based on appearance. Keep the original transforms and filters.
    layouts['skillSlot'] = {'sourceSWF':library['path'],'sourceSpriteId':2541,
        'instances':sprite_frames(library,2541)[0]}
    layouts['attackSlot'] = {'sourceSWF':library['path'],'sourceSpriteId':2307,
        'instances':sprite_frames(library,2307)[0]}
    progress = {}
    for key,cid,asset in [('healthGreen',49,'healthRingGreen'),('healthRed',64,'healthRingRed')]:
        clip = progress_clip(docs['PlayerGauges'],cid,library)
        clip.update(viewBox=[0,0,84,84], content={'asset':asset,'width':125,'height':125,
            'matrixPixels':[0.649993896484375,0,0,0.649993896484375,1,1.2]},
            webMapping={'mode':'nearest-source-frame','formula':'1+round(clamp(ratio,0,1)*38)',
                        'ratioOrder':'ascending',
                        'zeroBehavior':'hide-all-color','sourceFirstFrame':'near-empty thin needle',
                        'sourceLastFrame':'full circle','mappingIsWebAdaptation':True})
        clip['sourceRole'] = 'selected-player-target'
        clip['content']['colorTransform'] = {**(IDENTITY_COLOR if key=='healthGreen' else
            {'multiply':[256]*4,'add':[255,-100,0,0]}),'multiplyUnit':256,'colorSpace':'sRGB'}
        progress['selectedPlayerHealthGreen' if key=='healthGreen' else 'selectedPlayerHealthRed'] = clip
    self_color = layouts['self']['fields']['HP.HP_instance']['chain'][-1]['colorTransform']
    progress['healthGreen'] = self_health_clip(library,self_color)
    progress['cooldownAttack'] = progress_clip(docs['OperationPanel2'],61,library)
    progress['cooldownSkill'] = progress_clip(docs['OperationPanel2'],99,library)
    for key,cid,source_shape in [('cooldownAttack',61,22),('cooldownSkill',99,63)]:
        doc = docs['OperationPanel2']
        kind,payload = doc['records'][source_shape]
        shape = vector_shape(kind,payload)
        progress[key]['content'] = {'kind':'source-vector','sourceShapeId':source_shape,
            'sourceSWF':doc['path'],'matrixPixels':pixels(IDENTITY),**shape}
        progress[key]['webMapping'] = {'mode':'nearest-source-frame','ratioOrder':'ascending',
            'zeroBehavior':'hide-all-color','mappingIsWebAdaptation':True}
        bounds = shape['boundsPixels']
        progress[key]['viewBox'] = [bounds[0],bounds[2],bounds[1]-bounds[0],bounds[3]-bounds[2]]
    progress['experience'] = progress_clip(docs['ExpBar'],98,library)
    progress['experience'].update(asset='experienceFill',
        sourceMeaning='ExpBar root expMc, 101 mask frames with increasing horizontal scale',
        viewBox=[0,0,1136,8],
        content={'asset':'experienceFill','width':250,'height':8,
            'matrixPixels':[4.54400634765625,0,0,1,0,-.25],
            'colorTransform':{'multiply':[256,256,0,256],'add':[255,0,0,0],
                              'multiplyUnit':256,'colorSpace':'sRGB'}},
        webMapping={'ratioFillIsWebAdaptation':True,'sourceFullWidthPixels':1136,
                    'ratioOrder':'ascending','mappingIsWebAdaptation':True})
    config, tutorial = load(CONFIG), load(TUTORIAL)
    wanted = {'Gauges','PlayerGauges','EnemyGauges','OperationPanel','ShortCutBar','ExpBar'}
    anchors = [block for block in _ini_blocks(config) if block.get('name') in wanted]
    expected_urls = {'Gauges2.swf','PlayerGauges.swf','EnemyGauges.swf','OperationPanel2.swf','ShortCutBar2.swf','ExpBar.swf'}
    if {block.get('url') for block in anchors} != expected_urls or len(anchors) != 6:
        raise ValueError('Original common_2 HUD component configuration changed')
    tutorials = [block for block in _ini_blocks(tutorial) if block.get('tutorial_id') in
                 {'TUTORIAL_ATTACK_NORMAL','TUTORIAL_ATTACK_SKILL'}]
    expected_paths = {'TUTORIAL_ATTACK_NORMAL':'Spellbtn.SpellSlot0',
                      'TUTORIAL_ATTACK_SKILL':'Spellbtn.spellSlots.SpellSlot1'}
    if {row['tutorial_id']:row.get('symbol_name') for row in tutorials} != expected_paths:
        raise ValueError('Original tutorial skill-slot semantic binding changed')
    profile = {'format':'oc2-original-hud-v1','assets':assets,'layouts':layouts,'progress':progress,
        'anchors':{'source':CONFIG,'sections':anchors,'interpretation':'Raw source relative positions; frontend responsive placement is an adaptation.'},
        'semantics':{'attack':{'source':TUTORIAL,'bindings':tutorials},
            'health':'Gauges2.HP.HP_instance is self HP; PlayerGauges green/red are selected-player-target fields, not self layers.',
            'selectedPlayerRedMeaning':'Source name/tint proven; delayed-damage versus other semantics not established.',
            'experience':'ExpBar root expMc; hud_exp_dh belongs to magicBar and is not reused as XP.',
            'skillFields':['DisplayIconForSkill','CooldownForSkill','IsLockedForSkill','HitzoneForSkill'],
            'localGameplayHasMP':False,'unusedSourceControlsAreNotImplementedGameplay':True},
        'provenance':{'sources':{path:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for path,data in cache.items()},
            'swfScriptExecution':False,'timelineReader':'PlaceObject2/3, masks, affine matrices, source color transforms; no ActionScript execution',
            'limitations':['Local source timelines and common_2 configuration do not prove every device override or original runtime layout.',
                'Percentage-to-source-frame selection and responsive web anchoring are explicit adaptations.',
                'Original MP/vehicle/interaction/consumable systems are not added to the local prototype.',
                'Portrait content is provided separately; the source playerIcon placeholder is not a static portrait.']}}
    (output/'hud.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2))
    return profile
