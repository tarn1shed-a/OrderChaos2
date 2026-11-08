import random
import unittest
from pathlib import Path

from scene_effect_compiler import (FORMAT, COMPILER, COMPILER_SIZE, FRONTIER,
                                   empty_input_contract, verify_native, analyze_compiler)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


def rows(counts=(1,), flags=0):
    return [{'name': 'tech'+str(i), 'passes': [{'state': bytes(28), 'programWordE2': flags,
             'programByteDF': 0} for _ in range(n)]} for i, n in enumerate(counts)]


def probe():
    from analyze_native_resources import NativeImage
    from native_effect_compiler_probe import NativeEffectCompilerProbe
    p = NativeEffectCompilerProbe(NativeImage(NATIVE.read_bytes())); p.use_fixture()
    return p


class EffectCompilerTests(unittest.TestCase):
    def test_explicit_empty_input_contract_keeps_pointer_count_and_effect_allocation_separate(self):
        result = empty_input_contract(rows((1, 2)), 'fixture')
        self.assertEqual(result, {'techniqueCount': 2, 'pointerArrayBytes': 16,
                                 'effectAllocationBytes': 384, 'index': 65535,
                                 'packedWord': 512, 'stackWords': [0]*7})
        for data, name in [([], 'fx'), (rows(), ''), (rows(), 'bad\0name')]:
            with self.assertRaises(ValueError): empty_input_contract(data, name)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_actual_compiler_traverses_built_lists_and_calls_constructor_without_patching_inputs(self):
        p = probe(); rng = random.Random(COMPILER)
        for i in range(32):
            inputs = rows([rng.randrange(1, 4) for _ in range(rng.randrange(1, 6))])
            for t in inputs:
                for v in t['passes']:
                    v.update(state=rng.randbytes(28), programWordE2=rng.getrandbits(16), programByteDF=rng.getrandbits(8))
            p.build(inputs, i & 1); pointers = p._list(p.TECH+0x58, 0x18)
            result = p.compile_frontier('effect'+str(i)); expected = empty_input_contract(inputs, 'effect'+str(i))
            f = result['factoryInput']
            self.assertEqual(result['frontier'], hex(FRONTIER)); self.assertFalse(result['factoryInputsPatched'])
            self.assertEqual(result['factoryTechniquePointers'], pointers)
            self.assertEqual(result['pointerArrayAllocationBytes'], [expected['pointerArrayBytes']])
            self.assertEqual(result['effectAllocationBytes'], [expected['effectAllocationBytes']])
            self.assertEqual((f['manager'], f['name'], f['provider']), (p.TECH+0x1000, p.TECH+0x1a00, p.EXT+0x2000))
            self.assertEqual((f['index'], f['techniqueCount'], f['ordinaryCount'], f['ordinaryArray']), (65535, len(inputs), 0, 0))
            self.assertEqual(f['stackWords'], [0]*7)
            self.assertEqual(result['inputBuilderHolder'], 0); self.assertEqual(result['publicOutput'], 0xfeedcafe)
            self.assertEqual(result['compilerModeAtFrontier'], 1); self.assertEqual(result['effectReferences'], 1)
            self.assertEqual(result['index'], 65535); self.assertEqual(result['packedWord'], expected['packedWord'])
            for actual, source in zip(result['techniques'], inputs):
                self.assertEqual(actual['name'], source['name'])
                self.assertEqual(actual['states'], [v['state'].hex() for v in source['passes']])
                self.assertEqual(actual['programReferences'], [101]*len(source['passes']))
                self.assertEqual(actual['headerByte11'], int(len(source['passes']) == 1 and bool(source['passes'][0]['programWordE2'] & 0x400)))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_real_list_order_and_intermediate_storage_control_original_compiler_inputs(self):
        p = probe(); original = rows((1, 1, 1)); p.build(original)
        pointers = p._list(p.TECH+0x58, 0x18)[::-1]; sentinel = p.TECH+0x58
        p.write(sentinel, '2Q', pointers[0]+0x18, pointers[-1]+0x18)
        for i, at in enumerate(pointers):
            p.write(at+0x18, '2Q', pointers[i+1]+0x18 if i+1 < len(pointers) else sentinel,
                    pointers[i-1]+0x18 if i else sentinel)
        passes = p.read(pointers[0]+8, 'Q')[0]; changed = bytes(range(28)); p.uc.mem_write(passes, changed)
        result = p.compile_frontier()
        self.assertEqual(result['factoryTechniquePointers'], pointers)
        self.assertEqual([t['name'] for t in result['techniques']], ['tech2', 'tech1', 'tech0'])
        self.assertEqual(result['techniques'][0]['states'], [changed.hex()])
        self.assertEqual([t['name'] for t in original], ['tech0', 'tech1', 'tech2'])
        self.assertEqual(original[2]['passes'][0]['state'], bytes(28))

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_both_source_profiles_feed_real_compiler_and_constructor_at_declared_frontier(self):
        from scene_effect_modifiers import source_profiles
        from scene_sky_binding_tests import source_extract
        p = probe(); source = source_profiles(source_extract())
        for profile in source['profiles']:
            for flags in (0, 0x440):
                p.use_source(source, profile['field'])
                inputs = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                           'programWordE2': flags, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
                p.build(inputs); result = p.compile_frontier()
                self.assertEqual(result['factoryInput']['techniqueCount'], 3)
                self.assertEqual(result['packedWord'], 0x300)
                self.assertEqual([t['name'] for t in result['techniques']], ['tech0', 'blend', 'solid'])
                self.assertEqual([t['states'][0] for t in result['techniques']], [t['passes'][0]['state'].hex() for t in inputs])
                self.assertEqual([t['headerByte11'] for t in result['techniques']], [int(bool(flags & 0x400))]*3)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_null_and_open_technique_guards_return_without_consuming_builder_or_calling_factory(self):
        p = probe()
        for null in (False, True):
            p.use_fixture(); p.build(rows()); result = p.reject_guard(null)
            self.assertEqual(result, {'output': 0, 'builderHolder': 0 if null else p.TECH, 'logs': 1, 'factoryCalled': False})

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_uncovered_binding_or_reflection_inputs_and_changed_native_code_fail_closed(self):
        p = probe(); p.build(rows()); p.write(p.TECH+0xd4, 'I', 1)
        with self.assertRaises(ValueError): p.compile_frontier()
        p.write(p.TECH+0xd4, 'I', 0)
        for offset, fmt in [(0xde, 'B'), (0x3a, 'H'), (0x6a, 'H'), (0x9a, 'H')]:
            p.write(p.programs[0]+offset, fmt, 1)
            with self.assertRaises(ValueError): p.compile_frontier()
            p.write(p.programs[0]+offset, fmt, 0)
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        def changed(at, size):
            raw = read(at, size)
            return raw[:-1]+bytes([raw[-1] ^ 1]) if at == COMPILER and size == COMPILER_SIZE else raw
        image.read = changed
        with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_report_distinguishes_observed_factory_inputs_from_cache_registration_and_live_compilation(self):
        from analyze_native_resources import NativeImage
        from scene_sky_binding_tests import source_extract
        report = analyze_compiler(NativeImage(NATIVE.read_bytes()), source_extract())
        self.assertEqual(report['format'], FORMAT)
        for key in ('factoryInputsPatched', 'shaderCompilerExecuted', 'cacheRegistrationExecuted',
                    'fullCompilerExecuted', 'activeProfileRecovered', 'GPUExecuted', 'appliedAsLiveState'):
            self.assertFalse(report[key])


if __name__ == '__main__': unittest.main()
