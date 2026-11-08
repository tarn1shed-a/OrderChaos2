import random
import unittest
from pathlib import Path

from scene_shader_metadata import (FORMAT, ROUTINES, CONSTANTS, map_fixture, shader_word,
                                    manifest_inventory, analyze_metadata, verify_native)

NATIVE = Path(__file__).resolve().parents[1]/'analysis/raw/beff-native/library.so'


class ShaderMetadataTests(unittest.TestCase):
    def test_map_model_uses_character_comparison_and_records_pointer_offsets(self):
        self.assertEqual(map_fixture(b';0;2;sky\nshader;X;0;other\r\n'), [
            {'key': 'sky', 'alias': None, 'keyOffset': 5, 'firstFlag': 0, 'discardFlag': 1},
            {'key': 'other', 'alias': 'shader', 'keyOffset': 20, 'firstFlag': 1, 'discardFlag': 0}])
        self.assertEqual(map_fixture(b''), [])
        for data in [b'x;0;1;key', b'x;00;1;k\n', b'x;0;1;\n', b'x;0;1;k\0\n',
                     b'x;0;1;k\r', b'x;0;1;k;extra\n', b'x;0;1;\xff\n', b';0;1;k\n'*9]:
            with self.assertRaises(ValueError): map_fixture(data)

    def test_constructor_model_uses_flag_low_bit_and_separate_compile_fixture(self):
        self.assertEqual(shader_word(1, 2), 1)
        self.assertEqual(shader_word(2, 0xffffffff, True), 26)
        self.assertEqual(shader_word(0, 0x80000000, True), 8)
        for args in [(3, 0), (True, 0), (1, True), (1, -1), (1, 1 << 32), (1, 0, 1)]:
            with self.assertRaises(ValueError): shader_word(*args)

    def test_manifest_inventory_cannot_claim_runtime_mount_or_find_similar_names(self):
        self.assertEqual(manifest_inventory(['a/file.map', 'b\\FILE.MAP', 'a/file.map.bak', 'filemaps', 'x.map']),
                         ['a/file.map', 'b\\FILE.MAP'])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_complete_original_manifest_parser_matches_bounded_independent_model(self):
        from analyze_native_resources import NativeImage
        from native_shader_metadata_probe import NativeShaderMetadataProbe
        p = NativeShaderMetadataProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x141cf60)
        for i in range(64):
            data = b''.join((f'{"alias"+str(n) if n & 1 else ""};{rng.choice("012X")};{rng.choice("012X")};key{n}'
                            +rng.choice(['\n', '\r\n'])).encode() for n in range(i % 9))
            actual = p.parse_map(data)
            self.assertEqual([{k: row[k] for k in map_fixture(data)[j]} for j, row in enumerate(actual['records'])], map_fixture(data))
            self.assertEqual(actual['loadedByte'], 1); self.assertEqual(actual['streamReferences'], 99)
            self.assertEqual(actual['path'], 'fixture-shaders/file.map')
            self.assertEqual(actual['callbacks'], [0, 1, 2, 3, 4])
            self.assertEqual(actual['buffer'][-1], 0)
            for row in actual['records']:
                self.assertEqual(actual['buffer'][row['keyOffset']-4], row['firstFlag'])
                self.assertEqual(actual['buffer'][row['keyOffset']-2], row['discardFlag'])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_complete_original_shader_constructor_preserves_explicit_metadata_despite_source_tokens(self):
        from analyze_native_resources import NativeImage
        from native_shader_metadata_probe import NativeShaderMetadataProbe
        p = NativeShaderMetadataProbe(NativeImage(NATIVE.read_bytes()))
        for stage in range(3):
            for flag in (0, 1, 2, 3, 0x80000000, 0xffffffff):
                for compile_word in (0, 1, 2, 3):
                    for sources in [[], ['discard;'], ['prefix', 'plain', 'suffix']]:
                        handle = 91 if flag & 2 else 0
                        result = p.construct_shader(stage, flag, sources, compile_word, handle)
                        self.assertEqual(result['word18'], shader_word(stage, flag, bool(compile_word & 1)))
                        self.assertEqual(result['vptr'], 0x2496a48); self.assertEqual(result['references'], 0)
                        self.assertEqual(result['name'], 'fixture-shader'); self.assertEqual(result['handle'], handle)
                        self.assertEqual(result['cacheStatus'], 0xffff); self.assertEqual(result['cachedBeforeCompile'], 0)
                        self.assertEqual(result['events'], [['createShader', [0x8b31, 0x8b30, 0x91b9][stage]],
                                                           ['source', len(sources), sources], ['compileShader', compile_word]])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_factory_reads_normalized_parser_bytes_without_reconstructed_headers(self):
        from analyze_native_resources import NativeImage
        from native_shader_metadata_probe import NativeShaderMetadataProbe
        p = NativeShaderMetadataProbe(NativeImage(NATIVE.read_bytes()))
        # 32 maps,128 parsed-record consumers,32 absent descriptors and32 preprocessing failures.
        for i in range(32):
            data = b''.join(f'a;{a};{b};key{n}\n'.encode() for n, (a, b) in enumerate(
                [('0', '0'), ('0', 'X'), ('2', '0'), ('1', '1')]))
            parsed = p.parse_map(data); before = parsed['buffer']
            for n, row in enumerate(map_fixture(data)):
                actual = p.factory_from_map(n, i % 3)
                self.assertEqual(actual['output'], p.EXT+0x8000); self.assertEqual(actual['status'], 0)
                self.assertEqual(actual['preprocessInputs'], [1-row['firstFlag']])
                self.assertEqual(actual['allocations'], [48]); self.assertEqual(actual['shader']['references'], 1)
                self.assertEqual(actual['shader']['word18'], shader_word(i % 3, row['discardFlag'], True))
            absent = p.factory_from_map(None)
            self.assertEqual(absent['shader']['word18'], 9); self.assertEqual(absent['preprocessInputs'], [1])
            failed = p.factory_from_map(i % 4, preprocess_ok=False)
            self.assertEqual(failed, {'output': 0, 'status': 8, 'preprocessInputs': [1-map_fixture(data)[i % 4]['firstFlag']],
                                      'allocations': [], 'shader': None})
            self.assertEqual(bytes(p.uc.mem_read(p.EXT+0x10000, len(data)+1)), before)
        for value in [-1, True, 4]:
            with self.assertRaises(ValueError): p.factory_from_map(value)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_new_native_code_and_constants_fail_closed_when_changed(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in [*ROUTINES, *CONSTANTS]:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        image.read = read; self.assertEqual(verify_native(image)['routines'], 9)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_report_separates_recovered_metadata_write_from_missing_active_manifest_and_preprocessing(self):
        from analyze_native_resources import NativeImage
        report = analyze_metadata(NativeImage(NATIVE.read_bytes()))
        self.assertEqual(report['format'], FORMAT); self.assertTrue(report['shaderFlagWriteRecovered'])
        self.assertFalse(report['activeSkyDiscardRecovered']); self.assertFalse(report['appliedAsLiveState'])
        self.assertFalse(report['preprocessedSkySourceRecovered'])
        self.assertEqual(report['consumer']['GLTable'], [0x8b31, 0x8b30, 0x91b9])
        self.assertIn('148c160 preprocessing/injection', report['executionScope']['staticOnly'])


if __name__ == '__main__': unittest.main()
