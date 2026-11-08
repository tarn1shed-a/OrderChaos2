import random
import unittest
from pathlib import Path

from scene_effect_registration import (FORMAT, ROUTINES, RELOCATIONS, name_hash,
                                       verify_native, analyze_registration)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


def rows(counts=(1,), flags=0):
    return [{'name': 'tech'+str(i), 'passes': [{'state': bytes(28), 'programWordE2': flags,
             'programByteDF': 0} for _ in range(n)]} for i, n in enumerate(counts)]


def probe():
    from analyze_native_resources import NativeImage
    from native_effect_registration_probe import NativeEffectRegistrationProbe
    p = NativeEffectRegistrationProbe(NativeImage(NATIVE.read_bytes())); p.use_fixture()
    return p


class EffectRegistrationTests(unittest.TestCase):
    def test_hash_uses_signed_utf8_bytes_and64_bit_accumulator_before_final_truncation(self):
        for name, value in [('', 0), ('fixture-effect', 0xafcc5758), ('冰霜-火球', 0xa2cc40b9), ('é'*20, 0xbc9aa8)]:
            self.assertEqual(name_hash(name), value)
        wrong = 0
        for b in b'fixture-effect': wrong = (wrong ^ ((wrong << 6)+(wrong >> 2)+b+0x9e3779b9)) & 0xffffffff
        self.assertNotEqual(name_hash('fixture-effect'), wrong)
        for value in [b'name', 'bad\0name', 'x'*97]:
            with self.assertRaises(ValueError): name_hash(value)

    def test_real_hash_collision_names_are_distinct_and_names_are_not_normalized(self):
        self.assertEqual(name_hash('cache-28295'), 0x603d673f)
        self.assertEqual(name_hash('cache-28408'), 0x603d673f)
        self.assertNotEqual(name_hash('cache-28295'), name_hash('CACHE-28295'))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_full_bounded_original_compiler_return_miss_hit_reference_and_scratch_lifetimes(self):
        p = probe(); rng = random.Random(0x140203c)
        for i in range(32):
            counts = [rng.randrange(1, 4) for _ in range(rng.randrange(1, 6))]; inputs = rows(counts)
            for t in inputs:
                for v in t['passes']:
                    v.update(state=rng.randbytes(28), programWordE2=rng.getrandbits(16), programByteDF=rng.getrandbits(8))
            p.use_fixture(); p.build(inputs); hit = bool(i & 1); name = ('冰霜-' if i % 3 == 0 else 'fixture-')+str(i)
            result = p.register(name, 'hit' if hit else 'miss')
            self.assertTrue(result['boundedCompilerBodyReturned']); self.assertFalse(result['factoryInputsPatched'])
            self.assertEqual(result['nativeHashes'], [name_hash(name)]*(1 if hit else 2))
            self.assertEqual(result['outputReferences'], 21 if hit else 2)
            self.assertEqual(result['publicOutput'], result['cachedFixture'] if hit else result['freshEffect'])
            self.assertEqual(result['cacheCount'], 1); self.assertEqual(result['outputIndex'], 0)
            self.assertEqual(result['cacheAllocationBytes'], [] if hit else [72])
            self.assertEqual(result['registrationCalls'], int(not hit))
            self.assertEqual(result['effectDestructorCalls'], int(hit))
            self.assertEqual(result['freshEffectDeletes'], int(hit)); self.assertEqual(result['auxiliaryDeletes'], int(hit))
            self.assertEqual(result['auxiliaryVirtualCalls'], [int(hit)]*2)
            self.assertEqual(result['managerTreeRemovalCalls'], int(hit)); self.assertEqual(result['strcmpCalls'], int(hit))
            self.assertEqual(result['builderDestructorCalls'], 1); self.assertEqual(result['intermediateDestructorCalls'], len(inputs))
            self.assertEqual(result['scratchAllocationsFreed'], 6*len(inputs)+1)
            self.assertEqual(result['ownedFixtureFrees'], 2)
            self.assertEqual(result['programReferences'], [99 if hit else 100]*sum(counts))
            self.assertTrue(result['allocatorModeRestored']); self.assertEqual(result['inputHolder'], 0)
            self.assertEqual(result['builderBeforeFree'], {'techniqueCount': 0, 'name': 0,
                              'techniqueHead': p.TECH+0x58, 'allocatorMode': 0 if hit else 1})
            self.assertEqual(len(result['lockEvents']), 2 if hit else 4)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_lookup_compares_names_after_actual_hash_collision(self):
        p = probe()
        for name, other in [('cache-28295', 'cache-28408'), ('cache-28408', 'cache-28295')]:
            p.use_fixture(); p.build(rows()); result = p.register(name, 'collision', other)
            self.assertEqual(result['nativeHashes'], [0x603d673f]*2)
            self.assertEqual(result['strcmpCalls'], 2); self.assertEqual(result['registrationCalls'], 1)
            self.assertEqual(result['cacheCount'], 2); self.assertEqual(result['nextIndex'], 2)
            self.assertEqual(result['outputIndex'], 1); self.assertEqual(result['publicOutput'], result['freshEffect'])
            self.assertEqual(result['outputReferences'], 2); self.assertEqual(result['effectDestructorCalls'], 0)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_registration_retains_exact_node_hash_name_owner_and_index_vector(self):
        p = probe(); p.build(rows((1, 2))); result = p.register('cache-28408', 'collision', 'cache-28295')
        c = p.CACHE; node = c+0x3000; previous = c+0x4000
        self.assertEqual(result['cacheSlots'], [previous, node])
        self.assertEqual(p.read(node, '2Q'), (previous, 0x603d673f))
        self.assertEqual(p.read(node+0x30, 'Q')[0], result['freshEffect'])
        self.assertEqual(p.read(node+0x38, 'Q')[0], p.read(result['freshEffect']+0x10, 'Q')[0])
        self.assertEqual(p.read(node+0x42, 'H')[0], 1)
        self.assertEqual(p.read(c+0x1000+8*(0x603d673f & 7), 'Q')[0], node)
        self.assertNotIn(node, p.freed); self.assertNotIn(result['freshEffect'], p.freed)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_source_profiles_reach_full_miss_hit_return_with_explicit_program_flags(self):
        from scene_effect_modifiers import source_profiles
        from scene_sky_binding_tests import source_extract
        p = probe(); source = source_profiles(source_extract())
        for profile in source['profiles']:
            for flags in (0, 0x440):
                for mode in ('miss', 'hit'):
                    p.use_source(source, profile['field'])
                    inputs = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                               'programWordE2': flags, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
                    p.build(inputs); result = p.register(mode=mode)
                    self.assertTrue(result['boundedCompilerBodyReturned'])
                    self.assertEqual(result['intermediateDestructorCalls'], 3)
                    self.assertEqual(result['programReferences'], [99 if mode == 'hit' else 100]*3)
                    self.assertEqual(result['outputIndex'], 0); self.assertTrue(result['allocatorModeRestored'])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_code_auxiliary_vtable_and_uncovered_cache_fixtures_fail_closed(self):
        p = probe()
        for kwargs in [{'mode': 'growth'}, {'mode': 'collision', 'collision_name': 'different'},
                       {'mode': 'collision', 'collision_name': 'fixture-effect'}]:
            with self.assertRaises(ValueError): p.register(**kwargs)
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read, elf = image.read, image.elf
        for target in ROUTINES:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        image.read = read
        class Section:
            def iter_relocations(self):
                for r in elf.get_section_by_name('.rela.dyn').iter_relocations():
                    yield {**dict(r.entry), 'r_addend': 0} if r['r_offset'] == 0x2493088 else r
        class ChangedELF:
            def __getattr__(self, name): return getattr(elf, name)
            def get_section_by_name(self, name): return Section() if name == '.rela.dyn' else elf.get_section_by_name(name)
        image.elf = ChangedELF()
        with self.assertRaises(ValueError): verify_native(image)
        image.elf = elf; self.assertEqual(verify_native(image)['auxiliarySlots'], len(RELOCATIONS))

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_report_keeps_bounded_return_separate_from_real_shader_cache_capacity_and_active_device(self):
        from analyze_native_resources import NativeImage
        from scene_sky_binding_tests import source_extract
        report = analyze_registration(NativeImage(NATIVE.read_bytes()), source_extract())
        self.assertEqual(report['format'], FORMAT); self.assertTrue(report['boundedCompilerBodyReturned'])
        for key in ('allCompilerPathsRecovered', 'shaderCompilerExecuted', 'activeProfileRecovered', 'GPUExecuted', 'appliedAsLiveState'):
            self.assertFalse(report[key])


if __name__ == '__main__': unittest.main()
