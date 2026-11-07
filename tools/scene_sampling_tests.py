import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from bdae_convert import BDAE
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_sampling import (FIELDS, LOADER_VPTRS, read_sampler_2d,
                            material_samplers, effect_profile_samplers, verify_native)

ROOT = Path(__file__).resolve().parents[1]


def raw_reader(raw):
    # Format entry/header validation is tested in bdae_tests; these fixtures
    # exercise bounded pointer/property reads with unequal sampler values.
    reader = BDAE.__new__(BDAE)
    reader.b = raw
    reader.info = 0
    return reader


def material_fixture():
    raw = bytearray(800)
    struct.pack_into('<Ii', raw, 148, 1, 512 - 152)
    struct.pack_into('<Ii', raw, 172, 1, 256 - 176)
    struct.pack_into('<3Q', raw, 256, 700, 710, 730)
    struct.pack_into('<Ii', raw, 256 + 32, 1, 400 - (256 + 36))
    struct.pack_into('<2Q4I', raw, 400, 680, 680, 17, 1, 600 - 424, 608 - 428)
    struct.pack_into('<Q', raw, 512 + 16, 750)
    struct.pack_into('<2I', raw, 600, 1, 0)
    struct.pack_into('<i4I', raw, 608, 512 - 608, 255, 255, 255, 255)
    for at, text in [(680, b'texture'), (700, b'mat'), (710, b'effect.bdae'),
                     (730, b'#effect-fx'), (750, b'texture/source.tga')]:
        raw[at:at + len(text) + 1] = text + b'\0'
    return raw


def effect_fixture():
    raw = bytearray(800)
    struct.pack_into('<Ii', raw, 164, 1, 256 - 168)
    struct.pack_into('<Q', raw, 256, 700)
    struct.pack_into('<2i', raw, 288, 400 - 288, 448 - 292)
    for profile, prop, state, value in [(400, 512, 600, 608), (448, 544, 632, 640)]:
        struct.pack_into('<Ii', raw, profile + 8, 1, prop - (profile + 12))
        struct.pack_into('<Q5I', raw, prop, 730, 17, 2, 1, state - (prop + 20), value - (prop + 24))
        struct.pack_into('<2I', raw, state, 1, 0)
        struct.pack_into('<5I', raw, value, 0, 0, 0, 255, 255)
    raw[700:710] = b'effect-fx\0'
    raw[730:738] = b'texture\0'
    return raw


class SceneSamplingTests(unittest.TestCase):
    def test_ff_skips_setter_and_zero_remains_an_explicit_request(self):
        reader = raw_reader(struct.pack('<i4I', 0, 255, 0, 4, 1))
        self.assertEqual(read_sampler_2d(reader, 0), dict(zip(FIELDS, (None, 0, 4, 1))))
        self.assertEqual(read_sampler_2d(raw_reader(struct.pack('<5I', 0, 4, 2, 0, 0)), 0),
                         dict(zip(FIELDS, (4, 2, 0, 0))))

    def test_unrecognized_or_truncated_sampler_requests_are_rejected(self):
        for words in [(0, 5, 0, 0, 0), (0, 0, 256, 0, 0), (0, 0, 0, 6, 0),
                      (0, 0, 0, 0, 0xffffffff)]:
            with self.assertRaises(ValueError):
                read_sampler_2d(raw_reader(struct.pack('<5I', *words)), 0)
        with self.assertRaises(ValueError):
            read_sampler_2d(raw_reader(bytes(19)), 0)
        with self.assertRaises(ValueError):
            read_sampler_2d(raw_reader(bytes(20)), -4)

    def test_material_requests_resolve_exact_texture_and_preserve_inheritance(self):
        result = material_samplers(raw_reader(material_fixture()))[0]
        self.assertEqual(result['material'], 'mat')
        self.assertEqual(result['samplers']['texture'],
                         {'texture': 'texture/source.tga', 'request': dict.fromkeys(FIELDS)})

    def test_material_wrong_count_state_and_texture_record_are_rejected(self):
        for at, value in [(420, 2), (600, 0), (604, 1), (608, 513 - 608), (288, 257)]:
            raw = material_fixture()
            struct.pack_into('<i', raw, at, value)
            with self.assertRaises(ValueError):
                material_samplers(raw_reader(raw))
        raw = material_fixture()
        struct.pack_into('<I', raw, 288, 2)
        raw[432:464] = raw[400:432]
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            material_samplers(raw_reader(raw))

    def test_changed_native_code_is_not_accepted_as_sampler_evidence(self):
        class Changed:
            def read(self, address, size): return bytes(size)
        with self.assertRaisesRegex(ValueError, 'retrace'):
            verify_native(Changed())

    def test_fx_profile_pointers_null_defaults_and_unsupported_states(self):
        result = effect_profile_samplers(raw_reader(effect_fixture()))
        self.assertEqual(len(result['profiles']), 2)
        self.assertEqual(result['profiles'][0]['samplers']['texture']['request'],
                         dict(zip(FIELDS, (0, 0, None, None))))
        for at, value in [(164, 2), (408, 65), (520, 18), (528, 2), (600, 0), (608, 4), (288, 800)]:
            raw = effect_fixture()
            struct.pack_into('<I', raw, at, value)
            with self.assertRaises(ValueError):
                effect_profile_samplers(raw_reader(raw))

    @unittest.skipUnless((ROOT/'analysis/raw/beff-native/library.so').is_file(), 'Original native library stays local')
    def test_real_native_setters_type_mask_and_noop_loader_hooks(self):
        from analyze_native_resources import NativeImage
        image = NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())
        result = verify_native(image)
        self.assertEqual(result['checkedLoaderHooks'], len(LOADER_VPTRS))
        self.assertFalse(result['appliedAsActiveSamplerState'])
        class ChangedRelocations:
            def iter_relocations(self):
                for row in image.elf.get_section_by_name('.rela.dyn').iter_relocations():
                    yield {'r_offset': row['r_offset'], 'r_addend': 0 if row['r_offset'] == LOADER_VPTRS[0] + 0x48 else row['r_addend']}
        class ChangedELF:
            def get_section_by_name(self, name): return ChangedRelocations()
        class ChangedHook:
            elf = ChangedELF()
            read = image.read
        with self.assertRaisesRegex(ValueError, 'loader hook changed'):
            verify_native(ChangedHook())

    @unittest.skipUnless((DEFAULT_SOURCE/'res_scene_generator_temple_000.bin').is_file(), 'Original scene assets stay local')
    def test_original_scene_materials_skip_all_four_sampler_setters(self):
        archive = ResourceArchive(DEFAULT_SOURCE/'res_scene_generator_temple_000.bin')
        with tempfile.TemporaryDirectory() as temp:
            for name in ('god_wall_03', 'god_temple04', 'god_bridge_step01'):
                path = Path(temp)/(name + '.bdae')
                path.write_bytes(archive.read('model/scene_generator_temple_000/' + name + '.bdae'))
                materials = material_samplers(BDAE(path))
                self.assertTrue(materials)
                for material in materials:
                    self.assertEqual(set(material['samplers']), {'texture', 'lightMap'})
                    for sampler in material['samplers'].values():
                        self.assertEqual(sampler['request'], dict.fromkeys(FIELDS))

    @unittest.skipUnless((DEFAULT_SOURCE/'res.bin').is_file(), 'Original effect assets stay local')
    def test_original_fx_profiles_keep_defaults_separate_from_material_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'effect.bdae'
            path.write_bytes(ResourceArchive(DEFAULT_SOURCE/'res.bin').read('ut_cull_lightmap_solid.bdae'))
            reader = BDAE(path)
            self.assertEqual(hashlib.sha256(reader.b).hexdigest(),
                             '61556eb0430899ddf7588a1e63d2a39237a0d7c13b023b9c48bd394eb2340026')
            result = effect_profile_samplers(reader)
            self.assertEqual(result['effectName'], 'ut_cull_lightmap_solid-fx')
            self.assertEqual([p['sourcePointerField'] for p in result['profiles']], [32, 36])
            for profile in result['profiles']:
                self.assertEqual(set(profile['samplers']), {'texture', 'lightMap'})
                for sampler in profile['samplers'].values():
                    self.assertEqual(sampler, {'texture': None, 'request': dict(zip(FIELDS, (0, 0, None, None)))})
            self.assertFalse(result['appliedAsActiveSamplerState'])
            # Do not silently treat a real default texture as the null case.
            raw = bytearray(reader.b)
            count, effects = reader.section(164)
            profile = reader.rel(effects + 32)
            parameters = reader.rel(profile + 12)
            value = reader.rel(parameters + 24)
            struct.pack_into('<I', raw, value, 4)
            reader.b = raw
            with self.assertRaisesRegex(ValueError, 'default texture'):
                effect_profile_samplers(reader)

    @unittest.skipUnless((DEFAULT_SOURCE/'res.bin').is_file(), 'Original effect assets stay local')
    def test_other_scene_fx_profiles_have_same_sampler_requests(self):
        fingerprints = {
            'ut_lightmap_solid': 'b0a169c06aef00e817f77ad965696d1f42e7d445879e27b6036de0e36bfadb72',
            'ut_lightmap_trans': '4f440961fa2cd78dddec5f2a1fc40f3839168ec66112e99f88161f2288f98817',
        }
        archive = ResourceArchive(DEFAULT_SOURCE/'res.bin')
        with tempfile.TemporaryDirectory() as temp:
            for name, digest in fingerprints.items():
                path = Path(temp)/'effect.bdae'
                path.write_bytes(archive.read(name + '.bdae'))
                reader = BDAE(path)
                self.assertEqual(hashlib.sha256(reader.b).hexdigest(), digest)
                result = effect_profile_samplers(reader)
                self.assertEqual(result['effectName'], name + '-fx')
                for profile in result['profiles']:
                    self.assertEqual(set(profile['samplers']), {'texture', 'lightMap'})
                    self.assertTrue(all(s['request'] == dict(zip(FIELDS, (0, 0, None, None)))
                                        for s in profile['samplers'].values()))


if __name__ == '__main__':
    unittest.main()
