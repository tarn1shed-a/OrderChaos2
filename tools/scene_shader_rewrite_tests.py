import random
import unittest
from pathlib import Path

from scene_shader_rewrite import (FORMAT, ROUTINES, TABLES, PROPERTY_SOURCE, property_spans,
                                  fsm_step, discover_tokens, validate_machine, machine,
                                  expected_rewrite, rewrite_sources, verify_native, analyze_rewrite)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class ShaderRewriteTests(unittest.TestCase):
    def test_circular_sibling_fsm_model_and_guard_against_nonreturning_cycles(self):
        chars = bytearray(256); chars[65] = 1; chars[66] = 2
        toy = (bytes(chars), bytes([1, 0, 2]), bytes([1, 3, 1]), bytes([2, 1, 0]))
        validate_machine(toy)
        self.assertEqual(fsm_step(toy, 0, 66), (1, None))
        self.assertEqual(fsm_step(toy, 1, 32), (0, 1))
        self.assertEqual(discover_tokens(toy), {1: 'A'})
        sibling_terminal = (toy[0], toy[1], bytes([1, 3, 3]), toy[3])
        self.assertEqual(fsm_step(sibling_terminal, 0, 66), (0, 0))
        bad = (*toy[:3], bytes([2, 1, 2]))
        with self.assertRaises(ValueError): fsm_step(bad, 0, 67)
        for tables in [(), (b'', b'a', b'\0', b'\0'), (bytes(chars), b'a', b'\2', b'\0')]:
            with self.assertRaises(ValueError): validate_machine(tables)

    def test_property_model_preserves_byte_ranges_and_orders_semantic_before_texcoord(self):
        source = b'XGLITCH_UNIFORM_PROPERTIES(tex, (texcoord = UV, semantic = Color))\n'
        records = property_spans(source)
        self.assertEqual(records, [{'start': 1, 'end': len(source)-1,
                                    'text': b'#define tex tex_glitchprops_semColor_tcUV', 'owned': 1}])
        self.assertEqual(len(property_spans(b'// '+source+b'"GLITCH_ATTRIBUTE_PROPERTIES(v,(semantic=Position))"')), 2)
        for bad in [b'GLITCH_IN_BLOCK(T,x)', b'GLITCH_UNIFORM_PROPERTIES(x,())',
                    b'GLITCH_UNIFORM_PROPERTIES(x,(semantic=X,semantic=Y))',
                    b'GLITCH_UNIFORM_PROPERTIES(x,(id=2))',
                    b'GLITCH_ATTRIBUTE_PROPERTIES(x,(texcoord=UV))',
                    b'GLITCH_UNIFORM_PROPERTIES(x,(semantic=X)',
                    b'GLITCH_UNIFORM_PROPERTIES(x,(semantic=X))'*9]:
            with self.assertRaises(ValueError): property_spans(bad)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_fsm_tables_decode_six_markers_and_the_observed_property_keys(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); verify_native(image)
        self.assertEqual(discover_tokens(machine(image, 0x1f4fbac, 100)), {
            47: 'GLITCH_IN_BLOCK', 72: 'GLITCH_UNIFORM_BLOCK', 88: 'GLITCH_END_UNIFORM_BLOCK',
            89: 'GLITCH_UNIFORM_PROPERTIES', 93: 'GLITCH_BEGIN_UNIFORM_BLOCK', 94: 'GLITCH_ATTRIBUTE_PROPERTIES'})
        self.assertEqual(set(discover_tokens(machine(image, 0x1f4fdd8, 51)).values()),
                         {'id', 'access', 'semantic', 'texcoord', 'instancing', 'depthtexture'})
        self.assertEqual(discover_tokens(machine(image, 0x1f4ff71, 9)), {8: 'semantic'})

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_complete_original_rewrite_records_source_array_and_cleanup_match_192_cases(self):
        from analyze_native_resources import NativeImage
        from native_shader_rewrite_probe import NativeShaderRewriteProbe
        image = NativeImage(NATIVE.read_bytes()); probe = NativeShaderRewriteProbe(image); rng = random.Random(0x14836bc)
        inserted = 0
        for i in range(96):
            chunks = [b'#version 100\n' if i % 4 == 0 else b'void fixture(){}\n']
            for j in range(i % 9):
                name = ('v'+str(i)+'_'+str(j)).encode(); sem = ('Semantic'+str(rng.randrange(100))).encode()
                if j & 1:
                    token = b'GLITCH_ATTRIBUTE_PROPERTIES('+name+b', (semantic = '+sem+b'))'
                else:
                    fields = [b'semantic='+sem, b'texcoord=UV'+str(j).encode()]
                    if i & 1: fields.reverse()
                    token = b'GLITCH_UNIFORM_PROPERTIES('+name+b', ('+b', '.join(fields)+b'))'
                chunks.append([b'// '+token+b'\n', b'"'+token+b'"\n', b'#if 0\n'+token+b'\n#endif\n'][j % 3])
            source = b''.join(chunks); flags = (0, 7, 16, 23, 32, 39, 48, 55)[i % 8]
            extra = [None, b'', b'#define FIXTURE_EXTRA\n'][i % 3]
            for enabled in (False, True):
                result = probe.rewrite(source, i % 3, flags, i % 4, i % 8, extra, enabled)
                self.assertEqual(result['records'], property_spans(source) if enabled else [])
                self.assertEqual(result['segments'], expected_rewrite(image, source, i % 3, flags, i % 4, i % 8, extra, enabled))
                self.assertEqual(result['rewriteCalls'], int(enabled)); self.assertEqual(result['rewriteReturns'], [1] if enabled else [])
                self.assertTrue(result['sourceRestored']); self.assertEqual(result['remainingAllocations'], 0)
                self.assertEqual(result['freed'], len(result['allocations'])); self.assertEqual(result['cleanupFields'], [0, 0, 0])
            inserted += len(property_spans(source))
        self.assertEqual(inserted, 375)
        for flags in (0, 16):
            source = b' '*8192; result = probe.rewrite(source, flags=flags)
            self.assertEqual(result['segments'], expected_rewrite(image, source, flags=flags))
            self.assertEqual(len(result['segments'][-1]), 8193); self.assertTrue(result['sourceRestored'])
            self.assertEqual(result['remainingAllocations'], 0)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/shader source stay local')
    def test_96_original_source_cases_include_zero_sky_rewrites_and_real_material_annotation(self):
        from analyze_native_resources import NativeImage
        from native_shader_rewrite_probe import NativeShaderRewriteProbe
        from scene_sky_binding_tests import source_extract
        image = NativeImage(NATIVE.read_bytes()); probe = NativeShaderRewriteProbe(image); count = 0
        for row in rewrite_sources(source_extract()):
            for flags in (0, 7, 16, 23, 32, 39, 48, 55):
                for allow in (0, 1):
                    for enabled in (False, True):
                        result = probe.rewrite(row['data'], row['stage'], flags, allow, enabled=enabled)
                        expected = property_spans(row['data']) if enabled else []
                        self.assertEqual(result['records'], expected)
                        self.assertEqual(len(expected), int(enabled and row['name'] == PROPERTY_SOURCE))
                        self.assertEqual(result['segments'], expected_rewrite(image, row['data'], row['stage'], flags, allow, enabled=enabled))
                        self.assertTrue(result['sourceRestored']); self.assertEqual(result['remainingAllocations'], 0)
                        count += 1
        self.assertEqual(count, 96)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_rewriter_code_all_tables_and_suffix_constant_fail_closed_on_change(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in [*ROUTINES, *TABLES]:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        image.read = read; self.assertEqual(verify_native(image)['tablesAndConstants'], 15)

    @unittest.skipUnless(SOURCE.is_dir(), 'Original shader source stays local')
    def test_original_property_shader_changes_are_rejected(self):
        from scene_sky_binding_tests import source_extract
        extract = source_extract()
        with self.assertRaises(ValueError):
            rewrite_sources(lambda name: extract(name)+b'\n' if name == PROPERTY_SOURCE else extract(name))

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/shader source stay local')
    def test_scope_and_explicit_alpha_calls_do_not_claim_automatic_insertion_or_live_state(self):
        from analyze_native_resources import NativeImage
        from native_shader_rewrite_probe import NativeShaderRewriteProbe
        from scene_sky_binding_tests import source_extract
        image = NativeImage(NATIVE.read_bytes()); report = analyze_rewrite(image, source_extract())
        self.assertEqual(report['format'], FORMAT); self.assertEqual(report['skyObservedRewrites'], 0)
        for key in ('automaticSkyAlphaCallInserted', 'activeSkyInputsRecovered', 'GPUExecuted', 'appliedAsLiveState'):
            self.assertFalse(report[key])
        probe = NativeShaderRewriteProbe(image)
        for source in [b'void main(){ GLITCH_ALPHA_TEST(color.a); }', b'// GLITCH_ALPHA_TEST(x)\n',
                       b'void main(){ gl_FragColor=vec4(1.0); }']:
            result = probe.rewrite(source)
            self.assertEqual(result['records'], []); self.assertEqual(result['rewriteReturns'], [1])
            self.assertEqual(result['segments'], expected_rewrite(image, source)); self.assertTrue(result['sourceRestored'])


if __name__ == '__main__': unittest.main()
