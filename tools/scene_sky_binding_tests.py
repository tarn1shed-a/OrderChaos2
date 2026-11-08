import copy
import random
import unittest
from pathlib import Path

from scene_sky_binding import (FORMAT, ROUTINES, RELOCATIONS, analyze_binding, source_inputs,
                               predict_binding, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


def prop(name='CurrentTechnique', kind=28, technique='solid', words=(2, 0)):
    return {'name': name, 'kind': kind, 'techniqueName': technique, 'valueWords': list(words)}


def spec(properties=None, word40=0):
    return {'name': 'fixture-material', 'word40': word40,
            'properties': [prop()] if properties is None else properties}


def source_extract():
    from resource_packs import ResourceArchive, index, normalize_resource_name
    entries, packs = {}, {}
    for entry in index(SOURCE): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
    def extract(name):
        entry, = entries[normalize_resource_name(name)]; pack = entry['pack']
        if pack not in packs: packs[pack] = ResourceArchive(SOURCE/pack)
        return packs[pack].read(name)
    return extract


class SkyBindingTests(unittest.TestCase):
    def test_named_full_table_selection_order_and_raw_word40(self):
        self.assertEqual(predict_binding(spec(word40=0x1234), ['tech0', 'blend', 'solid']),
                         {'selectorByte': 2, 'variationByte': 52, 'selectorWrites': [2]})
        self.assertEqual(predict_binding(spec(), ['solid', 'tech0', 'blend'], 3)['selectorByte'], 0)
        rows = [prop(technique='blend'), prop(technique='missing'), prop(kind=8), prop(technique=None)]
        self.assertEqual(predict_binding(spec(rows), ['solid', 'blend', 'solid'])['selectorWrites'], [1])
        self.assertEqual(predict_binding(spec([prop(words=(0xffffffff, 0x1234))]), ['solid'])['selectorByte'], 0)
        self.assertEqual(predict_binding(spec([]), [])['selectorByte'], 0)

    def test_reject_implicit_fields_and_unbounded_pointer_views(self):
        for material, names, bits in [(spec(), ['x']*17, 0), (spec(), [''], 0), (spec(), ['a'], True),
                                      (spec(), ['a'], 6), (spec([prop()]*9), ['a'], 0),
                                      (spec(word40=-1), ['a'], 0)]:
            with self.assertRaises(ValueError): predict_binding(material, names, bits)
        for key, value in [('name', 'x\0y'), ('kind', True), ('techniqueName', ''), ('valueWords', [0])]:
            material = spec(); material['properties'][0][key] = value
            with self.assertRaises(ValueError): predict_binding(material, ['solid'])
        material = spec(); material['assumedDeviceProfile'] = 0
        with self.assertRaises(ValueError): predict_binding(material, ['solid'])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_full_original_wrapper_creation_and_loader_match_ordered_inputs(self):
        from analyze_native_resources import NativeImage
        from native_sky_binding_probe import NativeSkyBindingProbe
        p = NativeSkyBindingProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x112920c)
        for i in range(120):
            names = [rng.choice(['tech0', 'blend', 'solid', 'other']) for _ in range(rng.randrange(9))]
            rows = [prop('property'+str(n), rng.choice([8, 17, 28, 28]),
                         rng.choice(['tech0', 'blend', 'solid', 'missing', None]),
                         (rng.getrandbits(32), rng.getrandbits(32))) for n in range(rng.randrange(9))]
            material = spec(rows, rng.getrandbits(32)); bits = i % 6
            actual = p.bind(material, names, bits); expected = predict_binding(material, names, bits)
            self.assertEqual({k: actual[k] for k in expected}, expected)
            self.assertEqual(actual['outputMaterial'], p.BASE+0x5000)
            self.assertEqual(actual['owner'], p.BASE+0x4000)
            self.assertEqual(actual['materialReferences'], 1); self.assertEqual(actual['effectReferences'], 101)
            self.assertEqual(actual['parameterLookups'], [r['name'] for r in rows])
            self.assertEqual(actual['techniqueLookups'], sum(r['kind'] == 28 for r in rows))
            self.assertEqual(actual['allocationBytes'], [0x40+4*len(names)])
            self.assertEqual(actual['auxiliary'], bytes(4*len(names)))
            self.assertTrue(all(v == (1001 if name == material['name'] else 1000)
                                for name, v in actual['internReferences'].items()))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_source_type_gate_name_pointer_and_ignored_value_words(self):
        from analyze_native_resources import NativeImage
        from native_sky_binding_probe import NativeSkyBindingProbe
        p = NativeSkyBindingProbe(NativeImage(NATIVE.read_bytes()))
        for words in [(2, 0), (0, 0), (0xffffffff, 0xffffffff), (1, 0x1234)]:
            for names in [['tech0', 'blend', 'solid'], ['solid', 'blend', 'tech0'], ['tech0', 'solid', 'solid']]:
                actual = p.bind(spec([prop(words=words)]), names, 2)
                self.assertEqual(actual['selectorByte'], names.index('solid'))
        for material in [spec([prop(kind=8)]), spec([prop(technique=None)]), spec([prop(technique='missing')])]:
            actual = p.bind(material, ['tech0', 'blend', 'solid'])
            self.assertEqual(actual['selectorByte'], 0); self.assertEqual(actual['selectorWrites'], [])
        for rows in [[prop(technique='blend'), prop(technique='missing')],
                     [prop(technique='blend'), prop(technique='solid')]]:
            actual = p.bind(spec(rows), ['tech0', 'blend', 'solid'])
            self.assertEqual(actual['selectorWrites'], predict_binding(spec(rows), ['tech0', 'blend', 'solid'])['selectorWrites'])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_loader_creation_and_factory_fingerprints_fail_closed(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read, elf = image.read, image.elf
        for target in ROUTINES:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        image.read = read
        rels = [dict(r.entry) for r in elf.get_section_by_name('.rela.dyn').iter_relocations()]
        class ChangedSection:
            def __init__(self, target): self.target = target
            def iter_relocations(self):
                for row in rels:
                    yield {**row, 'r_addend': row['r_addend'] ^ 1} if row['r_offset'] == self.target else row
        class ChangedELF:
            def __init__(self, target): self.target = target
            def __getattr__(self, name): return getattr(elf, name)
            def get_section_by_name(self, name):
                return ChangedSection(self.target) if name == '.rela.dyn' else elf.get_section_by_name(name)
        for target in RELOCATIONS:
            image.elf = ChangedELF(target)
            with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original sky/native sources stay local')
    def test_source_named_solid_runs_as_explicit_declared_order_experiment(self):
        from analyze_native_resources import NativeImage
        from native_sky_binding_probe import NativeSkyBindingProbe
        extract = source_extract(); image = NativeImage(NATIVE.read_bytes())
        report = analyze_binding(image, extract); material, tables = source_inputs(extract)
        self.assertEqual(report['format'], FORMAT); self.assertFalse(report['appliedAsLiveState'])
        self.assertFalse(report['compiledEffectTableRecovered']); self.assertFalse(report['runtimeQueueFlagBindingRecovered'])
        self.assertEqual(material['word40'], 0)
        self.assertEqual([r['kind'] for r in material['properties']], [17, 8, 28])
        self.assertEqual(material['properties'][-1]['techniqueName'], 'solid')
        p = NativeSkyBindingProbe(image)
        for table, experiment in zip(tables, report['declaredOrderExperiments']):
            self.assertEqual(table['names'], ['tech0', 'blend', 'solid'])
            self.assertEqual(table['declaredParameters'], ['skyTexture', 'fog_intensity'])
            actual = p.bind(material, table['names'])
            self.assertEqual(actual['selectorByte'], 2); self.assertEqual(actual['variationByte'], 0)
            self.assertEqual(actual['selectorWrites'], [2]); self.assertEqual(experiment['selectorByte'], 2)
            self.assertEqual(actual['parameterLookups'], [r['name'] for r in material['properties']])
        changed = copy.deepcopy(material); changed['properties'][-1]['valueWords'] = [0xffffffff, 0x1234]
        self.assertEqual(p.bind(changed, ['solid', 'blend', 'tech0'])['selectorByte'], 0)

    @unittest.skipUnless(SOURCE.is_dir(), 'Original sky sources stay local')
    def test_model_and_effect_source_hashes_fail_closed(self):
        from scene_sky import MODEL, EFFECT
        extract = source_extract()
        for target in [MODEL, EFFECT]:
            def changed(name):
                raw = extract(name)
                return bytes([raw[0] ^ 1])+raw[1:] if name == target else raw
            with self.assertRaises(ValueError): source_inputs(changed)


if __name__ == '__main__': unittest.main()
