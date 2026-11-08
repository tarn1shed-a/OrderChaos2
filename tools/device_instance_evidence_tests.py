"""Original device/instance positive and negative branches; no live profile assumed."""
import struct
import unittest
from pathlib import Path

from device_instance_evidence import analyze, verify_native
from map_selection_evidence import DEFAULT_APK
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(NATIVE.is_file(), 'Original ARM64 image remains local')
class DeviceNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())

    def test_fingerprints_reject_changed_condition_body(self):
        image = self.image
        self.assertEqual(verify_native(image)['additionalRoutines'], 27)
        class Changed:
            elf = image.elf
            def read(self, at, size):
                raw = image.read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == 0xc5b854 else raw
        with self.assertRaisesRegex(ValueError, 'device/instance routine changed'):
            verify_native(Changed())

    def test_original_eight_operators_and_missing_property(self):
        from native_device_instance_probe import NativeDeviceInstanceProbe
        p = NativeDeviceInstanceProbe(self.image)
        cases = [('N<=4', {'N': (2, 4)}, 1), ('N>=4', {'N': (2, 3)}, 0),
                 ('N<4', {'N': (2, 3)}, 1), ('N>4', {'N': (2, 4)}, 0),
                 ('S!=ABC', {'S': (4, 'abc')}, 1), ('S=ABC', {'S': (4, 'abc')}, 0),
                 ('S$$530', {'S': (4, 'SGX 530')}, 1), ('S!$530', {'S': (4, 'SGX 530')}, 0),
                 ('S$$530', {}, 0), ('S$$530', {'S': (2, 530)}, 0),
                 ('B=true', {'B': (1, True)}, 1), ('B=false', {'B': (1, True)}, 0),
                 ('N>=1.5', {'N': (3, 1.5)}, 1)]
        for text, spec, expected in cases:
            with self.subTest(text=text, spec=spec):
                self.assertEqual(p.condition(text, spec), expected)

    def test_original_selector_nesting_first_match_and_fallback(self):
        from native_device_selection_probe import NativeDeviceSelectionProbe
        fixture = {'defaults': [], 'overrides': {}, 'priority': {}, 'selection': [
            {'A': [[['GPU$$A', 'GPU$$B'], ['CORES>=4']], [['MODEL=Y']]]},
            {'B': [[['GPU$$B']]]}, {'fallback': [[]]}]}
        for spec, expected in [({'GPU': (4, 'A'), 'CORES': (2, 4)}, 'A'),
                               ({'GPU': (4, 'B'), 'CORES': (2, 4)}, 'A'),
                               ({'GPU': (4, 'B'), 'CORES': (2, 2)}, 'B'),
                               ({'MODEL': (4, 'Y')}, 'A'), ({}, 'fallback')]:
            with self.subTest(spec=spec):
                self.assertEqual(NativeDeviceSelectionProbe(self.image).select(fixture, spec), expected)

    def test_original_update_order_and_layer_upper_clamp(self):
        from native_device_selection_probe import NativeDeviceSelectionProbe
        fixture = {'defaults': [{'Default': [['TerrainTileSight', 2], ['DeviceLayer', 5]]}],
                   'overrides': {'A': {'TerrainTileSight': 1, 'DeviceLayer': 2}},
                   'priority': {}, 'selection': []}
        p = NativeDeviceSelectionProbe(self.image)
        self.assertEqual(p.updates(fixture, 'A'),
                         [['TerrainTileSight', 2], ['DeviceLayer', 5], ['DeviceLayer', 2], ['TerrainTileSight', 1]])
        for value, expected in [(0, 0), (1, 1), (4, 4), (5, 4), (6, 4)]:
            self.assertEqual(p.layer_clamp(value), expected)

    def test_original_level_query_precedence_and_missing_model(self):
        from native_device_instance_probe import NativeDeviceInstanceProbe
        p = NativeDeviceInstanceProbe(self.image)
        p.configure_levels([{'name': 'model/a.bdae', 'level': 4, 'exceptions': ['7']},
                            {'name': 'model/a.bdae', 'level': 5, 'exceptions': []}],
                           [{'id': '9', 'level': 2}])
        self.assertEqual(p.lookup('model/a.bdae', 9), 2)
        self.assertEqual(p.lookup('model/a.bdae', 7), 0)
        self.assertEqual(p.lookup('model/a.bdae', 8), 4)
        self.assertEqual(p.lookup('missing.bdae', 8), 0)

    def test_original_admission_separates_dynamic_detail_and_xml_level(self):
        from native_device_instance_probe import NativeDeviceInstanceProbe
        query, gate = NativeDeviceInstanceProbe(self.image), NativeDeviceInstanceProbe(self.image)
        query.configure_levels([{'name': 'model/a.bdae', 'level': 3, 'exceptions': []}], [])
        gate.level_delegate = query.lookup
        def raw(dynamic=0xffffffff, detail=3):
            record = bytearray(76)
            struct.pack_into('<4I', record, 0, 2, 7, 0, 0)
            struct.pack_into('<2I', record, 0x38, detail, dynamic)
            name = b'model/a.bdae\0'
            return struct.pack('<4s5I', b'AITM', 5, 0, 0, 1, 1)+record+struct.pack('<2I', 1, len(name))+name
        gate.load_itm(raw())
        self.assertEqual(gate.admission(0, 2, 3), 'admittedBeforeTypeFactory')
        self.assertEqual(gate.admission(0, 2, 2), 'detailOrLevelRejected')
        gate.load_itm(raw(detail=1))
        self.assertEqual(gate.admission(0, 2, 4), 'detailOrLevelRejected')
        gate.load_itm(raw(dynamic=1))
        self.assertEqual(gate.admission(0, 2, 4), 'dynamicIdRejected')
        self.assertEqual(gate.admission(0, 2, 4, [1]), 'admittedBeforeTypeFactory')


@unittest.skipUnless(NATIVE.is_file() and DEFAULT_APK.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                     'Original APK, library and source packs remain local')
class DeviceSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.result = analyze(NativeImage(NATIVE.read_bytes()), DEFAULT_SOURCE, DEFAULT_APK, probe=True)

    def test_original_android_profile_and_priority_examples(self):
        rows = self.result['experiments']['deviceCases']
        self.assertEqual([r['selectedGPU'] for r in rows], ['GPU_0M', 'GPU_0', 'GPU_4', 'GPU_6'])
        self.assertEqual([r['deviceLayerAfterOriginalClamp'] for r in rows], [1, 1, 3, 4])
        self.assertEqual([r['relatedValuesAtSetterBoundary']['TerrainTileSight'] for r in rows], [1, 2, 2, 2])
        self.assertTrue(self.result['experiments']['parameterSetterIsRecordedBoundary'])
        self.assertFalse(self.result['experiments']['originalProcessExecuted'])

    def test_original_tutorial_records_and_conditional_admission(self):
        r = self.result
        self.assertEqual(r['recordFields']['detailLow2'], {3: 1354})
        self.assertEqual(r['recordFields']['dynamicWords'], {0xffffffff: 1354})
        e = r['experiments']
        self.assertEqual([e['admissionByExplicitLayer'][i]['admittedBeforeTypeFactory'] for i in range(5)],
                         [404, 513, 1171, 1316, 1327])
        self.assertEqual(e['sourceLevelCounts'][5], 27)
        self.assertEqual([v['admittedBeforeFactoryByLayer'][1] for v in e['conditionalRegions']], [30, 82])
        self.assertEqual(len(r['EntityConfigSourceJoin']['matchingSourceIds']), 12)
        self.assertFalse(r['EntityConfigSourceJoin']['consumerFullyRecovered'])


if __name__ == '__main__':
    unittest.main()
