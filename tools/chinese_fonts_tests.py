"""Verify CJK coverage and preservation without requiring any system fonts."""
import io
import json
import tempfile
import unittest
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from chinese_fonts import (DEFAULT_REQUIRED_TEXT, SOURCE_FONTS, _head_without_checksum,
                           convert_full_font, coverage_for_text, inspect_font,
                           recover_chinese_fonts)
from resource_packs import DEFAULT_SOURCE


def synthetic_font():
    """A tiny authored font with a Chinese codepoint and an unencoded glyph."""
    order = ['.notdef', 'letterA', 'han', 'unencoded']
    glyphs = {'.notdef': TTGlyphPen(None).glyph()}
    for index, name in enumerate(order[1:], 1):
        pen = TTGlyphPen(None)
        pen.moveTo((50, -80))
        pen.lineTo((100 + index * 80, 700))
        pen.lineTo((450, -80))
        pen.closePath()
        glyphs[name] = pen.glyph()
    builder = FontBuilder(1024, isTTF=True)
    builder.setupGlyphOrder(order)
    # Deliberately mapped .notdef must not count as a recovered Chinese glyph.
    builder.setupCharacterMap({ord('A'): 'letterA', ord('中'): 'han', ord('空'): '.notdef'})
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (500 + i, 50) for i, name in enumerate(order)})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({'familyName': 'Authored Test', 'styleName': 'Regular',
        'uniqueFontIdentifier': 'Authored-Test', 'fullName': 'Authored Test',
        'psName': 'AuthoredTest'})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    output = io.BytesIO()
    builder.save(output)
    return output.getvalue()


class ChineseFontTests(unittest.TestCase):
    def test_real_codepoints_determine_coverage_including_notdef_rejection(self):
        result = inspect_font(synthetic_font(), '中A空龘')
        self.assertEqual(result['sourceGlyphCount'], 4)
        self.assertEqual(result['codePointCount'], 2)
        self.assertEqual(result['coverage']['cjkBlocks']['unified'], 1)
        self.assertEqual(result['coverage']['requiredText']['missingCharacters'], '空龘')
        self.assertEqual(result['coverage']['requiredText']['charactersCovered'], 2)
        self.assertFalse(result['coverage']['completeDigits'])

    def test_coverage_does_not_claim_unseen_rare_extension_characters(self):
        result = coverage_for_text({ord('中'): 'han'}, '中中\n\t𠀀')
        self.assertEqual(result['charactersChecked'], 2)
        self.assertEqual(result['missingCodePoints'], [0x20000])
        self.assertEqual(result['status'], 'missing')
        with self.assertRaises(ValueError):
            coverage_for_text({}, None)

    def test_full_woff_preserves_every_table_and_unencoded_glyph(self):
        original = synthetic_font()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'full.woff'
            verification = convert_full_font(original, path)
            source = TTFont(io.BytesIO(original), lazy=True)
            exported = TTFont(io.BytesIO(path.read_bytes()), lazy=True)
            self.assertEqual(set(source.reader.keys()), set(exported.reader.keys()))
            for tag in source.reader.keys():
                left, right = source.reader[tag], exported.reader[tag]
                if tag == 'head':
                    left, right = _head_without_checksum(left), _head_without_checksum(right)
                self.assertEqual(left, right, tag)
            self.assertIn('unencoded', exported.getGlyphOrder())
            self.assertEqual(exported['maxp'].numGlyphs, 4)
            self.assertEqual(source.getBestCmap(), exported.getBestCmap())
            self.assertEqual(exported['hmtx']['han'], source['hmtx']['han'])
            self.assertEqual(exported.flavor, 'woff')
            self.assertTrue(verification['allSourceTablesVerified'])

    def test_unverified_renamed_font_is_not_labeled_original(self):
        called = []
        with tempfile.TemporaryDirectory() as temp:
            def read(path):
                called.append(path)
                return synthetic_font()
            with self.assertRaisesRegex(ValueError, 'Unverified original'):
                recover_chinese_fonts(read, temp)
            self.assertEqual(called, ['ui/Font/Fontin.ttf'])
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_bad_required_text_fails_before_reading_sources(self):
        def forbidden(_):
            self.fail('No source reads expected')
        with self.assertRaises(ValueError):
            recover_chinese_fonts(forbidden, '.', required_text=None)
        for data in (b'', b'OTTO' + b'\0' * 20, b'\0\1\0\0'):
            with self.assertRaises(ValueError):
                inspect_font(data)

    @unittest.skipUnless(all((DEFAULT_SOURCE / spec['path']).is_file() for spec in SOURCE_FONTS.values()),
                         'Original downloaded loose fonts are local-only')
    def test_real_original_fonts_keep_all_glyphs_and_cover_gb2312_hanzi(self):
        # GB2312 is a useful finite Chinese coverage sample, rather than a claim
        # that any font can render every CJK extension in Unicode.
        required = set(DEFAULT_REQUIRED_TEXT)
        for lead in range(0xa1, 0xff):
            for trail in range(0xa1, 0xff):
                try:
                    char = bytes([lead, trail]).decode('gb2312')
                except UnicodeDecodeError:
                    continue
                if 0x4e00 <= ord(char) <= 0x9fff:
                    required.add(char)
        self.assertGreaterEqual(len(required), 6763)
        with tempfile.TemporaryDirectory() as temp:
            profile = recover_chinese_fonts(lambda path: DEFAULT_SOURCE / path, temp,
                                            required_text=''.join(sorted(required)))
            self.assertEqual(profile['requiredTextStatus'], 'complete')
            self.assertEqual(set(profile['faces']), {'chineseText', 'chineseDisplay'})
            for key, face in profile['faces'].items():
                source = TTFont(io.BytesIO((DEFAULT_SOURCE / face['sourcePath']).read_bytes()), lazy=True)
                exported = TTFont(io.BytesIO((Path(temp) / 'ui' / (key + '.woff')).read_bytes()), lazy=True)
                self.assertFalse(face['subset'])
                self.assertEqual(face['sourceGlyphCount'], source['maxp'].numGlyphs)
                self.assertEqual(exported['maxp'].numGlyphs, source['maxp'].numGlyphs)
                self.assertEqual(source.getBestCmap(), exported.getBestCmap())
                self.assertEqual(face['coverage']['cjkBlocks']['unified'], 20932)
                self.assertEqual(face['coverage']['requiredText']['missingCodePoints'], [])
                self.assertTrue(face['output']['allSourceTablesVerified'])
                self.assertEqual(exported.reader['glyf'], source.reader['glyf'])
                self.assertEqual(exported.reader['hmtx'], source.reader['hmtx'])
            metadata = json.loads((Path(temp) / 'ui' / 'chinese-fonts.json').read_text())
            self.assertEqual(metadata, profile)
            self.assertFalse(profile['provenance']['archiveCRCVerified'])


if __name__ == '__main__':
    unittest.main()
