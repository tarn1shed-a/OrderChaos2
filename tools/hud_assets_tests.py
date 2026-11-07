"""Synthetic HUD display-list checks and optional original-resource recovery."""
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from hud_assets import (IDENTITY, ART, compose, document, named_path, pixels, placement,
                        rectangle_bitmap, recover_hud_assets, timeline, vector_shape)
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from ui_assets_tests import Writer, bitmap_shape, matrix_bytes, path_bytes, rect_bytes, tag, swf_bytes


def place2(character=9, depth=1, move=False, matrix=True, name=None):
    flags = int(move) | (2 if character is not None else 0) | (4 if matrix else 0) | (32 if name else 0)
    data = bytes([flags]) + struct.pack('<H',depth)
    if character is not None: data += struct.pack('<H',character)
    if matrix: data += matrix_bytes(tx=40,ty=60,scale=1)
    if name: data += name.encode()+b'\0'
    return tag(26,data)


def solid_shape(points, rgba=(17,34,51,128), bounds=(0,40,0,60)):
    return struct.pack('<H',8)+rect_bytes(bounds)+b'\x01\x00'+bytes(rgba)+b'\x00'+path_bytes(points)


class HUDAssetTests(unittest.TestCase):
    def test_affine_parent_child_order_and_twip_to_pixel_conversion(self):
        combined = compose([0,1,-1,0,100,200],[2,0,0,3,10,20])
        self.assertEqual(combined,[0,2,-3,0,80,210])
        self.assertEqual(pixels(combined),[0,2,-3,0,4,10.5])

    def test_placeobject3_reads_class_matrix_and_name(self):
        raw = b'\x24\x08'+struct.pack('<H',4)+b'OriginalSlot\0'+matrix_bytes(tx=-120,ty=60,scale=1)+b'Icon\0'
        result = placement(70,raw)
        self.assertEqual(result['className'],'OriginalSlot')
        self.assertEqual(result['name'],'Icon')
        self.assertEqual(result['depth'],4)
        self.assertEqual(result['matrixTwips'],[1,0,0,1,-120,60])
        self.assertNotIn('characterId',result)

    def test_unknown_flags_filters_and_trailing_fields_fail(self):
        for raw in (b'\x24\x10\x01\0', b'\x80\0\x01\0',
                    b'\0\x01\x01\0\x01\x09', b'\0\0\x01\0x'):
            with self.assertRaises(ValueError):
                placement(70,raw)
        with self.assertRaises(ValueError):
            placement(26,b'\x20\x01\0unterminated')

    def test_timeline_moves_inherit_state_without_mutating_prior_frames(self):
        data = (place2(name='Icon')+tag(1,b'')+
                place2(character=None,move=True,matrix=False)+tag(1,b'')+
                tag(28,struct.pack('<H',1))+tag(1,b'')+tag(0,b''))
        frames = timeline(data,0,3)
        self.assertEqual(frames[0][0]['name'],'Icon')
        self.assertEqual(frames[1][0]['matrixPixels'],[1,0,0,1,2,3])
        self.assertEqual(frames[2],[])
        frames[1][0]['name']='changed'
        self.assertEqual(frames[0][0]['name'],'Icon')
        with self.assertRaisesRegex(ValueError,'absent depth'):
            timeline(place2(character=None,move=True,matrix=False)+tag(1,b'')+tag(0,b''),0,1)
        with self.assertRaisesRegex(ValueError,'frame count'):
            timeline(tag(1,b'')+tag(0,b''),0,2)

    def test_twelve_segment_scaling_grid_rectangle_is_lossless(self):
        points = [(0,0),(10,0),(30,0),(40,0),(40,15),(40,45),(40,60),
                  (30,60),(10,60),(0,60),(0,45),(0,15),(0,0)]
        bitmap,rect,matrix,bounds,segments = rectangle_bitmap(bitmap_shape(points))
        self.assertEqual((bitmap,rect,segments),(2,[6,10,8,13],12))
        triangle = [(0,0),(40,0),(0,60),(0,0)]
        with self.assertRaisesRegex(ValueError,'perimeter'):
            rectangle_bitmap(bitmap_shape(triangle))

    def test_vector_masks_keep_original_color_path_and_open_contours_fail(self):
        points = [(0,0),(40,0),(40,60),(0,60),(0,0)]
        shape = vector_shape(32,solid_shape(points))
        self.assertEqual(shape['sourceFillRGBA'],[17,34,51,128])
        self.assertEqual(shape['boundsPixels'],[0,2,0,3])
        self.assertIn('M ',shape['pathPixels'])
        self.assertTrue(shape['pathPixels'].endswith('Z'))
        with self.assertRaisesRegex(ValueError,'open fill contour'):
            vector_shape(32,solid_shape([(0,0),(40,0)]))
        with self.assertRaisesRegex(ValueError,'fill style'):
            vector_shape(2,bitmap_shape())

    def test_bad_stage_timeline_cannot_silently_become_a_layout(self):
        with self.assertRaisesRegex(ValueError,'ShowFrame count|frame count'):
            document(swf_bytes(b''),'synthetic.swf')

    @unittest.skipUnless((DEFAULT_SOURCE/'ui.bin').is_file() and (DEFAULT_SOURCE/'conf.bin').is_file(),
                         'Original game UI artwork is local-only')
    def test_real_crops_source_roles_transforms_and_masks(self):
        archives = {name:ResourceArchive(DEFAULT_SOURCE/(name+'.bin')) for name in ['ui','conf']}
        def extract(path):
            return archives['conf' if path.startswith('ui/Config/') else 'ui'].read(path)
        with tempfile.TemporaryDirectory() as temp:
            profile = recover_hud_assets(extract,temp)
            self.assertEqual(profile['format'],'oc2-original-hud-v1')
            controls=profile['nativeControls']
            self.assertEqual(controls['format'],'oc2-original-mobile-controls-v1')
            self.assertAlmostEqual(controls['mapFrame']['boundsPixels'][0],17.5)
            self.assertAlmostEqual(controls['mapFrame']['boundsPixels'][1],25.8)
            self.assertAlmostEqual(controls['mapFrame']['boundsPixels'][2],110)
            self.assertAlmostEqual(controls['mapFrame']['boundsPixels'][3],110)
            self.assertEqual(controls['joystick']['sourceControlSymbol'],'control')
            self.assertTrue(controls['joystick']['runtimePositionAndSizeAreNotProvenBySWF'])
            self.assertEqual(profile['layouts']['joystick']['fields']['bg']['matrixPixels'][:4],[.75,0,0,.75])
            self.assertEqual(profile['layouts']['joystick']['fields']['stick']['leafCharacterId'],2)
            self.assertGreater(profile['layouts']['operations']['interaction']['boundsPixels'][2],80)
            self.assertEqual(len(profile['assets']),len(ART))
            for key,asset in profile['assets'].items():
                original = Image.open(io.BytesIO(extract(asset['sourceAtlas']))).crop(asset['sourceRect'])
                if asset['sourceFlipX']: original = original.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                if asset['sourceFlipY']: original = original.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                actual = Image.open(Path(temp)/'ui'/Path(asset['url']).name)
                self.assertEqual(actual.size,original.size,key)
                self.assertEqual(actual.tobytes(),original.tobytes(),key)
                self.assertFalse(asset['colorTransformBaked'])
            self.assertNotIn('portraitFrame',profile['assets'])
            self.assertEqual(profile['layouts']['player']['sourceRole'],'selected-player-target')
            self.assertTrue(profile['layouts']['self']['portraitIsWebAdaptation'])
            self.assertEqual(len(profile['layouts']['shortcuts']['fields']),6)
            slots = profile['layouts']['operations']['slots']
            self.assertEqual(set(slots),set('01234'))
            self.assertAlmostEqual(slots['0']['centerPixels'][0],160.36164056509733)
            self.assertAlmostEqual(slots['1']['centerPixels'][1],86.8544189453125)
            hp = profile['progress']['healthGreen']
            self.assertEqual((hp['sourceOwnerSWF'],hp['sourceOwnerPath']),('ui/Flash/Gauges2.swf','HP.HP_instance'))
            self.assertEqual(hp['frameCount'],50)
            self.assertEqual(hp['webMapping']['ratioOrder'],'descending')
            self.assertEqual(hp['content']['colorTransform']['add'],[-150,30,0,0])
            self.assertEqual(hp['frames'][0]['masks'][0]['sourceShapeId'],2399)
            self.assertEqual(hp['frames'][-1]['masks'][0]['sourceShapeId'],2447)
            mappings = {(mask['sourceBitmapId'],tuple(mask['sourceBitmapMatrixTwips']))
                        for frame in hp['frames'] for mask in frame['masks']}
            self.assertEqual(len(mappings),1)
            cooldown = profile['progress']['cooldownSkill']
            self.assertEqual(cooldown['content']['sourceFillRGBA'],[0,0,0,178])
            self.assertEqual(cooldown['frames'][0]['masks'],[])
            self.assertEqual(cooldown['frameCount'],40)
            self.assertEqual(profile['progress']['experience']['frameCount'],101)
            self.assertFalse(profile['semantics']['localGameplayHasMP'])
            self.assertFalse(profile['provenance']['swfScriptExecution'])
            self.assertEqual(json.loads((Path(temp)/'ui/hud.json').read_text()),profile)


if __name__ == '__main__':
    unittest.main()
