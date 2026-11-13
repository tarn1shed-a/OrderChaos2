"""Original CPU tests, not a certified map route or running source elevator."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
CONFIG = ROOT / 'analysis/raw/tutorial-elevator-20261114/four-inside-candidate/native-physics.json'
SOURCE = ROOT / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


@unittest.skipUnless(NATIVE.is_file(), 'Original native binary stays private')
class OriginalRegistryTests(unittest.TestCase):
    def setUp(self):
        from analyze_native_resources import NativeImage
        from tutorial_elevator_probe import DynamicShapeProbe
        self.engine = DynamicShapeProbe(NativeImage(NATIVE.read_bytes()))

    def test_original_empty_iterator_ends_at_the_header(self):
        self.assertEqual(self.engine.enumerate_shapes(), [])

    def test_original_registration_sorts_keys_and_replaces_without_duplicate_nodes(self):
        e = self.engine
        a, b, c, replacement = [e.alloc(0x128) for _ in range(4)]
        for key, head in ((739, a), (900, c), (100, b)):
            e.register_dynamic(key, head)
        self.assertEqual(e.enumerate_shapes(), [b, a, c])
        e.register_dynamic(739, replacement)
        self.assertEqual(e.enumerate_shapes(), [b, replacement, c])
        self.assertEqual(e.r(e.manager + 0x98, 'Q')[0], 3)

    def test_original_null_resource_does_not_add_a_dynamic_shape(self):
        e = self.engine
        e.register_dynamic(739, 0)
        self.assertEqual(e.enumerate_shapes(), [])
        self.assertEqual(e.r(e.manager + 0x98, 'Q')[0], 0)


@unittest.skipUnless(NATIVE.is_file() and CONFIG.is_file() and (SOURCE / 'tables.bin').is_file(),
                     'Original archive and isolated four-inside candidate stay private')
class OriginalLiftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from map_loading_evidence import Sources
        from tutorial_elevator_probe import load_fixture, LIFT_PHY
        cls.engine, cls.loaded = load_fixture(CONFIG)
        cls.source = Sources(SOURCE)
        cls.raw = cls.source.read(LIFT_PHY)
        cls.x, cls.z = -2652.93994140625, -63.892398834228516

    def setUp(self):
        e = self.engine
        e.w(0x2528df8, 'Q', e.manager)

    def place_lift(self, y, owner=0):
        return self.engine.lift_pose(self.raw, [self.x, y, self.z], owner)

    def fresh_actor(self, suffix, y=141.4329833984375):
        return self.engine.actor('lift-test-' + suffix, [self.x, y, self.z])

    def test_original_lift_is_one_source_cylinder_not_a_created_slope(self):
        from scene_collision import decode_phy
        from tutorial_elevator_probe import LIFT_PHY_SHA256
        decoded = decode_phy(self.raw)
        self.assertEqual(decoded['sourceSHA256'], LIFT_PHY_SHA256)
        self.assertEqual(len(decoded['shapes']), 1)
        self.assertEqual(decoded['shapes'][0]['sourceType'], 4)
        self.assertEqual(decoded['shapes'][0]['flags'], 2048)

    def test_original_query_tracks_explicit_upper_and_lower_poses(self):
        e = self.engine
        self.place_lift(140.63299560546875)
        self.assertAlmostEqual(e.ground_excluding(self.x,self.z,150)['height'],
                               141.4329833984375, places=5)
        self.place_lift(107.61000061035156)
        self.assertAlmostEqual(e.ground_excluding(self.x,self.z,150)['height'],
                               108.41000366210938, places=5)
        self.assertEqual(len(e.enumerate_shapes()), 1)

    def test_original_owner_and_shape_filters_remove_platform_support(self):
        e = self.engine; owner = e.alloc(0x100)
        head = self.place_lift(140.63299560546875, owner)
        baseline = 107.64344787597656
        self.assertAlmostEqual(e.ground_excluding(self.x,self.z,150,owner)['height'],baseline)
        for offset in (0x118, 0x119):
            e.w(head + offset,'B',1)
            self.assertAlmostEqual(e.ground_excluding(self.x,self.z,150)['height'],baseline)
            e.w(head + offset,'B',0)

    def test_original_motion_stands_on_the_dynamic_shape(self):
        e = self.engine; self.place_lift(140.63299560546875)
        start = [self.x,141.4329833984375,self.z]
        frames = [e.actor_tick('lift-standing-test',start,[0,0],50) for _ in range(20)]
        self.assertTrue(all(f['grounded'] for f in frames))
        self.assertTrue(all(abs(f['position'][1]-start[1])<1e-5 for f in frames))

    def test_original_passenger_mark_requires_the_source_shape_bounds(self):
        e = self.engine; head = self.place_lift(140.63299560546875)
        actor = self.fresh_actor('bounds')
        self.assertEqual(e.mark_passenger(actor,head),1)
        e.w(actor['address']+0xca0,'B',0)
        e.w(actor['address']+0x118,'3f',self.x+30,141.4329833984375,self.z)
        self.assertEqual(e.mark_passenger(actor,head),0)

    def test_original_passenger_resample_uses_moved_support_and_clears_flag(self):
        e = self.engine; actor = self.fresh_actor('support')
        head = self.place_lift(140.88299560546875)
        self.assertEqual(e.mark_passenger(actor,head),1)
        result = e.passenger_support_fragment(actor,numeric_gate=True)
        self.assertAlmostEqual(result['position'][1],141.6829833984375,places=5)
        self.assertEqual(result['passengerFlagAfter'],0)
        self.assertEqual(result['supportCacheValid'],1)

    def test_original_vertical_acceleration_skips_the_extra_resample(self):
        e = self.engine; actor = self.fresh_actor('accelerated')
        head = self.place_lift(140.88299560546875)
        self.assertEqual(e.mark_passenger(actor,head),1)
        e.w(actor['address']+0x138,'f',1.0)
        result = e.passenger_support_fragment(actor,numeric_gate=True)
        self.assertAlmostEqual(result['position'][1],141.4329833984375,places=5)
        self.assertEqual(result['passengerFlagAfter'],0)
        self.assertEqual(result['supportCacheValid'],0)

    def test_numeric_world_gate_is_required_not_silently_assumed(self):
        e = self.engine; actor = self.fresh_actor('missing-mode')
        head = self.place_lift(140.88299560546875)
        self.assertEqual(e.mark_passenger(actor,head),1)
        result = e.passenger_support_fragment(actor,numeric_gate=False)
        self.assertEqual(result['supportCacheValid'],0)
        # The source fragment has already raised the search position by one;
        # without its real session gate the resample is absent. This is not a
        # valid ride and must never be enabled as a recovered active state.
        self.assertAlmostEqual(result['position'][1],142.4329833984375,places=5)


if __name__ == '__main__':
    unittest.main()
