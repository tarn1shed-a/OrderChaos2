import copy
import hashlib
import json
import unittest
from unittest.mock import patch
from pathlib import Path

from scene_baked_lighting import ENCODING_ROUTINES, FORMAT, recover_model_lighting, verify_native

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class ModelReader:
    def section(self, offset): return (1, 80) if offset == 172 else (0, 0)
    def u(self, offset): return {112: 0}.get(offset, 0)
    def rel(self, offset): return 0


class BakedContractTests(unittest.TestCase):
    def test_source_model_sampler_skip_branch_requires_default_lightmap_and_complete_uv1(self):
        data = {'materials': [{'name': 'synthetic', 'diffuse': 'texture/a.tga'}],
                'meshes': [{'positions': [0, 0, 0], 'sourceUV1': [.25, .75]}]}
        record = {'material': 'synthetic', 'samplers': {'lightMap': {
            'texture': 'texture/lightmap.tga', 'request': {'addressU': None}}}}
        with patch('scene_baked_lighting.material_samplers', return_value=[record]):
            self.assertEqual(recover_model_lighting(ModelReader(), data)['format'], FORMAT)
            for change in ('UV1', 'sampler', 'texture', 'name'):
                d, r = copy.deepcopy(data), copy.deepcopy(record)
                if change == 'UV1': d['meshes'][0]['sourceUV1'] = []
                if change == 'sampler': r['samplers']['lightMap']['request']['addressU'] = 0
                if change == 'texture': r['samplers']['lightMap']['texture'] = 'explicit-other.tga'
                if change == 'name': r['material'] = 'other'
                with self.subTest(change=change), patch('scene_baked_lighting.material_samplers', return_value=[r]), self.assertRaises(ValueError):
                    recover_model_lighting(ModelReader(), d)


class BakedLightingTests(unittest.TestCase):
    @unittest.skipUnless(NATIVE.is_file(), 'Native source stays local')
    def test_native_pvr_dispatch_and_both_gl_uploads_use_non_srgb_rgb_formats(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual(result['formatIndex'], 52)
        self.assertEqual(result['compressedUploadFormats'], [0x8d64, 0x9274])
        self.assertFalse(result['automaticSRGBDecode'])
        for changed in [*ENCODING_ROUTINES, 0x1f3b90c+0x36*4]:
            class Changed:
                elf = image.elf
                def read(self, address, size):
                    return bytes(size) if address == changed else image.read(address, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())


if __name__ == '__main__': unittest.main()
