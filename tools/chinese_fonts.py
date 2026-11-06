"""Preserve the verified loose original CJK fonts as full WOFF containers.

The GBMP archive index has no TTF entries. This build instead loads loose files
under files/ui/Font. Fontin is the native default and Alegreya-Bold is selected
for the Alegreya Bold UI alias. No system font supplies any exported glyph.
Requires the existing fonttools dependency; WOFF1 uses standard zlib only.
"""
import hashlib
import io
import json
from pathlib import Path

from fontTools.ttLib import TTFont, TTLibError

from ui_assets import unicode_ranges


SOURCE_FONTS = {
    'chineseText': {
        'path': 'ui/Font/Fontin.ttf', 'family': 'OC2 Fontin Full',
        'bytes': 9775796,
        'sha256': '4b238fc14857f15968a285adf0de864746ba80fa821b5d5cacb75b69a17b1b61',
        'nativeAlias': 'Fontin', 'webRole': 'body',
        'loaderEvidence': ['0x5df560-0x5df56c: initial default ui/Font/Fontin.ttf',
            '0x5e3050-0x5e3214: Fontin preloaded at 16,18,24,36,42'],
        'swfEvidence': [
            {'path': 'ui/Flash/Amulet.swf', 'editTextId': 99, 'fontId': 76,
             'label': 'Set Bonuses :', 'fontSize': 24},
            {'path': 'ui/Flash/Philosopher.swf', 'editTextId': 33, 'fontId': 17,
             'label': 'Time Limit Today:', 'fontSize': 24}],
    },
    'chineseDisplay': {
        'path': 'ui/Font/Alegreya-Bold.ttf', 'family': 'OC2 Alegreya Full',
        'bytes': 12031036,
        'sha256': '361512a5a3e337bf3f57d998451831539363497390440be0250f00d5d53e5ba4',
        'nativeAlias': 'Alegreya Bold', 'webRole': 'heading-and-name',
        'loaderEvidence': ['0x5df5e4-0x5df5f0: matches Alegreya Bold',
            '0x5df624-0x5df634: selects Alegreya-Bold.ttf',
            '0x5df694-0x5df6b0: prepends ui/Font/',
            '0x5e3218-0x5e33e0: Alegreya Bold preloaded at 20,22,24,30,32'],
        'swfEvidence': [
            {'path': 'ui/Flash/PlayerGauges.swf', 'editTextId': 66, 'fontId': 65,
             'label': 'NPC NAME', 'fontSize': 20, 'bold': True},
            {'path': 'ui/Flash/library.swf', 'editTextId': 1713, 'fontId': 423,
             'label': 'Create New Character', 'fontSize': 24, 'bold': True}],
    },
}
NATIVE_SHA256 = '77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4'
DEFAULT_REQUIRED_TEXT = '混沌与秩序角色生命魔法攻击冰霜爆破火球术联机奖励经验等级金币复活'
CJK_BLOCKS = {
    'unified': (0x4e00, 0x9fff), 'extensionA': (0x3400, 0x4dbf),
    'extensionB': (0x20000, 0x2a6df), 'compatibility': (0xf900, 0xfaff),
}
# Raw sfnt tables are copied into a compressed container. Verify every source
# table, including layout/hinting, except the standard head checksum field.
HEAD_CHECKSUM_SPAN = (8, 12)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _head_without_checksum(raw):
    return raw[:HEAD_CHECKSUM_SPAN[0]] + b'\0' * 4 + raw[HEAD_CHECKSUM_SPAN[1]:]


def _open_font(data):
    if len(data) > 32 * 1024 * 1024 or data[:4] != b'\0\x01\0\0':
        raise ValueError('Expected a bounded original TrueType sfnt font')
    try:
        font = TTFont(io.BytesIO(data), recalcTimestamp=False, lazy=True)
        for tag in ('head', 'maxp', 'cmap', 'name', 'hhea', 'hmtx', 'glyf', 'loca', 'OS/2'):
            if tag not in font:
                raise ValueError(f'Original font lacks required table {tag}')
        return font
    except (TTLibError, KeyError, IndexError) as error:
        raise ValueError('Invalid original TrueType font') from error


def coverage_for_text(cmap, text):
    """Check actual mapped glyph IDs; whitespace needs no visible glyph."""
    if not isinstance(text, str):
        raise ValueError('Required font text must be a string')
    required = set(ord(ch) for ch in text if not ch.isspace())
    missing = sorted(required - set(cmap))
    return {'status': 'complete' if not missing else 'missing',
        'charactersChecked': len(required), 'charactersCovered': len(required) - len(missing),
        'missingCodePoints': missing, 'missingCharacters': ''.join(map(chr, missing))}


def inspect_font(data, required_text=DEFAULT_REQUIRED_TEXT):
    """Inventory a candidate without using its filename as evidence of coverage."""
    font = _open_font(data)
    cmap = font.getBestCmap() or {}
    # A .notdef mapping is not coverage even when a cmap entry is present.
    glyph_order = font.getGlyphOrder()
    if not glyph_order:
        raise ValueError('Font contains no glyphs')
    cmap = {cp: name for cp, name in cmap.items() if name != glyph_order[0]}
    if not cmap:
        raise ValueError('Font contains no usable Unicode character map')
    names = {}
    for name_id, key in ((1, 'family'), (2, 'subfamily'), (4, 'fullName'), (6, 'postscriptName')):
        records = [record for record in font['name'].names if record.nameID == name_id]
        # Keep source metadata, even when a merged font has a surprising name.
        names[key] = sorted(set(record.toUnicode() for record in records))
    block_counts = {name: sum(start <= cp <= end for cp in cmap)
                    for name, (start, end) in CJK_BLOCKS.items()}
    return {'sourceBytes': len(data), 'sourceSHA256': _sha(data),
        'sourceNames': names, 'sourceWeight': font['OS/2'].usWeightClass,
        'sourceGlyphCount': font['maxp'].numGlyphs,
        'codePointCount': len(cmap), 'unicodeRange': unicode_ranges(cmap),
        'coverage': {'cjkBlocks': block_counts,
            'requiredText': coverage_for_text(cmap, required_text),
            'completeDigits': all(cp in cmap for cp in range(48, 58)),
            'unicodeClaim': 'All source glyphs retained; not every possible CJK Unicode character exists.'}}


def convert_full_font(data, destination):
    """Wrap the entire source sfnt as WOFF without rebuilding any font table.

    Building WOFF directly from the raw SFNTReader table bytes avoids recompiling
    source name/cmap/layout tables or changing duplicate glyph-name aliases.
    """
    from fontTools.ttLib.sfnt import SFNTWriter
    font = _open_font(data)
    tables = {tag: font.reader[tag] for tag in font.reader.keys()}
    target = io.BytesIO()
    writer = SFNTWriter(target, len(tables), font.sfntVersion, flavor='woff')
    for tag in sorted(tables):
        writer[tag] = tables[tag]
    writer.close()
    result = target.getvalue()
    restored = TTFont(io.BytesIO(result), lazy=True)
    if set(restored.reader.keys()) != set(tables):
        raise ValueError('WOFF conversion changed the source table set')
    table_hashes = {}
    for tag, source in tables.items():
        actual = restored.reader[tag]
        if tag == 'head':
            source, actual = _head_without_checksum(source), _head_without_checksum(actual)
        if actual != source:
            raise ValueError(f'WOFF conversion changed source table {tag}')
        table_hashes[tag] = _sha(source)
    Path(destination).write_bytes(result)
    return {'bytes': len(result), 'sha256': _sha(result),
        'sourceTables': table_hashes, 'allSourceTablesVerified': True,
        'headChecksumAdjustmentMayDiffer': True}


def recover_chinese_fonts(read_loose, output, required_text=DEFAULT_REQUIRED_TEXT):
    """Read the two verified ui/Font paths -> bytes/Path; output=converted root.

    Writes ui/chineseText.woff, ui/chineseDisplay.woff, ui/chinese-fonts.json.
    No subsetting, system-font fallback conversion, or archive-CRC claim occurs.
    Missing Chinese characters are reported honestly for runtime fallback.
    """
    if not isinstance(required_text, str):
        raise ValueError('Required font text must be a string')
    sources = {}
    for key, spec in SOURCE_FONTS.items():
        value = read_loose(spec['path'])
        data = value if isinstance(value, bytes) else Path(value).read_bytes()
        if len(data) != spec['bytes'] or _sha(data) != spec['sha256']:
            raise ValueError(f'Unverified original loose font bytes: {spec["path"]}')
        metadata = inspect_font(data, required_text)
        if metadata['coverage']['cjkBlocks']['unified'] < 20000:
            raise ValueError('Verified source lacks the observed CJK coverage')
        sources[key] = (data, metadata)
    destination = Path(output) / 'ui'
    destination.mkdir(parents=True, exist_ok=True)
    faces = {}
    for key, (data, metadata) in sources.items():
        spec = SOURCE_FONTS[key]
        filename = key + '.woff'
        verification = convert_full_font(data, destination / filename)
        faces[key] = {**metadata, 'family': spec['family'], 'url': '/assets/ui/' + filename,
            'format': 'woff', 'weight': metadata['sourceWeight'], 'style': 'normal',
            'sourcePath': spec['path'], 'sourceStorage': 'loose-downloaded-file',
            'sourceNativeAlias': spec['nativeAlias'], 'webRole': spec['webRole'],
            'subset': False, 'conversion': 'lossless-full-sfnt-to-woff',
            'output': verification, 'loaderEvidence': spec['loaderEvidence'],
            'swfEvidence': spec['swfEvidence']}
    profile = {'format': 'oc2-original-chinese-fonts-v1',
        'status': 'original-full-source-fonts', 'faces': faces,
        'chineseStatus': 'source-fonts-available',
        'requiredTextStatus': ('complete' if all(face['coverage']['requiredText']['status'] == 'complete'
                                              for face in faces.values()) else 'missing'),
        'provenance': {'nativeSHA256': NATIVE_SHA256, 'nativeABI': 'arm64-v8a',
            'nativeBuild': '3.1.3a', 'sourceDirectory': 'files/ui/Font/',
            'archiveCRCVerified': False, 'looseSourcesVerifiedBy': 'exact byte length and SHA256',
            'fontPolicy': 'Preserve all original glyph, metric, layout, hinting and name tables.',
            'matisseOmitted': {'reason': 'Native language-6 branch and APK video subtitles select Matisse for Japanese.',
                'outlineDeduplication': 'Matisse-B.ttf and MatisseB.ttf have identical raw glyf,loca,hmtx,cmap tables; other metadata differs.'},
            'limitations': ['Web body/display roles reuse verified original families; complete original Flash typography/layout is not restored.',
                'Original merged-font name/weight metadata is preserved, including Alegreya-Bold.ttf reporting Quark Light and weight 300.',
                'Source fonts cover common Chinese; rare CJK extensions can still require runtime fallback.']}}
    (destination / 'chinese-fonts.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2))
    return profile
