"""Local integration checks against user-supplied extracted model fixtures."""
import unittest,struct
from pathlib import Path
from bdae_convert import BDAE
from bdae_primitives import primitive_indices,verify_native

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = ROOT / 'game-data/extracted'
HUMAN = EXTRACTED / 'model/npc/character/human/male/oc2_human_m_body_01.bdae'
ELF = EXTRACTED / 'model/npc/creature/humanoid/forest_elf/forest_elf.bdae'
WALL = EXTRACTED / 'model/scene_generator_temple_000/god_wall_03.bdae'
BRIDGE = EXTRACTED / 'model/scene_generator_temple_000/god_bridge_step01.bdae'


def primitive_fixture(first=5,last=10,indices=(0,1,5)):
    raw=bytearray(144)
    struct.pack_into('<I',raw,16,len(indices)//3)
    struct.pack_into('<3I',raw,28,first,last,len(indices))
    struct.pack_into('<2Q',raw,48,128,len(indices)*2)
    struct.pack_into('<'+'H'*len(indices),raw,128,*indices)
    reader=BDAE.__new__(BDAE);reader.b=raw
    return reader


class PrimitiveWindowTests(unittest.TestCase):
    def test_local_indices_use_the_inclusive_source_vertex_window(self):
        indices,window=primitive_indices(primitive_fixture(),0,12)
        self.assertEqual(indices,[5,6,10]);self.assertEqual(window,{'sourceVertexStart':5,'sourceVertexEnd':10})
    def test_overlapping_windows_are_independent_not_cumulative(self):
        a,_=primitive_indices(primitive_fixture(5,10,(0,2,5)),0,12)
        b,_=primitive_indices(primitive_fixture(2,6,(0,2,4)),0,12)
        self.assertEqual(a,[5,7,10]);self.assertEqual(b,[2,4,6])
    def test_mesh_valid_but_window_invalid_index_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Local index'):
            primitive_indices(primitive_fixture(5,10,(0,1,6)),0,20)
        for first,last in [(10,5),(0,12),(12,13),(0xffffffff,0xffffffff)]:
            with self.assertRaises(ValueError):primitive_indices(primitive_fixture(first,last),0,12)
        with self.assertRaisesRegex(ValueError,'32-bit'):
            primitive_indices(primitive_fixture(0,65535),0,65536)
    def test_unknown_topology_short_buffer_and_wrong_counts_are_rejected(self):
        for at,fmt,value in [(0,'I',1),(16,'I',2),(36,'I',4),(48,'Q',143),(56,'Q',4)]:
            reader=primitive_fixture();struct.pack_into('<'+fmt,reader.b,at,value)
            with self.assertRaises(ValueError):primitive_indices(reader,0,12)
    def test_changed_native_binding_is_rejected(self):
        class Changed:
            def read(self,address,size):return bytes(size)
        with self.assertRaisesRegex(ValueError,'retrace'):verify_native(Changed())
    @unittest.skipUnless((ROOT/'analysis/raw/beff-native/library.so').exists(),'Original native library stays local')
    def test_native_index_binding_fingerprints(self):
        from analyze_native_resources import NativeImage
        result=verify_native(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
        self.assertTrue(result['lastVertexInclusive']);self.assertEqual(result['firstVertexOffset'],28)


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
        self.assertEqual([g['sourceVertexStart'] for g in mesh['groups']],[0,78,134])
        self.assertEqual([g['sourceVertexEnd'] for g in mesh['groups']],[77,133,212])
        for group in mesh['groups']:
            indices=mesh['indices'][group['start']:group['start']+group['count']]
            self.assertGreaterEqual(min(indices),group['sourceVertexStart'])
            self.assertLessEqual(max(indices),group['sourceVertexEnd'])
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
