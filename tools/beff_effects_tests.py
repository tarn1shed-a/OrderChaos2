import struct
import unittest

from beff_effects import decode_effect, EFFECT_SOURCES
from resource_packs import ResourceArchive, DEFAULT_SOURCE


def sample(names=('fire.tga', '.'), duration=766):
    data = bytearray(52)
    struct.pack_into('<4sI', data, 0, b'beff', 9)
    struct.pack_into('<I', data, 24, duration)
    struct.pack_into('<I', data, 48, len(names))
    for name in names:
        string = name.encode() + b'\0'
        string += b'\0' * (-len(string) % 4)
        data.extend(struct.pack('<I', len(string)))
        data.extend(string)
    data.extend(b'opaque-emitter-data')
    return data


class EffectTests(unittest.TestCase):
    def test_recover_finite_and_unbounded_lifetime_and_safe_dependencies(self):
        result = decode_effect(sample())
        self.assertEqual(result['durationMs'], 766)
        self.assertFalse(result['loop'])
        self.assertEqual(result['textures'], ['texture/fire.tga'])
        self.assertEqual(len(result['sourceSHA256']), 64)
        result = decode_effect(sample(duration=0xffffffff))
        self.assertIsNone(result['durationMs'])
        self.assertTrue(result['loop'])

    def test_reject_bad_version_extents_terminators_and_path_escape(self):
        broken = sample()
        struct.pack_into('<I', broken, 4, 10)
        with self.assertRaises(ValueError): decode_effect(broken)
        broken = sample()
        struct.pack_into('<I', broken, 52, 0xfffffff0)
        with self.assertRaises(ValueError): decode_effect(broken)
        broken = sample()
        broken[56:68] = b'no-terminatr'
        with self.assertRaises(ValueError): decode_effect(broken)
        for names in [('file.bdae', '.'), ('../fire.tga', '.'), ('fire\\bad.tga', '.'), ('a.tga',), ('a.tga', '.', '.')]:
            with self.subTest(names=names):
                with self.assertRaises(ValueError): decode_effect(sample(names))
        with self.assertRaises(ValueError): decode_effect(b'beff')
        with self.assertRaises(ValueError): decode_effect(sample()[:56])

    @unittest.skipUnless((DEFAULT_SOURCE / 'res.bin').is_file(), 'Original effect archive is local-only')
    def test_original_selected_dependencies_and_lifetimes(self):
        archive = ResourceArchive(DEFAULT_SOURCE / 'res.bin')
        expected = {
            'fireCast': (None, ['fire_015.tga', 'jpg_6755.tga', 'fx_sun.tga']),
            'fireMissile': (None, ['blur_a.tga', '2590977160622662525.tga', 'jpg_s_fire012e.tga']),
            'fireHit': (766, ['fx_stick.tga', 'fire03_xulie4x4.tga']),
            'frostHit': (633, ['ray045.tga', 'quan_02.tga', 'fx_iceblock01.tga', 'ice06.tga']),
        }
        textures = ResourceArchive(DEFAULT_SOURCE / 'res_t.bin')
        for key, (duration, dependencies) in expected.items():
            with self.subTest(effect=key):
                result = decode_effect(archive.read(EFFECT_SOURCES[key]))
                self.assertEqual(result['durationMs'], duration)
                self.assertEqual(result['textures'], ['texture/' + name for name in dependencies])
                for path in result['textures']:
                    self.assertGreater(len(textures.read(path)), 52)


if __name__ == '__main__':
    unittest.main()
