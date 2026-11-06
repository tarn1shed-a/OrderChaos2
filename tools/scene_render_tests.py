import unittest

from recover_scene_render import build_scene_profile, source_color, LUT_PATH
from resource_packs import ResourceArchive, DEFAULT_SOURCE


class SceneRenderTests(unittest.TestCase):
    def test_recovered_native_color_byte_order(self):
        # Native 0x4c4238 reads the least significant byte into its first channel.
        self.assertEqual(source_color(0x56474e), [78 / 255, 71 / 255, 86 / 255])
        self.assertEqual(source_color(0xf0caa6), [166 / 255, 202 / 255, 240 / 255])
        for invalid in (-1, 0x1000000, 1.5):
            with self.assertRaises(ValueError):
                source_color(invalid)

    def test_invalid_bounds_fail_before_extracting(self):
        def forbidden(_):
            self.fail('Invalid bounds should be rejected before source reads')
        for bounds in [(1, 0, -1, 0), (0, 1, 0, -1), (0, 0, float('nan'), 1), (0, 0, 1)]:
            with self.assertRaises(ValueError):
                build_scene_profile(forbidden, bounds)

    @unittest.skipUnless((DEFAULT_SOURCE / 'tables.bin').is_file() and
                         (DEFAULT_SOURCE / 'res_t_upd15.bin').is_file(),
                         'Original tables and textures are local-only')
    def test_crc_checked_tutorial_zones_lut_and_boundary(self):
        packs = {name: ResourceArchive(DEFAULT_SOURCE / name) for name in
                 ('tables.bin', 'res.bin', 'res_t_upd15.bin')}
        def extract(name):
            pack = 'tables.bin' if name.startswith('tables/') else (
                'res_t_upd15.bin' if name.startswith('texture/') else 'res.bin')
            return packs[pack].read(name)
        profile = build_scene_profile(extract)
        self.assertEqual(profile['world']['mapId'], 5)
        self.assertEqual(profile['hdr']['blurIterations'], 2)
        self.assertEqual(profile['hdr']['blurWidths'], [2, 4])
        self.assertEqual(profile['hdr']['downscale'], .5)
        self.assertEqual([zone['id'] for zone in profile['zones']], [194, 195])
        outside, spawn = profile['zones']
        self.assertEqual((spawn['priority'], spawn['fog']['near'], spawn['fog']['halfSpan']), (14, 89, 101))
        self.assertEqual(spawn['fog']['sourceStartEnd'], [89, 190, 1 / 101])
        self.assertEqual(outside['fog']['color'], source_color(0xf0caa6))
        self.assertAlmostEqual(spawn['bloom']['decrease'], .3945, places=6)
        self.assertGreater(spawn['bloom']['intensity'], profile['hdr']['maxIntensity'])
        self.assertEqual(profile['lutPath'], LUT_PATH)
        self.assertFalse(profile['lut']['flipY'])
        self.assertEqual(profile['lut']['sourceSHA256'],
                         'd80370abbad247f57e39824eaff2159e4d6497f69a29f25277951f2fa04c3ea5')
        self.assertEqual(profile['sources']['tables/zones.tbl']['rows'], 439)
        north = build_scene_profile(extract, (-2700, 252, -2600, 319))
        self.assertEqual([zone['id'] for zone in north['zones']], [194])
        def bad_lut(name):
            raw = extract(name)
            if name == LUT_PATH:
                raw = bytearray(raw)
                raw[12:14] = b'\x01\x00'
            return raw
        with self.assertRaisesRegex(ValueError, 'LUT'):
            build_scene_profile(bad_lut)


if __name__ == '__main__':
    unittest.main()
