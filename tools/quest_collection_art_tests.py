"""Paired mask format controls, plus optional checks against the original UI."""
import re
import struct
import unittest

from swf_morph_pairs import morph_shape
from ui_assets_tests import Writer, signed_size, rect_bytes


def edges(points, *, end=False):
    w = Writer()
    w.u(0 if end else 1, 4)
    w.u(0, 4)
    w.u(0, 1)
    w.u(1 if end else 5, 5)  # EndEdges move only; styles come from StartEdges.
    size = signed_size(points[0])
    w.u(size, 5)
    for value in points[0]:
        w.s(value, size)
    if not end:
        w.u(1, 1)  # FillStyle1, so path direction is retained.
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        size = max(2, signed_size([dx, dy]))
        w.u(1, 1)
        w.u(1, 1)
        w.u(size - 2, 4)
        w.u(1, 1)
        w.s(dx, size)
        w.s(dy, size)
    w.u(0, 6)
    return w.bytes()


START = [(0, 0), (100, 0), (100, 80), (0, 80), (0, 0)]
END = [(20, 10), (220, 10), (220, 170), (20, 170), (20, 10)]


def record(start=START, end=END, paint=0):
    styles = bytes([1, paint, 10, 20, 30, 255, 110, 120, 130, 255, 0])
    first = styles + edges(start)
    return (struct.pack('<H', 1) + rect_bytes([0, 100, 0, 80]) +
            rect_bytes([20, 220, 10, 170]) + struct.pack('<I', len(first)) +
            first + edges(end, end=True))


def numbers(path):
    return [float(n) for n in re.findall(r'-?\d+(?:\.\d+)?', path)]


class PairedMaskTests(unittest.TestCase):
    def test_end_geometry_uses_start_styles_and_keeps_move(self):
        for ratio, points, color in [(0, START, [10, 20, 30, 255]),
                                     (65535, END, [110, 120, 130, 255])]:
            value = morph_shape(46, record(), ratio=ratio)
            self.assertEqual(value['sourceMorph']['edgeCount'], 4)
            self.assertEqual(value['fills'][0]['paint']['color'], color)
            # Independent expected rectangle coordinates, including nonzero End MoveTo.
            self.assertEqual(numbers(value['fills'][0]['path']),
                             [v for p in points for v in p])

    def test_partial_ratio_changes_geometry_and_color(self):
        value = morph_shape(46, record(), ratio=32768)
        self.assertAlmostEqual(numbers(value['fills'][0]['path'])[0], 20*32768/65535, places=5)
        self.assertAlmostEqual(value['fills'][0]['paint']['color'][0], 10+100*32768/65535)
        self.assertFalse(value['sourceMorph']['sourceRasterizationObserved'])

    def test_wrong_kind_ratio_truncation_and_unsupported_style_rejected(self):
        for kind, raw, ratio in [(84, record(), 0), (46, record(), True),
                                 (46, record(), -1), (46, record(), 65536),
                                 (46, record()[:-2], 0), (46, record(paint=16), 0),
                                 (46, record(end=END[:-1]), 0)]:
            with self.subTest(kind=kind, ratio=ratio, size=len(raw)):
                with self.assertRaises(ValueError):
                    morph_shape(kind, raw, ratio=ratio)


if __name__ == '__main__':
    unittest.main()
