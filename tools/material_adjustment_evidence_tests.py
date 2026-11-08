"""Source declarations and original material/cache consumers; no GPU success fixtures."""
import unittest
from pathlib import Path

from material_adjustment_evidence import analyze, verify_native
from bres_world_bounds_evidence import inner_bres
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
BOX = 'model/scene/main_human/hum_other_box003.bdae'


@unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                     'Original native/model materials stay private')
class MaterialAdjustmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.result = analyze(cls.image, DEFAULT_SOURCE)

    def fixture(self):
        from native_material_adjustment_probe import NativeMaterialAdjustmentProbe
        p = NativeMaterialAdjustmentProbe(self.image)
        s = Sources(DEFAULT_SOURCE)
        root = p.scene(p.load(inner_bres(s.read(BOX)))['info'])
        p.finish(root, [0, 0, 0, 0, 0, 0, 1, 1, 1, 1], BOX, slot=0)
        raw = s.read('world/tutorial/items/-042_-001.itm')[24+9*76:24+10*76]
        p.source_shadow_field(raw, 1)
        p.atlas_presence_fixture(0, False)
        return p, root

    def test_original_material_and_postcall_identities_fail_closed(self):
        image = self.image
        self.assertEqual(verify_native(image)['additionalRoutines'], 8)
        for changed in (0x327160, 0x33b854, 0x550db4, 0x33e86c):
            class Changed:
                elf = image.elf
                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == changed else raw
            with self.subTest(changed=hex(changed)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_twelve_source_ids_have_both_slot_records_and_unique_atlas_candidates(self):
        self.assertEqual(len(self.result['instances']), 12)
        for row in self.result['instances']:
            self.assertEqual(row['sourceITMWord64'], 1)
            self.assertEqual(len(row['atlasSlots']), 2)
            for slot in row['atlasSlots']:
                self.assertEqual(slot['textureLoadedInOriginalProcess'], 'unobserved')
                self.assertEqual(len(slot['requests']), 1)
                request, = slot['requests']
                self.assertEqual(request['sourceRecord']['sortKey'], 0)
                self.assertEqual(len(request['candidates']), 1)

    def test_seven_materials_keep_their_real_effect_and_sampler_differences(self):
        models = self.result['models']
        self.assertEqual((len(models), sum(len(r['materials']) for r in models)), (6, 7))
        holder = next(v for v in models if v['model'].endswith('god_hammer_holder_01.bdae'))
        self.assertNotIn('lightMap', holder['materials'][0]['samplers'])
        smithy = next(v for v in models if v['model'].endswith('hum_archi_smithy001_03.bdae'))
        self.assertEqual(len(smithy['materials']), 2)
        for row in models:
            for material in row['materials']:
                self.assertEqual(len(material['effectCandidates']), 1)
                if 'lightMap' in material['samplers']:
                    fallback = material['samplers']['lightMap']
                    self.assertEqual(fallback['texture'], 'texture/lightmap.tga')
                    self.assertEqual(len(fallback['candidates']), 2)

    def test_original_source_config_atlas_and_fade_consumers_generate_the_options(self):
        checked = 0
        for row in self.result['instances']:
            for slot in row['conditionalSlots']:
                for case in slot['optionCases']:
                    expected = (0x2000 if case['explicitConfig40'] == 2 else 0)
                    expected |= 0x80 if case['explicitAtlasPointerPresent'] else 0
                    expected |= 0x140004 if case['explicitFading'] else 0
                    self.assertEqual(case['result']['options']['requestedFlags'], expected)
                    self.assertEqual(case['sourceShadowConsumer']['sourceBit'], 1)
                    self.assertEqual(case['sourceShadowConsumer']['ownerByte178'],
                                     int(case['explicitConfig40'] == 2))
                    checked += 1
        self.assertEqual(checked, 192)

    def test_first_preparation_generates_real_macros_and_stops_without_completion(self):
        for row in self.result['instances']:
            for slot in row['conditionalSlots']:
                cold = slot['firstPreparation']
                self.assertEqual(cold['boundary']['kind'], 'materialPreparationNotExecuted')
                self.assertIsNone(cold['returnedWord'])
                reload, = cold['trace']
                self.assertEqual(reload['mode'], 1)
                self.assertEqual(reload['rootStamp'], 0xffffffff)
                self.assertIn('#define UV1_TRANSFORM', reload['defines'])
                self.assertEqual('#define SHADOWMAP' in reload['defines'], slot['slot'] == 1)
                self.assertEqual(cold['before']['cachedFlags'], 64)
                self.assertEqual(cold['after']['cachedFlags'], 64)
                self.assertTrue(cold['after']['processedBits'] & (1 << slot['slot']))
        self.assertFalse(self.result['scope']['shaderOrGPUResultSupplied'])

    def test_original_zero_reload_return_still_leads_to_adjustment_return_one(self):
        p, root = self.fixture()
        p.w(root+0x148, 'I', 0)  # Explicit already-stamped state; not an observed source load.
        result = p.adjustment(0)
        self.assertEqual(result['returnedWord'], 1)
        self.assertIsNone(result['boundary'])
        self.assertIn({'kind': 'originalReloadReturned', 'word': 0}, result['trace'])
        self.assertEqual(result['after']['cachedFlags'], 0)
        unchanged = p.adjustment(0)
        self.assertEqual(unchanged['returnedWord'], 1)
        self.assertEqual(unchanged['trace'], [])
        self.assertEqual(p.adjustment(1)['returnedWord'], 0)  # Missing model slot.

    def test_processed_bit_only_selects_a_branch_without_proving_material_readiness(self):
        p, root = self.fixture()
        p.w(p.owner+0x5b, 'B', 1)  # Explicit prior-processed-bit condition.
        self.assertEqual(p.r(root+0x148, 'I')[0], 0xffffffff)
        result = p.adjustment(0)
        self.assertEqual(result['trace'][0]['mode'], 2)
        self.assertEqual(result['boundary']['kind'], 'materialRebuildNotExecuted')
        self.assertIsNone(result['returnedWord'])

    def test_original_postcall_attachment_ignores_the_incoming_return_word(self):
        p, root = self.fixture()
        parent = p.make_parent_fixture()
        p.bind_parent_fragment(parent)
        for word in (0, 1):
            # Separate original consumer fragment, not a fabricated material response.
            p.regs()
            p.set('W0', word)
            p.set('X19', root)
            p.set('X21', p.owner)
            p.run(0x33e870, 0x33e904)
            self.assertEqual(p.r(root+0xe8, 'Q')[0], parent)
            p.regs()
            p.set('X0', root)
            p.run(0x1363b80)


if __name__ == '__main__':
    unittest.main()
