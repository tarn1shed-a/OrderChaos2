"""Public face-query checks and opt-in original-package/native acceptance."""
import json
import math
import unittest
from pathlib import Path

from tutorial_temple_scene_probe import (
    DEFAULT_NATIVE, DEFAULT_PACKAGE, FORMAT, MODELS, ROOT, boundary_edges,
    capture_rays, inspect, pixel_rays, private_path, raycast, transform, triangle_hit)

IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


class FaceQueries(unittest.TestCase):
    def test_ray_retains_source_triangle_winding(self):
        vertices = [[0, 0, 0], [1, 0, 0], [0, 0, 1]]
        above = triangle_hit([.2, 1, .3], [0, -1, 0], vertices)
        below = triangle_hit([.2, -1, .3], [0, 1, 0], vertices)
        self.assertIsNotNone(above)
        self.assertEqual(above['position'], [.2, 0, .3])
        self.assertNotEqual(above['frontFacing'], below['frontFacing'])
        self.assertIsNone(triangle_hit([2, 1, 2], [0, -1, 0], vertices))
        self.assertIsNone(triangle_hit([.2, -1, .3], [0, -1, 0], vertices))

    def test_open_edges_do_not_misclassify_a_split_vertex_seam(self):
        # Two triangles form one square but duplicate seam vertex identities.
        mesh = {'positions': [0, 0, 0, 1, 0, 0, 1, 0, 1,
                              0, 0, 0, 1, 0, 1, 0, 0, 1],
                'indices': [0, 1, 2, 3, 4, 5]}
        edges = boundary_edges(mesh, IDENTITY)
        self.assertEqual(len(edges), 4)
        self.assertFalse(any(row['sourceEndpoints'] == [[0, 0, 0], [1, 0, 1]] for row in edges))

    def test_ray_reports_exact_part_not_just_model_bounds(self):
        mesh = {'name': 'two-source-parts',
                'positions': [0, 0, 0, 1, 0, 0, 0, 0, 1,
                              0, 2, 0, 1, 2, 0, 0, 2, 1],
                'indices': [0, 1, 2, 3, 4, 5],
                'groups': [{'start': 0, 'count': 3, 'material': 1, 'materialName': 'floor'},
                           {'start': 3, 'count': 3, 'material': 0, 'materialName': 'roof'}]}
        hits = raycast({'source': 'explicit-fixture', 'meshes': [mesh]}, {'id': 7}, [IDENTITY],
                      {'origin': [.2, 3, .2], 'direction': [0, -2, 0]})
        self.assertEqual([row['part'] for row in hits], [1, 0])
        self.assertEqual([row['distance'] for row in hits], [1, 3])
        self.assertEqual([row['triangle'] for row in hits], [1, 0])

    def test_private_records_cannot_target_public_paths(self):
        with self.assertRaises(ValueError):
            private_path(ROOT/'docs/source-faces.json')
        self.assertTrue(private_path(ROOT/'analysis/raw/temple-explicit-input.json').is_absolute())


class OriginalFaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DEFAULT_PACKAGE.exists() or not DEFAULT_NATIVE.exists():
            raise unittest.SkipTest('Original local package/native image are not distributed')
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
            import elftools  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional native analysis dependencies are unavailable')
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        cls.result = inspect(DEFAULT_PACKAGE, Sources(DEFAULT_SOURCE), DEFAULT_NATIVE)

    def test_each_original_part_matches_current_preview(self):
        self.assertEqual(self.result['format'], FORMAT)
        self.assertEqual([r['model'] for r in self.result['models']], list(MODELS))
        self.assertEqual([sum(p['count']//3 for m in row['parts'] for p in m)
                          for row in self.result['models']], [4808, 2538, 2968, 2528, 162, 7900, 894])
        self.assertTrue(all(r['sourceFacesAndPreviewArraysEqual'] for r in self.result['models']))
        self.assertTrue(all(i['originalITMPlacementEqual'] for r in self.result['models'] for i in r['instances']))

    def test_actual_native_initial_nodes_are_visible(self):
        for row in self.result['models']:
            self.assertTrue(all(n['visibilityWord0x40'] == 1 and n['modeByte0x44'] == 0 for n in row['sourceNodes']))
            native = row['originalInitialAssembly']
            meshes = [n for n in native['tree'] if n['vptr'] == '0x244e538']
            self.assertEqual(len(meshes), 1)
            self.assertEqual(int(meshes[0]['flags'], 16) & 0x18, 0x18)
            self.assertTrue(native['flagWrites'])
        inside_model, = [r for r in self.result['models'] if r['model'].endswith('/god_temple01_inside01.bdae')]
        inside = inside_model['originalInitialAssembly']['preparedBuffers']
        self.assertEqual(inside[0]['prefixCount'], 21)
        self.assertTrue(inside[0]['bboxBytesEqual'])

    def test_no_render_or_spawn_success_is_claimed(self):
        scope = self.result['scope']
        self.assertFalse(scope['GPUOrAndroidFrameExecuted'])
        self.assertFalse(scope['productionChanged'])
        self.assertFalse(scope['savesChanged'])
        self.assertFalse(scope['originalSpawnEstablished'])

    def test_actual_door_capture_matches_source_faces_and_all_parts(self):
        capture_path = ROOT/'analysis/raw/temple-start-review-20261114/w7-door-camera.json'
        if not capture_path.exists():
            self.skipTest('Same-camera host observation remains private')
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        capture = json.loads(capture_path.read_text())
        # Independently reconstructed projection rays reproduce host ray input.
        rebuilt = pixel_rays(capture, [{'name': str(i), 'pixel': row['clientPixel']}
                                      for i, row in enumerate(capture['samples'])])
        for actual, expected in zip(rebuilt, capture_rays(capture)):
            self.assertLess(max(abs(x-y) for x, y in zip(actual['direction'], expected['direction'])), 1e-10)
        result = inspect(DEFAULT_PACKAGE, Sources(DEFAULT_SOURCE), capture=capture)
        self.assertTrue(all(r['nearestSourceFaceEqual'] for r in result['hostRayComparisons']))
        self.assertTrue(all(r.get('withinFloat32PositionTolerance', True) for r in result['hostRayComparisons']))
        for name, count in [('god_temple01.bdae', 16), ('god_temple01_inside01.bdae', 21)]:
            row, = [r for r in result['models'] if r['model'].endswith('/'+name)]
            actual = row['hostCaptureReview'][0]['meshes'][0]
            self.assertEqual(actual['sourceMatrixMaxDifference'], 0)
            self.assertEqual(sum(r['submitted'] for r in actual['sourcePartsSubmitted']), count)

    def test_reproduced_old_opening_has_exact_eave_and_bridge_faces(self):
        capture_path = ROOT/'analysis/raw/temple-start-review-20261114/old-bridge-allstatic.json'
        if not capture_path.exists():
            self.skipTest('Final same-camera static observation remains private')
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        capture = json.loads(capture_path.read_text())
        self.assertEqual(capture['viewport']['width'], 473)
        self.assertEqual(capture['viewport']['height'], 849)
        result = inspect(DEFAULT_PACKAGE, Sources(DEFAULT_SOURCE), capture=capture)
        self.assertTrue(all(r['nearestSourceFaceEqual'] for r in result['hostRayComparisons']))
        for pixel, basename, triangle in [([80, 320], 'god_bridge_04.bdae', 360),
                                          ([30, 340], 'god_bridge_04.bdae', 436),
                                          ([230, 95], 'god_temple02.bdae', 1373),
                                          ([310, 115], 'god_temple02.bdae', 1412)]:
            index, = [i for i, r in enumerate(capture['samples'])
                       if max(abs(a-b) for a, b in zip(r['clientPixel'], pixel)) < 1e-8]
            check = result['hostRayComparisons'][index]
            self.assertTrue(check['sourceModel'].endswith('/'+basename))
            self.assertEqual(check['sourceTriangle'], triangle)
            self.assertLess(check['worldPointMaxDifference'], 2e-4)
        index, = [i for i, r in enumerate(capture['samples'])
                   if max(abs(a-b) for a, b in zip(r['clientPixel'], [230, 165])) < 1e-8]
        self.assertEqual(result['hostRayComparisons'][index]['allResidentHostHitCount'], 0)
        self.assertFalse(result['rayHits']['pixel-'+str(index)])
        bridge, = [r for r in result['models'] if r['model'].endswith('/god_bridge_04.bdae')]
        draw = bridge['hostCaptureReview'][0]['meshes'][0]
        self.assertEqual(draw['sourceMatrixMaxDifference'], 0)
        self.assertEqual(sum(r['submitted'] for r in draw['sourcePartsSubmitted']), 1)


if __name__ == '__main__':
    unittest.main()
