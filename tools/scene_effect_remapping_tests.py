import copy
import random
import unittest
from pathlib import Path

from scene_effect_remapping import FORMAT, ROUTINES, predict_remap, validate_rules, verify_native, analyze_remapping

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


def rule(**changes):
    return {'pattern': '*', 'profiles': None, 'variants': None, 'source': None, 'target': 'tech2', **changes}


def rows(n=3):
    return [{'name': 'tech'+str(i), 'passes': [{'state': bytes(28), 'programWordE2': 0, 'programByteDF': 0}]} for i in range(n)]


def probe(cls=None):
    from analyze_native_resources import NativeImage
    from native_effect_remapping_probe import NativeEffectRemappingProbe
    return (cls or NativeEffectRemappingProbe)(NativeImage(NATIVE.read_bytes()))


class EffectRemappingTests(unittest.TestCase):
    def test_rule_fixtures_reject_ambiguous_empty_lists_ranges_and_unmodeled_patterns(self):
        validate_rules(['tech0', 'tech1'], [rule(target='tech1')], 2, 3)
        for r, p, v in [([rule(profiles=[])], 2, 2), ([rule(variants=[2])], 2, 2),
                         ([rule(pattern='[ab]')], 2, 2), ([rule(profiles=[True])], 2, 2),
                         ([rule()], 0, 2), ([rule()], 2, 5)]:
            with self.assertRaises(ValueError): validate_rules(['tech0', 'tech1'], r, p, v)

    def test_independent_model_uses_profile_variation_rows_and_later_full_vector_replacement(self):
        names = ['tech0', 'tech1', 'tech2']
        rules = [rule(profiles=[1], variants=[0]), rule(profiles=[1], variants=[0], source='tech0', target='tech1')]
        self.assertEqual(predict_remap(names, rules, 2, 2), bytes([0, 1, 2, 0, 1, 2, 1, 1, 2, 0, 1, 2]))
        for value in [[], [rule(pattern='missing')], [rule(target='missing')], [rule(source='missing')], [rule(target=None)]]:
            self.assertIsNone(predict_remap(names, value, 2, 2))
        self.assertIsNone(predict_remap(['tech0'], [rule(target='tech0')], 1, 1))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_rule_chain_initialization_rows_and_selector_match_bounded_independent_model(self):
        p = probe(); rng = random.Random(0x1408860)
        for i in range(32):
            n = rng.randrange(1, 6); profiles = rng.randrange(1, 5); variants = rng.randrange(1, 5)
            names = ['tech'+str(j) for j in range(n)]; rules = []
            for j in range(rng.randrange(4)):
                rules.append(rule(pattern=rng.choice(['*', 'fixture*', 'missing']),
                    profiles=None if rng.randrange(2) else [rng.randrange(profiles)],
                    variants=None if rng.randrange(2) else [rng.randrange(variants)],
                    source=rng.choice([None, '*', 'tech0', 'tech?', 'missing']),
                    target=rng.choice([*names, None, 'missing'])))
            p.use_fixture(); p.build(rows(n)); result = p.register_rules(rules, profiles, variants)
            expected = predict_remap(names, rules, profiles, variants)
            self.assertEqual(result['map'], expected.hex() if expected is not None else None)
            self.assertEqual(result['remapCalls'], int(bool(rules)))
            self.assertEqual(result['tableCalls'], int(expected is not None))
            self.assertTrue(result['boundedCompilerBodyReturned']); self.assertTrue(result['allocatorModeRestored'])
            if rules and n > 1:
                self.assertEqual(result['temporaryAllocationBytes'], [2*max(profiles, variants), n, n])
                self.assertEqual(result['temporaryFrees'], 3)
            else: self.assertEqual(result['temporaryFrees'], 0)
            for profile in range(profiles):
                for variant in range(variants):
                    for base in range(n):
                        want = expected[n*(variants*profile+variant)+base] if expected is not None else base
                        self.assertEqual(p.select_registered(base, profile, variant), want)
            for base in range(n): self.assertEqual(p.select_registered(base, -1, 0), base)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_selector_reads_actual_produced_cache_table_and_bypass_ignores_mutated_table(self):
        p = probe(); p.use_fixture(); p.build(rows()); rules = [rule(profiles=[1], variants=[0])]
        saved = copy.deepcopy(rules); result = p.register_rules(rules, 2, 2)
        self.assertEqual(result['matrixAllocationBytes'], [12]); self.assertEqual(p.select_registered(0, 1, 0), 2)
        p.write(result['mapPointer']+6, 'B', 1)
        self.assertEqual(p.select_registered(0, 1, 0), 1)
        self.assertEqual(p.select_registered(0, -1, 0), 0); self.assertEqual(rules, saved)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_target_match_requires_intern_pointer_identity_even_when_text_is_equal(self):
        from native_effect_remapping_probe import NativeEffectRemappingProbe
        class ForeignName(NativeEffectRemappingProbe):
            def _install_rules(self):
                super()._install_rules()
                at = self.RULES+0x1000+8*(self.profile_count+self.variant_count)
                part = at+0x14; pair = (part+4+7) & ~7
                self.uc.mem_write(self.RULES+0x7018, b'tech2\0')
                self.write(pair+8, 'Q', self.RULES+0x7000)
        p = probe(ForeignName); p.use_fixture(); p.build(rows())
        result = p.register_rules([rule()], 2, 2)
        self.assertIsNone(result['map']); self.assertEqual(result['tableCalls'], 0)
        self.assertEqual(p.select_registered(0, 1, 0), 0)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_source_declared_names_and_states_reach_original_remapping_and_selector(self):
        from scene_effect_modifiers import source_profiles
        from scene_sky_binding_tests import source_extract
        p = probe(); source = source_profiles(source_extract())
        for profile in source['profiles']:
            for flags in (0, 0x440):
                for policy in [rule(profiles=[1], variants=[0], target='solid'), rule(source='tech0', target='blend')]:
                    p.use_source(source, profile['field'])
                    inputs = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                               'programWordE2': flags, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
                    p.build(inputs); result = p.register_rules([policy], 2, 2)
                    expected = predict_remap(['tech0', 'blend', 'solid'], [policy], 2, 2)
                    self.assertEqual(result['map'], expected.hex())
                    for pr in range(2):
                        for va in range(2):
                            for base in range(3): self.assertEqual(p.select_registered(base, pr, va), expected[3*(2*pr+va)+base])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_code_changes_and_uncovered_selector_contexts_fail_closed(self):
        p = probe(); p.use_fixture(); p.build(rows()); p.register_rules([], 2, 2)
        for args in [(3, 0, 0), (0, 2, 0), (0, 0, 2), (True, 0, 0)]:
            with self.assertRaises(ValueError): p.select_registered(*args)
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in ROUTINES:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_report_does_not_promote_rule_fixtures_into_device_rules_or_profile_word_production(self):
        from analyze_native_resources import NativeImage
        from scene_sky_binding_tests import source_extract
        report = analyze_remapping(NativeImage(NATIVE.read_bytes()), source_extract())
        self.assertEqual(report['format'], FORMAT)
        for key in ('actualDeviceRulesRecovered', 'driverProfileProducerRecovered', 'shaderCompilerExecuted',
                    'activeProfileRecovered', 'GPUExecuted', 'appliedAsLiveState'):
            self.assertFalse(report[key])


if __name__ == '__main__': unittest.main()
