import copy
import random
import unittest
from pathlib import Path

from resource_packs import DEFAULT_SOURCE
from scene_rgb_offsets import (CALLSITES, PARAMETERS, ROUTINES, NativeFlashProbe,
    analyze_offsets, flash_phase, light_with_offsets, verify_native)
from scene_lighting import f32, lightmap_global

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class RGBOffsetTests(unittest.TestCase):
    def test_rgb_plateau_ends_before_hdr_tail_instead_of_sharing_a_smooth_fade(self):
        peak = flash_phase(1, 450, hdr_enabled=True)
        self.assertEqual(peak['ambientAdd'], PARAMETERS['ambientPeak'])
        self.assertEqual(peak['diffuseAdd'], PARAMETERS['diffusePeak'])
        self.assertEqual(peak['hdrFlash'], PARAMETERS['hdrPeak'])
        self.assertEqual(flash_phase(1, 300)['ambientAdd'], peak['ambientAdd'])
        tail = flash_phase(1, 299)
        self.assertEqual((tail['ambientAdd'], tail['diffuseAdd']), (0, 0))
        self.assertGreater(tail['hdrFlash'], 0)
        self.assertLess(tail['hdrFlash'], peak['hdrFlash'])
        self.assertEqual(flash_phase(1, 150)['hdrFlash'], f32(.5*PARAMETERS['hdrPeak']))
        self.assertEqual(flash_phase(1, 0)['hdrFlash'], 0)

    def test_non_lightning_positive_clock_clears_but_expired_clock_retains_previous_rgb_and_hdr(self):
        previous = dict(ambientAdd=.25, diffuseAdd=.5, hdrFlash=.75, hdrFlags=0x11)
        clear = flash_phase(4, 1, previous=previous)
        self.assertEqual((clear['ambientAdd'], clear['diffuseAdd'], clear['hdrFlash']), (0, 0, 0))
        self.assertEqual(clear['hdrFlags'], 0x08000001)
        self.assertEqual((clear['nextStrikeMs'], clear['remainingMs']), (0, 0))
        for remaining in (0, -1):
            kept = flash_phase(4, remaining, previous=previous)
            self.assertEqual({k: kept[k] for k in previous}, previous)
            self.assertEqual((kept['nextStrikeMs'], kept['remainingMs']), (0, 0))
        missing = flash_phase(1, 100, previous=previous, next_strike_ms=800, context_available=False)
        self.assertEqual({k: missing[k] for k in previous}, previous)
        self.assertEqual((missing['nextStrikeMs'], missing['remainingMs']), (800, 100))

    def test_hdr_config_gates_flag_activation_only_and_dirty_bit_changes_only_when_bit4_changes(self):
        disabled = flash_phase(1, 450)
        enabled = flash_phase(1, 450, hdr_enabled=True)
        self.assertEqual(disabled['hdrFlags'], 0)
        self.assertEqual(enabled['hdrFlags'], 0x08000010)
        for key in ('ambientAdd', 'diffuseAdd', 'hdrFlash'): self.assertEqual(disabled[key], enabled[key])
        previous = dict(ambientAdd=0, diffuseAdd=0, hdrFlash=0, hdrFlags=0x12)
        self.assertEqual(flash_phase(1, 450, previous=previous, hdr_enabled=True)['hdrFlags'], 0x12)
        self.assertEqual(flash_phase(1, 0, previous=previous)['hdrFlags'], 0x08000002)
        with self.assertRaises(ValueError): flash_phase(1, 1, tail_ms=0)
        with self.assertRaises(ValueError): flash_phase(1, 1 << 31)

    def test_two_scalar_adds_precede_diffuse_half_and_model_intensity_without_clamping(self):
        self.assertEqual(light_with_offsets([1, 2, 3], [2, 4, 6], [.25, .5], 2), [5, 9, 13])
        self.assertEqual(light_with_offsets([0]*3, [0]*3, [-1, -.5], 2), [-2.5]*3)
        with self.assertRaises(ValueError): light_with_offsets([1, 2], [1, 2, 3], [0, 0], 1)


@unittest.skipUnless(NATIVE.is_file(), 'Original renderer/weather ARM64 evidence stays local')
class NativeRGBOffsetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes()); cls.probe = NativeFlashProbe(cls.image)

    def test_original_constructor_clears_controller_and_initializes_nine_exact_parameters(self):
        actual = self.probe.constructor()
        self.assertEqual(actual, tuple(PARAMETERS.values()))
        self.assertEqual(self.probe.read(0x10004000, '72s')[0], bytes(72))

    def test_weather_owner_reader_virtual_bindings_and_confirmed_rgb_writers_are_fingerprint_pinned(self):
        result = verify_native(self.image)
        self.assertEqual(result['newRoutines'], 7); self.assertEqual(result['ownerCallsites'], 3)
        self.assertEqual(result['weatherController'], 'world+0x288')
        self.assertFalse(result['allWritersRecovered']); self.assertFalse(result['appliedToRendering'])
        for changed in ROUTINES | CALLSITES:
            class Changed:
                elf = self.image.elf
                def read(_, address, size):
                    return bytes(size) if address == changed else self.image.read(address, size)
            with self.subTest(changed=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    def test_original_phase_matches_boundary_and_random_explicit_clock_config_and_stale_state_cases(self):
        rng = random.Random(0x36ede8)
        before = dict(ambientAdd=.25, diffuseAdd=.5, hdrFlash=.75, hdrFlags=0x10)
        for index in range(100):
            mode = rng.choice((0, 1, 4, 0xffffffff))
            remaining = rng.choice((-1, 0, 1, 150, 299, 300, 450, (1 << 24)+1, (1 << 31)-1))
            inputs = dict(previous=copy.deepcopy(before), hdr_enabled=bool(index % 2),
                          tail_ms=rng.choice((150, 300, 1000, 1 << 24)),
                          peaks=[rng.choice((-.5, .0675, .36, 2)) for _ in range(3)],
                          next_strike_ms=-100 if index % 3 else 900,
                          context_available=index % 7 != 0)
            inputs['previous']['hdrFlags'] = rng.choice((0, 0x10, 0x12, 0x08000010, 0xffffffff))
            with self.subTest(index=index):
                self.assertEqual(self.probe.run(mode, remaining, **inputs), flash_phase(mode, remaining, **inputs))

    def test_original_renderer_adds_each_scalar_to_three_channels_before_calling_global_light(self):
        ambient, diffuse, adds = [.1, .2, .3], [.4, .5, .6], [.0675, .36]
        a, d = self.probe.consumer_inputs(ambient, diffuse, adds)
        self.assertEqual(a, [f32(f32(v)+f32(adds[0])) for v in ambient])
        self.assertEqual(d, [f32(f32(v)+f32(adds[1])) for v in diffuse])
        self.assertEqual(lightmap_global(a, d, 1.33), light_with_offsets(ambient, diffuse, adds, 1.33))

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(), 'Original source tables stay local')
    def test_original_tutorial_uses_ash_extra4_and_default0_not_lightning1(self):
        result = analyze_offsets(self.image)
        self.assertEqual(result['sourceWeatherRowCount'], 13)
        refs = result['tutorialPlainWeather']
        self.assertEqual({r['zoneId']: (r['weatherId'], r['plainExtraMode']) for r in refs},
                         {194: (0, 0), 195: (6, 4), 196: (0, 0), 197: (0, 0), 199: (0, 0)})
        self.assertFalse(any(r['lightningMode1'] for r in refs))
        self.assertEqual(result['weather6Effects']['effect1'], 'Effects/scene/scene_weather_ash.beff')
        self.assertEqual(len(result['explicitPhaseSamples']), 14)
        self.assertFalse(result['nativeActiveStateObserved']); self.assertFalse(result['appliedToRendering'])


if __name__ == '__main__': unittest.main()
