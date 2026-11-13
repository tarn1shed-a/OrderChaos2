import unittest
from pathlib import Path
from resource_packs import DEFAULT_SOURCE
from character_presentation_evidence import assets

ROOT = Path(__file__).resolve().parents[1]
SO = ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


@unittest.skipUnless(SO.is_file(), 'Original library stays local')
class NativePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from native_character_presentation_probe import PresentationProbe
        cls.vm = PresentationProbe(NativeImage(SO.read_bytes()))

    def test_original_new_model_neutral_colors_and_update_permission(self):
        self.assertEqual(self.vm.new_model(), {'hair': [1., 1., 1.], 'skin': [1., 1., 1.],
            'eye': [0., 0., 0.], 'materialUpdateAllowed': 1, 'nativeCPU': True})

    def test_dirty_rebuild_reaches_original_in_game_factory_not_assumed_ui_macro(self):
        result = self.vm.rebuild_factory()
        self.assertEqual(result['flags'], [0x807])
        self.assertTrue(result['stoppedBeforeMacroFormatting'])

    def test_actual_ui_quaternion_and_uniform_uploader_keep_positive_z(self):
        vector = self.vm.ui_light()['uploadedObjectDirection']
        for a, b in zip(vector, [-.6875166296958923, .6875166296958923, .2337557077407837]):
            self.assertAlmostEqual(a, b, places=7)

    def test_cached_original_name_offset_keeps_all_three_axes(self):
        for row in ([0, 0, 0], [1.25, 2.5, -.75], [-8., 12., 3.]):
            self.assertEqual(self.vm.cached_name_offset(row), row)

    def test_font_geometry_unit_is_not_css_font_size_or_distance_spacing(self):
        metric = self.vm.font_geometry_units()
        self.assertEqual(metric['glyphUnitMultiplier'][0], .0625)
        self.assertAlmostEqual(metric['glyphUnitMultiplier'][1], .013, places=8)
        self.assertFalse(metric['screenPixelSizeRecovered'])

    def test_original_color_unpack_block_is_low_red_not_high_red(self):
        from struct import pack, unpack
        f = lambda value: unpack('<f', pack('<f', value))[0]
        self.assertEqual(self.vm.packed_colors(0x12abef, 0xf05431), {
            'hair': [f(v*f(1/255)) for v in (239,171,18)],
            'skin': [f(v*f(1/255)) for v in (49,84,240)]})


@unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').is_file(), 'Original resources stay local')
class PresentationAssetTests(unittest.TestCase):
    def test_original_viewport_camera_and_all_six_effects_match_adapter(self):
        from map_loading_evidence import Sources
        data = assets(Sources(DEFAULT_SOURCE).read)
        self.assertEqual(data['boundsTwips'], [0, 0, 6059, 10307])
        self.assertEqual(data['camera'], {'camera': [0, 1, 3.4], 'target': [0, 1, 0]})
        self.assertEqual(len(data['effects']), 6)
        for name, effect in data['effects'].items():
            self.assertEqual(effect['cullEnabled'], name.startswith('lt_cull_'))
            for profile in effect['profiles']:
                self.assertEqual(profile['vertexShader']['file'], 'lt_pal_normal_vs.glsl')
                self.assertEqual(profile['fragmentShader']['file'], 'lt_pal_normal_fs.glsl')
                self.assertFalse(profile['state']['blendEnabled'])


if __name__ == '__main__':
    unittest.main()
