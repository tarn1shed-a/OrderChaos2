import struct
import tempfile
import unittest
from pathlib import Path

from bdae_convert import BDAE
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_alpha import ROUTINES, material_techniques, recover_scene_alpha, texture_alpha, verify_native

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def fixture():
    raw = bytearray(1200)
    struct.pack_into('<Ii', raw, 172, 1, 256-176)
    struct.pack_into('<Q', raw, 272, 800)
    struct.pack_into('<Ii', raw, 288, 3, 400-292)
    for index, (name, kind) in enumerate(((820, 17), (840, 17), (860, 28))):
        prop = 400+index*32
        struct.pack_into('<2QIIii', raw, prop, name, name, kind, 1, 600-(prop+24), 640-(prop+28))
    struct.pack_into('<2I', raw, 600, 1, 0)
    struct.pack_into('<2IQ', raw, 640, 2, 0, 950)
    for at, value in ((800, '#synthetic-fx'), (820, 'texture'), (840, 'lightMap'),
                       (860, 'synthetic-fx-profile_GLES2/CurrentTechnique'), (950, 'tech0')):
        raw[at:at+len(value)+1] = value.encode()+b'\0'
    result = BDAE.__new__(BDAE)
    result.b, result.info = raw, 0
    return result


class SceneAlphaTests(unittest.TestCase):
    def test_technique_name_is_a_pointer_at_plus_eight_not_the_first_integer(self):
        result = material_techniques(fixture())
        self.assertEqual(result[0]['name'], 'tech0')
        self.assertEqual(result[0]['valueWord0'], 2)
        self.assertNotIn('ordinal', result[0])

    def test_extra_arguments_bad_types_counts_states_and_name_pointers_are_rejected(self):
        for at, fmt, value in ((280, 'Q', 1), (288, 'I', 4), (480, 'I', 27), (484, 'I', 2),
                               (600, 'I', 0), (640, 'I', 0), (648, 'Q', 2000), (292, 'i', 2000)):
            with self.subTest(offset=at):
                reader = fixture()
                struct.pack_into('<'+fmt, reader.b, at, value)
                with self.assertRaises(ValueError):
                    material_techniques(reader)
        reader = fixture()
        reader.b[950:956] = b'tech1\0'
        self.assertEqual(material_techniques(reader)[0]['name'], 'tech1','Name resolution is kept separate from effect selection')

    def test_duplicate_and_unknown_properties_do_not_silently_disable_alpha(self):
        for at, pointer in ((432, 820), (464, 840), (464, 950)):
            reader = fixture()
            struct.pack_into('<Q', reader.b, at, pointer)
            with self.assertRaises(ValueError):
                material_techniques(reader)

    def test_changed_native_technique_loader_is_rejected(self):
        class Changed:
            def read(self, address, size):
                return bytes(size)
        with self.assertRaises(ValueError):
            verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file(), 'Original native library stays local')
    def test_native_technique_name_resolution_and_source_loader_hooks(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual(result['bindingRoutineCount'], 10)
        self.assertEqual(result['checkedLoaderHooks'], 8)
        self.assertTrue(result['splitAlphaMacroDefaultEnabled'])
        self.assertFalse(result['cullingApplied'])
        class ChangedMacro:
            elf = image.elf
            def read(self, address, size):
                return bytes(size) if address == 0x1e17569 else image.read(address, size)
        with self.assertRaisesRegex(ValueError, 'split alpha macro changed'):
            verify_native(ChangedMacro())
        for changed in ROUTINES:
            with self.subTest(native=hex(changed)):
                class ChangedBinding:
                    elf = image.elf
                    def read(self, address, size):
                        return bytes(size) if address == changed else image.read(address, size)
                with self.assertRaisesRegex(ValueError, 'binding changed'):
                    verify_native(ChangedBinding())

    @unittest.skipUnless((DEFAULT_SOURCE/'res.bin').is_file(), 'Original scene evidence stays local')
    def test_original_scene_passes_resolve_tech0_and_tree_split_red_alpha(self):
        archives = {name: ResourceArchive(DEFAULT_SOURCE/(name+'.bin')) for name in
                    ('res', 'res_t', 'res_scene_generator_temple_000', 'res_scene')}
        def extract(path):
            pack = 'res_t' if path.startswith('texture/') else 'res_scene_generator_temple_000' if path.startswith('model/scene_generator_') else 'res_scene' if path.startswith('model/') else 'res'
            return archives[pack].read(path)
        with tempfile.TemporaryDirectory() as temp:
            for source, expected_rule in (('model/scene_generator_temple_000/god_wall_03.bdae', 'none'),
                                          ('model/scene/region_whisper_island/wp_plant_small_tree006.bdae', 'discard-less-equal')):
                target = Path(temp)/'source.bdae'
                target.write_bytes(extract(source))
                reader = BDAE(target)
                data = reader.parse()
                profile = recover_scene_alpha(extract, reader, data)
                self.assertEqual(profile['format'], 'oc2-scene-alpha-v1')
                for entry in profile['materials']:
                    self.assertEqual(entry['rule'], expected_rule)
                    self.assertEqual(entry['sourceTechnique']['name'], 'tech0')
                    self.assertEqual(entry['resolvedTechniqueIndex'], 0)
                    self.assertEqual(entry['sourceAlpha']['mode'], 'split-red' if expected_rule != 'none' else 'opaque-ETC1')
                data['materials'][0]['diffuse'] = 'texture/wrong.tga'
                with self.assertRaises(ValueError):
                    recover_scene_alpha(extract, reader, data)
            encoded = extract('texture/hum_city_big_tree01.tga')
            alpha = texture_alpha(encoded)
            self.assertEqual((alpha['width'], alpha['height']), (256, 256))
            with self.assertRaises(ValueError):
                texture_alpha(encoded[:-10])

    @unittest.skipUnless((DEFAULT_SOURCE/'res.bin').is_file(), 'Original scene evidence stays local')
    def test_changed_shader_or_fallback_cannot_use_the_recorded_cutout_rule(self):
        archive, textures = ResourceArchive(DEFAULT_SOURCE/'res.bin'), ResourceArchive(DEFAULT_SOURCE/'res_t.bin')
        for changed in ('ut_common_fs.glsl', 'texture/shaderalpha.tga'):
            def extract(path):
                raw = textures.read(path) if path.startswith('texture/') else archive.read(path)
                return raw+b'\n' if path == changed else raw
            with self.assertRaisesRegex(ValueError, 'changed'):
                recover_scene_alpha(extract, None, None)


if __name__ == '__main__':
    unittest.main()
