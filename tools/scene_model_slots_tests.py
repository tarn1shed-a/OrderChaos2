import copy
import itertools
import random
import unittest
from pathlib import Path

from scene_lighting import f32
from scene_model_slots import (CALLSITES, FORMAT, GLOBALS, ROUTINES, analyze_slots,
    bounds_parameters, completion_refresh, configured_request, distance_request,
    slot_transition, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def params(**changes):
    return dict(center=[0, 0, 0], position=[0, 0, 0], radius=0, scale160=1, config18=10) | changes


class ModelSlotTests(unittest.TestCase):
    def test_bounds_have_separate_height_weighted_scale_and_preserve_non_special_prior_scale(self):
        result = bounds_parameters([-1, -1, -1, 1, 1, 1])
        self.assertEqual(result['center'], [0, 0, 0])
        self.assertNotEqual(result['radius'], result['scale160'])
        self.assertAlmostEqual(result['radius'], 3**.5, places=6)
        self.assertAlmostEqual(result['scale160'], 6**.5, places=6)
        self.assertEqual(bounds_parameters([0]*6, 'hum_archi_stonewall_test')['scale164'], 2.5)
        self.assertEqual(bounds_parameters([0]*6, 'ordinary', 2.5)['scale164'], 2.5)

    def test_inner_outer_boundaries_use_previous_requested_slot_not_a_single_cutoff(self):
        self.assertEqual(distance_request(**params(position=[8, 0, 0])), 0)
        self.assertEqual(distance_request(**params(position=[9, 0, 0])), 1)
        self.assertIsNone(distance_request(**params(position=[16, 0, 0])))  # Already sentinel2.
        self.assertIsNone(distance_request(**params(position=[13, 0, 0], current=0)))
        self.assertEqual(distance_request(**params(position=[13, 0, 0], current=2)), 1)
        self.assertIsNone(distance_request(**params(position=[23, 0, 0], current=1)))
        self.assertEqual(distance_request(**params(position=[24, 0, 0], current=1)), 2)
        self.assertEqual(distance_request(**params(position=[0, 24, 0], current=1)), 2)  # Full XYZ distance.
        self.assertEqual(distance_request(**params(position=[24, 0, 0], current=1, config28=0)), 2)

    def test_config_compare_order_projection_hysteresis_and_explicit_metric_requirements(self):
        self.assertIsNone(distance_request(**params(position=[10, 0, 0], current=1, config28=0)))
        self.assertEqual(configured_request(0, 1, 1), 0)  # Manual wrapper has different ordering.
        self.assertIsNone(distance_request(**params(current=0, projection_enabled=True, projection_metric=.09, config14=.1)))
        self.assertEqual(distance_request(**params(current=1, projection_enabled=True, projection_metric=.09, config14=.1)), None)
        self.assertEqual(distance_request(**params(current=2, projection_enabled=True, projection_metric=.09, config14=.1)), 1)
        with self.assertRaises(ValueError): distance_request(**params(projection_enabled=True))
        self.assertEqual(distance_request(**params(projection_enabled=True, context_available=False)), 0)
        self.assertIsNone(distance_request(**params(scale160=-1, projection_enabled=True)))

    def test_loaded_fallback_sentinel_and_deferred_queue_are_distinct_states(self):
        fallback = slot_transition(2, 2, [True, False], 1)
        self.assertEqual((fallback['requested'], fallback['active']), (1, 0))
        self.assertTrue(fallback['apply'])
        missing = slot_transition(0, 1, [False, False], 0)
        self.assertEqual(missing['active'], 1)  # No loaded candidate keeps previous.
        self.assertEqual(slot_transition(1, 1, [True, True], 2)['active'], 2)
        pending = slot_transition(0, 0, [True, True], 1, defer=True, mask_matches=True)
        self.assertTrue(pending['allocate']); self.assertTrue(pending['queued']); self.assertFalse(pending['apply'])
        broken_membership = slot_transition(0, 0, [True, True], 1, queued=True, contains=False)
        self.assertTrue(broken_membership['queued']); self.assertFalse(broken_membership['apply'])

    def test_completion_rechecks_requested_slot_and_updates_even_when_arrival_is_lower(self):
        self.assertTrue(completion_refresh(1, 0, 1))
        self.assertTrue(completion_refresh(1, 1, 0))
        self.assertFalse(completion_refresh(0, 0, 1))
        self.assertFalse(completion_refresh(2, 0, 1))


@unittest.skipUnless(NATIVE.is_file(), 'Original model-slot ARM64 evidence stays local')
class NativeModelSlotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from native_model_slot_probe import NativeModelSlotProbe
        cls.image = NativeImage(NATIVE.read_bytes()); cls.probe = NativeModelSlotProbe(cls.image)

    def test_selector_bounds_queue_consumers_and_caller_slices_are_fingerprint_pinned(self):
        result = verify_native(self.image)
        self.assertEqual(result['newRoutines'], 4); self.assertEqual(result['callerSlices'], 2)
        self.assertFalse(result['projectedAreaProducerRecovered']); self.assertFalse(result['appliedToRendering'])
        for changed in [*(ROUTINES | CALLSITES), 0x25091c4, 0x1df7a10, 0x1df8f2e]:
            class Changed:
                elf = self.image.elf
                def read(_, address, size):
                    return bytes(size) if address == changed else self.image.read(address, size)
            with self.subTest(changed=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())
        report = analyze_slots(self.image)
        self.assertEqual(report['format'], FORMAT); self.assertEqual(len(report['explicitDistanceExperiments']), 7)

    def test_original_bounds_tail_matches_float32_asymmetric_and_special_name_cases(self):
        rng = random.Random(0x340f9c)
        for index in range(50):
            low = [rng.uniform(-100, 0) for _ in range(3)]
            high = [rng.uniform(0, 200) for _ in range(3)]
            name = ('ordinary', 'hum_archi_stonewall_A', 'hum_other_step_B', 'hum_other_fountain_C')[index % 4]
            previous = 1 if index % 2 else 2.5
            with self.subTest(index=index):
                self.assertEqual(self.probe.bounds(low+high, name, previous), bounds_parameters(low+high, name, previous))

    def test_original_selector_matches_explicit_distance_direction_projection_and_config_matrix(self):
        rng = random.Random(0x341c60)
        for index in range(240):
            g = copy.deepcopy(GLOBALS); g['minimumSlot'] = rng.choice((-1, 0, 1, 2))
            values = params(center=[rng.uniform(-10, 10) for _ in range(3)],
                            position=[rng.uniform(-60, 60) for _ in range(3)],
                            radius=rng.choice((0, 1, 5)), scale160=rng.choice((-1, 0, .5, 2)),
                            scale164=rng.choice((1, 2.5)), override168=rng.choice((-1, -.5, 25)),
                            current=rng.randrange(3), config28=rng.randrange(3), config18=rng.choice((1, 10, 30)),
                            override_enabled=bool(index % 2), direction_enabled=bool(index % 3),
                            context_available=index % 7 != 0,
                            camera_first=[1, 3, 5], camera_second=[-2, 1, -4],
                            projection_enabled=bool(index % 4), projection_metric=rng.choice((-1, 0, .05, .09, .2)),
                            config14=.1, globals=g)
            with self.subTest(index=index): self.assertEqual(self.probe.select(**values), distance_request(**values))
        # Source front multiplier is one float32 step below1, not exactly1.
        edge = params(position=[0, 0, 15.999999046325684], direction_enabled=True,
                      camera_first=[0, 0, 1], camera_second=[0, 0, -1])
        self.assertIsNone(self.probe.select(**edge))
        self.assertEqual(self.probe.select(**(edge | {'direction_enabled': False})), 1)
        for current, metric in itertools.product(range(3), (-1, 0, .05, .09, .12, .12000000476837158)):
            values = params(current=current, projection_enabled=True, projection_metric=metric, config14=.1)
            self.assertEqual(self.probe.select(**values), distance_request(**values))
        self.assertIsNone(self.probe.select(**params(position=[100, 0, 0], projection_enabled=True)))
        self.assertEqual(self.probe.metric_calls, 0)  # Far path never invokes unresolved area producer.

    def test_original_manual_wrapper_and_completion_callback_match_all_slot_combinations(self):
        for config, desired, current in itertools.product(range(3), repeat=3):
            self.assertEqual(self.probe.manual(config, desired, current), configured_request(config, desired, current))
        for requested, active, arrived in itertools.product(range(3), range(3), range(2)):
            refresh, mask = self.probe.completion(requested, active, arrived, 1)
            self.assertEqual(refresh, completion_refresh(requested, active, arrived))
            self.assertEqual(mask, 1 | (1 << arrived))

    def test_original_slot_writer_runs_real_intrusive_queue_insertion_removal_and_loaded_fallback(self):
        rng = random.Random(0x341aa0)
        for index in range(160):
            requested, active, desired = [rng.randrange(3) for _ in range(3)]
            loaded = [bool(rng.randrange(2)) for _ in range(2)]
            options = dict(defer=bool(index & 1), mask_matches=bool(index & 2),
                           queued=bool(index & 4), contains=bool(index & 8))
            with self.subTest(index=index):
                self.assertEqual(self.probe.transition(requested, active, loaded, desired, **options),
                                 slot_transition(requested, active, loaded, desired, **options))


if __name__ == '__main__': unittest.main()
