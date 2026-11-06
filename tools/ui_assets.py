"""Export a bounded original SWF UI skin and embedded font subsets.

Gameloft's FWS files contain metadata-only DefineBitsLossless tags. Their
SymbolClass bitmap names identify external RGBA atlases in ui/Texture. Selected
rectangular DefineShape fills provide exact pixel crops; no SWF scripts execute.
Font3 glyphs are original quadratic outlines, not substituted system fonts.
Requires Pillow and fonttools==4.68.0; generated artwork/fonts stay in game-data.
"""
import hashlib
import io
import json
import struct
import zlib
from pathlib import Path

LIBRARY = 'ui/Flash/library.swf'
SELECTION = {
    'buttonGreen': ('buttongreen_192x64', 584),
    'buttonGray': ('buttonyellow_192x64', 567),
    'skillOrb': ('pic_hudsmallcircleskill', 2453),
    'skillFrame': ('skill_frame', 1618),
    'healthRing': ('hud_blood_CIRCLE', 1108),
    'experienceRing': ('hud_exp_black', 2382),
    'healthFill': ('enemtblood2', 2797),
    'manaFill': ('questloadingpanel1', 2148),
    'panelBlue': ('haradon_card_blue_pic', 690),
}
# Bounded set chosen from the actual embedded subsets. No missing glyph is made
# up or taken from another named family. League Gothic supplies all ten digits.
FONT_SOURCES = {
    'leagueGothic': ('League Gothic', [
        'IAP', 'ControllerSchemePopup', 'BattleRecord', 'AdvLevelUp',
        'BattleField', 'ClassicDungeon']),
    'alegreya': ('Alegreya', [
        'Craft', 'DailyGiftPage', 'BattleFieldTeamComplete', 'VIP', 'CardFeed',
        'InviteFriends', 'AgeGating', 'AttributePage', 'CardArchive',
        'ExpandStorage', 'ItemCompare']),
}


class Bits:
    def __init__(self, data, offset=0):
        self.data, self.at = data, offset * 8

    def u(self, size):
        if not 0 <= size <= 32 or self.at + size > len(self.data) * 8:
            raise ValueError('Truncated or invalid SWF bit field')
        value = 0
        for _ in range(size):
            value = (value << 1) | ((self.data[self.at // 8] >> (7 - self.at % 8)) & 1)
            self.at += 1
        return value

    def s(self, size):
        value = self.u(size)
        return value - (1 << size) if size and value & (1 << (size - 1)) else value

    def align(self):
        self.at = (self.at + 7) // 8 * 8

    def pos(self):
        return (self.at + 7) // 8

    def rect(self):
        size = self.u(5)
        values = [self.s(size) for _ in range(4)]
        self.align()
        return values

    def matrix(self):
        a = d = 1
        b = c = 0
        if self.u(1):
            size = self.u(5)
            a, d = self.s(size) / 65536, self.s(size) / 65536
        if self.u(1):
            size = self.u(5)
            b, c = self.s(size) / 65536, self.s(size) / 65536
        size = self.u(5)
        tx, ty = self.s(size), self.s(size)
        self.align()
        return [a, b, c, d, tx, ty]


def tags(data, start, end):
    at = start
    while at < end:
        if at + 2 > end:
            raise ValueError('Truncated SWF tag header')
        word, = struct.unpack_from('<H', data, at)
        kind, size = word >> 6, word & 63
        at += 2
        if size == 63:
            if at + 4 > end:
                raise ValueError('Truncated long SWF tag header')
            size, = struct.unpack_from('<I', data, at)
            at += 4
        if at + size > end:
            raise ValueError('SWF tag exceeds its container')
        yield kind, at, size
        at += size
        if not kind:
            break


def read_swf(data):
    if len(data) < 13 or data[:3] not in (b'FWS', b'CWS'):
        raise ValueError('Unsupported SWF header')
    length, = struct.unpack_from('<I', data, 4)
    if length > 32 * 1024 * 1024:
        raise ValueError('SWF exceeds bounded UI reader limit')
    if data[:3] == b'CWS':
        dec = zlib.decompressobj()
        body = dec.decompress(data[8:], length - 8 + 1)
        if not dec.eof or dec.unused_data or len(body) != length - 8:
            raise ValueError('Invalid compressed SWF extent')
        data = b'FWS' + data[3:8] + body
    if len(data) != length:
        raise ValueError('SWF declared length mismatch')
    bits = Bits(data, 8)
    bits.rect()
    start = bits.pos() + 4
    records, symbols, bitmaps, fonts = {}, {}, {}, []
    for kind, at, size in tags(data, start, len(data)):
        payload = data[at:at + size]
        if kind in (2, 22, 32, 83, 39):
            if size < 2:
                raise ValueError('Truncated SWF character')
            cid, = struct.unpack_from('<H', payload)
            if cid in records:
                raise ValueError('Duplicate SWF character ID')
            records[cid] = (kind, payload)
        elif kind == 20:
            if size != 7:
                raise ValueError('Expected original externalized bitmap metadata')
            cid, fmt, width, height = struct.unpack('<HBHH', payload)
            if fmt != 5 or not width or not height:
                raise ValueError('Unsupported source atlas metadata')
            bitmaps[cid] = (width, height)
        elif kind == 76:
            count, = struct.unpack_from('<H', payload)
            q = 2
            for _ in range(count):
                if q + 2 > len(payload):
                    raise ValueError('Truncated SWF SymbolClass ID')
                cid, = struct.unpack_from('<H', payload, q)
                q += 2
                try:
                    end = payload.index(0, q)
                except ValueError as error:
                    raise ValueError('Unterminated SWF SymbolClass name') from error
                name = payload[q:end].decode('utf-8')
                if name in symbols:
                    raise ValueError('Duplicate SWF SymbolClass name')
                symbols[name] = cid
                q = end + 1
        elif kind == 75:
            fonts.append(payload)
    return {'records': records, 'symbols': symbols, 'bitmaps': bitmaps,
            'fonts': fonts, 'sha256': hashlib.sha256(data).hexdigest()}


def shape_edges(data):
    """Read a style-free SHAPE's directed fill edges, including quadratics."""
    bits = Bits(data)
    fill_bits, line_bits = bits.u(4), bits.u(4)
    x = y = fill0 = fill1 = 0
    edges = []
    for _ in range(100000):
        if bits.u(1):
            straight, size = bits.u(1), bits.u(4) + 2
            start = (x, y)
            if straight:
                if bits.u(1):
                    dx, dy = bits.s(size), bits.s(size)
                elif bits.u(1):
                    dx, dy = 0, bits.s(size)
                else:
                    dx, dy = bits.s(size), 0
                x, y = x + dx, y + dy
                edge = (start, None, (x, y))
            else:
                control = (x + bits.s(size), y + bits.s(size))
                x, y = control[0] + bits.s(size), control[1] + bits.s(size)
                edge = (start, control, (x, y))
            if fill0:
                edges.append((edge[2], edge[1], edge[0]))
            if fill1:
                edges.append(edge)
        else:
            flags = bits.u(5)
            if not flags:
                return edges
            if flags & 1:
                size = bits.u(5)
                x, y = bits.s(size), bits.s(size)
            if flags & 2:
                fill0 = bits.u(fill_bits)
            if flags & 4:
                fill1 = bits.u(fill_bits)
            if flags & 8:
                bits.u(line_bits)
            if flags & 16:
                raise ValueError('Unexpected new styles inside a glyph/rectangle')
    raise ValueError('SWF shape record limit exceeded')


def rectangular_bitmap(payload):
    """Require an actual four-edge rectangle with one bitmap fill and no line."""
    bits = Bits(payload, 2)
    bounds = bits.rect()
    at = bits.pos()
    if payload[at:at + 1] != b'\x01' or payload[at + 1] not in (64, 65, 66, 67):
        raise ValueError('Expected one original bitmap fill')
    bitmap, = struct.unpack_from('<H', payload, at + 2)
    bits = Bits(payload, at + 4)
    matrix = bits.matrix()
    at = bits.pos()
    if payload[at] != 0:
        raise ValueError('Source rectangle unexpectedly has line styles')
    edges = shape_edges(payload[at + 1:])
    xmin, xmax, ymin, ymax = bounds
    expected = {frozenset(pair) for pair in [
        ((xmin, ymin), (xmax, ymin)), ((xmax, ymin), (xmax, ymax)),
        ((xmax, ymax), (xmin, ymax)), ((xmin, ymax), (xmin, ymin))]}
    actual = {frozenset((edge[0], edge[2])) for edge in edges}
    if len(edges) != 4 or any(e[1] is not None for e in edges) or actual != expected:
        raise ValueError('Source bitmap shape is not a complete rectangle')
    a, b, c, d, tx, ty = matrix
    if b or c or a != 20 or d != 20:
        raise ValueError('Only lossless axis-aligned original-size crops are supported')
    values = [(xmin - tx) / a, (ymin - ty) / d,
              (xmax - tx) / a, (ymax - ty) / d]
    if any(abs(value - round(value)) > 1e-9 for value in values):
        raise ValueError('Source crop does not land on whole pixels')
    return bitmap, [int(value) for value in values], matrix, bounds


def sprite_references(swf, cid, seen=None):
    seen = set() if seen is None else seen
    if cid in seen:
        return seen
    seen.add(cid)
    record = swf['records'].get(cid)
    if record and record[0] == 39:
        payload = record[1]
        for kind, at, size in tags(payload, 4, len(payload)):
            if kind == 26 and size >= 5 and payload[at] & 2:
                child, = struct.unpack_from('<H', payload, at + 3)
                sprite_references(swf, child, seen)
            elif kind == 4 and size >= 2:
                child, = struct.unpack_from('<H', payload, at)
                sprite_references(swf, child, seen)
    return seen


def parse_font3(payload):
    if len(payload) < 7:
        raise ValueError('Truncated DefineFont3')
    cid, flags, language, length = struct.unpack_from('<HBBB', payload)
    name = payload[5:5 + length].rstrip(b'\0').decode('utf-8')
    at = 5 + length
    count, = struct.unpack_from('<H', payload, at)
    at += 2
    width, fmt = (4, '<I') if flags & 8 else (2, '<H')
    if not flags & 128 or count > 8192 or at + (count + 1) * width > len(payload):
        raise ValueError('Unsupported DefineFont3 layout/offset table')
    offsets = [struct.unpack_from(fmt, payload, at + i * width)[0] for i in range(count)]
    codes_at, = struct.unpack_from(fmt, payload, at + count * width)
    code_width, code_fmt = (2, '<H') if flags & 4 else (1, '<B')
    layout = at + codes_at + count * code_width
    if (not offsets or offsets[0] < (count + 1) * width
            or any(b <= a for a, b in zip(offsets, offsets[1:]))
            or offsets[-1] >= codes_at or layout + 6 + count * 2 > len(payload)):
        raise ValueError('Invalid DefineFont3 glyph extents')
    ascent, descent, leading = struct.unpack_from('<hhh', payload, layout)
    if ascent <= 0 or descent < 0:
        raise ValueError('Invalid source font metrics')
    advances = struct.unpack_from('<' + 'h' * count, payload, layout + 6)
    glyphs = {}
    for i, start in enumerate(offsets):
        cp, = struct.unpack_from(code_fmt, payload, at + codes_at + i * code_width)
        end = offsets[i + 1] if i + 1 < count else codes_at
        if cp in glyphs:
            raise ValueError('Duplicate code point inside original font subset')
        glyphs[cp] = {'outline': payload[at + start:at + end], 'advance': advances[i]}
    return {'id': cid, 'name': name, 'flags': flags, 'glyphs': glyphs,
            'ascent': ascent, 'descent': descent, 'leading': leading,
            'sha256': hashlib.sha256(payload).hexdigest()}


def unicode_ranges(codes):
    ranges = []
    for cp in sorted(codes):
        if ranges and cp == ranges[-1][1] + 1:
            ranges[-1][1] = cp
        else:
            ranges.append([cp, cp])
    return ','.join('U+%X' % a if a == b else 'U+%X-%X' % (a, b) for a, b in ranges)


def write_font(fonts, destination, family):
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    glyphs, provenance = {}, []
    for source, font in fonts:
        provenance.append({'path': source, 'fontId': font['id'],
                           'fontTagSHA256': font['sha256'], 'glyphs': len(font['glyphs'])})
        for cp, glyph in font['glyphs'].items():
            # Some SWFs round source coordinates differently. Keep one complete
            # original glyph with its own advance; never average outlines.
            glyphs.setdefault(cp, glyph)
    if not glyphs:
        raise ValueError('No original glyphs recovered')
    scale = lambda p: (round(p[0] / 10), round(-p[1] / 10))
    order, cmap, outlines = ['.notdef'], {}, {'.notdef': TTGlyphPen(None).glyph()}
    metrics = {'.notdef': (1024, 0)}
    for cp, glyph in sorted(glyphs.items()):
        edges = shape_edges(glyph['outline'])
        pen = TTGlyphPen(None)
        while edges:
            edge = edges.pop(0)
            start, position = edge[0], edge[2]
            pen.moveTo(scale(start))
            while True:
                if edge[1] is None:
                    pen.lineTo(scale(position))
                else:
                    pen.qCurveTo(scale(edge[1]), scale(position))
                if position == start:
                    break
                index = next((i for i, e in enumerate(edges) if e[0] == position), None)
                if index is None:
                    raise ValueError(f'Original glyph U+{cp:04X} has an open contour')
                edge = edges.pop(index)
                position = edge[2]
            pen.closePath()
        name = f'uni{cp:04X}'
        original = pen.glyph()
        original.recalcBounds(None)
        order.append(name)
        cmap[cp] = name
        outlines[name] = original
        metrics[name] = (round(glyph['advance'] / 10), getattr(original, 'xMin', 0))
    # DefineFont3 uses 20 times the Font2 em (1024). Scale /10 gives em=2048.
    ascent = round(max(font['ascent'] for _, font in fonts) / 10)
    descent = round(max(font['descent'] for _, font in fonts) / 10)
    builder = FontBuilder(2048, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=ascent, descent=-descent)
    bold = bool(fonts[0][1]['flags'] & 1)
    builder.setupNameTable({'familyName': family, 'styleName': 'Bold' if bold else 'Regular',
        'uniqueFontIdentifier': family + '-original-subset', 'fullName': family,
        'psName': family.replace(' ', '')})
    builder.setupOS2(sTypoAscender=ascent, sTypoDescender=-descent,
        usWinAscent=ascent, usWinDescent=descent, usWeightClass=700 if bold else 400)
    builder.setupPost()
    builder.setupMaxp()
    builder.font.flavor = 'woff'
    builder.save(destination)
    return {'family': family, 'url': '/assets/ui/' + destination.name,
            'format': 'woff', 'weight': 700 if bold else 400,
            'glyphCount': len(cmap), 'unicodeRange': unicode_ranges(cmap),
            'codePoints': sorted(cmap), 'sourceFamily': fonts[0][1]['name'],
            'sources': provenance, 'completeDigits': all(cp in cmap for cp in range(48, 58)),
            'chineseGlyphs': sum(0x4e00 <= cp <= 0x9fff for cp in cmap)}


def recover_ui_assets(extract, output):
    """extract(path) -> Path or bytes; output is the converted-assets root.

    Writes ui/*.png, ui/*.woff and ui/profile.json; returns that profile. The
    caller can expose it at /assets/ui/profile.json. No copyrighted bytes enter
    tracked source files, and no network or Flash runtime is used.
    """
    from PIL import Image
    destination = Path(output) / 'ui'
    destination.mkdir(parents=True, exist_ok=True)
    cache = {}

    def load(path):
        if path not in cache:
            value = extract(path)
            cache[path] = value if isinstance(value, bytes) else Path(value).read_bytes()
        return cache[path]

    swf = read_swf(load(LIBRARY))
    bitmap_names = {cid: name for name, cid in swf['symbols'].items() if cid in swf['bitmaps']}
    assets = {}
    for key, (symbol, shape_id) in SELECTION.items():
        cid = swf['symbols'].get(symbol)
        if cid is None or shape_id not in sprite_references(swf, cid):
            raise ValueError(f'Original UI symbol/shape link missing: {symbol}/{shape_id}')
        kind, payload = swf['records'][shape_id]
        if kind != 2:
            raise ValueError('Selected original bitmap is not DefineShape')
        bitmap, rect, matrix, bounds = rectangular_bitmap(payload)
        name = bitmap_names.get(bitmap)
        if not name or Path(name).name != name:
            raise ValueError('Unsafe or missing original atlas SymbolClass name')
        atlas_path = 'ui/Texture/' + name
        raw = load(atlas_path)
        atlas = Image.open(io.BytesIO(raw))
        if atlas.mode != 'RGBA' or atlas.size != swf['bitmaps'][bitmap]:
            raise ValueError('Original atlas format/dimensions differ from SWF metadata')
        left, top, right, bottom = rect
        if not 0 <= left < right <= atlas.width or not 0 <= top < bottom <= atlas.height:
            raise ValueError('Original crop exceeds atlas bounds')
        piece = atlas.crop(rect)
        filename = key + '.png'
        piece.save(destination / filename)
        assets[key] = {'url': '/assets/ui/' + filename, 'width': piece.width,
            'height': piece.height, 'sourceSymbol': symbol, 'sourceSpriteId': cid,
            'sourceShapeId': shape_id, 'sourceBitmapId': bitmap, 'sourceSWF': LIBRARY,
            'sourceAtlas': atlas_path, 'sourceAtlasSHA256': hashlib.sha256(raw).hexdigest(),
            'sourceRect': rect, 'sourceMatrixTwips': matrix, 'sourceBoundsTwips': bounds,
            'mode': 'lossless-source-atlas-crop'}
    fonts = {}
    for key, (source_name, stems) in FONT_SOURCES.items():
        found = []
        for stem in stems:
            path = 'ui/Flash/' + stem + '.swf'
            parsed = read_swf(load(path))
            matching = [payload for payload in parsed['fonts'] if len(payload) >= 5
                        and payload[5:5 + payload[4]].rstrip(b'\0').decode('utf-8') == source_name]
            matches = [parse_font3(payload) for payload in matching]
            if len(matches) != 1:
                raise ValueError(f'Expected one source font {source_name} in {path}')
            found.append((path, matches[0]))
        if len({font['flags'] & 3 for _, font in found}) != 1:
            raise ValueError('Original font style variants must not be merged')
        fonts[key] = write_font(found, destination / (key + '.woff'), 'OC2 ' + source_name)
    profile = {'format': 'oc2-original-ui-v1', 'assets': assets,
        'fonts': {'status': 'original-embedded-subsets', 'faces': fonts,
                  'chineseStatus': 'incomplete-use-system-fallback',
                  'chineseFallback': 'PingFang SC, Microsoft YaHei, Noto Sans CJK SC, sans-serif'},
        'provenance': {'librarySHA256': swf['sha256'], 'swfScriptExecution': False,
            'bitmapMapping': 'SymbolClass -> external DefineBitsLossless atlas -> rectangular fill matrix',
            'fontConversion': 'DefineFont3 quadratic outlines /10, y flipped; original advances; em 2048',
            'limitations': ['Selected art is reused in a web layout; original complete Flash UI behavior is not restored.',
                'Only embedded font glyphs exist; Chinese text and unavailable Latin glyphs require fallback.',
                'Font conversion preserves original quadratic outlines and advances; kerning and hinting are not restored.',
                'No nine-slice coordinates or spell-icon meanings are inferred from artwork.']}}
    (destination / 'profile.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    return profile
