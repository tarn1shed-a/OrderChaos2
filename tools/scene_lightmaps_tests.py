import json
import struct
import tempfile
import unittest
from pathlib import Path

from bdae_convert import BDAE
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_lightmaps import ROUTINES, STRINGS, analyze, object_records, read_records, source_names, verify_native
from scene_sampling import material_samplers

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
MANIFEST = ROOT/'game-data/converted/manifest.json'


def fixture(rows=None, maximum=2):
    rows = rows if rows is not None else [(0x89abcdef, 0xfedcba98, 9, 2, bytes(range(16)))]
    return struct.pack('<Ii', len(rows), maximum)+b''.join(
        struct.pack('<4I', ident, opaque, key, page)+payload for ident, opaque, key, page, payload in rows)


class SceneLightmapTests(unittest.TestCase):
    def test_records_keep_unknown_bytes_opaque_and_allow_the_inclusive_last_atlas(self):
        result = read_records(fixture())
        self.assertEqual(result['recordCount'], 1)
        self.assertEqual(result['maximumAtlasIndex'], 2)
        self.assertEqual(result['records'][0], {'objectId': 0x89abcdef, 'opaqueWord4': 0xfedcba98,
                         'sortKey': 9, 'atlasIndex': 2, 'payload16Hex': bytes(range(16)).hex()})
        self.assertNotIn('uv', result['records'][0])
        # Unknown payload is not guessed to be finite floats or normalized UVs.
        payload = struct.pack('<4I', 0x7fc00000, 0xffffffff, 0x7f800000, 0x12345678)
        self.assertEqual(read_records(fixture([(1, 0, 0, 0, payload)], 0))['records'][0]['payload16Hex'], payload.hex())

    def test_bad_lengths_counts_and_atlas_ranges_fail_before_lookup(self):
        raw = fixture()
        for value in (raw[:7], raw[:-1], raw+b'\0', struct.pack('<Ii', 0, 0),
                      struct.pack('<Ii', 100001, 0), struct.pack('<Ii', 1, -1)+raw[8:],
                      struct.pack('<Ii', 1, 4096)+raw[8:], fixture(maximum=1)):
            with self.assertRaises(ValueError): read_records(value)

    def test_native_lookup_uses_u32_id_first_contiguous_run_and_stable_sort_key(self):
        rows = [(7, 4, 9, 1, b'a'*16), (7, 5, 2, 0, b'b'*16), (7, 6, 2, 0, b'c'*16),
                (8, 0, 0, 0, b'd'*16), (7, 0, 0, 0, b'e'*16)]
        table = read_records(fixture(rows))
        self.assertEqual([r['payload16Hex'] for r in object_records(table, 7)],
                         [(b'b'*16).hex(), (b'c'*16).hex(), (b'a'*16).hex()])
        self.assertEqual(object_records(table, 9), [])
        for ident in (-1, 1<<32, True, 7.0):
            with self.assertRaises(ValueError): object_records(table, ident)

    def test_names_follow_native_unpadded_coordinates_and_exact_suffix_order(self):
        self.assertEqual(source_names('tutorial', -41, 2), {
            'record': 'world/tutorial/lightmap/-41_2.dat',
            'texture': 'texture/lightmap/tutorial/lightmap/-41_2.tga'})
        self.assertEqual(source_names('tutorial', -41, 2, slot=1, phase=9, atlas=3), {
            'record': 'world/tutorial/lightmap/phasing/-41_2_9_l.dat',
            'texture': 'texture/lightmap/tutorial/lightmap/phasing/-41_2_l__3_9.tga'})
        for args in (('../tutorial', 0, 0), ('tutorial', 1<<31, 0), ('tutorial', 0, 0, 2),
                     ('tutorial', 0, 0, 0, -1), ('tutorial', 0, 0, 0, 0, 4096)):
            with self.assertRaises(ValueError): source_names(*args)

    def test_unknown_native_build_cannot_validate_this_layout(self):
        class Changed:
            def read(self, address, size): return bytes(size)
        with self.assertRaisesRegex(ValueError, 'loader changed'): verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file(), 'Original native evidence stays local')
    def test_source_lookup_loader_and_filename_fingerprints(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual((result['routines'], result['strings'], result['objectIdBits']), (6, 7, 32))
        self.assertFalse(result['appliedToRendering'])
        for changed in [*ROUTINES, *STRINGS]:
            class Changed:
                def read(self, address, size):
                    return bytes(size) if address == changed else image.read(address, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    @unittest.skipUnless((DEFAULT_SOURCE/'tutorial.bin').is_file(), 'Original map evidence stays local')
    def test_current_source_instances_have_primary_records_without_selecting_the_second_slot(self):
        result = analyze()
        self.assertEqual(result['instanceCount'], 39)
        self.assertEqual(result['phaseScope'], 'non-phasing-files-only')
        self.assertEqual(len(result['files']), 7)
        declared = [a for f in result['files'].values() for a in f['declaredAtlases']]
        self.assertEqual(len(declared), 24)
        self.assertEqual(sum(not a['candidates'] for a in declared), 17)
        primary = [b for b in result['bindings'] if b['slot'] == 0]
        self.assertEqual(len(primary), 39)
        self.assertTrue(all(b['status'] == 'found' and len(b['requests']) == 1 for b in primary))
        self.assertTrue(all(r['atlasIndex'] == 0 and len(r['candidates']) == 1 for b in primary for r in b['requests']))
        secondary = [b for b in result['bindings'] if b['slot'] == 1]
        self.assertEqual(sum(b['status'] == 'record-file-missing' for b in secondary), 1)
        self.assertEqual(sum(not r['candidates'] for b in secondary for r in b.get('requests', [])), 2)
        self.assertEqual(len(result['defaultTextureCandidates']), 2)
        self.assertEqual(len({c['sha256'] for c in result['defaultTextureCandidates']}), 2)
        self.assertFalse(result['appliedToRendering'])

    @unittest.skipUnless(MANIFEST.is_file() and (DEFAULT_SOURCE/'res_scene.bin').is_file(), 'Original scene materials stay local')
    def test_all_current_scene_and_door_material_defaults_are_not_per_instance_atlas_names(self):
        manifest = json.loads(MANIFEST.read_text())
        archives = {p: ResourceArchive(DEFAULT_SOURCE/(p+'.bin')) for p in
                    ('res_scene', 'res_scene_generator_temple_000')}
        count = 0
        with tempfile.TemporaryDirectory() as temp:
            for item in manifest['scenery']+manifest['dynamicModels']:
                source = item['model']
                pack = 'res_scene_generator_temple_000' if source.startswith('model/scene_generator_') else 'res_scene'
                target = Path(temp)/'source.bdae'; target.write_bytes(archives[pack].read(source))
                for material in material_samplers(BDAE(target)):
                    self.assertEqual(material['samplers']['lightMap']['texture'], 'texture/lightmap.tga')
                    count += 1
        self.assertEqual(count, 52)


if __name__ == '__main__': unittest.main()
