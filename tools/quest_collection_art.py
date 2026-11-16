"""Export original Channelbar timelines and shared artwork as one SVG atlas.

No quest state, timer, character, server or reward rule is created. Full artwork
and timelines stay private. The paired morph reader projects original masks;
it does not substitute a new rectangular progress bar.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
from xml.etree import ElementTree as ET
import zlib
from PIL import Image

from hud_assets import document, sprite_frames, resolve, compose, _ini_blocks
from login_ui_assets import element, matrix, rgba
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from swf_ui_graphics import shape
from swf_morph_pairs import morph_shape
from ui_assets import Bits, tags

ROOT = Path(__file__).resolve().parents[1]
BASE = '/assets/source-quest461-channel-v1/'
PINS = {'Channelbar': '61e43d93416010dd07fd6e3f6a3c8ace1bd906a219367dcb58f9c01af61eda47',
        'library': 'd984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89'}
digest = lambda raw: hashlib.sha256(raw).hexdigest()


def recover(source, output):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT / 'analysis/raw') or output.exists():
        raise ValueError('New ignored original artwork output required')
    output.mkdir(parents=True)
    sources, docs = Sources(source), {}
    for name, pin in PINS.items():
        path = 'ui/Flash/' + name + '.swf'
        raw = sources.read(path)
        if digest(raw) != pin:
            raise ValueError('Original Channelbar drawing source differs: ' + name)
        doc = docs[name] = document(raw, path, name != 'library')
        data = b'FWS' + raw[3:8] + zlib.decompress(raw[8:]) if raw[:3] == b'CWS' else raw
        bits = Bits(data, 8)
        bits.rect()
        for kind, at, length in tags(data, bits.pos() + 4, len(data)):
            if kind == 46:
                doc['records'][struct.unpack_from('<H', data, at)[0]] = (kind, data[at:at+length])
    channel, library = docs['Channelbar'], docs['library']
    if channel['stagePixels'] != [0, 340, 0, 48] or channel['frameRate'] != 24:
        raise ValueError('Original Channelbar stage differs')
    svg = element('svg', {'viewBox': '0 0 6800 960', 'width': 340, 'height': 48})
    defs = element('defs')
    svg.append(defs)
    serial, assets, patterns = 0, {}, {}
    def unique():
        nonlocal serial
        serial += 1
        return 'channel-art-' + str(serial)
    def png(doc, bitmap):
        names = [n for n, cid in doc['symbols'].items() if cid == bitmap]
        if len(names) != 1 or Path(names[0]).name != names[0]:
            raise ValueError('Original bitmap name is ambiguous')
        path = 'ui/Texture/' + names[0]
        if path not in assets:
            raw = sources.read(path)
            image = Image.open(io.BytesIO(raw))
            image.verify()
            if tuple(image.size) != doc['bitmaps'][bitmap]:
                raise ValueError('Original PNG metadata differs')
            name = digest(raw) + '.png'
            (output / name).write_bytes(raw)
            assets[path] = {'file': name, 'url': BASE + name, 'sha256': digest(raw),
                            'bytes': len(raw), 'size': list(image.size)}
        return assets[path]
    def paint(doc, value):
        if value['kind'] == 'solid':
            return rgba(value['color']), value['color'][3] / 255
        if value['kind'] != 'bitmap':
            raise ValueError('Uncovered original Channelbar paint type')
        asset = png(doc, value['bitmapId'])
        key = json.dumps([asset['sha256'], value['matrix'], value['sourceType']])
        if key not in patterns:
            pid = unique()
            patterns[key] = pid
            w, h = asset['size']
            node = element('pattern', {'id': pid, 'patternUnits': 'userSpaceOnUse',
                                       'width': w, 'height': h, 'patternTransform': matrix(value['matrix'])})
            node.append(element('image', {'href': asset['url'], 'width': w, 'height': h,
                                          'image-rendering': 'auto' if value['sourceType'] < 66 else 'pixelated'}))
            defs.append(node)
        return 'url(#' + patterns[key] + ')', 1
    def flatten(node, clip, parent=(1, 0, 0, 1, 0, 0)):
        local = node.get('transform')
        combined = compose(parent, list(map(float, local[7:-1].split()))) if local else parent
        if node.tag.rsplit('}', 1)[-1] == 'path':
            leaf = ET.fromstring(ET.tostring(node))
            leaf.set('transform', matrix(combined))
            leaf.set('fill-opacity', '1')
            leaf.set('clip-rule', leaf.get('fill-rule', 'evenodd'))
            clip.append(leaf)
        else:
            for child in node:
                flatten(child, clip, combined)
    def draw(doc, cid, frame=1, ratio=0, depth=0):
        if depth > 16:
            raise ValueError('Original Channelbar recursion bound')
        kind, raw = doc['records'][cid]
        group = element('g', {'data-source-file': doc['path'], 'data-source-id': cid})
        if kind == 39:
            frames = sprite_frames(doc, cid)
            if not 1 <= frame <= len(frames):
                raise ValueError('Original source frame unavailable')
            masks = []
            for row in frames[frame-1]:
                if row.get('filters') or row.get('blendMode', 1) not in (0, 1):
                    raise ValueError('Uncovered original Channelbar placement effect')
                dd, ii = resolve(doc, row, library)
                child = draw(dd, ii, ratio=row.get('ratio', 0), depth=depth+1)
                child.set('transform', matrix(row['matrixTwips']))
                color = row['colorTransform']
                if color != {'multiply': [256]*4, 'add': [0]*4}:
                    key = unique()
                    filt = element('filter', {'id': key, 'color-interpolation-filters': 'sRGB'})
                    values = []
                    for r in range(4):
                        values.extend([color['multiply'][r]/256 if r == j else 0 for j in range(4)] + [color['add'][r]/255])
                    filt.append(element('feColorMatrix', {'type': 'matrix', 'values': ' '.join(map(str, values))}))
                    defs.append(filt)
                    child.set('filter', 'url(#' + key + ')')
                masks = [(end, key) for end, key in masks if row['depth'] <= end]
                if 'clipDepth' in row:
                    key = unique()
                    clip = element('clipPath', {'id': key, 'clipPathUnits': 'userSpaceOnUse'})
                    flatten(child, clip)
                    if not len(clip):
                        raise ValueError('Original mask geometry unresolved')
                    defs.append(clip)
                    masks.append((row['clipDepth'], key))
                    continue
                for _, key in masks:
                    wrapper = element('g', {'clip-path': 'url(#' + key + ')'})
                    wrapper.append(child)
                    child = wrapper
                group.append(child)
            return group
        spec = morph_shape(kind, raw, ratio=ratio) if kind == 46 else shape(kind, raw, extended=True)
        for row in spec['fills']:
            color, alpha = paint(doc, row['paint'])
            group.append(element('path', {'d': row['path'], 'fill': color,
                                          'fill-opacity': alpha, 'fill-rule': spec['fillRule']}))
        for row in spec['lines']:
            color, alpha = paint(doc, row['paint'])
            group.append(element('path', {'d': row['path'], 'fill': 'none', 'stroke': color,
                                          'stroke-opacity': alpha, 'stroke-width': row['width'],
                                          'stroke-linecap': ['round', 'butt', 'square'][row['cap']],
                                          'stroke-linejoin': ['round', 'bevel', 'miter'][row['join']]}))
        return group
    clips = {}
    for name, cid, expected in [('bar', 3, 300), ('barInterrupt', 6, 300), ('barFinish', 4, 12)]:
        frames = sprite_frames(channel, cid)
        if len(frames) != expected:
            raise ValueError('Original source clip length differs')
        ids = []
        for number in range(1, len(frames)+1):
            key = name + '-' + str(number)
            symbol = element('g', {'id': key, 'data-source-frame': number, 'data-source-clip': name})
            symbol.append(draw(channel, cid, frame=number))
            defs.append(symbol)
            ids.append(key)
        clips[name] = {'sourceCharacterId': cid, 'frames': ids}
    raw = ET.tostring(svg, encoding='utf-8')
    (output / 'channel.svg').write_bytes(raw)
    config = [r for r in _ini_blocks(sources.read('ui/Config/interface_common_2.ini')) if r.get('name') == 'Channelbar']
    if len(config) != 1:
        raise ValueError('Original Channelbar window config differs')
    manifest = {'format': 'oc2-original-channel-art-v1', 'sourceSHA256': PINS,
                'viewBoxTwips': [0, 0, 6800, 960], 'sourceMovieFrameRate': channel['frameRate'],
                'sourceWindow': config[0], 'sourceRootPlacements': channel['root'][0], 'clips': clips, 'assets': assets,
                'svg': {'file': 'channel.svg', 'url': BASE+'channel.svg', 'bytes': len(raw), 'sha256': digest(raw)},
                'sourceProofs': sources.proofs,
                'scope': {'originalFramesExported': 612, 'originalMasksPreserved': True,
                          'SVGProjectionIsHostAdaptation': True, 'FlashGPUObserved': False,
                          'questOrServerStateChanged': False}}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':'))+'\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = recover(args.source, args.output)
    print(json.dumps({'svg': result['svg'], 'assets': len(result['assets']), 'scope': result['scope']}))
