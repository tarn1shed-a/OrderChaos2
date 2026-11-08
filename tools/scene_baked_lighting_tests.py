import copy
import hashlib
import io
import json
import struct
import unittest
from unittest.mock import patch
from pathlib import Path

from scene_baked_lighting import ENCODING_ROUTINES, FORMAT, recover_baked_lighting, recover_model_lighting, verify_native
from resource_packs import DEFAULT_SOURCE, index, normalize_resource_name, read_entry

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
MANIFEST = ROOT/'game-data/converted/manifest.json'


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

    def test_changed_source_shader_is_rejected_before_map_or_texture_requests(self):
        calls = []
        def extract(path): calls.append(path); return b'changed source shader'
        with self.assertRaisesRegex(ValueError, 'shader changed'):
            recover_baked_lighting(extract, [], lambda p: self.fail('must not convert'))
        self.assertEqual(len(calls), 1)


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

    @unittest.skipUnless((DEFAULT_SOURCE/'tutorial.bin').is_file() and MANIFEST.is_file(), 'Original map stays local')
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text())
        lookup = {}
        for entry in index(DEFAULT_SOURCE): lookup.setdefault(normalize_resource_name(entry['path']), []).append(entry)
        self.lookup = lookup

    def extract(self, path):
        candidates = self.lookup[normalize_resource_name(path)]
        self.assertEqual(len(candidates), 1, path)
        return read_entry(candidates[0], DEFAULT_SOURCE)

    def profile(self, scenery=None, extract=None, texture=None):
        return recover_baked_lighting(extract or self.extract, scenery or self.manifest['scenery'], texture or (lambda p:'/assets/'+p+'.png'))

    def test_all39_instances_bind_from_their_own_tile_with_three_unique_crc_checked_pages(self):
        p = self.profile()
        self.assertEqual(p['format'], FORMAT)
        self.assertEqual(len(p['instances']), 39)
        self.assertEqual(len(p['atlases']), 3)
        self.assertEqual([z['id'] for z in p['zones']], [194, 195, 196, 197, 199])
        self.assertEqual(p['configuration']['modelSlot'], 0)
        self.assertFalse(p['configuration']['observedOriginalDevice'])
        for obj in p['instances']:
            x, z = obj['tile']
            self.assertEqual(obj['recordPath'], f'world/tutorial/lightmap/{x}_{z}.dat')
            self.assertEqual(len(obj['bindings']), 1)
            self.assertEqual(obj['bindings'][0]['ordinal'], 0)
        for atlas in p['atlases']:
            self.assertEqual(atlas['sha256'], hashlib.sha256(self.extract(atlas['sourcePath'])).hexdigest())
            self.assertIn([atlas['width'], atlas['height'], atlas['fileMipLevels']], [[256, 256, 9], [32, 32, 6]])

    def test_missing_required_record_or_atlas_and_failed_conversion_do_not_choose_other_slots(self):
        for missing in ['record', 'atlas', 'shader', 'zones']:
            def changed(path):
                raw = self.extract(path)
                if (missing == 'record' and path.endswith('.dat')): return raw[:-1]
                if (missing == 'atlas' and '/lightmap/' in path and path.endswith('.tga')): return raw[:-1]
                if missing == 'shader' and path.endswith('.glsl'): return raw+b'\n'
                if missing == 'zones' and path.endswith('zones.tbl'): return raw[:-1]
                return raw
            with self.subTest(missing=missing), self.assertRaises(ValueError): self.profile(extract=changed)
        with self.assertRaisesRegex(ValueError, 'conversion failed'): self.profile(texture=lambda p:None)

    def test_instance_tile_selects_its_own_table_even_when_neighbor_repeats_id_and_duplicates_fail(self):
        scenery = copy.deepcopy(self.manifest['scenery'])
        scenery[0]['instances'][0]['tile'] = [-41, 3]
        original = self.profile()['instances'][0]
        neighbor = self.profile(scenery=scenery)['instances'][0]
        self.assertEqual(neighbor['objectId'], original['objectId'])
        self.assertNotEqual(neighbor['recordPath'], original['recordPath'])
        self.assertEqual(neighbor['recordPath'], 'world/tutorial/lightmap/-41_3.dat')
        self.assertNotEqual(neighbor['bindings'][0]['atlas'], original['bindings'][0]['atlas'])
        scenery = copy.deepcopy(self.manifest['scenery'])
        scenery[0]['instances'].append(copy.deepcopy(scenery[0]['instances'][0]))
        with self.assertRaisesRegex(ValueError, 'Ambiguous'): self.profile(scenery=scenery)

    def test_material_profile_accepts_shader_uniform_and_rejects_missing_uv1(self):
        from bdae_convert import BDAE
        import tempfile
        for entry in self.manifest['scenery']:
            data = json.loads((ROOT/'game-data/converted'/entry['url'][8:]).read_text())
            with tempfile.TemporaryDirectory() as tmp:
                source = Path(tmp)/'model.bdae'; source.write_bytes(self.extract(entry['model']))
                p = recover_model_lighting(BDAE(source), data)
                self.assertEqual(len(p['materials']), len(data['materials']))
                self.assertTrue(all(m['uvTransformOrigin'] == 'shader-uniform-under-UV1_TRANSFORM' for m in p['materials']))
                del data['meshes'][0]['sourceUV1']
                with self.assertRaisesRegex(ValueError, 'UV1'): recover_model_lighting(BDAE(source), data)

    def test_png_atlas_channels_keep_decoder_bytes_without_color_profile_or_gamma_chunks(self):
        from PIL import Image
        from texture_decode import decode
        for atlas in self.profile()['atlases']:
            decoded = decode(self.extract(atlas['sourcePath']))
            stream = io.BytesIO(); decoded.save(stream, format='PNG'); stream.seek(0)
            png = Image.open(stream)
            self.assertEqual(png.tobytes(), decoded.tobytes())
            self.assertFalse(set(png.info) & {'gamma', 'srgb', 'icc_profile'})


if __name__ == '__main__': unittest.main()
