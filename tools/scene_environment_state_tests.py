import copy
import math
import unittest
from pathlib import Path

from resource_packs import DEFAULT_SOURCE
from scene_environment_state import (RENDERER_CALLSITES, ROUTINES, U32, EnvironmentValue, analyze_environment,
    apply_zone_targets, initial_environment, light_rgb_roundtrip, sample, verify_native)
from scene_lighting import DEFAULTS, f32, lightmap_global, tone_distance_uniform, zone_targets

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def targets(**overrides):
    row = {'ID': 1, 'light_ambient': 0xffffff, 'light_diffuse': 0xffffff,
           'tone_near': 0.0, 'tone_half': 0.0, 'tone_color_near': 0,
           'tone_color_far': 0, **{name: 0.0 for name in DEFAULTS}, 'model_intensity_lightMap': 0.0}
    return zone_targets(row | overrides)


class EnvironmentStateTests(unittest.TestCase):
    def test_constructor_known_fields_are_independent_and_skipped_tone_has_a_real_initial_value(self):
        a, b = initial_environment(), initial_environment()
        self.assertEqual(len(a), 13)
        self.assertEqual(sample(a)['values']['toneDistance'], [0, 50])
        self.assertEqual(sample(a)['toneDistanceUniform'], [0, f32(-1/50)])
        self.assertEqual(a['toneGainNear'].read(), [1, 1, 1])
        self.assertEqual(a['toneOffsetNear'].read(), [0, 0, 0])
        a['ambient'].set([.1, .2, .3])
        self.assertEqual(b['ambient'].read(), [1, 1, 1])
        apply_zone_targets(a, targets())
        self.assertEqual(a['toneDistance'].read(), [0, 50])

    def test_scalar_vec2_vec3_reads_interpolate_without_mutating_base_or_clocks(self):
        for width in (1, 2, 3):
            value = EnvironmentValue([0]*width)
            value.set([10]*width, 2000)
            value.advance(500)
            before = copy.deepcopy(value.__dict__)
            self.assertEqual(value.read(), [2.5]*width)
            self.assertEqual(value.__dict__, before)
            value.advance(1500)
            self.assertEqual(value.read(), [10]*width)
            self.assertEqual(value.pending, [])

    def test_pending_clocks_run_in_parallel_and_values_fold_in_insertion_order(self):
        value = EnvironmentValue([0])
        value.set([10], 2000); value.advance(500)
        value.set([20], 2000); value.advance(500)
        self.assertEqual([p['elapsed'] for p in value.pending], [1000, 500])
        self.assertEqual(value.read(), [8.75])  # 0 -> 5 -> 8.75.
        self.assertNotEqual(value.read(), [5])  # Latest target alone is wrong.
        value.advance(1000)
        self.assertEqual(value.base, [10])
        self.assertEqual(value.read(), [17.5])
        self.assertEqual(len(value.pending), 1)

    def test_later_short_transition_completion_prunes_earlier_unfinished_nodes(self):
        value = EnvironmentValue([0])
        value.set([10], 2000); value.advance(200)
        value.set([99], 100); value.advance(100)
        self.assertEqual(value.base, [99])
        self.assertEqual(value.pending, [])
        self.assertEqual(value.read(), [99])

    def test_same_target_does_not_restart_an_earlier_finish_but_can_append_a_shorter_clock(self):
        value = EnvironmentValue([0, 0])
        self.assertFalse(value.set([0, 0], 2000))
        self.assertTrue(value.set([10, 20], 2000)); value.advance(500)
        self.assertFalse(value.set([10, 20], 1500))
        self.assertEqual(value.pending[-1]['elapsed'], 500)
        self.assertTrue(value.set([10, 20], 1499))
        self.assertEqual(len(value.pending), 2)
        value.set([7, 8], 0)
        self.assertEqual(value.read(), [7, 8])
        self.assertEqual(value.pending, [])

    def test_advance_guard_and_uint32_counter_addition_follow_native_boundaries(self):
        value = EnvironmentValue([0]); value.set([1], U32)
        before = copy.deepcopy(value.__dict__)
        for delta in (0, 100001, U32): self.assertFalse(value.advance(delta))
        self.assertEqual(value.__dict__, before)
        self.assertTrue(value.advance(1)); self.assertTrue(value.advance(100000))
        self.assertEqual(value.pending[0]['elapsed'], 100001)
        value.pending[0]['elapsed'] = U32-10
        value.advance(20)
        self.assertEqual(value.pending[0]['elapsed'], 9)
        for invalid in (-1, U32+1, True, 1.0):
            with self.assertRaises(ValueError): value.advance(invalid)

    def test_invalid_targets_are_rejected_before_mutation_and_float32_equal_targets_deduplicate(self):
        value = EnvironmentValue([.1])
        self.assertFalse(value.set([f32(.1)], 100))
        for invalid in ([math.nan], [1e100], [True], [1, 2]):
            before = copy.deepcopy(value.__dict__)
            with self.assertRaises(ValueError): value.set(invalid, 100)
            self.assertEqual(value.__dict__, before)
        environment = initial_environment()
        before = copy.deepcopy({k: v.__dict__ for k, v in environment.items()})
        bad = targets(tone_half=17)
        bad['tone']['gainFar'] = [1, math.nan, 1]
        with self.assertRaises(ValueError): apply_zone_targets(environment, bad, 1000)
        self.assertEqual({k: v.__dict__ for k, v in environment.items()}, before)

    def test_half_span_blends_before_reciprocal_and_skipped_gain_keeps_pending_state(self):
        environment = initial_environment()
        environment['toneGainNear'].set([.5]*3, 1000)
        apply_zone_targets(environment, targets(tone_half=17), 2000)
        self.assertEqual(len(environment['toneGainNear'].pending), 1)
        for value in environment.values(): value.advance(1000)
        state = sample(environment)
        self.assertEqual(state['values']['toneDistance'], [0, 33.5])
        self.assertEqual(state['toneDistanceUniform'], tone_distance_uniform(0, 33.5))
        wrong = f32((f32(-1/50)+f32(-1/17))*.5)
        self.assertNotEqual(state['toneDistanceUniform'][1], wrong)
        self.assertEqual(state['values']['toneGainNear'], [.5]*3)

    def test_intermediate_light_rgb_is_byte_quantized_before_global_lighting_but_tone_gain_is_not(self):
        environment = initial_environment()
        environment['ambient'].set([0]*3)
        environment['diffuse'].set([0]*3)
        environment['ambient'].set([1]*3, 2000)
        environment['ambient'].advance(1000)
        environment['toneGainNear'].set([.5]*3)
        state = sample(environment)
        self.assertEqual(state['values']['ambient'], [.5]*3)
        quantized = light_rgb_roundtrip([.5]*3)
        self.assertEqual(quantized, [f32(128*f32(1/255))]*3)
        self.assertEqual(state['nativeLightInputRGB']['ambient'], quantized)
        self.assertEqual(state['modelLightBeforeRuntimeRGBAdds'], lightmap_global(quantized, [0]*3, f32(1.33)))
        self.assertNotEqual(state['modelLightBeforeRuntimeRGBAdds'], lightmap_global([.5]*3, [0]*3, f32(1.33)))
        self.assertEqual(state['values']['toneGainNear'], [.5]*3)
        for invalid in ([-.01, 0, 0], [1.01, 0, 0], [math.nan, 0, 0], [1, 2]):
            with self.assertRaises(ValueError): light_rgb_roundtrip(invalid)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native evidence stays local')
    def test_native_constructor_advance_and_separate_receiver_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual(result['initialToneDistance'], [0, 50])
        self.assertEqual(result['acceptedAdvanceMilliseconds'], [1, 100000])
        self.assertEqual(result['rendererCallsites'], 2)
        self.assertFalse(result['appliedToRendering'])
        for changed in ROUTINES | RENDERER_CALLSITES:
            class Changed:
                elf = image.elf
                def read(self, address, size):
                    return bytes(size) if address == changed else image.read(address, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(), 'Original environment evidence stays local')
    def test_explicit_tutorial_timeline_retains_base_half_then_reaches_original_overlay_targets(self):
        report = analyze_environment()
        self.assertEqual(report['afterExplicitBase194']['values']['toneDistance'], [0, 50])
        trace = report['scriptedOverlay195']
        self.assertEqual([s['elapsedMilliseconds'] for s in trace], [0, 500, 1000, 2000])
        self.assertEqual([s['values']['toneDistance'][1] for s in trace], [50, 41.75, 33.5, 17])
        self.assertEqual(trace[-1]['toneDistanceUniform'], tone_distance_uniform(0, 17))
        self.assertTrue(all(size == 0 for size in trace[-1]['queueLengths'].values()))
        self.assertEqual(report['rendererRGBAddConstructor']['ambient'], 0)
        self.assertFalse(report['rendererRGBAddConstructor']['allLaterWritersRecovered'])
        self.assertFalse(report['nativeActiveStateObserved'])
        self.assertFalse(report['appliedToRendering'])


if __name__ == '__main__': unittest.main()
