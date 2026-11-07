"""Source-only rectangle tests and optional original bag/equipment recovery."""
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from inventory_assets import (ART, _single_bitmap_rectangle, _source_affine_texture,
                              recover_inventory_assets)
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from ui_assets_tests import bitmap_shape


class InventoryAssetTests(unittest.TestCase):
    def test_rectangle_reader_preserves_source_mapping(self):
        bitmap, rect, matrix, bounds = _single_bitmap_rectangle(bitmap_shape())
        self.assertEqual(bitmap,2)
        self.assertEqual(rect,[6,10,8,13])
        self.assertEqual(matrix,[20,0,0,20,-120,-200])
        self.assertEqual(bounds,[0,40,0,60])

    def test_nonrectangular_art_cannot_silently_become_background(self):
        with self.assertRaisesRegex(ValueError,'four-edge rectangle'):
            _single_bitmap_rectangle(bitmap_shape([(0,0),(40,0),(0,60),(0,0)]))

    def test_identity_bitmap_render_and_fractional_edge_alpha(self):
        source=Image.new('RGBA',(4,4),(30,60,90,200))
        image=_source_affine_texture(source,[20,0,0,20,0,0],[0,50,0,30])
        self.assertEqual(image.size,(3,2))
        self.assertTrue(all(abs(a-b)<=1 for a,b in zip(image.getpixel((0,0)),(30,60,90,200))))
        self.assertEqual(image.getpixel((2,0))[3],100)
        self.assertEqual(image.getpixel((0,1))[3],100)
        self.assertEqual(image.getpixel((2,1))[3],50)

    def test_invalid_source_matrix_and_output_extent_are_rejected(self):
        source=Image.new('RGBA',(2,2))
        for matrix in [[20,1,0,20,0,0],[0,0,0,20,0,0]]:
            with self.assertRaisesRegex(ValueError,'nonzero axis-aligned'):
                _source_affine_texture(source,matrix,[0,40,0,40])
        with self.assertRaisesRegex(ValueError,'dimensions'):
            _source_affine_texture(source,[20,0,0,20,0,0],[0,100000,0,40])

    @unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').is_file() and (DEFAULT_SOURCE/'conf.bin').is_file(),
                         'Original bag/equipment art is local-only')
    def test_real_source_pixels_original_layout_and_honest_boundaries(self):
        archives={name:ResourceArchive(DEFAULT_SOURCE/(name+'.bin')) for name in ['ui','conf']}
        def extract(path):return archives['conf' if path.startswith('ui/Config/') else 'ui'].read(path)
        with tempfile.TemporaryDirectory() as temp:
            profile=recover_inventory_assets(extract,temp)
            self.assertEqual(profile['format'],'oc2-original-inventory-v1')
            self.assertEqual(len(profile['assets']),len(ART)+1)
            for key,asset in profile['assets'].items():
                raw=Image.open(io.BytesIO(extract(asset['sourceAtlas'])))
                actual=Image.open(Path(temp)/'ui'/Path(asset['url']).name)
                self.assertEqual(actual.size,(asset['width'],asset['height']))
                if key=='panelTexture':
                    self.assertEqual(asset['mode'],'source-bitmap-affine-render')
                    expected=_source_affine_texture(raw,asset['sourceMatrixTwips'],asset['sourceBoundsTwips'])
                else:
                    expected=raw.crop(asset['sourceRect'])
                    if asset['sourceFlipX']:expected=expected.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    if asset['sourceFlipY']:expected=expected.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    self.assertEqual(asset['mode'],'lossless-source-atlas-crop')
                self.assertEqual(actual.tobytes(),expected.tobytes(),key)
            bag=profile['layouts']['bag']
            self.assertEqual((bag['columns'],bag['visibleRows'],len(bag['slots'])),(8,5,40))
            self.assertTrue(bag['visibleRowsAreNotTotalCapacity'])
            for a,b in zip(bag['slots'][0]['boundsPixels'],[73.65,77.7,96,96]):self.assertAlmostEqual(a,b)
            self.assertAlmostEqual(bag['slots'][8]['boundsPixels'][1]-bag['slots'][0]['boundsPixels'][1],95.65)
            equipment=profile['layouts']['equipment']
            self.assertEqual({slot['index'] for slot in equipment['slots']},{0,1,2,4,6,7,8,9,13,21})
            for a,b in zip(equipment['slots'][0]['boundsPixels'],[137.65,13.95,96,96]):self.assertAlmostEqual(a,b)
            self.assertTrue(equipment['modelViewport']['placeholderGeometryOnly'])
            self.assertFalse(equipment['sourceSlotBodyPartMappingRecovered'])
            self.assertEqual(equipment['fields']['cnt.EquipDisplay.objImage']['leafCharacterId'],28)
            self.assertFalse(profile['panel']['completePanelRendered'])
            self.assertFalse(profile['provenance']['swfScriptExecution'])
            self.assertFalse(profile['semantics']['localInventoryRulesRecovered'])
            self.assertEqual(profile,json.loads((Path(temp)/'ui/inventory.json').read_text()))


if __name__=='__main__':unittest.main()
