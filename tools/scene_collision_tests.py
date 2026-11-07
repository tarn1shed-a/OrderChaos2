import struct
import unittest
from pathlib import Path
from scene_collision import decode_phy, geometry_transforms
from bdae_convert import BDAE
from resource_packs import DEFAULT_SOURCE, ResourceArchive

def box(kind=3):return struct.pack('<3I7f',1,kind,2048,.25,1,2,3,4,5,6)
def poly():
    vertices=[(1,1,1),(-1,-1,1),(-1,1,-1),(1,-1,-1)]
    faces=[(0,1,2,0),(0,3,1,1),(0,2,3,0),(1,3,2,0)]
    return struct.pack('<3I6f2h',1,7,2048,1,2,3,1,1,1,4,4)+b''.join(struct.pack('<3f',*v) for v in vertices)+b''.join(struct.pack('<4H',*v) for v in faces)

class SceneCollisionTests(unittest.TestCase):
    def test_native_box_axis_and_angle_and_cylinder_are_preserved(self):
        for kind,name in [(3,'box'),(4,'cylinder')]:
            p=decode_phy(box(kind));shape=p['shapes'][0]
            self.assertEqual(shape['kind'],name);self.assertEqual(shape['center'],[1,3,-2])
            self.assertEqual(shape['halfExtents'],[4,6,5]);self.assertEqual(shape['yawRadians'],.25)
            self.assertEqual(shape['flags'],2048);self.assertEqual(p['bytesConsumed'],40)
    def test_polyhedron_keeps_face_flags_and_source_triangle_indices(self):
        p=decode_phy(poly())['shapes'][0]
        self.assertEqual(p['vertices'][0],[1,1,-1]);self.assertEqual(p['faces'][1],[0,3,1,1])
        self.assertEqual(p['sourceOffset'],4)
    def test_truncation_trailing_bad_dimensions_indices_and_unsupported_types_reject(self):
        for raw in [box()[:39],poly()[:-1],box()+b'x',box(6),struct.pack('<I',0),box().replace(struct.pack('<f',4),struct.pack('<f',float('nan'))),poly()[:-8]+struct.pack('<4H',999,3,2,0)]:
            with self.assertRaises(ValueError):decode_phy(raw)
    @unittest.skipUnless((DEFAULT_SOURCE/'model_phy.bin').is_file(),'Original collision shapes remain local')
    def test_source_compound_shapes_consume_all_bytes_without_guessing_unknown_types(self):
        archive=ResourceArchive(DEFAULT_SOURCE/'model_phy.bin')
        for name,count in [('god_temple04',29),('god_temple03',55),('god_altar_03',2),('god_bridge_02',6)]:
            raw=archive.read(f'model/scene_generator_temple_000/{name}.phy');p=decode_phy(raw)
            self.assertEqual(len(p['shapes']),count);self.assertEqual(p['bytesConsumed'],len(raw))
        self.assertEqual(p['shapes'][0]['kind'],'box')
    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'game-data/extracted/model/scene_generator_temple_000/god_wall_08.bdae').is_file(),'Original scene node tree remains local')
    def test_geometry_binding_is_explicit_pivot_instead_of_untransformed_geometry(self):
        path=Path(__file__).resolve().parents[1]/'game-data/extracted/model/scene_generator_temple_000/god_wall_08.bdae'
        reader=BDAE(path);model=reader.parse();bindings=geometry_transforms(reader,model)
        self.assertEqual(bindings[0]['reference'],'#Box698-mesh');self.assertEqual(bindings[0]['node'],'Box698-node_PIVOT')
        matrix=bindings[0]['matrix'];self.assertAlmostEqual(matrix[13],5.961455345153809)
        self.assertAlmostEqual(matrix[0],1.4829955101013184)
        model['meshes'][0]['name']='foreign'
        with self.assertRaisesRegex(ValueError,'geometry binding'):geometry_transforms(reader,model)

if __name__=='__main__':unittest.main()
