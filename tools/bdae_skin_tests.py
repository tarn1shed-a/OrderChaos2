"""Optional original-resource integration checks for recovered 946 skinning."""
import struct
import unittest
from pathlib import Path

from bdae_convert import BDAE
from bdae_skin import recover_skin
from bdae_character import convert_character, aliases

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / 'game-data/extracted'
MODEL = EXTRACTED / 'model/npc/creature/humanoid/forest_elf/forest_elf.bdae'
ANIMATION = EXTRACTED / 'model/npc/character/elf/female/anim/animations.bdae'
SOURCE = EXTRACTED / 'model/npc/character/elf/female/oc2_elf_f_body_01.bdae'


class RestAliasTests(unittest.TestCase):
    def test_ambiguous_source_alias_cannot_retarget_to_a_different_node(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            aliases([{'name':'left','aliases':['shared']}, {'name':'right','aliases':['shared']}])


@unittest.skipUnless(MODEL.exists(), 'Requires local original forest elf model')
class SkinIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.reader = BDAE(MODEL)
        self.model = self.reader.parse()

    def test_hierarchy_weights_and_mesh_bind_shape_are_independently_consistent(self):
        result = recover_skin(self.reader, self.model)
        self.assertEqual(len(result['nodes']), 52)
        self.assertEqual([len(skin['boneNodes']) for skin in result['skins']], [1, 46])
        for skin in result['skins']:
            self.assertLess(skin['verification']['maximumRestBindShapeError'], 1e-5)
            self.assertEqual(len(skin['skinWeights']), self.model['meshes'][skin['mesh']]['vertexCount'] * 4)
            self.assertLess(max(skin['skinIndices']), len(skin['boneNodes']))
            for at in range(0, len(skin['skinWeights']), 4):
                self.assertAlmostEqual(sum(skin['skinWeights'][at:at+4]), 1)

    def test_reject_wrong_weight_buffer_length(self):
        _, table = self.reader.section(188)
        wrapper = self.reader.rel(table + 16)
        data = self.reader.q(wrapper + 8) + ((self.reader.u(wrapper + 4) & 0xffffff) - 1) * 8
        broken = bytearray(self.reader.b)
        struct.pack_into('<Q', broken, data + 112, 4)
        self.reader.b = bytes(broken)
        with self.assertRaisesRegex(ValueError, 'vertex count'):
            recover_skin(self.reader, self.model)

    def test_reject_mismatched_bind_matrix(self):
        _, table = self.reader.section(188)
        wrapper = self.reader.rel(table + 16)
        data = self.reader.q(wrapper + 8) + ((self.reader.u(wrapper + 4) & 0xffffff) - 1) * 8
        matrix = self.reader.rel(data + 12)
        broken = bytearray(self.reader.b)
        struct.pack_into('<f', broken, matrix, 50)
        self.reader.b = bytes(broken)
        with self.assertRaisesRegex(ValueError, 'bind shape'):
            recover_skin(self.reader, self.model)

    @unittest.skipUnless(ANIMATION.exists() and SOURCE.exists(), 'Requires original animation and rest model')
    def test_locomotion_rebases_to_target_rest_and_cannot_move_server_root(self):
        result = convert_character(MODEL, ANIMATION, SOURCE)
        self.assertEqual(result['format'], 'bdae946-character-v1')
        self.assertEqual(result['animationBinding']['boundNodes'], 42)
        self.assertEqual(len(result['animationBinding']['ignoredSourceNodes']), 12)
        for clip in result['clips']:
            for track in clip['tracks']:
                node = result['rig']['nodes'][track['node']]
                if node['parent'] == -1 and track['type'] == 'position':
                    for at in range(0, len(track['values']), 3):
                        self.assertEqual(track['values'][at], node['position'][0])
                        self.assertEqual(track['values'][at+2], node['position'][2])


if __name__ == '__main__':
    unittest.main()
