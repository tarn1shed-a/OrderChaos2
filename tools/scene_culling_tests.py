import copy
import io
import math
import tempfile
import unittest
import zipfile
from pathlib import Path

from bdae_convert import BDAE
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_alpha import recover_scene_alpha
from scene_collision import apply_scene_transforms
from scene_culling import ROUTINES, cull_state, positive_affine, recover_scene_culling, verify_native

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def profiles():
    state = {'frontFaceGLBeforeTargetXor': 0x901, 'cullFaceGL': 0x405,
             'blendEnabled': False, 'depthTestEnabled': True,
             'depthWriteEnabled': True, 'depthFunctionGL': 0x203, 'cullEnabled': True}
    return [{'technique': 'tech0', 'state': copy.deepcopy(state)} for _ in range(2)]


class SceneCullingTests(unittest.TestCase):
    def test_native_target_reflection_and_front_face_xor_preserve_projected_classification(self):
        # Clip vertices have different W: test after perspective division,
        # rather than checking only an identity projection or axis labels.
        triangles = [[(-.7, -.5, .4), (.9, -.3, 1.2), (.1, .8, .9)],
                     [(.1, .8, .9), (.9, -.3, 1.2), (-.7, -.5, .4)]]
        def ccw(points):
            (ax, ay), (bx, by), (cx, cy) = [(x/w, y/w) for x, y, w in points]
            return (bx-ax)*(cy-ay)-(by-ay)*(cx-ax) > 0
        for triangle in triangles:
            for flipped in (False, True):
                for rotation in range(4):
                    # 13b6f6c / 1413868 negate the Y row, then 147b2bc
                    # performs the source surface-rotation row operations.
                    points = []
                    for x, y, w in triangle:
                        if flipped: y = -y
                        if rotation in (1, 3): x, y = y, x
                        if rotation in (2, 3): y = -y
                        if rotation in (1, 2): x = -x
                        points.append((x, y, w))
                    for front_cw in (False, True):
                        native_front = ccw(points) != (front_cw ^ flipped)
                        self.assertEqual(native_front, ccw(triangle) != front_cw)
        self.assertNotEqual(ccw(triangles[0]), ccw([(x, -y, w) for x, y, w in triangles[0]]),
                            'Copying the target bit without projection inversion would be wrong')

    def test_affine_transform_scope_rejects_mirrors_singular_and_nonfinite_nodes(self):
        self.assertEqual(positive_affine(IDENTITY), 1)
        value = IDENTITY.copy(); value[0] = value[5] = -2
        self.assertEqual(positive_affine(value), 4)
        for at, val in ((0, -1), (0, 0), (0, math.nan), (0, math.inf), (3, 1), (15, 0)):
            value = IDENTITY.copy(); value[at] = val
            with self.assertRaises(ValueError): positive_affine(value)
        for value in (None, IDENTITY[:-1]):
            with self.assertRaises(ValueError): positive_affine(value)
        value = IDENTITY.copy(); value[0] = value[5] = value[10] = 1e308
        with self.assertRaises(ValueError): positive_affine(value)

    def test_pass_profiles_must_agree_and_keep_the_observed_winding_depth_and_blend_branch(self):
        self.assertTrue(cull_state(profiles(), 'tech0'))
        value = profiles()
        for p in value: p['state']['cullEnabled'] = False
        self.assertFalse(cull_state(value, 'tech0'))
        for key, val in (('frontFaceGLBeforeTargetXor', 0x900), ('cullFaceGL', 0x404),
                         ('blendEnabled', True), ('depthTestEnabled', False),
                         ('depthWriteEnabled', False), ('depthFunctionGL', 0x201), ('cullEnabled', False)):
            value = profiles(); value[1]['state'][key] = val
            with self.assertRaises(ValueError): cull_state(value, 'tech0')
        for value, technique in (([], 'tech0'), (profiles()[:1], 'tech0'), (profiles(), 'tech1')):
            with self.assertRaises(ValueError): cull_state(value, technique)

    def test_unverified_bindings_and_missing_geometry_do_not_guess_a_side(self):
        from scene_alpha_tests import fixture
        for data in ({'materials': [], 'meshes': []},
                     {'materials': [{}], 'sceneAlpha': {'materials': []}, 'meshes': [{}]}):
            with self.assertRaises(ValueError): recover_scene_culling(None, fixture(), data)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native evidence stays local')
    def test_source_target_and_projection_fingerprints_and_hooks(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual(result['routineCount'], 9)
        self.assertFalse(result['requiresOriginalTargetFlagValue'])
        self.assertFalse(result['mirroredObjectBranchRestored'])
        for changed in ROUTINES:
            class Changed:
                elf = image.elf
                def read(self, address, size):
                    return bytes(size) if address == changed else image.read(address, size)
            with self.subTest(address=hex(changed)), self.assertRaisesRegex(ValueError, 'winding changed'):
                verify_native(Changed())

    @unittest.skipUnless((DEFAULT_SOURCE/'res.bin').is_file(), 'Original scene files stay local')
    def test_original_wall_tree_and_door_keep_their_distinct_source_cull_rules(self):
        archives = {name: ResourceArchive(DEFAULT_SOURCE/(name+'.bin')) for name in
                    ('res', 'res_t', 'res_scene', 'res_scene_generator_temple_000')}
        def extract(path):
            pack = ('res_t' if path.startswith('texture/') else
                    'res_scene_generator_temple_000' if path.startswith('model/scene_generator_') else
                    'res_scene' if path.startswith('model/') else 'res')
            return archives[pack].read(path)
        with tempfile.TemporaryDirectory() as temp:
            for path, enabled in (('model/scene_generator_temple_000/god_wall_03.bdae', True),
                                  ('model/scene_generator_temple_000/god_door_01.bdae', True),
                                  ('model/scene/region_whisper_island/wp_plant_small_tree006.bdae', False)):
                target = Path(temp)/'source.bdae'; target.write_bytes(extract(path))
                reader = BDAE(target); data = reader.parse(); apply_scene_transforms(reader, data)
                data['sceneAlpha'] = recover_scene_alpha(extract, reader, data)
                result = recover_scene_culling(extract, reader, data)
                self.assertTrue(all(m['cullEnabled'] == enabled for m in result['materials']))
                changed = copy.deepcopy(data); changed['meshes'][0]['sourceNodeTransform']['matrix'][0] *= -1
                with self.assertRaises(ValueError): recover_scene_culling(extract, reader, changed)
                changed = copy.deepcopy(data); changed['sceneAlpha']['materials'][0]['resolvedTechniqueIndex'] = 2
                with self.assertRaises(ValueError): recover_scene_culling(extract, reader, changed)
                def changed_fx(source):
                    raw = extract(source)
                    if source.endswith('.bdae'):
                        if raw.startswith(b'PK'):
                            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                                raw = archive.read('little_endian_not_quantized.bdae')
                        raw = bytearray(raw); raw[16] ^= 1
                    return raw
                with self.assertRaisesRegex(ValueError, 'FX changed'):
                    recover_scene_culling(changed_fx, reader, data)


if __name__ == '__main__': unittest.main()
