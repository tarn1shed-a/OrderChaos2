import unittest
from pathlib import Path

from scene_effect_modifiers import (FORMAT, ROUTINES, RELOCATIONS, builder_gate, getter_index,
                                    source_profiles, verify_native, analyze_modifiers)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class EffectModifierTests(unittest.TestCase):
    def test_builder_gate_uses_count_low_byte_and_zero_policy_instead_of_assumed_limit(self):
        self.assertEqual(builder_gate(0, 0), {'continues': True, 'warnsCount': False, 'queriesZeroPolicy': True})
        self.assertFalse(builder_gate(256, 1)['continues'])
        self.assertTrue(builder_gate(8, 1)['continues']); self.assertTrue(builder_gate(8, 1)['warnsCount'])
        self.assertFalse(builder_gate(257, 1)['queriesZeroPolicy'])
        for values in [(True, 0), (-1, 0), (0, True), (0, 1 << 32)]:
            with self.assertRaises(ValueError): builder_gate(*values)

    def test_getter_low_byte_index_is_separate_from_probe_array_bounds(self):
        self.assertEqual(getter_index(0x101, 3), 1)
        self.assertEqual(getter_index(0xffffff00, 1), 0)
        for values in [(0, 0), (3, 3), (True, 1), (-1, 1), (0, 8)]:
            with self.assertRaises(ValueError): getter_index(*values)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_actual_provider_count_name_relative_array_and_zero_policy_methods(self):
        from analyze_native_resources import NativeImage
        from native_effect_modifier_probe import NativeEffectModifierProbe
        p = NativeEffectModifierProbe(NativeImage(NATIVE.read_bytes()))
        for count in range(8):
            names = ['modifier'+str(i) for i in range(count)]
            for policy in (0, 1, 0xffffffff):
                p.use_fixture(names, policy)
                result = p.query(); self.assertEqual(result['countWord'], count)
                self.assertEqual(result['zeroAllowed'], int(policy == 0))
                for i, name in enumerate(names):
                    for high in (0, 256, 0xffffff00):
                        self.assertEqual(p.query(i+high)['name'], name)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_builder_gate_stops_at_continuation_or_completes_early_rejection(self):
        from analyze_native_resources import NativeImage
        from native_effect_modifier_probe import NativeEffectModifierProbe
        p = NativeEffectModifierProbe(NativeImage(NATIVE.read_bytes()))
        for count in (0, 1, 7, 8, 9, 255, 256, 257, 0x80000000, 0xffffffff):
            for policy in (0, 1, 0xffffffff):
                p.use_fixture(policy=policy, count_word=count); result = p.gate(); expected = builder_gate(count, policy)
                self.assertEqual(result['continues'], expected['continues'])
                self.assertEqual(result['logs'], int(expected['warnsCount'])+int(not expected['continues']))
                self.assertEqual(result['countCalls'], 1); self.assertEqual(result['zeroCalls'], int(expected['queriesZeroPolicy']))
                self.assertEqual(result['output'], 0xfeedface if expected['continues'] else 0)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_provider_virtuals_feed_full_effect_constructor_for_explicit_names(self):
        from analyze_native_resources import NativeImage
        from native_effect_modifier_probe import NativeEffectModifierProbe
        from scene_sky_assembly import assembly_layout
        p = NativeEffectModifierProbe(NativeImage(NATIVE.read_bytes()))
        for count in range(6):
            names = ['feature'+str(i) for i in range(count)]; p.use_fixture(names)
            rows = [{'name': 'tech'+str(i), 'passes': [{'state': bytes(28), 'programWordE2': 0, 'programByteDF': 0}]} for i in range(2)]
            result = p.assemble_provider(rows)
            self.assertEqual(result['packedWord'], 0x200 | count)
            self.assertEqual(result['originalModifierCountCalls'], 2)
            self.assertEqual(result['originalModifierNameCalls'], count)
            self.assertEqual(result['originalNameIndices'], list(range(count)))
            self.assertEqual(result['fixtureModifierCountCallbacks'], 0)
            self.assertEqual(result['allocationBytes'], [assembly_layout(rows, names)['allocationBytes']])

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_actual_source_zero_descriptors_passes_and_constructor_count_bridge(self):
        from analyze_native_resources import NativeImage
        from native_effect_modifier_probe import NativeEffectModifierProbe
        from scene_sky_binding_tests import source_extract
        p = NativeEffectModifierProbe(NativeImage(NATIVE.read_bytes())); source = source_profiles(source_extract())
        for profile in source['profiles']:
            p.use_source(source, profile['field'])
            self.assertEqual(profile['descriptorWords'], [0]*8)
            self.assertEqual(p.query(), {'countWord': 0, 'zeroAllowed': 1, 'name': None})
            self.assertTrue(p.gate()['continues'])
            for i, row in enumerate(profile['techniques']):
                for alias in (0, 256, 0xffffff00):
                    result = p.apply_zero(i, alias)
                    self.assertEqual(result, {'returnWord': 1, 'loaderCalls': [{
                        'effectOffset': source['effectOffset'], 'techniqueOffset': row['offset'], 'passOffset': row['passes'][0]['offset']}]})
            for flags in (0, 0x440):
                result = p.assemble_profile(profile, flags)
                self.assertEqual(result['packedWord'], 0x300); self.assertEqual(result['originalModifierCountCalls'], 2)
                self.assertEqual(result['originalNameIndices'], [])
                self.assertEqual([t['name'] for t in result['techniques']], ['tech0', 'blend', 'solid'])
                self.assertEqual([t['headerByte11'] for t in result['techniques']], [int(bool(flags & 0x400))]*3)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_code_and_real_provider_slot_targets_fail_closed_when_changed(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read, elf = image.read, image.elf
        for target in ROUTINES:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        image.read = read
        class ChangedSection:
            def iter_relocations(self):
                for r in elf.get_section_by_name('.rela.dyn').iter_relocations():
                    yield {**dict(r.entry), 'r_addend': 0} if r['r_offset'] == 0x245a410 else r
        class ChangedELF:
            def __getattr__(self, name): return getattr(elf, name)
            def get_section_by_name(self, name): return ChangedSection() if name == '.rela.dyn' else elf.get_section_by_name(name)
        image.elf = ChangedELF()
        with self.assertRaises(ValueError): verify_native(image)
        image.elf = elf; self.assertEqual(verify_native(image)['providerSlots'], len(RELOCATIONS))

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_source_hash_and_report_do_not_turn_zero_modifiers_into_active_profile_claim(self):
        from analyze_native_resources import NativeImage
        from scene_sky_binding_tests import source_extract
        extract = source_extract()
        with self.assertRaises(ValueError): source_profiles(lambda name: extract(name)+b'\0')
        report = analyze_modifiers(NativeImage(NATIVE.read_bytes()), extract)
        self.assertEqual(report['format'], FORMAT)
        self.assertEqual([p['modifierCount'] for p in report['sourceProfiles']], [0, 0])
        for key in ('activeProfileRecovered', 'fullCompilerExecuted', 'GPUExecuted', 'appliedAsLiveState'):
            self.assertFalse(report[key])


if __name__ == '__main__': unittest.main()
