import random
import unittest
from pathlib import Path

from scene_material_cache import (FORMAT, ROUTINES, STRINGS, analyze_cache, apply_selector,
                                  lookup_name, reset_selector, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class MaterialCacheTests(unittest.TestCase):
    def test_selector_missing_names_low_modifier_bits_and_group_retention(self):
        self.assertEqual(apply_selector(255, 9, [11, 22, 33], [2, 3], 33),
                         {'baseByte': 10, 'variationByte': 9, 'baseOrdinal': 2})
        self.assertEqual(apply_selector(0, 9, [11], [1, 0], 22, True, 0x1234),
                         {'baseByte': 253, 'variationByte': 52, 'baseOrdinal': 255})
        self.assertEqual(lookup_name([11, 11, 22], 2, 11), 0)
        self.assertEqual(lookup_name([0, 11], 0, 0), 255)
        self.assertEqual(reset_selector(255, 0), 0)
        self.assertEqual(reset_selector(255, 1), 1)
        self.assertEqual(reset_selector(255, 32), 0)
        self.assertEqual(reset_selector(255, 31), 255)

    def test_reject_unbounded_grouped_tables_and_implicit_values(self):
        for args in [([], 6, 1), ([1]*8, 5, 1), ([], True, 1), ([1], 0, True), ([1.0], 0, 1)]:
            with self.assertRaises(ValueError): lookup_name(*args)
        for args in [(True, 1, [1], [], 1), (0, 256, [1], [], 1),
                     (0, 1, [1], [-1], 1), (0, 1, [1], [], 1, 1, 0)]:
            with self.assertRaises(ValueError): apply_selector(*args)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_constructor_reset_copy_preserve_precise_cache_fields(self):
        from analyze_native_resources import NativeImage
        from native_material_cache_probe import NativeMaterialCacheProbe
        p = NativeMaterialCacheProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x13ecc24)
        for i in range(96):
            header = rng.randbytes(14); aux = rng.randbytes(4*rng.randrange(9)); copied = bool(i & 1)
            result = p.construct(header, aux, copied)
            expected = bytearray([0xa5]*14)
            for a, z in [(0, 3), (4, 9), (10, 14)]: expected[a:z] = header[a:z]
            if copied: expected[10:12] = b'\xff\xff'
            self.assertEqual(result['header'], bytes(expected))
            self.assertEqual(result['references'], 0); self.assertEqual(result['effectReferences'], 101)
            self.assertEqual(result['auxiliaryPointer'], p.BASE+0x40); self.assertEqual(result['name'], 0)
            self.assertEqual(result['auxiliary'], aux if copied else bytes(len(aux)))
            base, variation, shift = rng.randrange(256), rng.randrange(256), rng.randrange(256)
            self.assertEqual(p.reset_cache(base, variation, shift), (reset_selector(base, shift), 0, 0xffffffff))
            src, dst = tuple(rng.randrange(256) for _ in range(2)), (base, variation)
            same_effect, same_object = bool(i & 2), bool(i & 4)
            result = p.copy_cache(src, dst, same_effect, same_object, aux)
            copies = same_effect and not same_object
            self.assertEqual(result['returnWord'], int(same_object or same_effect))
            self.assertEqual((result['baseByte'], result['variationByte']), src if copies else dst)
            self.assertEqual(result['dirtyWord'], 0xffff if copies else 0)
            self.assertEqual(result['auxiliary'], aux if copies else bytes(len(aux)))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_grouped_lookup_differs_from_complete_table_ordinal(self):
        from analyze_native_resources import NativeImage
        from native_material_cache_probe import NativeMaterialCacheProbe
        p = NativeMaterialCacheProbe(NativeImage(NATIVE.read_bytes()))
        for bits in range(6):
            names = [p.BASE+0xc000+i*128 for i in range(5)]
            for i, name in enumerate(names):
                self.assertEqual(p.lookup(names, bits, name), i)
                self.assertEqual(p.lookup(names, bits, name, complete=True), i << bits)
            for name in [0, p.BASE+0xd000]:
                self.assertEqual(p.lookup(names, bits, name), 255)
            self.assertEqual(p.lookup([names[0], names[0], names[1]], bits, names[0]), 0)
        self.assertEqual(p.lookup([], 0, p.BASE+0xc000), 255)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_provider_body_and_cache_bytes_match_independent_model(self):
        from analyze_native_resources import NativeImage
        from native_material_cache_probe import NativeMaterialCacheProbe
        p = NativeMaterialCacheProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x13eda68)
        for i in range(144):
            bits = i % 6; names = [p.BASE+0xc000+n*128 for n in range(5)]
            pointer = rng.choice([0, p.BASE+0xd000, *names]); present = i % 7 != 0
            features = [rng.getrandbits(32) for _ in range(bits)]
            base, variation, group = rng.randrange(256), rng.randrange(256), rng.getrandbits(32)
            nonempty = bool(i & 1)
            actual = p.apply(base, variation, names, features, pointer, nonempty, group, present)
            expected = apply_selector(base, variation, names, features, pointer if present else 0, nonempty, group)
            self.assertEqual(actual['baseByte'], expected['baseByte'])
            self.assertEqual(actual['variationByte'], expected['variationByte'])
            self.assertEqual(actual['modifierCalls'], bits)
            self.assertEqual(actual['internReferences'], 99 if present and pointer else (100 if pointer else None))
            self.assertEqual([c for c in actual['calls'] if c[0] == 'group'], [['group', group]] if nonempty else [])
            self.assertEqual([c for c in actual['calls'] if c[0] == 'field'],
                             [['field', 'Base Technique'], ['field', 'Group']])
            expected_sections = ['Technique Modifiers', 'Parameters'] if bits else ['Parameters']
            self.assertEqual([c[1] for c in actual['calls'] if c[0] == 'open'], expected_sections)
            self.assertEqual([c[1] for c in actual['calls'] if c[0] == 'close'], expected_sections)
            self.assertIn(['parameters'], actual['calls'])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_new_writer_lookup_and_provider_name_fingerprints_fail_closed(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in [*ROUTINES, *STRINGS]:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original sky sources stay local')
    def test_report_keeps_named_solid_separate_from_generic_provider(self):
        from analyze_native_resources import NativeImage
        from resource_packs import ResourceArchive, index, normalize_resource_name
        entries, packs = {}, {}
        for entry in index(SOURCE): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
        def extract(name):
            entry, = entries[normalize_resource_name(name)]; pack = entry['pack']
            if pack not in packs: packs[pack] = ResourceArchive(SOURCE/pack)
            return packs[pack].read(name)
        report = analyze_cache(NativeImage(NATIVE.read_bytes()), extract)
        self.assertEqual(report['format'], FORMAT); self.assertFalse(report['appliedAsLiveState'])
        self.assertEqual(report['sourceDeclaration']['techniqueByName']['name'], 'solid')
        self.assertFalse(report['sourceDeclaration']['providerBindingRecovered'])
        self.assertFalse(report['providerApplication']['sourceBDAELoaderIdentityProven'])
        self.assertEqual(report['providerApplication']['fields'], ['Base Technique', 'Technique Modifiers', 'Group', 'Parameters'])


if __name__ == '__main__': unittest.main()
