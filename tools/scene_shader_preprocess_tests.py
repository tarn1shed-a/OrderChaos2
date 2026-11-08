import unittest
from pathlib import Path

from scene_shader_preprocess import (FORMAT, ROUTINES, CONSTANTS, ALPHA_EXPRESSIONS, PREDICATES,
                                     prefix_plan, source_view, expected_segments, constant,
                                     source_shaders, verify_native, analyze_preprocess)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class ShaderPreprocessTests(unittest.TestCase):
    def test_independent_prefix_gate_order_capability_bits_and_empty_extra_pointer(self):
        result = prefix_plan(1, 23, 3, 2, b'')
        self.assertTrue(result['alphaEnabled']); self.assertEqual(result['discardPredicate'], 'a != ref')
        self.assertEqual(result['segments'], ['highp', 'bias', 'force-bias', 'extra', 'alpha-function',
                                              'alpha-uniform', 'alpha-discard', 'line1', 'source'])
        self.assertEqual(prefix_plan(1, 0, 2)['segments'], ['version120', 'precision-compatibility',
                                                         'empty-alpha-uniform', 'alpha-noop', 'line1', 'source'])
        for stage in (0, 2):
            self.assertEqual(prefix_plan(stage)['segments'], ['empty-alpha-uniform', 'empty', 'line1', 'source'])
        self.assertFalse(prefix_plan(1, 48)['alphaEnabled'])
        for enum in (0, 7):
            self.assertEqual(prefix_plan(1, alpha_func=enum)['segments'][1], 'empty-alpha-uniform')
        self.assertEqual(PREDICATES[0], 'always discard'); self.assertEqual(PREDICATES[7], 'never discard')
        self.assertEqual(source_view(b'#version 100\nvoid main(){}'), b'//ersion 100\nvoid main(){}\n')
        self.assertEqual(source_view(b'x\n'), b'x\n\n')

    def test_experiment_guards_do_not_claim_all_versions_rewriter_or_unbounded_source(self):
        for args in [(True,), (3,), (1, True), (1, 64), (1, 256), (1, 16, 256), (1, 16, True),
                     (1, 16, 1, 8), (1, 16, 1, True), (1, 16, 1, 2, 'x'), (1, 16, 1, 2, b'\0')]:
            with self.assertRaises(ValueError): prefix_plan(*args)
        for source in [b'\0', b'x'*8193, b'#version 300 es\n', b'#version 120', b'\xff', 'text']:
            with self.assertRaises(ValueError): source_view(source)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_expression_selector_returns_verified_predicate_pointer_and_length(self):
        from analyze_native_resources import NativeImage
        from native_shader_preprocess_probe import NativeShaderPreprocessProbe
        image = NativeImage(NATIVE.read_bytes()); probe = NativeShaderPreprocessProbe(image)
        for enum, address in enumerate(ALPHA_EXPRESSIONS):
            actual = probe.expression(enum)
            self.assertEqual(actual['pointer'], address)
            self.assertEqual(actual['length'], CONSTANTS[address][0]-1)
            self.assertEqual(actual['value'], constant(image, address))
        for enum in (-1, True, 8):
            with self.assertRaises(ValueError): probe.expression(enum)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_full_original_prefix_and_cleanup_match_independent_plan_for_768_cases(self):
        from analyze_native_resources import NativeImage
        from native_shader_preprocess_probe import NativeShaderPreprocessProbe
        image = NativeImage(NATIVE.read_bytes()); probe = NativeShaderPreprocessProbe(image); count = 0
        sources = [b'', b'void main(){}', b'#version 100\nvoid main(){}', b'#version 120\r\nvoid main(){}\n']
        for stage in range(3):
            for flags in (0, 7, 16, 23, 32, 39, 48, 55):
                for allow in (0, 1, 2, 3):
                    for enum in range(8):
                        source = sources[count % 4]; extra = [None, b'', b'#define FIXTURE_EXTRA\n'][count % 3]
                        result = probe.preprocess(source, stage, flags, allow, enum, extra)
                        self.assertEqual(result['segments'], expected_segments(image, source, stage, flags, allow, enum, extra))
                        self.assertEqual(result['mutatedSource'], source_view(source))
                        self.assertTrue(result['sourceRestored']); self.assertEqual(result['remainingAllocations'], 0)
                        self.assertEqual(result['freed'], len(result['allocations']))
                        self.assertEqual(result['cleanupFields'], [0, 0, 0]); self.assertEqual(result['versionScanCalls'], 1)
                        count += 1
        self.assertEqual(count, 768)
        # The original appends one temporary newline even at the source bound.
        for flags in (0, 16):
            source = b' '*8192
            result = probe.preprocess(source, flags=flags)
            self.assertEqual(result['segments'], expected_segments(image, source, 1, flags))
            self.assertEqual(len(result['segments'][-1]), 8193)
            self.assertTrue(result['sourceRestored']); self.assertEqual(result['remainingAllocations'], 0)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/sky source stay local')
    def test_actual_sky_source_bytes_are_restored_after_48_explicit_capability_experiments(self):
        from analyze_native_resources import NativeImage
        from native_shader_preprocess_probe import NativeShaderPreprocessProbe
        from scene_sky_binding_tests import source_extract
        image = NativeImage(NATIVE.read_bytes()); probe = NativeShaderPreprocessProbe(image); count = 0
        for row in source_shaders(source_extract()):
            for flags in (0, 16, 32, 48):
                for allow in (0, 1):
                    for enum in (0, 2, 7):
                        result = probe.preprocess(row['data'], row['stage'], flags, allow, enum)
                        self.assertEqual(result['segments'], expected_segments(image, row['data'], row['stage'], flags, allow, enum))
                        self.assertEqual(result['segments'][-1], row['data']+b'\n')
                        self.assertTrue(result['sourceRestored']); self.assertEqual(result['remainingAllocations'], 0)
                        count += 1
        self.assertEqual(count, 48)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_new_code_and_all_prefix_constant_fingerprints_fail_closed(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in [*ROUTINES, *CONSTANTS]:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)
        image.read = read; self.assertEqual(verify_native(image)['constants'], 23)

    @unittest.skipUnless(SOURCE.is_dir(), 'Original sky source stays local')
    def test_source_shader_hash_changes_are_rejected_before_using_experiment_inputs(self):
        from scene_sky_binding_tests import source_extract
        extract = source_extract()
        with self.assertRaises(ValueError):
            source_shaders(lambda name: extract(name)+b'\n' if name == 'sky_box_fs.glsl' else extract(name))

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/sky source stay local')
    def test_report_separates_prefix_evidence_from_live_selection_rewriting_and_gpu(self):
        from analyze_native_resources import NativeImage
        from scene_sky_binding_tests import source_extract
        report = analyze_preprocess(NativeImage(NATIVE.read_bytes()), source_extract())
        self.assertEqual(report['format'], FORMAT); self.assertEqual(len(report['sources']), 2)
        for field in ('tokenRewriterExecuted', 'activeSkyInputsRecovered', 'GPUExecuted', 'appliedAsLiveState'):
            self.assertFalse(report[field])
        self.assertIn('full148c160 with rewrite stack18=0', report['execution'])
        self.assertIn('entrySP+8', report['independentSwitches']['alphaPermission'])
        self.assertIn('entrySP+18', report['independentSwitches']['tokenRewrite'])
        # Verify the two argument slots independently through the actual factory.
        # Its preprocessing/GL outputs remain the preceding probe's fixtures.
        from native_shader_metadata_probe import NativeShaderMetadataProbe
        class SwitchCapture(NativeShaderMetadataProbe):
            def _shader_inputs(self, *args):
                super()._shader_inputs(*args)
                self.write(self.get('SP')+8, 'B', self.incoming_alpha)
            def _hook(self, uc, at, size, data):
                if at == 0x148c160:
                    self.observed.append((self.read(self.get('SP')+8, 'B')[0],
                                          self.read(self.get('SP')+0x18, 'B')[0]))
                return super()._hook(uc, at, size, data)
        probe = SwitchCapture(NativeImage(NATIVE.read_bytes()))
        probe.parse_map(b';0;0;rewrite\n;1;0;raw\n')
        for alpha in (0, 1, 2, 3):
            probe.incoming_alpha = alpha
            for record, rewrite in [(0, 1), (1, 0), (None, 1)]:
                probe.observed = []; result = probe.factory_from_map(record)
                self.assertEqual(result['status'], 0)
                self.assertEqual(probe.observed, [(alpha & 1, rewrite)])


if __name__ == '__main__': unittest.main()
