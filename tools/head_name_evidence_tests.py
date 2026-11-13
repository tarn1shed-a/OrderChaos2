import math
from pathlib import Path
import random
import unittest

from head_name_evidence import read_assets, verify_native
from native_head_name_probe import HeadNameProbe
from resource_packs import DEFAULT_SOURCE

SO = Path(__file__).resolve().parents[1]/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


@unittest.skipUnless(SO.is_file(), 'Original library stays local')
class HeadNameNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(SO.read_bytes())
        cls.vm = HeadNameProbe(cls.image)

    def test_pinned_source_table_does_not_enable_web_names(self):
        result = verify_native(self.image)
        self.assertEqual(result['routines'], 13)
        self.assertEqual(result['primaryFontByLanguageIndex'][6], 'Matisse-B')
        self.assertFalse(result['webNamesEnabled'])
        # Reject changed instructions even for a caller-supplied image wrapper.
        class Changed:
            def read(_, at, size):
                raw = self.image.read(at, size)
                return bytes([raw[0]^1])+raw[1:] if at == 0x36d344 else raw
        with self.assertRaisesRegex(ValueError, 'routine differs'):
            verify_native(Changed())

    def test_original_loader_builds_all_verified_primary_paths_and_secondary_path(self):
        for index in range(15):
            with self.subTest(language=index):
                result = self.vm.font_request(index)
                face = 'Matisse-B' if index == 6 else 'Alegreya-Bold'
                self.assertEqual(result['requestedPath'], f'ui/Font/{face}.ttf')
                self.assertFalse(result['FreeTypeExecuted'])
        self.assertEqual(self.vm.font_request(0, secondary=True)['requestedPath'],
                         'ui/Font/LeagueGothic-Regular.ttf')
        for index in (-1, 15):
            with self.assertRaises(ValueError):
                self.vm.font_request(index)

    def test_original_secondary_selection_requires_request_and_existing_face(self):
        for requested in (False, True):
            for exists in (False, True):
                result = self.vm.glyph_face(secondary=requested, secondary_available=exists)
                self.assertEqual(result['selectedFace'], 'secondary' if requested and exists else 'primary')
                self.assertEqual(result['requestedRasterHeight'], 32)
                self.assertFalse(result['FreeTypeExecuted'])

    def test_original_name_preflight_requires_enabled_nonempty_name_and_model(self):
        for enabled in (False, True):
            for name in (False, True):
                for model in (False, True):
                    with self.subTest(enabled=enabled, name=name, model=model):
                        output = self.vm.preflight(enabled=enabled, name=name, model=model)
                        self.assertEqual(output, 'position-requested' if enabled and name and model
                                         else 'returned-before-position')

    def test_original_material_getter_uses_depth_test_material_slot(self):
        self.assertTrue(self.vm.material())
        self.assertFalse(self.vm.material(manager_present=False))

    def test_relationship_manager_gate_does_not_give_unknown_fields_gameplay_labels(self):
        for flag in (0, 1, 2, 255):
            for code in (0, 1, 10, 11, 12, 0xffffffff):
                self.assertEqual(self.vm.relationship_manager_gate(flag=flag, code=code),
                                 flag == 0 or code == 11)

    def test_original_matrix_is_continuous_at_five_and_keeps_three_axis_position(self):
        position = [12.5, -2.25, 8]
        for distance in (0, 1, 4.99, 5, 5.0001, 10, 50, 200):
            result = self.vm.matrix(camera=[position[0], position[1], position[2]+distance],
                                    position=position)
            matrix = result['uploadedMatrix']
            factor = 1 if distance <= 5 else distance/15+2/3
            for index in (0, 5, 10):
                self.assertAlmostEqual(matrix[index], factor, delta=3e-6)
            self.assertEqual(matrix[12:15], position)
            self.assertEqual(matrix[15], 1)
            self.assertFalse(result['GPUExecuted'])

    def test_original_matrix_consumes_camera_basis_and_nonuniform_node_scale(self):
        rng = random.Random(20261114)
        for _ in range(24):
            angle = rng.uniform(-math.pi, math.pi)
            c, s = math.cos(angle), math.sin(angle)
            basis = [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 99, -88, 77, 1]
            scale = [rng.uniform(.2, 3) for _ in range(3)]
            position = [rng.uniform(-20, 20) for _ in range(3)]
            camera = [v+rng.uniform(-20, 20) for v in position]
            result = self.vm.matrix(camera=camera, position=position, scale=scale, basis=basis)
            matrix = result['uploadedMatrix']
            distance = math.dist(position, camera)
            factor = 1 if distance <= 5 else distance/15+2/3
            for col in range(3):
                for row in range(3):
                    self.assertAlmostEqual(matrix[col*4+row], basis[col*4+row]*scale[col]*factor, delta=3e-6)
            for actual, expected in zip(matrix[12:15], position):
                self.assertAlmostEqual(actual, expected, delta=2e-6)
            # Translation comes from the text node, not the camera basis.
            self.assertNotEqual(matrix[12:15], basis[12:15])


@unittest.skipUnless((DEFAULT_SOURCE/'ui/Font/Alegreya-Bold.ttf').is_file(), 'Original fonts stay local')
class HeadNameAssetTests(unittest.TestCase):
    def test_source_materials_and_full_font_bytes_are_distinct_from_ui_aliases(self):
        from map_loading_evidence import Sources
        result = read_assets(Sources(DEFAULT_SOURCE).read, DEFAULT_SOURCE)
        self.assertEqual(len(result['fonts']), 3)
        self.assertEqual(result['fonts']['Alegreya-Bold']['bytes'], 12031036)
        self.assertEqual(len(result['effects']), 4)
        for effect in result['effects']:
            self.assertEqual(effect['vertex']['file'], 'UnlitTexturedVP.glsl')
            self.assertEqual(effect['fragment']['file'], 'FontTexturedFP.glsl')
            self.assertTrue(effect['state']['blendEnabled'])
            self.assertFalse(effect['state']['depthWriteEnabled'])
            self.assertEqual(effect['state']['depthTestEnabled'],
                             effect['name'] == 'TTFBILLBOARD_Blend_Texture_Alpha_No_Culling')
        self.assertFalse(result['GPUExecuted'])

    def test_changed_shader_is_rejected_before_font_or_gpu_fallback(self):
        from map_loading_evidence import Sources
        source = Sources(DEFAULT_SOURCE)
        def changed(name):
            raw = source.read(name)
            return raw+b'\n' if name == 'FontTexturedFP.glsl' else raw
        with self.assertRaisesRegex(ValueError, 'asset differs'):
            read_assets(changed, DEFAULT_SOURCE)


if __name__ == '__main__':
    unittest.main()
