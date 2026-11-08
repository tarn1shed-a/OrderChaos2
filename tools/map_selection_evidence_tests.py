"""Check original selection evidence and exercise its positive/negative branches."""
import unittest
from pathlib import Path

from map_selection_evidence import analyze, verify_native, apk_config, DEFAULT_APK
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(NATIVE.is_file(), 'Original native sample remains local')
class NativeSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from native_map_selection_probe import NativeMapSelectionProbe
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.probe = NativeMapSelectionProbe(cls.image)

    def test_pinned_original_routines_reject_changed_initializer(self):
        image = self.image
        self.assertEqual(verify_native(image)['additionalRoutines'], 15)
        class Changed:
            elf = image.elf
            def read(self, at, size):
                raw = image.read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == 0x357b2c else raw
        with self.assertRaisesRegex(ValueError, 'selection routine changed'):
            verify_native(Changed())

    def test_original_constant_writes_and_packed_lookup_agree(self):
        p = self.probe
        constants = p.mask_constants()
        self.assertEqual(len(constants), 20)
        self.assertEqual({r['mapId'] for r in constants}, {1})
        self.assertEqual({r['phase'] for r in constants}, {0, 2})
        for r in constants:
            x, z = r['tile']
            self.assertEqual(p.mask_lookup(constants, 1, x, z, r['phase']), r['mask'])
            # Same coordinates and phase, different map must not alias.
            self.assertEqual(p.mask_lookup(constants, 5, x, z, r['phase']), 0)
        self.assertEqual(p.mask_lookup(constants, 1, 0, -5, 0), 0x7fc)
        self.assertEqual(p.mask_lookup(constants, 1, 0, -5, 1), 0)
        self.assertEqual(p.mask_lookup([], 5, -42, 3, 0), 0)

    def test_original_phase_loop_requires_active_id_map_and_coordinate(self):
        p = self.probe
        fixture = [{'id': 2, 'mapId': 1, 'tiles': [[-42, 3]]},
                   {'id': 4, 'mapId': 5, 'tiles': [[-42, 3]]}]
        self.assertEqual(p.phase_select(fixture, 5, -42, 3, [2, 4]), 4)
        self.assertEqual(p.phase_select(fixture, 1, -42, 3, [2, 4]), 2)
        self.assertEqual(p.phase_select(fixture, 5, -42, 3, [2]), 0)
        self.assertEqual(p.phase_select(fixture, 5, -42, 4, [2, 4]), 0)
        self.assertEqual(p.phase_select(fixture, 5, -42, 3, []), 0)

    def test_original_bounded_input_word_reaches_phase_field(self):
        self.assertEqual(self.probe.input_phase_word(0x80000014),
                         {'playerPhaseWord': 0x80000014, 'bufferCursor': 4})
        self.assertEqual(self.probe.input_phase_word(0x80000014, 3),
                         {'playerPhaseWord': 0, 'bufferCursor': 4})


@unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tables.bin').is_file(),
                     'Original tables and archives remain local')
class SourceSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.result = analyze(NativeImage(NATIVE.read_bytes()), DEFAULT_SOURCE, probe=True)

    def test_source_phase_table_and_native_branch_do_not_add_tutorial_phases(self):
        r = self.result
        self.assertTrue(r['phase']['nativeFormatMatchesSource'])
        self.assertEqual(len(r['phase']['rows']), 15)
        self.assertEqual(r['phase']['tutorialRows'], [])
        self.assertEqual(r['fragmentExperiments']['tutorialSelectedPhases'], [0, 0, 0])
        # A real table hit on another map confirms source row layout/lookup.
        from analyze_native_resources import NativeImage
        from native_map_selection_probe import NativeMapSelectionProbe
        p = NativeMapSelectionProbe(NativeImage(NATIVE.read_bytes()))
        row = r['phase']['rows'][0]
        self.assertEqual(p.phase_select(r['phase']['rows'], row['mapId'],
                                        *row['tiles'][0], [row['id']]), row['id'])

    def test_inventory_and_conditional_examples_never_become_live_selection(self):
        r = self.result
        inv = r['inventory']
        self.assertEqual([inv[k] for k in ['terrainIndexCount', 'buildingFileCount',
                                          'sourceRecordCount', 'sourceModelCount']], [251, 57, 1354, 176])
        self.assertEqual([len(c['requested']) for c in r['conditionalExamples']], [9, 25])
        self.assertEqual([c['sourceRecordCount'] for c in r['conditionalExamples']], [39, 217])
        self.assertIsNone(r['config']['actualAndroidRadius'])
        self.assertFalse(r['config']['legacyXMLConnectionToTerrainTileSightProven'])
        self.assertFalse(r['mask']['otherRuntimeWritersExhaustivelyExcluded'])
        self.assertIsNone(r['phase']['wireMessageNameAndOpcode'])
        self.assertIn('tables/phasing_area.tbl', r['sources'])
        self.assertEqual(len([k for k in r['sources'] if k.endswith('.itm')]), 57)


class APKSelectionTests(unittest.TestCase):
    @unittest.skipUnless(DEFAULT_APK.is_file(), 'Original APK remains local')
    def test_android_apk_supplies_radius_default_and_gpu_override(self):
        r = apk_config(DEFAULT_APK)
        self.assertEqual(r['header']['file_version'], 73)
        self.assertEqual(r['header']['library_version'], 1)
        self.assertEqual(r['radiusDefaults'], [{'group': 'GPU', 'label': 'Default', 'value': 2}])
        self.assertEqual(r['radiusOverrides'], [{'group': 'GPU', 'profile': 'GPU_0M', 'value': 1}])
        self.assertFalse(r['actualDeviceSelectionObserved'])
        self.assertEqual(len(r['GPU0MSelectionExpressions']), 1)


if __name__ == '__main__':
    unittest.main()
