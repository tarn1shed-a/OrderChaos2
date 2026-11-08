"""Check original lookup, source bytes, and conditional scene consumers."""
import unittest
from pathlib import Path

from mesh_scene_evidence import analyze, verify_native
from bres_world_bounds_evidence import inner_bres
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
BOX = 'model/scene/main_human/hum_other_box003.bdae'


@unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                     'Original native/model materials stay private')
class MeshSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.result = analyze(cls.image, DEFAULT_SOURCE)

    def test_original_lookup_options_and_scene_entry_identities_fail_closed(self):
        self.assertEqual(verify_native(self.image)['factoryRoutes'], 8)
        image = self.image
        for changed in (0x111b8c4, 0x551fc8, 0x33e774, 0xa6196c):
            class Changed:
                elf = image.elf
                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == changed else raw
            with self.subTest(changed=hex(changed)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_all_six_match_their_real_source_record_before_constructor(self):
        self.assertEqual(len(self.result['models']), 6)
        for row in self.result['models']:
            self.assertEqual(len(row['cases']), 4)
            for case in row['cases']:
                self.assertEqual(case['sourceReference'], '#'+case['sourceGeometryName'])
                self.assertEqual(case['constructorEntry']['kind'], 'originalConstructorEntry')
                self.assertEqual(case['constructorEntry']['args'][6:], [1, 0])

    def test_factory_switches_change_options_without_changing_source_vertex_bytes(self):
        for row in self.result['models']:
            a, b, c, d = row['cases']
            for case in (a, b):
                self.assertEqual(case['constructorEntry']['vertexOptions'], [9, 6])
                self.assertEqual(case['constructorEntry']['indexOptions'], [9, 6])
            self.assertEqual(c['constructorEntry']['vertexOptions'], [9, 6])
            self.assertEqual(c['constructorEntry']['indexOptions'], [1 << 32, 6])
            self.assertEqual(d['constructorEntry']['vertexOptions'], [1 << 32, 6])
            self.assertEqual(d['constructorEntry']['indexOptions'], [1 << 32, 6])
            requests = [case['firstVertexRequest'] for case in row['cases']]
            self.assertEqual(len({v['sha256'] for v in requests}), 1)
            self.assertTrue(all(v['bytes'] > 0 and v['originalBytesEqual'] for v in requests))
            self.assertTrue(all(not v['GPUResultSupplied'] for v in requests))

    def test_original_lookup_rejects_unknown_name_and_kind_and_stops_external_acquisition(self):
        from native_mesh_scene_probe import NativeMeshSceneProbe
        p = NativeMeshSceneProbe(self.image)
        sources = Sources(DEFAULT_SOURCE)
        info = p.load(inner_bres(sources.read(BOX)))['info']
        ref = p.local_geometry_ref(info)
        literal = bytes(p.uc.mem_read(ref, 32))
        bad, name = p.alloc(32), p.alloc(64)
        p.uc.mem_write(bad, literal)
        p.uc.mem_write(name, b'#UNKNOWN-source-name\0')
        p.w(bad+8, 'Q', name)
        self.assertEqual(p.lookup(info, 0x2416430, ref=bad)['kind'], 'nullOriginalLookup')
        record = info+0xb8+p.r(info+0xb8, 'i')[0]
        p.w(record+0x10, 'I', 1)  # In-memory counterfactual only; never alter source files.
        self.assertEqual(p.lookup(info, 0x2416430, ref=ref)['kind'], 'nullOriginalLookup')
        p.w(bad, 'Q', name)
        self.assertEqual(p.lookup(info, 0x2416430, ref=bad)['kind'], 'externalResourceNotExecuted')

    def test_visible_selection_preserves_unresolved_material_boundary(self):
        self.assertEqual(len(self.result['instances']), 12)
        self.assertFalse(self.result['scope']['materialSuccessSupplied'])
        self.assertFalse(self.result['scope']['actualSceneStateObserved'])
        for row in self.result['instances']:
            self.assertEqual(row['selectedUntilMaterialBoundary']['boundary']['kind'],
                             'materialUpdateNotExecuted')
            self.assertTrue(row['attachmentFragmentExecutedSeparately'])
            self.assertEqual(row['identityParentWorldBox'], row['initialCallback']['worldBox'])

    def test_native_parent_translation_changes_all_twelve_boxes(self):
        for row in self.result['instances']:
            delta = [b-a for a, b in zip(row['identityParentWorldBox'], row['translatedParentWorldBox'])]
            for actual, expected in zip(delta, [5, 0, 0, 5, 0, 0]):
                self.assertAlmostEqual(actual, expected, delta=0.0005)

    def test_parent_visibility_inheritance_and_original_hidden_slot_detach(self):
        for row in self.result['instances']:
            hidden_mesh, = [v for v in row['parentHiddenTree'] if v['vptr'] == '0x244e538']
            restored_mesh, = [v for v in row['parentRestoredTree'] if v['vptr'] == '0x244e538']
            self.assertEqual(int(hidden_mesh['flags'], 16) & 8, 8)
            self.assertNotEqual(int(hidden_mesh['flags'], 16) & 0x18, 0x18)
            self.assertEqual(int(restored_mesh['flags'], 16) & 0x18, 0x18)
            self.assertEqual(row['rootParentAfterHiddenSlot'], 0)
            self.assertIsNone(row['originalHiddenSlotResult']['boundary'])
            self.assertEqual(row['originalHiddenSlotResult']['ownerVisibleByte'], 0)
            self.assertEqual(row['originalHiddenSlotResult']['slotWeights'], [0, 0])
            self.assertEqual(row['selectedUntilMaterialBoundary']['slotPointers'],
                             row['originalHiddenSlotResult']['slotPointers'])


if __name__ == '__main__':
    unittest.main()
