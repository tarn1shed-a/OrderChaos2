import copy
import math
import unittest
from pathlib import Path

from resource_packs import DEFAULT_SOURCE
from scene_zone_selection import (ROUTINES, U32, ZoneCatalog, ZoneRefresh,
    analyze_selection, phase_allows, rectangle_contains, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def row(ident, **values):
    return {'ID': ident, 'map_id': 5, 'level': 0, 'parent_ID': -1, 'fly': 0,
            'definition': 0, 'phasing_id': 0, 'priority': 0,
            'x': -10, 'x1': 10, 'z': -10, 'z1': 10} | values


class ZoneSelectionTests(unittest.TestCase):
    def test_native_raw_rectangle_includes_all_edges_uses_float32_and_does_not_reorder_ends(self):
        value = row(1, x=-2624, x1=-2500, z=128, z1=251)
        for point in [(-2624, 128), (-2624, 251), (-2500, 128), (-2500, 251)]:
            self.assertTrue(rectangle_contains(value, *point))
        self.assertTrue(rectangle_contains(value, -2624-1e-5, 200))  # Source float32 rounds to edge.
        self.assertFalse(rectangle_contains(value, -2624-.001, 200))
        self.assertFalse(rectangle_contains(value, -2600, 251.00002))
        self.assertFalse(rectangle_contains(row(1, x=10, x1=-10), 0, 0))
        with self.assertRaises(ValueError): rectangle_contains(row(1, definition=1), 0, 0)
        with self.assertRaises(ValueError): rectangle_contains(value, math.nan, 0)

    def test_base_bucket_uses_level_map_and_signed_fly_instead_of_parent_minus_one(self):
        catalog = ZoneCatalog([row(10, parent_ID=99), row(11, level=1),
                               row(12, map_id=6), row(13, fly=1), row(14, fly=U32)], 5)
        self.assertEqual([r['ID'] for r in catalog.base], [10, 14])
        with self.assertRaises(ValueError): ZoneCatalog([row(1), row(1)], 5)

    def test_overlay_is_direct_child_of_selected_base_without_a_second_map_or_level_filter(self):
        catalog = ZoneCatalog([row(10), row(11, level=1, parent_ID=10, map_id=6, priority=1, fly=1),
                               row(12, level=2, parent_ID=11, priority=99),
                               row(13, level=1, parent_ID=99, priority=100)], 5)
        selected = catalog.select(0, 0)
        self.assertEqual((selected['base']['ID'], selected['overlay']['ID']), (10, 11))
        self.assertEqual(catalog.select(100, 100), {'base': None, 'overlay': None})

    def test_unsigned_priority_and_first_traversal_tie_are_distinct_from_resorting_candidates(self):
        a, b = row(9, priority=U32), row(1, priority=U32)
        self.assertEqual(ZoneCatalog.choose([a, b], 0, 0)['ID'], 9)
        self.assertEqual(ZoneCatalog.choose([b, a], 0, 0)['ID'], 1)
        catalog = ZoneCatalog([a, b, row(2, priority=0x7fffffff)], 5)
        self.assertEqual(catalog.select(0, 0)['base']['ID'], 1)
        self.assertEqual(ZoneCatalog.choose([row(1, priority=1), row(2, priority=0x80000000)], 0, 0)['ID'], 2)

    def test_phase_zero_needs_no_actor_and_inactive_polygons_are_not_evaluated(self):
        self.assertTrue(phase_allows(0))
        self.assertFalse(phase_allows(1))
        self.assertFalse(phase_allows(31, 0))
        self.assertTrue(phase_allows(31, 0x80000000))
        self.assertTrue(phase_allows(1, 2))
        for phase in (32, U32): self.assertFalse(phase_allows(phase, U32))
        polygon = row(2, definition=1, phasing_id=1, priority=99)
        self.assertEqual(ZoneCatalog.choose([row(1), polygon], 0, 0)['ID'], 1)
        with self.assertRaises(ValueError): ZoneCatalog.choose([polygon], 0, 0, 2)
        with self.assertRaises(ValueError): phase_allows(True)

    def test_refresh_is_strictly_past_500_and_force_bit0_not_other_bits(self):
        catalog = ZoneCatalog([row(10), row(11, level=1, parent_ID=10)], 5)
        clock = ZoneRefresh()
        self.assertEqual(clock.elapsed, 1000)
        initial = clock.tick(catalog, 0, [0, 0, 0])
        self.assertTrue(initial['queried']); self.assertEqual(initial['pair'], [10, 11])
        # Reset only for the exact threshold experiment, not as a native default.
        clock = ZoneRefresh(); clock.elapsed = 0
        first = clock.tick(catalog, 500, [0, 0, 0])
        self.assertFalse(first['queried']); self.assertEqual(clock.elapsed, 500)
        self.assertTrue(first['queueAdvanceRequested'])
        second = clock.tick(catalog, 1, [0, 0, 0])
        self.assertTrue(second['queried']); self.assertEqual(second['pair'], [10, 11])
        self.assertTrue(second['targetRefreshRequested']); self.assertEqual(clock.elapsed, 0)
        self.assertFalse(clock.tick(catalog, 500, [0, 0, 0])['queried'])
        self.assertFalse(clock.tick(catalog, 1, [0, 0, 0])['targetRefreshRequested'])
        self.assertFalse(clock.tick(catalog, 0, force_flags=2)['queried'])
        forced = clock.tick(catalog, 0, force_flags=1, upload_enabled=True)
        self.assertTrue(forced['queried'])
        self.assertFalse(forced['queueDeltaAccepted'])
        self.assertTrue(forced['uniformUploadRequested'])

    def test_suspend_skips_all_routing_and_position_resolution_prefers_explicit_then_actor_then_origin(self):
        catalog = ZoneCatalog([row(1)], 5)
        clock = ZoneRefresh(); clock.elapsed = 499
        before = copy.deepcopy(clock.__dict__)
        result = clock.tick(catalog, 1000, suspended=True, upload_enabled=True)
        self.assertEqual(clock.__dict__, before)
        self.assertFalse(result['queried']); self.assertFalse(result['queueAdvanceRequested'])
        self.assertFalse(result['uniformUploadRequested'])
        explicit = clock.tick(catalog, 1, [100, 55, 100], actor_position=[0, 9, 0], force_flags=1)
        self.assertEqual(explicit['pair'], [None, None])
        actor = clock.tick(catalog, 0, actor_position=[0, 9999, 0], force_flags=1)
        self.assertEqual(actor['pair'], [1, None])  # Y is not a containment input.
        self.assertEqual(clock.tick(catalog, 0, force_flags=1)['position'], [0, 0, 0])

    def test_uint32_add_signed_comparison_and_queue_delta_guard_are_separate(self):
        catalog = ZoneCatalog([row(1)], 5); clock = ZoneRefresh()
        clock.elapsed = 0x7fffffff
        self.assertFalse(clock.tick(catalog, 1)['queried'])
        self.assertEqual(clock.elapsed, 0x80000000)
        self.assertTrue(clock.tick(catalog, 0, force_flags=1)['queried'])
        clock.elapsed = U32
        self.assertFalse(clock.tick(catalog, 1)['queried']); self.assertEqual(clock.elapsed, 0)
        result = clock.tick(catalog, 100001)
        self.assertTrue(result['queried']); self.assertTrue(result['queueAdvanceRequested'])
        self.assertFalse(result['queueDeltaAccepted'])
        for bad in (-1, U32+1, True, 0.5):
            with self.assertRaises(ValueError): clock.tick(catalog, bad)

    @unittest.skipUnless(NATIVE.is_file(), 'Original zone native evidence stays local')
    def test_native_loader_child_rebuild_phase_rectangle_and_refresh_fingerprints(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); result = verify_native(image)
        self.assertEqual(result['selectionRoutines'], 8)
        self.assertEqual(result['initialRefreshAccumulator'], 1000)
        self.assertEqual(result['activeChangeTargetConsumer'], '0x4c5b90')
        self.assertFalse(result['appliedToRendering'])
        for changed in ROUTINES:
            class Changed:
                elf = image.elf
                def read(self, address, size):
                    return bytes(size) if address == changed else image.read(address, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(), 'Original zone table stays local')
    def test_original_tutorial_selection_source_edges_priority_and_refresh_trace(self):
        result = analyze_selection()
        self.assertEqual(result['tutorialBaseIds'], [194])
        self.assertEqual(result['tutorialDirectChildIds'], [195, 196, 197, 199])
        self.assertEqual([q['pair'] for q in result['queries']], [
            {'base': 194, 'overlay': 195}, {'base': 194, 'overlay': None},
            {'base': 194, 'overlay': 195}, {'base': 194, 'overlay': None},
            {'base': 194, 'overlay': 196}, {'base': 194, 'overlay': 199},
            {'base': None, 'overlay': None}])
        self.assertEqual([r['queried'] for r in result['explicitFrameTrace']], [True, False, True, False, True])
        self.assertFalse(result['explicitFrameTrace'][-1]['targetRefreshRequested'])
        self.assertFalse(result['nativeActiveStateObserved'])
        self.assertFalse(result['appliedToRendering'])


if __name__ == '__main__': unittest.main()
