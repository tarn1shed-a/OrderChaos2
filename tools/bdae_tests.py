"""Local integration checks against user-supplied extracted model fixtures."""
import unittest
from pathlib import Path
from bdae_convert import BDAE

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / 'game-data/extracted'
HUMAN = EXTRACTED / 'model/npc/character/human/male/oc2_human_m_body_01.bdae'
ELF = EXTRACTED / 'model/npc/creature/humanoid/forest_elf/forest_elf.bdae'
WALL = EXTRACTED / 'model/scene_generator_temple_000/god_wall_03.bdae'
BRIDGE = EXTRACTED / 'model/scene_generator_temple_000/god_bridge_step01.bdae'


@unittest.skipUnless(HUMAN.exists(), 'Requires local extracted game resources')
class ModelIntegrationTests(unittest.TestCase):
    def test_human_mesh_integrity_and_bounding_box(self):
        model = BDAE(HUMAN).parse()
        self.assertEqual(len(model['meshes']), 13)
        self.assertEqual(sum(m['vertexCount'] for m in model['meshes']), 1146)
        self.assertEqual(sum(m['triangleCount'] for m in model['meshes']), 1452)
        self.assertAlmostEqual(model['bounds'][1][1], 1.9492854, places=5)
        for mesh in model['meshes']:
            n = mesh['vertexCount']
            self.assertEqual(len(mesh['positions']), n * 3)
            self.assertEqual(len(mesh['normals']), n * 3)
            self.assertEqual(len(mesh['uvs']), n * 2)
            self.assertLess(max(mesh['indices']), n)
            self.assertEqual(mesh['material'], 0)
        self.assertEqual(model['materials'][0]['diffuse'], 'texture/oc2_human_m_body_01_d.tga')

    def test_multimaterial_elf_bindings_are_resolved(self):
        if not ELF.exists(): self.skipTest('Requires forest elf fixture')
        model = BDAE(ELF).parse()
        self.assertEqual(len(model['materials']), 2)
        self.assertEqual({m['material'] for m in model['meshes']}, {0, 1})
        for mesh in model['meshes']:
            self.assertEqual(sum(g['count'] for g in mesh['groups']), len(mesh['indices']))
            for group in mesh['groups']:
                self.assertEqual(model['materials'][group['material']]['name'], group['materialName'])

    def test_buffer_bounds_guard(self):
        model = BDAE(HUMAN)
        with self.assertRaises(ValueError): model.unpack('Q', len(model.b) - 1)
        with self.assertRaises(ValueError): model.unpack('I', -4)

    @unittest.skipUnless(WALL.exists(), 'Requires local temple fixtures')
    def test_variable_relocation_prefix_and_three_primitive_materials(self):
        model = BDAE(WALL).parse()
        mesh = model['meshes'][0]
        self.assertEqual(mesh['vertexCount'], 213)
        self.assertEqual(mesh['triangleCount'], 114)
        self.assertEqual([g['count'] for g in mesh['groups']], [111, 114, 117])
        self.assertEqual([g['material'] for g in mesh['groups']], [0, 1, 2])
        self.assertIsNone(mesh['material'])
        self.assertEqual(sum(g['count'] for g in mesh['groups']), len(mesh['indices']))
        for group in mesh['groups']:
            self.assertEqual(model['materials'][group['material']]['name'], group['materialName'])

    @unittest.skipUnless(BRIDGE.exists(), 'Requires scene mesh with packed color before UV')
    def test_vertex_color_does_not_displace_diffuse_uv_stream(self):
        source = BDAE(BRIDGE)
        model = source.parse()
        count, table = source.section(180)
        wrapper = source.rel(table + 20)
        prefix = source.u(wrapper + 4) & 0xffffff
        data = source.q(wrapper + 8) + (prefix - 1) * 8
        vertex_ptr = source.q(data + 64)
        # Known fixture layout: position0, normal12, UV0=24, UV1=32,
        # packed uint8 color40; stream table lists color before both UVs.
        expected = source.unpack('2f', vertex_ptr + 24)
        self.assertAlmostEqual(model['meshes'][0]['uvs'][0], expected[0], places=6)
        self.assertAlmostEqual(model['meshes'][0]['uvs'][1], expected[1], places=6)


if __name__ == '__main__':
    unittest.main()
