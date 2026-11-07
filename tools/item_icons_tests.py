import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from item_icons import recover_item_icons, SELECTION, ITEMS_TABLE, DISPLAY_TABLE, NAME_TABLE
from skill_icons_tests import ftable
from resource_packs import ResourceArchive, DEFAULT_SOURCE


def fixtures():
    result = {
        ITEMS_TABLE: ftable([('entry','u'),('name1','u'),('displayid','u')], [
            {'entry': identifier, 'name1': name, 'displayid': 0} for identifier, name, _ in SELECTION.values()]),
        DISPLAY_TABLE: ftable([('ID','u'),('Icon','s')], [
            {'ID': identifier, 'Icon': filename} for identifier, _, filename in SELECTION.values()]),
        NAME_TABLE: ftable([('ID','u'),('text','s')], [{'ID': name, 'text': key} for key, (_, name, _) in SELECTION.items()], localized=True),
    }
    data = io.BytesIO(); Image.new('RGBA', (96,96), (122,95,60,255)).save(data, format='PNG')
    for _, _, filename in SELECTION.values(): result['ui/icons/item/' + filename] = data.getvalue()
    return result


class ItemIconTests(unittest.TestCase):
    def test_copies_checked_source_bytes_and_retains_unresolved_link_boundary(self):
        source = fixtures()
        with tempfile.TemporaryDirectory() as folder:
            profile = recover_item_icons(source.__getitem__, folder)
            self.assertFalse(profile['provenance']['nativeZeroDisplayFallbackVerified'])
            for entry in profile['icons'].values():
                self.assertEqual((Path(folder)/entry['url'].removeprefix('/assets/')).read_bytes(), source[entry['sourcePath']])
                self.assertEqual(entry['item']['entry'], entry['display']['ID'])
    def test_refuses_different_table_link_before_writing(self):
        source = fixtures(); source[DISPLAY_TABLE] = source[DISPLAY_TABLE].replace(b'faith_feet.png', b'faith_fake.png')
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'reference mismatch'): recover_item_icons(source.__getitem__, folder)
            self.assertFalse((Path(folder)/'ui/item-icons.json').exists())
    def test_refuses_half_resolution_icon(self):
        source = fixtures(); image = io.BytesIO(); Image.new('RGBA',(48,48)).save(image,format='PNG')
        source['ui/icons/item/august_spatha.png'] = image.getvalue()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError,'dimensions'): recover_item_icons(source.__getitem__, folder)
    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file() and (DEFAULT_SOURCE/'ui_icon_1.bin').is_file(), 'Original art remains local-only')
    def test_real_source_tables_and_icons(self):
        packs = {key: ResourceArchive(DEFAULT_SOURCE/key) for key in ('tables.bin','ui_icon_1.bin')}
        with tempfile.TemporaryDirectory() as folder:
            profile = recover_item_icons(lambda path: packs['ui_icon_1.bin' if path.startswith('ui/') else 'tables.bin'].read(path), folder)
            self.assertEqual(profile['icons']['wolfPelt']['sourceName']['value'], '狼皮')
            self.assertEqual(len(profile['icons']), 6)

if __name__ == '__main__': unittest.main()
