"""Original selection transforms/camera transitions versus independent math."""
import math
import unittest
from pathlib import Path
from creation_stage_probe import CreationStageProbe, source_splash, source_race_panel, CONFIG_SHA256

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


class Guards(unittest.TestCase):
    def test_unknown_or_changed_source_configuration_is_rejected(self):
        class Source:
            def read(self, name): return b'[splash]\ncharacterScale=5.5\n'
        for name in ['conf/game.conf', 'another.conf']:
            with self.assertRaises(ValueError): source_splash(Source(), name)


@unittest.skipUnless(LIB.is_file(), 'Original private ARM64 sample absent')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        cls.image = NativeImage(LIB.read_bytes()); cls.sources = Sources(DEFAULT_SOURCE)
        cls.splash = source_splash(cls.sources)

    def probe(self): return CreationStageProbe(self.image, self.splash)

    def test_platform_configuration_consumed_vectors_match_original_files(self):
        keys = [k for k in self.splash if k.startswith(('character', 'camera', 'racecamera')) or '_camera_' in k]
        for name in CONFIG_SHA256:
            actual = source_splash(self.sources, name)
            self.assertEqual({k: actual[k] for k in keys}, {k: self.splash[k] for k in keys})

    def test_real_lazy_controller_owns_real_camera_and_keeps_original_near(self):
        p = self.probe(); controller = p.controller; camera = p.camera
        p.call(0xa5a008, {'X0': p.world_context})
        self.assertEqual(p.r(p.world_context+0x38, 'Q')[0], controller)
        self.assertEqual(p.r(p.controller+0x18, 'Q')[0], camera)
        self.assertEqual(p.r(p.scene+0x238, 'Q')[0], camera)
        self.assertEqual((p.parameters()['near'], p.parameters()['far']), (1., 3000.))
        p.viewport([0, 0, 1136, 640], 640)
        self.assertAlmostEqual(p.parameters()['fovRadians'], math.pi/4, places=6)
        self.assertEqual((p.parameters()['near'], p.parameters()['far']), (1., 3000.))

    def test_original_config_block_uses_raw_rotation_and_integer_scale(self):
        p = self.probe(); out = p.transform()
        self.assertEqual(out['position'], [-2572, 139, -30]); self.assertEqual(out['scale'], [5, 5, 5])
        self.assertEqual(out['inputEuler'], [0, 45, 0]); self.assertEqual(out['freshModelEyeColor'], [0, 0, 0])
        q = out['quaternion']
        self.assertAlmostEqual(q[1], math.sin(45/2), places=6)
        self.assertAlmostEqual(q[3], math.cos(45/2), places=6)
        self.assertGreater(abs(q[1]-math.sin(math.radians(45)/2)), .5)
        expected = [5*math.cos(45), 0, -5*math.sin(45), 0, 0, 5, 0, 0,
                    5*math.sin(45), 0, 5*math.cos(45), 0, -2572, 139, -30, 1]
        for a, b in zip(out['matrix'], expected): self.assertAlmostEqual(a, b, places=5)
        self.assertFalse(out['originalModelCompleted'])
        self.assertEqual([q['key'] for q in p.queries], ['characterPosition', 'characterRotation', 'characterScale'])

    def test_missing_model_node_is_not_invented_by_transform_calls(self):
        p = self.probe(); out = p.transform(False)
        self.assertEqual(out['wrapperNode'], 0); self.assertIsNone(out['matrix'])
        self.assertIsNone(out['position']); self.assertFalse(out['originalModelCompleted'])
        self.assertEqual(out['inputEuler'], [0, 45, 0])

    def test_original_race_target_is_relative_and_same_group_does_not_restart(self):
        p = self.probe(); out = p.select_camera(3)
        eye = [float(v) for v in self.splash['racecamerapos'].split(',')]
        direction = [float(v) for v in self.splash['racecameratar'].split(',')]
        for a, b in zip(out['eye'], eye): self.assertAlmostEqual(a, b, delta=.0002)
        for a, b, c in zip(out['target'], eye, direction): self.assertAlmostEqual(a, b+c, delta=.0002)
        queries = list(p.queries); self.assertEqual(p.select_camera(3, 4), out); self.assertEqual(p.queries, queries)

    def test_actual_race_swf_callback_selects_original_race_camera_group(self):
        evidence = source_race_panel(self.sources); p = self.probe()
        self.assertEqual(evidence['panel'], 0)
        self.assertEqual(p.select_camera(evidence['panel'], panel=True)['group'], 3)

    def test_native_camera_moves_in_original_update_steps_and_snaps_to_target(self):
        p = self.probe(); before = p.pose(); selected = p.select_camera(4, 0)
        first = p.step_camera()
        for i in range(3):
            step = p._f32(p._f32(selected['eye'][i]-before['eye'][i])*p.r(0x1df7ab8, 'f')[0])
            self.assertEqual(first['eye'][i], p._f32(before['eye'][i]+step))
        frames = 1
        while first['moving'] and frames < 40: first = p.step_camera(); frames += 1
        self.assertEqual(frames, 25); self.assertEqual(first['eye'], selected['eye']); self.assertEqual(first['target'], selected['target'])
        self.assertEqual(p.step_camera()['eye'], first['eye'])
        p.viewport([0, 0, 1136, 640], 640); self.assertTrue(all(math.isfinite(v) for v in p.view()))


if __name__ == '__main__': unittest.main()
