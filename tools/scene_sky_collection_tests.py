import random
import unittest
from pathlib import Path

from scene_sky_collection import (FORMAT, ROUTINES, RELOCATIONS, verify_native, analyze_collection,
                                  visitor_decision, accumulate_root_counts)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class SkyCollectionTests(unittest.TestCase):
    def test_normal_gate_rechecks_after_acceptance_and_uses_low_bit(self):
        self.assertEqual(visitor_decision([1, 0], 0), {'submitted': False, 'counts': [0, 0], 'gateCalls': 2, 'frustumCalls': 0})
        self.assertTrue(visitor_decision([3, 3], 0)['submitted'])
        self.assertEqual(visitor_decision([2, 1], 1)['gateCalls'], 1)

    def test_mode5_skips_and_other_nonzero_modes_use_explicit_frustum_result(self):
        self.assertEqual(visitor_decision([1, 1], 5, counts=[7, 9]), {'submitted': False, 'counts': [7, 9], 'gateCalls': 1, 'frustumCalls': 0})
        self.assertEqual(visitor_decision([1, 1], 2, 0), {'submitted': False, 'counts': [1, 1], 'gateCalls': 1, 'frustumCalls': 1})
        self.assertTrue(visitor_decision([1, 1], 2, 2)['submitted'])

    def test_accepted_subtree_visitor_only_tests_first_gate_and_keeps_counters(self):
        self.assertEqual(visitor_decision([1, 0], 5, 0, [7, 9], True), {'submitted': True, 'counts': [7, 9], 'gateCalls': 1, 'frustumCalls': 0})
        self.assertFalse(visitor_decision([2, 1], 0, fast=True)['submitted'])

    def test_counter_wrap_aggregation_and_invalid_explicit_inputs(self):
        self.assertEqual(visitor_decision([1, 1], 1, 0, [0xffffffff, 0xffffffff])['counts'], [0, 0])
        rows = [[0xffffffff, 2, 3], [1, 4, 5]]
        self.assertEqual(accumulate_root_counts(rows), [0, 6, 8]); self.assertEqual(rows[0][0], 0xffffffff)
        for gates in ([1], [True, 1], [-1, 0], [1, 1 << 32]):
            with self.assertRaises(ValueError): visitor_decision(gates, 0)
        with self.assertRaises(ValueError): accumulate_root_counts([[1, 2]])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_original_visitors_and_adapter_match_explicit_gate_frustum_and_counter_inputs(self):
        from analyze_native_resources import NativeImage
        from native_sky_collection_probe import NativeSkyCollectionProbe
        p = NativeSkyCollectionProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(414)
        for _ in range(120):
            gates = [rng.choice([0, 1, 2, 3, 0xffffffff]) for _ in range(2)]
            mode = rng.choice([0, 1, 2, 3, 4, 5, 7, 0xffffffff]); result = rng.choice([0, 1, 2, 0xffffffff])
            counts = [rng.randrange(1 << 32) for _ in range(2)]
            for fast, adapter in ((False, False), (False, True), (True, False)):
                actual = p.visit(gates, mode, result, counts, fast, adapter); expected = visitor_decision(gates, mode, result, counts, fast)
                self.assertEqual({k: actual[k] for k in expected}, expected)
                if not fast: self.assertEqual(actual['returnWord'], 1)
        self.assertEqual(p.visit([1, 1], 1, 0, [0xffffffff, 0xffffffff])['counts'], [0, 0])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_root_list_uses_each_reference_address_and_wraps_all_three_aggregates(self):
        from analyze_native_resources import NativeImage
        from native_sky_collection_probe import NativeSkyCollectionProbe
        p = NativeSkyCollectionProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(4142)
        for _ in range(100):
            rows = [[rng.randrange(1 << 32) for _ in range(3)] for _ in range(rng.randrange(13))]
            actual = p.aggregate(rows)
            self.assertEqual(actual['counts'], accumulate_root_counts(rows))
            self.assertEqual(actual['references'], [p.BASE+0x2000+8*i for i in range(len(rows))])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_collector_and_visitor_routines_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); self.assertEqual(verify_native(image)['virtualSlots'], len(RELOCATIONS))
        for changed in ROUTINES:
            class Changed:
                elf = image.elf
                def read(self, at, size): return bytes(size) if at == changed else image.read(at, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_report_corrects_list_parameter_without_claiming_tree_or_sky_queue_recovery(self):
        from analyze_native_resources import NativeImage
        r = analyze_collection(NativeImage(NATIVE.read_bytes())); self.assertEqual(r['format'], FORMAT)
        self.assertFalse(r['appliedAsLiveState']); self.assertFalse(r['treeTraversalRecovered'])
        self.assertFalse(r['native']['actualSkyControllerRecovered'])
        self.assertIn('vector', r['parameterCorrection']['sceneVirtual0x78'])


if __name__ == '__main__': unittest.main()
