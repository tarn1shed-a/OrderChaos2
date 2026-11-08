"""Original-sample checks; no browser/prototype fixtures."""
import unittest
from pathlib import Path

from map_loading_evidence import audit, read_world_container, verify_native
from resource_packs import DEFAULT_SOURCE, ResourceArchive

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class OriginalMapLoadingTests(unittest.TestCase):
    @unittest.skipUnless((DEFAULT_SOURCE/'tutorial.bin').is_file(), 'Original map remains local')
    def test_world_file_spans_match_observed_native_copy_without_naming_unused_fields(self):
        raw = ResourceArchive(DEFAULT_SOURCE/'tutorial.bin').read('world/tutorial.wld')
        result = read_world_container(raw)
        self.assertEqual(len(raw), 52)
        self.assertEqual(result['name'], 'tutorial')
        self.assertEqual(result['nameSpan'], [32, 8])
        self.assertEqual(result['configurationSpan'], [40, 12])
        self.assertEqual(result['configurationWords'], [3, 3, 1])
        self.assertEqual(result['derivedTileSpan'], 64)
        self.assertEqual(result['unnamedHeaderWords'], {'24': 0, '28': 52})

    @unittest.skipUnless(NATIVE.is_file(), 'Original native image remains local')
    def test_original_calls_task_tables_and_virtual_factory_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual(result['nativeTaskJumpTables']['0x1e64430'],
                         ['0xa60a9c', '0xa60b2c', '0xa60ab4', '0xa60ad0', '0xa60b00'])
        class Changed:
            elf = image.elf
            def read(self, address, size):
                raw = image.read(address, size)
                return bytes([raw[0] ^ 1]) + raw[1:] if address == 0x8fd1e4 else raw
        with self.assertRaisesRegex(ValueError, 'routine changed'):
            verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                         'Original native/map inputs remain local')
    def test_map_item_model_and_phy_links_use_source_files_without_a_preview_manifest(self):
        result = audit(DEFAULT_SOURCE, NATIVE, 'tutorial', -43, 2, 3)
        self.assertEqual(result['mapInfoAssociation'], {'mapId': 5, 'file': 'world/tutorial.wld'})
        self.assertEqual((result['sample']['instances'], result['sample']['modelTypes']), (39, 16))
        self.assertEqual(result['sourceZoneIds'], [194, 195, 196, 197, 199])
        self.assertTrue(all(row.get('recordWord0Counts', {2: 0}).keys() == {2}
                            for row in result['sample']['tiles']))
        base_shapes = [m['collisionCandidates'][m['sourceModel'][:-5]+'.phy']['decodedShapes']
                       for m in result['sample']['models']]
        self.assertEqual(sum(base_shapes), 110)
        self.assertEqual(result['sources']['world/tutorial.wld']['sha256'],
                         '069112792958e0a5ac9708acee0c4cb3d6eb5148c412516ac5a5ce33fd88636e')
        self.assertTrue(all('crc32' in row and 'sha256' in row for row in result['sources'].values()))


if __name__ == '__main__':
    unittest.main()
