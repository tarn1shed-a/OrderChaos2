import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from bdae_convert import BDAE
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from scene_render_state import (CULL_FACES, FRONT_FACES, SHADERS, analyze,
                                effect_render_state, read_pass_state, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def reader(raw):
    result = BDAE.__new__(BDAE)
    result.b, result.info = raw, 0
    return result


def fixture():
    """Self-made two-profile fixture; no game bytes or original shader code."""
    raw = bytearray(4096)
    strings = {}
    cursor = 1400

    def string(text):
        nonlocal cursor
        if text not in strings:
            strings[text] = cursor
            encoded = text.encode()+b'\0'
            raw[cursor:cursor+len(encoded)] = encoded
            cursor += len(encoded)
        return strings[text]

    struct.pack_into('<Ii', raw, 164, 1, 256-168)
    struct.pack_into('<Q', raw, 256, string('synthetic-fx'))
    struct.pack_into('<2i', raw, 288, 400-288, 432-292)
    for index, (profile, technique, source_pass) in enumerate(((400, 512, 640), (432, 544, 848))):
        struct.pack_into('<Ii', raw, profile, 1, technique-(profile+4))
        struct.pack_into('<QIi', raw, technique, string('tech'), 1, source_pass-(technique+12))
        for stage, file in enumerate(('synthetic.vs', 'synthetic.fs')):
            at = source_pass + stage*24
            macros = 1100 + (index*2+stage)*32
            struct.pack_into('<2QIi', raw, at, string(file), string('entry'+str(index)), 2, macros-(at+20))
            struct.pack_into('<4Q', raw, macros, string('FEATURE'), string(''), string('COUNT'), string('2'))
        # Profile 0 back/CCW/LEQUAL; profile 1 front/CW/LESS. Keep distinct.
        flags = (1<<20) | (1<<22) | (1<<23) | ((3 if index == 0 else 1)<<12) | (index<<21)
        struct.pack_into('<2I', raw, source_pass+80, index<<30, flags)
    return raw


class SceneRenderStateTests(unittest.TestCase):
    def test_state_bits_have_independent_meanings_and_gl_table_values(self):
        raw = bytearray(88)
        self.assertEqual(read_pass_state(reader(raw), 0), {
            'blendEnabled': False, 'cullEnabled': False, 'cullFaceGL': 0x405,
            'frontFaceGLBeforeTargetXor': 0x901, 'depthTestEnabled': False,
            'depthWriteEnabled': False, 'depthFunctionGL': 0x200})
        for bit, field in ((19, 'blendEnabled'), (20, 'cullEnabled'),
                           (22, 'depthTestEnabled'), (23, 'depthWriteEnabled')):
            struct.pack_into('<I', raw, 12, 1<<bit)
            state = read_pass_state(reader(raw), 0)
            self.assertEqual([key for key, value in state.items() if isinstance(value, bool) and value], [field])
        for mode, gl in enumerate(CULL_FACES):
            struct.pack_into('<2I', raw, 8, mode<<30, 1<<21)
            state = read_pass_state(reader(raw), 0)
            self.assertEqual(state['cullFaceGL'], gl)
            self.assertEqual(state['frontFaceGLBeforeTargetXor'], FRONT_FACES[1])
        for compare in range(8):
            struct.pack_into('<2I', raw, 8, 0, compare<<12)
            self.assertEqual(read_pass_state(reader(raw), 0)['depthFunctionGL'], 0x200+compare)

    def test_state_rejects_unsupported_cull_index_and_truncation(self):
        raw = bytearray(88)
        struct.pack_into('<I', raw, 8, 3<<30)
        with self.assertRaisesRegex(ValueError, 'cull mode'):
            read_pass_state(reader(raw), 0)
        for data, offset in ((bytes(87), 0), (bytes(88), -1), (bytes(88), 1)):
            with self.assertRaises(ValueError):
                read_pass_state(reader(data), offset)

    def test_profiles_and_shader_defines_are_kept_separate_without_applying(self):
        result = effect_render_state(reader(fixture()))
        self.assertFalse(result['appliedAsLiveState'])
        self.assertEqual(result['effectName'], 'synthetic-fx')
        self.assertEqual([p['sourcePointerField'] for p in result['profiles']], [32, 36])
        first, second = result['profiles']
        self.assertEqual(first['vertexShader']['defines'], {'FEATURE': '', 'COUNT': '2'})
        self.assertEqual(first['fragmentShader']['file'], 'synthetic.fs')
        self.assertEqual(second['vertexShader']['entry'], 'entry1')
        self.assertEqual(first['state']['cullFaceGL'], 0x405)
        self.assertEqual(second['state']['cullFaceGL'], 0x404)
        self.assertEqual(first['state']['depthFunctionGL'], 0x203)
        self.assertEqual(second['state']['depthFunctionGL'], 0x201)

    def test_unknown_counts_and_out_of_buffer_pointers_are_rejected(self):
        for offset, value in ((164, 2), (400, 2), (520, 2), (656, 65),
                              (288, 4096), (404, 4096), (524, 4096), (660, 4096)):
            with self.subTest(offset=offset):
                raw = fixture()
                struct.pack_into('<I', raw, offset, value)
                with self.assertRaises(ValueError):
                    effect_render_state(reader(raw))
        raw = fixture()
        # Move only the second pass record out of bounds; the other pointers
        # and strings remain valid, isolating the complete-record check.
        struct.pack_into('<i', raw, 556, 3889-556)
        with self.assertRaises(ValueError):
            effect_render_state(reader(raw))

    def test_duplicate_empty_and_invalid_define_strings_are_rejected(self):
        for replacement in (None, b''):
            raw = fixture()
            if replacement is None:
                raw[1116:1124] = raw[1100:1108]
            else:
                struct.pack_into('<Q', raw, 1100, 4095)
            with self.assertRaises(ValueError):
                effect_render_state(reader(raw))
        raw = fixture()
        struct.pack_into('<Q', raw, 1108, 5000)
        with self.assertRaises(ValueError):
            effect_render_state(reader(raw))

    def test_changed_native_code_is_rejected(self):
        class Changed:
            def read(self, address, size):
                return bytes(size)
        with self.assertRaisesRegex(ValueError, 'retrace'):
            verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file(), 'Original native library stays local')
    def test_native_converter_gl_consumers_tables_and_target_xor(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual((result['routineCount'], result['glTableCount']), (8, 3))
        self.assertTrue(result['frontFaceTargetXorVerified'])
        self.assertFalse(result['appliedAsLiveState'])
        class Changed:
            def read(self, address, size):
                return bytes(size) if address == 0x1f41958 else image.read(address, size)
        with self.assertRaisesRegex(ValueError, 'GL state table'):
            verify_native(Changed())

    @unittest.skipUnless((DEFAULT_SOURCE/'res.bin').is_file(), 'Original effects stay local')
    def test_original_profiles_distinguish_culling_and_cutout_from_blending(self):
        archive = ResourceArchive(DEFAULT_SOURCE/'res.bin')
        from scene_texture_sampling import EFFECTS
        with tempfile.TemporaryDirectory() as temp:
            for name, digest in EFFECTS.items():
                path = Path(temp)/'effect.bdae'
                path.write_bytes(archive.read(name))
                original = BDAE(path)
                self.assertEqual(hashlib.sha256(original.b).hexdigest(), digest)
                result = effect_render_state(original)
                self.assertEqual([p['vertexShader']['entry'] for p in result['profiles']], ['main', 'VS'])
                self.assertEqual([p['fragmentShader']['entry'] for p in result['profiles']], ['main', 'FS'])
                for profile in result['profiles']:
                    state = profile['state']
                    self.assertEqual(state['cullEnabled'], name == 'ut_cull_lightmap_solid.bdae')
                    self.assertFalse(state['blendEnabled'])
                    self.assertEqual(state['cullFaceGL'], 0x405)
                    self.assertEqual(state['frontFaceGLBeforeTargetXor'], 0x901)
                    self.assertEqual(state['depthFunctionGL'], 0x203)
                    self.assertTrue(state['depthTestEnabled'] and state['depthWriteEnabled'])
                    for stage in ('vertexShader', 'fragmentShader'):
                        macros = profile[stage]['defines']
                        self.assertEqual('ALPHA_TEST' in macros, name == 'ut_lightmap_trans.bdae')
                        self.assertEqual(macros['LIGHTMAP'], '')

    @unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'res.bin').is_file(), 'Original evidence stays local')
    def test_audit_checks_source_shaders_and_effect_fingerprints(self):
        from analyze_native_resources import NativeImage
        image, archive = NativeImage(NATIVE.read_bytes()), ResourceArchive(DEFAULT_SOURCE/'res.bin')
        result = analyze(archive, image)
        self.assertEqual(len(result['effects']), 3)
        self.assertFalse(result['appliedAsLiveState'])
        self.assertEqual(result['conditionalShaderRule'], {
            'define': 'ALPHA_TEST', 'reference': 0.5, 'discardComparison': 'less-than-or-equal'})
        for path in SHADERS:
            class Changed:
                def read(self, name):
                    value = archive.read(name)
                    return value+b'\n' if name == path else value
            with self.assertRaisesRegex(ValueError, 'shader changed'):
                analyze(Changed(), image)
        class ChangedFX:
            def read(self, name):
                value = archive.read(name)
                if name == 'ut_lightmap_trans.bdae':
                    with tempfile.TemporaryDirectory() as temp:
                        target = Path(temp)/'effect.bdae'
                        target.write_bytes(value)
                        original = BDAE(target)
                        raw = bytearray(original.b)
                        _, fx = original.section(164)
                        profile = original.rel(fx+32)
                        technique = original.rel(profile+4)
                        source_pass = original.rel(technique+12)
                        raw[source_pass+84] ^= 1
                        return bytes(raw)
                return value
        with self.assertRaisesRegex(ValueError, 'FX changed'):
            analyze(ChangedFX(), image)


if __name__ == '__main__':
    unittest.main()
