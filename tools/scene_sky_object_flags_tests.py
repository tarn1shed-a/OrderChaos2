import random
import unittest
from pathlib import Path

from scene_sky_object_flags import (FORMAT, ROUTINES, STRINGS, analyze_object_flags,
                                    initial_flags, provider_flags, validate_stages, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class SkyObjectFlagTests(unittest.TestCase):
    def test_constructor_low_bits_metadata_bit9_and_provider_fields(self):
        self.assertEqual(initial_flags(0, 0xffffffff, 1, 2), 0x207)
        self.assertEqual(initial_flags(2, 0xffffffff, 0, 2), 7)
        self.assertEqual(initial_flags(1, 3, 0, 1), 0x343)
        self.assertEqual(initial_flags(1, 0xffff0000, 0, None), 0x140)
        self.assertEqual(provider_flags(0xffff, 2, 0, 4), 0xfebc)
        self.assertEqual(provider_flags(0, 3, 3, 7), 0x147)

    def test_reject_implicit_flags_and_holes_in_shader_interval_fixture(self):
        for values in [(True, 7, 0, None), (0, -1, 0, None), (0, 7, 0, -1)]:
            with self.assertRaises(ValueError): initial_flags(*values)
        for values in [(65536, 0, 0, 0), (0, 0, 0, 8), (0, True, 0, 0)]:
            with self.assertRaises(ValueError): provider_flags(*values)
        for stages in [[0, None, 2], [0, 1], [True, 1, None], [0, 256, None]]:
            with self.assertRaises(ValueError): validate_stages(stages)
        validate_stages([None, 17, None]); validate_stages([None, None, None])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_complete_original_base_constructor_and_real_name_initialization(self):
        from analyze_native_resources import NativeImage
        from native_sky_object_probe import NativeSkyObjectProbe
        p = NativeSkyObjectProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x1466860)
        for i in range(96):
            flags, mask, control = [rng.getrandbits(32) for _ in range(3)]
            count = rng.choice([None, 0, 1, 2, 0xffffffff]); name = '' if i & 1 else 'object-'+str(i)
            result = p.construct_base(flags, mask, control, count, i, name)
            self.assertEqual(result['wordE2'], initial_flags(flags, mask, control, count))
            self.assertEqual(result['vptr'], 0x2499d68); self.assertEqual(result['index'], i)
            self.assertEqual(result['references'], 0); self.assertEqual(result['name'], name)
            self.assertEqual(result['sourceHolders'], [0, 0])
            self.assertEqual(result['metadata'], p.EXT+0x2200 if count is not None else 0)
            self.assertEqual(result['otherMetadata'], p.EXT+0x2300)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_complete_original_backend_with_explicit_GL_cache_and_link_results(self):
        from analyze_native_resources import NativeImage
        from native_sky_object_probe import NativeSkyObjectProbe
        p = NativeSkyObjectProbe(NativeImage(NATIVE.read_bytes()))
        intervals = [(0, 0), (0, 1), (0, 2), (0, 3), (1, 1), (1, 2), (2, 1)]
        for start, count in intervals:
            for discard in (False, True):
                stages = [None, None, None]
                for i in range(start, start+count): stages[i] = i | (16 if i == 1 and discard else 0)
                for handle in (0, 71):
                    for cache in (2, 3):
                        for link in (2, 3):
                            result = p.construct_backend(stages, handle, cache, link)
                            expected_discard = bool(handle and stages[1] is not None and stages[1] & 16)
                            self.assertEqual(result['wordE2'], 7 | (0x40 if expected_discard else 0))
                            self.assertEqual(result['vptr'], 0x2496a00)
                            self.assertEqual(result['handle'], handle if handle and link & 1 else 0)
                            self.assertEqual(result['shaderMask'], sum(1 << i for i, f in enumerate(stages) if f is not None))
                            self.assertEqual(result['interval'], (start << 4) | (start+count) if count else 0x31)
                            self.assertEqual(result['shaderReferences'], [101 if f is not None else None for f in stages])
                            events = [['create']]
                            if handle:
                                events += [['cache']]
                                if cache & 1: events += [['compile', p.EXT+0x3100+256*i] for i, f in enumerate(stages) if f is not None]
                                events += [['attach', handle, 100+i] for i, f in enumerate(stages) if f is not None]
                                events += [['link']]
                                if not link & 1: events += [['cleanup'], ['delete', handle]]
                            self.assertEqual(result['events'], events)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_provider_sets_and_clears_HasDiscard_then_real_queue_reads_object(self):
        from analyze_native_resources import NativeImage
        from native_sky_object_probe import NativeSkyObjectProbe
        p = NativeSkyObjectProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x146a1d4)
        for _ in range(96):
            before, discard, alpha, enum, usage = rng.randrange(65536), rng.getrandbits(32), rng.getrandbits(32), rng.randrange(8), rng.getrandbits(32)
            result = p.apply_provider(before, discard, alpha, enum, usage)
            self.assertEqual(result['wordE2'], provider_flags(before, discard, alpha, enum))
            self.assertEqual(result['attributeMask'], usage)
            self.assertEqual(result['events'], [['open', 'Vertex Attributes'], ['close'],
                                               ['bool', 'HasDiscard'], ['bool', 'HasAlphaTest']])
            actual = p.queue_constructed(bytes(28))
            self.assertEqual(actual['objectWordE2'], result['wordE2']); self.assertEqual(actual['objectReferences'], 1)
            self.assertEqual(actual['queue']['queueOffset'], 0x148 if discard & 1 else 0x130)
            self.assertTrue(actual['queue']['completed']); self.assertEqual(actual['queue']['selectorCalls'], 2)
            self.assertEqual(actual['queue']['record'], [p.BASE+0x1800, 1, p.BASE+0x1500, 7, 9])

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original sky/native stay local')
    def test_actual_source_states_use_constructed_backend_object_without_guessing_shader_metadata(self):
        from analyze_native_resources import NativeImage
        from native_sky_object_probe import NativeSkyObjectProbe
        from scene_sky_assembly import source_states
        from scene_sky_binding_tests import source_extract
        p = NativeSkyObjectProbe(NativeImage(NATIVE.read_bytes()))
        for profile in source_states(source_extract()):
            for row in profile['techniques']:
                blob = p.translate(row['sourceState'])
                for flag in (1, 17):
                    produced = p.construct_backend((0, flag, None))
                    actual = p.queue_constructed(blob)
                    self.assertEqual(actual['objectWordE2'], produced['wordE2'])
                    distance = row['name'] != 'solid'
                    self.assertEqual(actual['queue']['queueOffset'], 0x160 if distance else (0x148 if flag & 16 else 0x130))
                    self.assertEqual(actual['queue']['completed'], not distance)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_new_code_provider_strings_and_stack_guard_boundary_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read, elf = image.read, image.elf
        for target in [*ROUTINES, *STRINGS]:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        image.read = read
        class GuardSection:
            def iter_relocations(self):
                for row in elf.get_section_by_name('.rela.dyn').iter_relocations():
                    yield {**dict(row.entry), 'r_info_type': 1027} if row['r_offset'] == 0x2505c38 else row
        class GuardELF:
            def __getattr__(self, name): return getattr(elf, name)
            def get_section_by_name(self, name): return GuardSection() if name == '.rela.dyn' else elf.get_section_by_name(name)
        image.elf = GuardELF()
        with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original sky/native stay local')
    def test_report_keeps_native_flag_identity_separate_from_active_shader_state(self):
        from analyze_native_resources import NativeImage
        from scene_sky_binding_tests import source_extract
        report = analyze_object_flags(NativeImage(NATIVE.read_bytes()), source_extract())
        self.assertEqual(report['format'], FORMAT); self.assertFalse(report['appliedAsLiveState'])
        self.assertEqual(report['flagIdentity']['wordE2Bit6'], 'HasDiscard')
        self.assertEqual(report['flagIdentity']['wordE2Bit8'], 'HasAlphaTest')
        self.assertTrue(report['backend']['onlySetsBit']); self.assertFalse(report['backend']['shaderByte18ProducerRecovered'])
        self.assertFalse(report['activeSkyDiscardRecovered']); self.assertFalse(report['activeProfileRecovered'])


if __name__ == '__main__': unittest.main()
