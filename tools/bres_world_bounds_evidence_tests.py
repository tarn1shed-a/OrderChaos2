"""Check source-to-world-box consumers, keeping process/rendering claims separate."""
import math
import struct
import unittest
from pathlib import Path

from bres_world_bounds_evidence import analyze, inner_bres, corner_check, verify_native
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
BOX = 'model/scene/main_human/hum_other_box003.bdae'
SMITHY = 'model/scene/main_human/hum_archi_smithy001_03.bdae'


class CornerCheckTests(unittest.TestCase):
    def test_eight_corner_cross_check_rejects_a_wrong_native_result(self):
        matrix = [-2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, 10, 20, 30, 1]
        self.assertEqual(corner_check([-1, -2, -3, 1, 2, 3], matrix, [8, 14, 27, 12, 26, 33])['maxAbsoluteDifference'], 0)
        with self.assertRaises(ValueError):
            corner_check([-1, -2, -3, 1, 2, 3], matrix, [9, 14, 27, 12, 26, 33])


@unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                     'Original ARM64/model inputs remain private')
class SourceWorldBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.sources = Sources(DEFAULT_SOURCE)
        cls.result = analyze(cls.image, DEFAULT_SOURCE)

    def probe(self):
        from native_bres_world_bounds_probe import NativeBresWorldBoundsProbe
        return NativeBresWorldBoundsProbe(self.image)

    def record(self):
        raw = self.sources.read('world/tutorial/items/-042_-001.itm')
        return raw[24+9*76:24+10*76]

    def test_original_bres_matrix_and_factory_identities_fail_closed(self):
        self.assertEqual(verify_native(self.image)['additionalRoutines'], 24)
        image = self.image
        for target in (0x148debc, 0x117c40c, 0x1364674, 0x11dd3e0):
            class Changed:
                elf = image.elf
                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            with self.subTest(target=hex(target)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_original_prefixes_one_and_two_reach_exact_source_bbox_bytes(self):
        cases = self.result['models']
        self.assertEqual({v['preparedBuffers'][0]['prefixCount'] for v in cases}, {1, 2})
        self.assertTrue(all(v['preparedBuffers'][0]['bboxBytesEqual'] for v in cases))
        for row in cases:
            b = row['preparedBuffers'][0]
            self.assertEqual(b['sourceBoxOffset'], b['sourceBufferOffset']+8*b['prefixCount']+0x60)
        self.assertEqual({v['preparedBuffers'][0]['prefixCount'] for v in cases if v['model'] == SMITHY}, {2})

    def test_all_twelve_have_eight_matching_original_branch_results(self):
        r = self.result
        self.assertEqual((len(r['models']), len(r['instances'])), (24, 12))
        self.assertTrue(all(len(v['variants']) == 8 for v in r['instances']))
        for row in r['instances']:
            boxes = [v['callbackResult']['worldBox'] for v in row['variants']]
            self.assertTrue(all(b == boxes[0] for b in boxes))
            self.assertTrue(all(math.isfinite(v) for v in boxes[0]))
            self.assertTrue(all(a <= b for a, b in zip(boxes[0][:3], boxes[0][3:])))
        self.assertFalse(r['scope']['VFSOrAndroidProcessExecuted'])
        self.assertTrue(r['scope']['meshGraphicsObjectAdaptedFromOriginalPreparedBBox'])
        self.assertFalse(r['appliedToGame'])

    def test_source_smithy_scale_and_pivot_are_native_ancestors(self):
        row = next(v for v in self.result['models'] if v['model'] == SMITHY)
        fields = row['sourceNodeFields']
        self.assertEqual(fields[1]['parent'], 0)
        self.assertNotEqual(fields[0]['literalTRS'][7:], [1, 1, 1])
        self.assertEqual(fields[1]['name'], 'Object001_PIVOT')
        instance = next(v for v in self.result['instances'] if v['id'] == 789231936)
        world = instance['variants'][0]['callbackResult']['worldBox']
        self.assertAlmostEqual(world[0], -2636.477294921875)
        self.assertAlmostEqual(world[3], -2634.739990234375)

    def test_original_flag_production_and_ordinary_bounds_branch(self):
        constructors = [w for v in self.result['models'] for w in v['constructionFlagWrites']]
        self.assertTrue(any(v['pc'] == 0x13430b4 and v['after'] == 0x31f8 for v in constructors))
        for row in self.result['instances']:
            for variant in row['variants']:
                mesh, = [v for v in variant['sourceTree'] if v['vptr'] == '0x244e538']
                self.assertEqual(int(mesh['flags'], 16) & 0x18, 0x18)
                self.assertEqual(int(mesh['flags'], 16) & 0x800, 0)
                self.assertTrue(any(w['pc'] == 0x1364790 for w in variant['originalFlagWrites']))

    def test_counterfactual_source_visibility_changes_native_inherited_gate(self):
        p = self.probe()
        loaded = p.load(inner_bres(self.sources.read(BOX)))
        info = loaded['info']
        scene = info+0xe0+p.r(info+0xe0, 'i')[0]
        node = scene+0x14+p.r(scene+0x14, 'i')[0]
        p.w(node+0x40, 'I', 0)  # Change only the in-memory research input.
        root = p.scene(info)
        mesh, = [v for v in p.tree(root) if v['vptr'] == '0x244e538']
        self.assertNotEqual(int(mesh['flags'], 16) & 0x18, 0x18)
        self.assertTrue(any(w['pc'] == 0x1362e80 and not w['after'] & 8 for w in p.flag_writes))

    def test_original_itm_words_keep_quaternion_bits_and_move_world_box(self):
        p = self.probe()
        loaded = p.load(inner_bres(self.sources.read(BOX)))
        root = p.scene(loaded['info'])
        config = self.sources.read('world/tutorial.wld')[40:52]
        record = self.record()
        trs = p.itm_transform(record, [-42, -1], config)
        self.assertEqual(tuple(trs[3:7]), struct.unpack_from('<4f', record, 28))
        initial = p.finish(root, trs, BOX)['worldBox']
        changed = bytearray(record)
        struct.pack_into('<f', changed, 16, struct.unpack_from('<f', changed, 16)[0]+5)
        moved = p.finish(root, p.itm_transform(changed, [-42, -1], config), BOX)['worldBox']
        self.assertEqual([moved[i]-initial[i] for i in range(6)], [5, 0, 0, 5, 0, 0])

    def test_research_guards_reject_incomplete_bres_and_untraced_factory(self):
        p = self.probe()
        raw = inner_bres(self.sources.read(BOX))
        with self.assertRaises(ValueError): p.load(raw[:-1])
        with self.assertRaises(ValueError): p.scene(0, factory=0)


if __name__ == '__main__':
    unittest.main()
