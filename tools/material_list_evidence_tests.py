"""Original source references and explicitly bounded list/rebuild experiments."""
import unittest
from pathlib import Path

from material_list_evidence import analyze, verify_native
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                     'Original native/model materials stay private')
class MaterialListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.result = analyze(cls.image, DEFAULT_SOURCE)

    def test_original_list_and_rebuild_bytes_fail_closed(self):
        image = self.image
        self.assertEqual(verify_native(image)['factoryMaterialSlot'], '0x80')
        for changed in (0x11850fc, 0x1184e70, 0x111a324, 0x33b854,
                        0x33b48c, 0x111b9f8, 0x33be44):
            class Changed:
                elf = image.elf
                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == changed else raw
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_source_primitives_match_original_local_reference_consumer(self):
        self.assertEqual(len(self.result['models']), 6)
        self.assertEqual(sum(len(r['materials']) for r in self.result['models']), 7)
        for model in self.result['models']:
            refs = model['originalReferenceConsumer']
            self.assertEqual([{k: r[k] for k in ('part', 'material', 'localIndex')}
                              for r in refs], model['sourceParts'])
            for row in refs:
                self.assertFalse(row['externalReference'])
                self.assertEqual(row['sourceExtraArgumentsPointer'], 0)
                self.assertEqual(model['materials'][row['localIndex']]['material'], row['material'])

    def test_smithy_uses_part_reference_order_not_material_table_order(self):
        smithy = next(m for m in self.result['models'] if m['model'].endswith('hum_archi_smithy001_03.bdae'))
        self.assertEqual([(r['material'], r['localIndex']) for r in smithy['sourceParts']],
                         [('shelf_rope_inn009', 1), ('box_hum_inn017_01', 0)])

    def test_both_original_factories_reach_source_effect_request_without_result(self):
        count = 0
        for model in self.result['models']:
            for row in model['originalCreationRequests']:
                source = model['materials'][model['sourceParts'][row['part']]['localIndex']]
                self.assertEqual((row['file'], row['name']),
                                 (source['effectPath'], source['effectName'][1:]))
                self.assertEqual(row['kind'], 'effectRequestNotCompleted')
                self.assertFalse(row['resultSupplied'])
                self.assertEqual(row['stoppedAt'], '0x1127250')
                for at in ('0x1184e70', '0x111a324', '0x112a6a4', '0x112920c', '0x1126e90'):
                    self.assertIn(at, row['trace'])
                self.assertEqual('0x550fec' in row['trace'], row['projectFactoryFixture'])
                count += 1
        self.assertEqual(count, 14)

    def test_null_results_do_not_insert_and_name_cache_reuses_fixture(self):
        for model in self.result['models']:
            experiment = model['separatePointerListExperiment']
            for case in experiment['conditions']:
                self.assertEqual(case['withoutDevice']['pointer'], 0)
                self.assertEqual(case['withoutDevice']['trace'], [])
                self.assertEqual(case['entriesBefore'], case['entriesAfterNull'])
                for field in ('cachedLookup', 'sameNameDifferentRecordLookup'):
                    self.assertEqual(case[field]['pointer'], case['pointerOnlyFixture'])
                    self.assertEqual(case[field]['trace'], [])
            self.assertEqual([r['material'] for r in experiment['entries']],
                             [r['material'] for r in model['sourceParts']])

    def test_rebuild_rejects_empty_list_missing_device_and_missing_factory(self):
        for model in self.result['models']:
            experiment = model['separatePointerListExperiment']
            for result in [experiment['emptyListRebuild'], *experiment['rebuildGuards']]:
                self.assertEqual((result['kind'], result['word']), ('returned', 0))

    def test_rebuild_modes_separate_old_parameter_query_and_empty_map_defaults(self):
        for model in self.result['models']:
            experiment = model['separatePointerListExperiment']
            first = experiment['entries'][0]
            a, b = experiment['rebuildBoundaries']
            self.assertEqual((a['mode'], a['kind']), (0, 'oldEffectInspectionNotExecuted'))
            self.assertEqual(a['waterEnabledBeforeBoundary'], 0)
            self.assertEqual((b['mode'], b['kind']), (1, 'oldParameterQueryNotExecuted'))
            for row in (a, b):
                self.assertEqual(row['definition'], first['definition'])
                self.assertEqual(row['materialPointerFixture'], first['pointerFixture'])
                self.assertEqual(row['parameterMapFixture'], 'empty')

    def test_replacement_branches_preserve_old_until_a_different_effect_and_new_material(self):
        for model in self.result['models']:
            cases = {r['case']: r for r in model['separatePostCallDecisions']}
            for name, row in cases.items():
                self.assertEqual(row['kind'], 'requestNewMaterial' if name == 'differentEffect' else 'keepOld')
                self.assertTrue(row['oldPointerUnchanged'])
                self.assertFalse(row['effectOrMaterialResultSuppliedToCreation'])

    def test_twelve_associations_are_conditional_and_no_game_or_frame_was_created(self):
        instances = self.result['instances']
        self.assertEqual(len(instances), 12)
        self.assertEqual(len({r['id'] for r in instances}), 12)
        # This sum assumes independently assembled model roots, not original
        # runtime sharing, residence, successful acquisition or actual display.
        self.assertEqual(sum(r['expectedEntriesIfAllRequestedMaterialsSucceed'] for r in instances), 13)
        self.assertTrue(all(not r['actualRuntimeListObserved'] for r in instances))
        self.assertFalse(self.result['scope']['completeMaterialCreationOrRebuildExecuted'])
        self.assertFalse(self.result['scope']['renderedFrameObserved'])
        self.assertFalse(self.result['appliedToGame'])


if __name__ == '__main__':
    unittest.main()
