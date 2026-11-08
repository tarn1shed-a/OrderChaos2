"""Source-backed request/residency checks, not a replacement streaming engine."""
import unittest
from pathlib import Path

from map_streaming_evidence import analyze, verify_native
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class MapStreamingEvidenceTests(unittest.TestCase):
    @unittest.skipUnless(NATIVE.is_file(), 'Original ARM64 sample remains local')
    def test_calls_vtable_targets_and_radius_key_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual(result['taskUpdateVtables']['0x2423f50'], '0xa62c90')
        class Changed:
            elf = image.elf
            def read(self, address, size):
                raw = image.read(address, size)
                return bytes([raw[0] ^ 1])+raw[1:] if address == 0x366ca0 else raw
        with self.assertRaisesRegex(ValueError, 'streaming routine changed'):
            verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tables.bin').is_file(),
                         'Original table/config inputs remain local')
    def test_map_file_layout_and_config_examples_do_not_select_an_android_profile(self):
        from analyze_native_resources import NativeImage
        result = analyze(NativeImage(NATIVE.read_bytes()), DEFAULT_SOURCE)
        self.assertTrue(result['mapRequest']['nativeTableFormatMatchesSource'])
        self.assertEqual(result['mapRequest']['runtimeFilenameOffset'], '0x40')
        self.assertEqual(result['mapRequest']['tutorialMapId'], 5)
        self.assertEqual(result['mapRequest']['tutorialFile'], 'world/tutorial.wld')
        self.assertEqual(result['radius']['lookupFallbackArgument'], 2)
        self.assertFalse(result['radius']['actualAndroidValueObserved'])
        self.assertEqual([row['value'] for row in result['radius']['sourceConfigOverrides']], [1, 1])
        self.assertTrue(all('iPad' in row['sourcePath'][-2]
                            for row in result['radius']['sourceConfigOverrides']))

    @unittest.skipUnless(NATIVE.is_file(), 'Original ARM64 fragments remain local')
    def test_original_offset_tables_are_center_first_and_complete_for_explicit_radii(self):
        from analyze_native_resources import NativeImage
        from native_map_streaming_probe import NativeMapStreamingProbe
        p = NativeMapStreamingProbe(NativeImage(NATIVE.read_bytes()))
        for radius in (0, 1, 2):
            result = p.offsets(radius)
            actual = result['offsets']
            self.assertEqual(result['allocationBytes'], [len(actual)*8])
            self.assertEqual(actual[0], [0, 0])
            self.assertEqual(len(actual), (2*radius+1)**2)
            self.assertEqual({tuple(v) for v in actual},
                             {(x, z) for x in range(-radius, radius+1) for z in range(-radius, radius+1)})
        self.assertEqual(p.offsets(1)['offsets'],
                         [[0,0],[1,0],[-1,0],[0,1],[0,-1],[1,1],[-1,1],[1,-1],[-1,-1]])

    @unittest.skipUnless(NATIVE.is_file(), 'Original ARM64 fragments remain local')
    def test_negative_center_and_retention_edge_execute_original_instructions(self):
        from analyze_native_resources import NativeImage
        from native_map_streaming_probe import NativeMapStreamingProbe
        p = NativeMapStreamingProbe(NativeImage(NATIVE.read_bytes()))
        for point, expected in [((-2752,128),[-43,2]), ((-.01,63.99),[-1,0]),
                                ((-64.01,-64),[-2,-1]), ((64,64),[1,1])]:
            self.assertEqual(p.center(*point), expected)
        for tile, expected in [([3,3],True), ([-3,-3],True), ([4,0],False), ([0,-4],False)]:
            self.assertEqual(p.retain_distance_branch([0,0],tile,2)['distanceAllowsRetain'], expected)


if __name__ == '__main__':
    unittest.main()
