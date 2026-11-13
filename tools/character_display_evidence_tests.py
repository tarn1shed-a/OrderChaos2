import hashlib
import math
from pathlib import Path
import unittest

from character_display_evidence import verify_native
from native_character_display_probe import CharacterDisplayProbe
from optimized_abc import extract_named_abc, parse_abc, named_method, disassemble
from resource_packs import ResourceArchive, DEFAULT_SOURCE

SO = Path(__file__).resolve().parents[1]/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


@unittest.skipUnless(SO.is_file(), 'Original library stays local')
class NativeCharacterDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(SO.read_bytes())
        cls.vm = CharacterDisplayProbe(cls.image)

    def test_source_pins_and_virtual_tables_do_not_claim_browser_recovery(self):
        record = verify_native(self.image)
        self.assertEqual(record['routines'], 16)
        self.assertFalse(record['webPreviewReady'])
        self.assertFalse(record['webNamesReady'])

    def test_each_native_preview_gate_prevents_draw(self):
        self.assertEqual(self.vm.preview_gate()['outcome'], 'passed-pre-draw-gates')
        for missing in ('model', 'created', 'visible', 'texture'):
            with self.subTest(missing=missing):
                result = self.vm.preview_gate(**{missing: False})
                self.assertEqual(result['outcome'], 'not-drawn')
                self.assertFalse(result['textureRendered'])
        self.assertEqual(self.vm.preview_gate(suppressed=True)['outcome'], 'not-drawn')

    def test_native_once_redraw_and_completion_are_separate(self):
        result = self.vm.preview_gate(once=True)
        self.assertEqual(result['outcome'], 'passed-pre-draw-gates')
        self.assertTrue(result['alreadyDrawn'])
        result = self.vm.preview_gate(once=True, already_drawn=True)
        self.assertEqual(result['outcome'], 'not-drawn')
        self.assertEqual(result['suppressionChecks'], 0)
        self.assertEqual(self.vm.preview_gate(already_drawn=True)['outcome'], 'passed-pre-draw-gates')

    def test_native_projection_matches_finite_right_handed_clip_coordinates(self):
        for aspect in (.5, 1., 16/9):
            with self.subTest(aspect=aspect):
                matrix = self.vm.projection(aspect=aspect)
                self.assertAlmostEqual(matrix[0], 1/math.tan(math.pi/8)/aspect, places=5)
                self.assertAlmostEqual(matrix[5], 1/math.tan(math.pi/8), places=5)
                self.assertEqual(matrix[11], -1)
                self.assertEqual(matrix[15], 0)
                # Independent near/far clip-space checks on original matrix.
                for distance, expected in ((.1, -1), (3000., 1)):
                    clip_z = matrix[10]*-distance+matrix[14]
                    self.assertAlmostEqual(clip_z/distance, expected, places=5)

    def test_native_light_constructor_colors_are_not_map_ambient(self):
        self.assertEqual(self.vm.light_defaults(), {
            'ambient': [0., 0., 0., 1.], 'diffuse': [1., 1., 1., 1.],
            'specular': [1., 1., 1., 1.]})

    def test_selected_relation_removes_name_before_display_bit_is_considered(self):
        for flags in (0, 0x40, 0xffffffff):
            result = self.vm.name_gate(flags=flags, relation=True, selected=True)
            self.assertEqual(result['outcome'], 'remove-name-branch')
            self.assertFalse(result['textRendered'])

    def test_native_name_bit_and_no_local_actor_branches(self):
        for local in (False, True):
            for relation in (False, True):
                with self.subTest(local=local, relation=relation):
                    self.assertEqual(self.vm.name_gate(local_actor=local, relation=relation)['outcome'], 'not-drawn')
                    result = self.vm.name_gate(flags=0x40, local_actor=local, relation=relation)
                    self.assertEqual(result['outcome'], 'draw-name-branch')
                    self.assertFalse(result['originalActorStateSupplied'])


@unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').is_file(), 'Original UI stays local')
class OriginalModel3DTests(unittest.TestCase):
    def test_exact_original_model3d_including_dead_terminal_jumps_decodes(self):
        raw = ResourceArchive(DEFAULT_SOURCE/'ui.bin').read('ui/Flash/MainUI.swf')
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'e18152cbddf51f335ad764fd57c928a990cb0846de05b2628968050e1dcbc0ac')
        block = extract_named_abc(raw, 'Common/gluicEx/components/ui/Model3D')
        self.assertEqual(hashlib.sha256(block).hexdigest(), '9a30e0c4cdc6f085a5c340a15c2f19bad947676f0b055b780af3a108902c10ee')
        p = parse_abc(block)
        for body in p['bodies'].values():
            disassemble(body['code'], p, body['exceptions'])
        cls = p['classes'][0]['name']
        for method, digest in {
            'Common.gluicEx.components.ui:Model3D::initObject': '8bc80fc970aad4df6133a7012d28850b8e5bedd9846a2dd38ccd3e0bf136bf7e',
            'Common.gluicEx.components.ui:Model3D::loadTexture': 'df47411ea2ba7d29d646a6fb62d8079f0f5c2c97c9059dc690588d35491019b9',
            'Common.gluicEx.components.ui:Model3D::releaseTexture': '14869183fa1c31b4336f4805ba7a03a69a07620232420ecd65c872ec1fdd7fb3',
        }.items():
            self.assertEqual(named_method(p, cls, method)['codeSHA256'], digest)


if __name__ == '__main__': unittest.main()
