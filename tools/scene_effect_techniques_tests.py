import random
import unittest
from pathlib import Path

from scene_effect_techniques import (FORMAT, ROUTINES, intermediate_header, validate_inputs,
                                     verify_native, analyze_techniques)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


def rows(counts=(1,), flags=0):
    return [{'name': 'tech'+str(i), 'passes': [{'state': bytes(28), 'programWordE2': flags,
             'programByteDF': 0} for _ in range(n)]} for i, n in enumerate(counts)]


def probe():
    from analyze_native_resources import NativeImage
    from native_effect_technique_probe import NativeEffectTechniqueProbe
    p = NativeEffectTechniqueProbe(NativeImage(NATIVE.read_bytes())); p.use_fixture()
    return p


class EffectTechniqueTests(unittest.TestCase):
    def test_intermediate_header_uses_count_low_byte_independently_of_program_metadata(self):
        for n in (0, 1, 2, 255, 256, 257, 0xffffff01):
            self.assertEqual(intermediate_header(n), int(n & 255 == 1))
        for n in (True, -1, 1 << 32):
            with self.assertRaises(ValueError): intermediate_header(n)

    def test_probe_inputs_require_bounded_distinct_preselected_names_and_explicit_metadata(self):
        self.assertEqual(validate_inputs(rows((1, 2, 3)), 0xffffffff),
                         {'techniqueCount': 3, 'passCounts': [1, 2, 3], 'intermediateHeaders': [1, 0, 0]})
        duplicate = rows((1, 1)); duplicate[1]['name'] = duplicate[0]['name']
        for values in [(duplicate, 0), ([], 0), (rows((0,)), 0), (rows((4,)), 0), (rows(), True)]:
            with self.assertRaises(ValueError): validate_inputs(*values)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_pass_admission_and_finalizer_preserve_order_state_refs_and_pool_reuse(self):
        p = probe(); rng = random.Random(0x1404728)
        total_passes = 0; total_techniques = 0
        for i in range(32):
            counts = [rng.randrange(1, 4) for _ in range(rng.randrange(1, 6))]
            r = rows(counts)
            for t in r:
                for v in t['passes']:
                    v.update(state=rng.randbytes(28), programWordE2=rng.getrandbits(16), programByteDF=rng.getrandbits(8))
            result = p.build(r, (0, 1, 0xfffffffe, 0xffffffff)[i % 4]); total = sum(counts)
            total_passes += total; total_techniques += len(counts)
            self.assertEqual(result['builderCount'], len(r)); self.assertEqual(result['originalIndexByte'], len(r))
            self.assertEqual(result['currentName'], 0); self.assertTrue(result['modeRestored'])
            for key in ('compilerFixtureCalls', 'poolCalls', 'cleanupCalls'):
                self.assertEqual(result[key], total)
            for key in ('constructorCalls', 'finalizerCalls'): self.assertEqual(result[key], len(r))
            self.assertEqual(result['programReferences'], [100]*total)
            for actual, source in zip(result['techniques'], r):
                self.assertEqual(actual['name'], source['name'])
                self.assertEqual(actual['passCount'], len(source['passes']))
                self.assertEqual(actual['headerByte11'], int(len(source['passes']) == 1))
                self.assertEqual(actual['states'], [v['state'].hex() for v in source['passes']])
                self.assertEqual(actual['flags'], [255]*len(source['passes']))
                self.assertEqual(actual['reflectionWords'], [[0]*4]*len(source['passes']))
            self.assertLessEqual(len(set(result['nodeUses'])), max(counts))
        self.assertGreater(total_passes, 160); self.assertGreater(total_techniques, 80)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_intermediate_and_final_headers_have_separate_producers(self):
        p = probe()
        for flags in (0, 0x40, 0x400, 0xffff):
            for finalize in (0, 1):
                result = p.build(rows((1, 2, 3), flags), finalize); actual = p.assemble_built()
                self.assertEqual([v['headerByte11'] for v in result['techniques']], [1, 0, 0])
                self.assertEqual([v['headerByte11'] for v in actual['techniques']], [int(bool(flags & 0x400)), 0, 0])
                self.assertEqual(actual['packedWord'], 0x300)
                self.assertEqual(actual['originalModifierCountCalls'], 2)
                self.assertEqual(actual['intermediateFactoryInputs'], [{'techniqueCount': 3, 'pointerArray': p.TECH+0x900}])
                self.assertEqual([v['programReferences'] for t in actual['techniques'] for v in t['passes']], [101]*6)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_constructor_consumes_actual_intermediate_storage_instead_of_rebuilt_copies(self):
        p = probe(); inputs = rows(); p.build(inputs)
        object_at = p.read(p.TECH+0x900, 'Q')[0]; passes = p.read(object_at+8, 'Q')[0]
        changed = bytes(range(28)); p.uc.mem_write(passes, changed)
        p.write(p.programs[0]+0xe2, 'H', 0x400)
        result = p.assemble_built()
        self.assertEqual(result['techniques'][0]['passes'][0]['state'], changed)
        self.assertEqual(result['techniques'][0]['headerByte11'], 1)
        self.assertEqual(inputs[0]['passes'][0]['state'], bytes(28))
        self.assertEqual(inputs[0]['passes'][0]['programWordE2'], 0)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_source_profiles_translate_admit_finalize_and_feed_real_effect_constructor(self):
        from scene_effect_modifiers import source_profiles
        from scene_sky_binding_tests import source_extract
        p = probe(); source = source_profiles(source_extract())
        for profile in source['profiles']:
            for flags in (0, 0x440):
                p.use_source(source, profile['field'])
                inputs = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                           'programWordE2': flags, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
                result = p.build(inputs); actual = p.assemble_built()
                self.assertEqual(result['builderCount'], 3); self.assertEqual(result['cleanupCalls'], 3)
                self.assertEqual([v['name'] for v in actual['techniques']], ['tech0', 'blend', 'solid'])
                self.assertEqual([v['headerByte11'] for v in result['techniques']], [1]*3)
                self.assertEqual([v['headerByte11'] for v in actual['techniques']], [int(bool(flags & 0x400))]*3)
                self.assertEqual(actual['packedWord'], 0x300)
                self.assertEqual([v['passes'][0]['state'] for v in actual['techniques']], [v['passes'][0]['state'] for v in inputs])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_uncovered_provider_route_and_changed_original_code_are_rejected(self):
        p = probe()
        for names, policy in [([], 1), (['feature'], 0)]:
            p.use_fixture(names, policy)
            with self.assertRaises(ValueError): p.build(rows())
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in ROUTINES:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_report_keeps_compilation_profiles_driver_and_live_rendering_unclaimed(self):
        from analyze_native_resources import NativeImage
        from scene_sky_binding_tests import source_extract
        report = analyze_techniques(NativeImage(NATIVE.read_bytes()), source_extract())
        self.assertEqual(report['format'], FORMAT)
        self.assertEqual([p['modifierCount'] for p in report['sourceProfiles']], [0, 0])
        for key in ('fullCompilerExecuted', 'activeProfileRecovered', 'GPUExecuted', 'appliedAsLiveState'):
            self.assertFalse(report[key])


if __name__ == '__main__': unittest.main()
