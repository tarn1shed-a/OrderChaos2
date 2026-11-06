"""Synthetic format checks plus optional CRC-checked original UI integration."""
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image

from resource_packs import DEFAULT_SOURCE, ResourceArchive
from ui_assets import (Bits, LIBRARY, parse_font3, read_swf, recover_ui_assets,
                       rectangular_bitmap, shape_edges, write_font)


class Writer:
    def __init__(self):
        self.bits = ''

    def u(self, value, size):
        if size:
            self.bits += format(value & ((1 << size) - 1), f'0{size}b')

    s = u

    def bytes(self):
        padded = self.bits + '0' * (-len(self.bits) % 8)
        return bytes(int(padded[i:i + 8], 2) for i in range(0, len(padded), 8))


def signed_size(values):
    return max(1, max(abs(value).bit_length() + 1 for value in values))


def rect_bytes(rect):
    writer = Writer()
    size = signed_size(rect)
    writer.u(size, 5)
    for value in rect:
        writer.s(value, size)
    return writer.bytes()


def matrix_bytes(tx=-120, ty=-200, scale=20):
    writer = Writer()
    fixed = round(scale * 65536)
    size = signed_size([fixed])
    writer.u(1, 1)
    writer.u(size, 5)
    writer.s(fixed, size)
    writer.s(fixed, size)
    writer.u(0, 1)
    size = signed_size([tx, ty])
    writer.u(size, 5)
    writer.s(tx, size)
    writer.s(ty, size)
    return writer.bytes()


def path_bytes(points):
    writer = Writer()
    writer.u(1, 4)
    writer.u(0, 4)
    writer.u(0, 1)
    writer.u(3, 5)  # MoveTo and FillStyle0.
    size = signed_size(points[0])
    writer.u(size, 5)
    writer.s(points[0][0], size)
    writer.s(points[0][1], size)
    writer.u(1, 1)
    for start, end in zip(points, points[1:]):
        dx, dy = end[0] - start[0], end[1] - start[1]
        size = max(2, signed_size([dx, dy]))
        writer.u(1, 1)
        writer.u(1, 1)
        writer.u(size - 2, 4)
        if dx and dy:
            writer.u(1, 1)
            writer.s(dx, size)
            writer.s(dy, size)
        else:
            writer.u(0, 1)
            writer.u(bool(dy), 1)
            writer.s(dy or dx, size)
    writer.u(0, 6)
    return writer.bytes()


RECTANGLE = [(0, 0), (40, 0), (40, 60), (0, 60), (0, 0)]


def bitmap_shape(points=RECTANGLE, tx=-120, scale=20):
    return (struct.pack('<H', 8) + rect_bytes([0, 40, 0, 60]) +
            b'\x01\x40' + struct.pack('<H', 2) + matrix_bytes(tx=tx, scale=scale) +
            b'\x00' + path_bytes(points))


def tag(kind, data):
    return (struct.pack('<H', (kind << 6) | 63) + struct.pack('<I', len(data)) + data)


def swf_bytes(body):
    full = b'FWS\x0b' + b'\0' * 4 + rect_bytes([0, 400, 0, 400]) + b'\0\x18\x01\0' + body + b'\0\0'
    return full[:4] + struct.pack('<I', len(full)) + full[8:]


class UIAssetTests(unittest.TestCase):
    def test_metadata_only_atlas_and_symbol_mapping(self):
        bitmap = struct.pack('<HBHH', 2, 5, 1024, 1024)
        symbols = struct.pack('<HH', 1, 2) + b'atlas.png\0'
        result = read_swf(swf_bytes(tag(20, bitmap) + tag(76, symbols)))
        self.assertEqual(result['bitmaps'], {2: (1024, 1024)})
        self.assertEqual(result['symbols'], {'atlas.png': 2})

    def test_bad_swf_extents_are_rejected(self):
        good = swf_bytes(tag(20, struct.pack('<HBHH', 2, 5, 32, 32)))
        for bad in (good[:-1], good + b'x', b'bad' + good[3:]):
            with self.assertRaises(ValueError):
                read_swf(bad)
        malformed = swf_bytes(struct.pack('<HI', (76 << 6) | 63, 100000))
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            read_swf(malformed)
        with self.assertRaisesRegex(ValueError, 'bit field'):
            Bits(b'').u(1)

    def test_inverse_bitmap_matrix_recovers_exact_pixel_rect(self):
        bitmap, rect, matrix, bounds = rectangular_bitmap(bitmap_shape())
        self.assertEqual(bitmap, 2)
        self.assertEqual(rect, [6, 10, 8, 13])
        self.assertEqual(bounds, [0, 40, 0, 60])
        self.assertEqual(matrix, [20, 0, 0, 20, -120, -200])

    def test_nonrectangle_rescale_and_subpixel_are_not_exported_as_original(self):
        triangle = [(0, 0), (40, 0), (0, 60), (0, 0)]
        for bad, message in ((bitmap_shape(triangle), 'rectangle'),
                             (bitmap_shape(scale=10), 'axis-aligned'),
                             (bitmap_shape(tx=-121), 'whole pixels')):
            with self.assertRaisesRegex(ValueError, message):
                rectangular_bitmap(bad)

    def test_original_quadratic_shape_rejects_style_payload_and_truncation(self):
        edges = shape_edges(path_bytes(RECTANGLE))
        self.assertEqual(len(edges), 4)
        with self.assertRaises(ValueError):
            shape_edges(path_bytes(RECTANGLE)[:-2])
        writer = Writer()
        writer.u(1, 4)
        writer.u(0, 4)
        writer.u(0, 1)
        writer.u(16, 5)
        with self.assertRaisesRegex(ValueError, 'new styles'):
            shape_edges(writer.bytes())

    def test_font3_glyph_and_woff_preserve_codepoint_advance_and_axes(self):
        outline = path_bytes([(100, -200), (500, -200), (500, 100), (100, 100), (100, -200)])
        name = b'Synthetic\0'
        payload = (struct.pack('<HBBB', 7, 132, 0, len(name)) + name +
                   struct.pack('<HHH', 1, 4, 4 + len(outline)) + outline +
                   struct.pack('<Hhhhh', ord('A'), 19000, 5000, 0, 8500))
        font = parse_font3(payload)
        self.assertEqual(set(font['glyphs']), {ord('A')})
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'original.woff'
            meta = write_font([('synthetic.swf', font)], path, 'Synthetic Subset')
            face = TTFont(path)
            self.assertEqual(set(face.getBestCmap()), {ord('A')})
            self.assertEqual(face['head'].unitsPerEm, 2048)
            self.assertEqual(face['hmtx']['uni0041'], (850, 10))
            glyph = face['glyf']['uni0041']
            self.assertEqual((glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax), (10, -10, 50, 20))
            self.assertEqual(meta['unicodeRange'], 'U+41')
            self.assertEqual(meta['chineseGlyphs'], 0)
            bad = dict(font, glyphs={65: {'outline': path_bytes([(0, 0), (40, 0)]), 'advance': 1000}})
            with self.assertRaisesRegex(ValueError, 'open contour'):
                write_font([('synthetic.swf', bad)], path, 'Invalid')

    @unittest.skipUnless((DEFAULT_SOURCE / 'ui.bin').is_file(), 'Original UI art is local-only')
    def test_real_crc_checked_art_and_original_font_subsets(self):
        archive = ResourceArchive(DEFAULT_SOURCE / 'ui.bin')
        with tempfile.TemporaryDirectory() as temp:
            profile = recover_ui_assets(archive.read, temp)
            destination = Path(temp) / 'ui'
            self.assertEqual(len(profile['assets']), 9)
            for key, asset in profile['assets'].items():
                original = Image.open(io.BytesIO(archive.read(asset['sourceAtlas'])))
                expected = original.crop(asset['sourceRect'])
                exported = Image.open(destination / (key + '.png'))
                self.assertEqual(exported.mode, 'RGBA')
                self.assertEqual(exported.size, expected.size)
                self.assertEqual(exported.tobytes(), expected.tobytes())
                self.assertEqual(asset['sourceSWF'], LIBRARY)
            fonts = profile['fonts']['faces']
            self.assertTrue(fonts['leagueGothic']['completeDigits'])
            self.assertFalse(fonts['alegreya']['completeDigits'])
            for key, metadata in fonts.items():
                face = TTFont(destination / (key + '.woff'))
                self.assertEqual(sorted(face.getBestCmap()), metadata['codePoints'])
            self.assertEqual(profile['fonts']['chineseStatus'], 'incomplete-use-system-fallback')
            self.assertFalse(profile['provenance']['swfScriptExecution'])
            self.assertEqual(json.loads((destination / 'profile.json').read_text()), profile)


if __name__ == '__main__':
    unittest.main()
