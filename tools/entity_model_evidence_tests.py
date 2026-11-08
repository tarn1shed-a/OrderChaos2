"""Check original EntityConfig consumers without constructing a replacement game."""
import collections
import unittest
from pathlib import Path

from entity_model_evidence import analyze, verify_native
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def xml_fixture(mode=2, extra='', instance_distance='113.018311'):
    return (f'<Entity><Item><Model name="model/test.bdae" culldistance="20.173920" '
            f'lodlevel="0" device="6"><Instance id="7" phasing="0" '
            f'culldistance="{instance_distance}" lodlevel="0" device="6" cullmode="{mode}" '
            f'{extra}/></Model></Item><Npc/><Object/></Entity>').encode()


@unittest.skipUnless(NATIVE.is_file(), 'Original ARM64 sample remains local')
class EntityNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())

    def probe(self):
        from native_entity_model_probe import NativeEntityModelProbe
        return NativeEntityModelProbe(self.image)

    def test_source_identity_rejects_changed_reader_or_initial_gate(self):
        self.assertEqual(verify_native(self.image)['additionalRoutines'], 10)
        image = self.image
        for changed in (0x4c975c, 0x1aaba78, 0xa61e7c, 0x250a8a8):
            class Changed:
                elf = image.elf
                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == changed else raw
            with self.subTest(changed=hex(changed)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_original_reader_uses_integer_conversion_for_decimal_distance(self):
        p = self.probe()
        model, = p.load(xml_fixture())
        self.assertEqual((model['distanceInt'], model['lod'], model['device']), (20, 0, 6))
        self.assertEqual(model['instances'], [dict(id=7, phase=0, distanceInt=113, lod=0, device=6, mode=2)])
        self.assertEqual(p.bind('model/test.bdae', 7), 113.0)
        with self.assertRaisesRegex(ValueError, 'fresh EntityConfig'):
            p.load(xml_fixture())

    def test_original_modes_and_missing_matches_preserve_prior_value(self):
        for mode, expected in ((0, 37.0), (1, 20.0), (2, 113.0), (3, 37.0)):
            p = self.probe()
            p.load(xml_fixture(mode))
            with self.subTest(mode=mode):
                self.assertEqual(p.bind('model/test.bdae', 7, 37), expected)
                self.assertEqual(p.bind('model/test.bdae', 8, 37), 37)
                self.assertEqual(p.bind('model/missing.bdae', 7, 37), 37)

    def test_stored_fields_do_not_override_identified_mode2_binding(self):
        p = self.probe()
        raw = xml_fixture().replace(b'phasing="0"', b'phasing="12"')
        raw = raw.replace(b'lodlevel="0"', b'lodlevel="5"').replace(b'device="6"', b'device="1"')
        model, = p.load(raw)
        self.assertEqual((model['instances'][0]['phase'], model['lod'], model['device']), (12, 5, 1))
        self.assertEqual(p.bind('model/test.bdae', 7), 113.0)
        # This asserts one original binding fragment, not global field disuse.

    def test_original_initial_config_and_missing_lower_filename_keep_slot_identity(self):
        p = self.probe()
        for config, incoming, slot, forced in ((0, 1, 0, True), (1, 0, 1, True),
                                                (2, 0, 0, False), (2, 1, 1, False)):
            self.assertEqual(p.initial(config, incoming), dict(requestedSlot=slot, forceSingleSlot=forced))
        for config, incoming, slot, forced in ((0, 0, 0, True), (1, 1, 1, True), (2, 1, 1, False)):
            self.assertEqual(p.static_initial(config),
                             dict(incomingSlot=incoming, requestedSlot=slot, forceSingleSlot=forced))
        missing = p.fresh('model/test.bdae', 1, True, lambda n: False)
        self.assertEqual(missing, {'requests': [{'slot': 1, 'path': 'model/test.bdae'}],
                                   'existsQueries': ['model/test_l.bdae']})
        present = p.fresh('model/test.bdae', 1, True, lambda n: True)
        self.assertEqual(present['requests'], [{'slot': 1, 'path': 'model/test_l.bdae'}])
        dynamic = p.fresh('model/test.bdae', 1, False, lambda n: False)
        self.assertEqual(dynamic, {'requests': [{'slot': 1, 'path': 'model/test_l.bdae'},
                                              {'slot': 0, 'path': 'model/test.bdae'}], 'existsQueries': []})

    def test_original_distance_gate_hysteresis_and_sentinel_do_not_release_loaded_slots(self):
        from native_model_slot_probe import NativeModelSlotProbe
        p = NativeModelSlotProbe(self.image)
        values = dict(center=[0, 0, 0], position=[20, 0, 0], radius=0,
                      scale160=1, config18=10, override168=50)
        self.assertIsNone(p.select(**values))
        self.assertEqual(p.select(**values, override_enabled=True), 1)
        for outer in (50, 113, 150):
            for current in (0, 1, 2):
                edge = outer+(8 if current < 2 else 0)
                for distance, expected in ((edge-1, 1), (edge, 2)):
                    request = p.select(**(values | dict(position=[distance, 0, 0], current=current,
                                                       override168=outer, override_enabled=True)))
                    self.assertEqual(current if request is None else request, expected)
        self.assertEqual(p.select(**(values | dict(position=[58, 0, 0], current=1,
                                                  config28=0, override_enabled=True))), 2)
        result = p.transition(0, 0, [True, True], 2)
        self.assertEqual((result['requested'], result['active']), (2, 2))
        self.assertEqual(p.loads, [])
        self.assertTrue(all(p.read(p.SELF+0x98, '2Q')))


@unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                     'Original ARM64 and source packs remain local')
class EntitySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.result = analyze(NativeImage(NATIVE.read_bytes()), DEFAULT_SOURCE, probe=True)

    def test_original_twelve_joined_instances_have_conditional_not_visible_counts(self):
        r = self.result
        self.assertEqual(len(r['models']), 6)
        self.assertEqual(len(r['instances']), 12)
        self.assertEqual(collections.Counter(v['boundObject168'] for v in r['instances']),
                         {50.0: 10, 113.0: 1, 150.0: 1})
        admitted = [sum(v['admissionByExplicitLayer'][layer] == 'admittedBeforeTypeFactory'
                        for v in r['instances']) for layer in range(5)]
        self.assertEqual(admitted, [1, 1, 12, 12, 12])
        self.assertTrue(all(v['sourceRecord']['sourceType'] == 2 for v in r['instances']))
        self.assertFalse(r['appliedToGame'])

    def test_original_base_assets_and_source_only_filename_experiment(self):
        r = self.result
        self.assertTrue(all(v['baseLocalCandidates'] == 1 and v['lowerLocalCandidates'] == 0
                            for v in r['models']))
        forced = [v for v in r['experiments']['freshRequests'] if v['explicitForceModelLodLevel'] == 1]
        self.assertEqual(len(forced), 6)
        self.assertTrue(all(v['freshRequest']['requests'] == [{'slot': 1, 'path': v['model']}] for v in forced))
        self.assertFalse(r['experiments']['originalXMLTokenizerExecuted'])
        self.assertTrue(r['experiments']['originalXMLFieldReaderExecuted'])
        self.assertFalse(r['experiments']['resourceTaskOrRendererExecuted'])


if __name__ == '__main__':
    unittest.main()
