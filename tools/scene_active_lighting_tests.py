import copy
import random
import struct
import unittest
from pathlib import Path

from scene_active_lighting import (CHANNELS, ROUTINES, NativeTargetProbe,
    analyze_active_lighting, apply_selected_lighting, state_record,
    transition_duration, verify_native)
from scene_environment_state import initial_environment
from scene_lighting import DEFAULTS
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def row(ident=1, **overrides):
    return {'ID': ident, 'light_ambient': 0xffffff, 'light_diffuse': 0xffffff,
            'tone_near': 0.0, 'tone_half': 0.0, 'tone_color_near': 0, 'tone_color_far': 0,
            **{name: 0.0 for name in DEFAULTS}, 'model_intensity_lightMap': 0.0} | overrides


class SelectedLightingTests(unittest.TestCase):
    def test_absent_pair_preserves_values_and_existing_queues_instead_of_falling_back_194(self):
        environment = initial_environment()
        environment['ambient'].set([.1, .2, .3], 1234)
        environment['toneDistance'].set([7, 17], 2345)
        for value in environment.values(): value.advance(111)
        before = state_record(copy.deepcopy(environment))
        result = apply_selected_lighting(environment, None, None, 4)
        self.assertIsNone(result['selectedZoneId']); self.assertEqual(result['writes'], {})
        self.assertEqual(state_record(environment), before)
        for invalid in (True, -1, 1 << 32, 4.0):
            with self.assertRaises(ValueError): apply_selected_lighting(environment, None, None, invalid)
        self.assertEqual(state_record(environment), before)

    def test_explicit_mode4_queues_2000ms_and_other_or_absent_modes_apply_immediately(self):
        base = row(194, light_ambient=0x0000ff, intensity_common=2, tone_near=7, tone_half=17,
                   tone_color_near=0xff0000)
        for mode in (None, 0, 1, 2, 3, 4, 5, 0xffffffff):
            environment = initial_environment()
            result = apply_selected_lighting(environment, base, None, mode)
            self.assertEqual(result['selectedZoneId'], 194)
            if mode == 4:
                self.assertEqual(environment['toneDistance'].base, [0, 50])
                self.assertEqual(environment['toneDistance'].pending,
                                 [{'duration': 2000, 'elapsed': 0, 'target': [7, 17]}])
                self.assertEqual(environment['ambient'].base, [1, 1, 1])
            else:
                self.assertEqual(environment['toneDistance'].base, [7, 17])
                self.assertEqual(environment['toneDistance'].pending, [])
                self.assertEqual(environment['ambient'].base, [1, 0, 0])
            self.assertEqual(result['durationMilliseconds'], transition_duration(mode))

    def test_selected_child_keeps_generic_owner_coupling_and_skipped_tone_pending_state(self):
        environment = initial_environment()
        environment['toneDistance'].set([8, 17], 1000)
        environment['toneDistance'].advance(300)
        before = copy.deepcopy(environment['toneDistance'].__dict__)
        base = row(194, intensity_lightMap=2, model_intensity_lightMap=3)
        child = row(195, model_intensity_lightMap=9)
        result = apply_selected_lighting(environment, base, child, None)
        self.assertEqual(result['selectedZoneId'], 195)
        self.assertEqual(environment['model_intensity_lightMap'].base, [3])
        self.assertEqual(environment['toneDistance'].__dict__, before)
        self.assertNotIn('toneDistance', result['writes'])
        apply_selected_lighting(environment, None, row(196, intensity_lightMap=4), None)
        self.assertEqual(environment['model_intensity_lightMap'].base, [4])


@unittest.skipUnless(NATIVE.is_file(), 'Original ARM64 environment evidence stays local')
class NativeSelectedLightingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.probe = NativeTargetProbe(cls.image)

    def compare(self, environment, base, overlay, mode):
        expected = copy.deepcopy(environment)
        apply_selected_lighting(expected, base, overlay, mode)
        for entry in ('selection', 'override'):
            actual = self.probe.run(environment, base, overlay, mode, entry=entry)
            self.assertEqual(state_record(actual), state_record(expected), entry)

    def test_actual_entry_and_original_list_insertion_are_fingerprint_pinned(self):
        result = verify_native(self.image)
        self.assertEqual(result['verifiedChannelCount'], 13)
        self.assertFalse(result['fullEntryEquivalent']); self.assertFalse(result['appliedToRendering'])
        for changed in ROUTINES:
            class Changed:
                elf = self.image.elf
                def read(_, address, size):
                    return bytes(size) if address == changed else self.image.read(address, size)
            with self.subTest(changed=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    def test_both_native_entries_match_float32_near_zero_edges_negative_values_and_color_byte_order(self):
        boundary = struct.unpack('<I', struct.pack('<f', 1e-6))[0]
        outside = struct.unpack('<f', struct.pack('<I', boundary+1))[0]
        rng = random.Random(0x4c5b90)
        values = (0, 1e-6, -1e-6, outside, -outside, -2, 3.25)
        for index in range(70):
            base, child = row(194), row(195)
            for name in (*DEFAULTS, 'model_intensity_lightMap'):
                base[name], child[name] = rng.choice(values), rng.choice(values)
            base.update(light_ambient=rng.randrange(1 << 24), light_diffuse=rng.randrange(1 << 24),
                        tone_near=-4, tone_half=rng.choice((0, -2, 17)),
                        tone_color_near=0x112233, tone_color_far=0x445566)
            child.update(light_ambient=rng.choice((0, 0x123456)), light_diffuse=rng.choice((0, 0xabcdef)),
                         tone_near=9, tone_half=rng.choice((0, -3, 23)),
                         tone_color_near=rng.choice((0, 0x445566)), tone_color_far=rng.choice((0, 0x112233)))
            with self.subTest(index=index):
                self.compare(initial_environment(), base if index % 5 else None,
                             child if index % 7 else None, (None, 3, 4)[index % 3])

    def test_real_native_writers_preserve_skip_and_handle_immediate_clear_duplicate_and_shorter_targets(self):
        base = row(194, light_ambient=0x112233, intensity_common=2, tone_half=0)
        child = row(195, light_ambient=0, tone_half=0)
        target = initial_environment()
        apply_selected_lighting(target, base, child, None)
        for duration in (1000, 3000):
            environment = initial_environment()
            for name, value in environment.items():
                # Two nodes exercise original list traversal/last target tests.
                value.set([.2]*len(value.base), 4000)
                value.set(target[name].base, duration)
                value.advance(300)
            for mode in (None, 4):
                with self.subTest(duration=duration, mode=mode):
                    self.compare(environment, base, child, mode)

    def test_native_tone_zero_offsets_do_not_alias_gains_and_float_pair_is_raw_near_half(self):
        environment = initial_environment()
        for name in ('toneOffsetNear', 'toneOffsetFar'): environment[name].set([.1, .2, .3])
        base = row(194, tone_near=7, tone_half=17, tone_color_near=0xff0000, tone_color_far=0x00ff00)
        for mode in (None, 4): self.compare(environment, base, None, mode)
        actual = self.probe.run(environment, base, None, None)
        self.assertEqual(actual['toneDistance'].base, [7, 17])
        self.assertEqual(actual['toneGainNear'].base, [0, 0, 1])
        self.assertEqual(actual['toneGainFar'].base, [0, 1, 0])
        self.assertEqual(actual['toneOffsetNear'].base, [0, 0, 0])
        self.assertEqual(actual['toneOffsetFar'].base, [0, 0, 0])
        self.assertEqual(set(actual), set(CHANNELS))

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(), 'Original zone table stays local')
    def test_all_five_tutorial_rows_and_no_selection_match_both_native_entries_in_three_explicit_modes(self):
        result = analyze_active_lighting(self.image)
        self.assertEqual(len(result['explicitSourceQueries']), 18)
        self.assertEqual({q['overlayId'] for q in result['explicitSourceQueries']}, {None, 195, 196, 197, 199})
        self.assertEqual(sum(q['nativeBlocksExecuted'] for q in result['explicitSourceQueries']), 15)
        self.assertTrue(all(q['nativeBlocksEqualOracle'] for q in result['explicitSourceQueries']))
        self.assertFalse(result['nativeActiveStateObserved']); self.assertFalse(result['appliedToRendering'])


if __name__ == '__main__': unittest.main()
