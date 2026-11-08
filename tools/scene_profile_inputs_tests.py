import random
import unittest
from pathlib import Path

from scene_profile_inputs import (FORMAT, ROOT_TAG, VERSION, ROUTINES, STRINGS,
                                  header_contract, profile_after_load, verify_native, analyze_inputs)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


def probe():
    from analyze_native_resources import NativeImage
    from native_profile_inputs_probe import NativeProfileInputsProbe
    return NativeProfileInputsProbe(NativeImage(NATIVE.read_bytes()))


class ProfileInputTests(unittest.TestCase):
    def test_document_header_contract_distinguishes_warning_from_header_rejection(self):
        self.assertEqual(header_contract(), {'headerAccepted': True, 'messages': 0})
        for version in (None, '', '0.0.1'):
            self.assertEqual(header_contract(version=version), {'headerAccepted': True, 'messages': 1})
        for change in [{'tag': ROOT_TAG.lower()}, {'node_type': 2}, {'reader_word': 2}]:
            self.assertEqual(header_contract(**change), {'headerAccepted': False, 'messages': 1})
        self.assertEqual(header_contract(document=False), {'headerAccepted': False, 'messages': 0})
        for change in [{'node_type': True}, {'reader_word': -1}, {'tag': 'x\0y'}]:
            with self.assertRaises(ValueError): header_contract(**change)

    def test_load_result_low_bit_controls_reset_without_assuming_any_nonzero_is_success(self):
        for result in (0, 1, 2, 3, 0xfffffffe, 0xffffffff):
            self.assertEqual(profile_after_load(17, result), 0xffffffff if result & 1 else 17)
        for args in [(True, 0), (0, -1)]:
            with self.assertRaises(ValueError): profile_after_load(*args)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_header_gate_root_type_reader_bit_and_version_warning_frontiers(self):
        p = probe()
        cases = [{}, {'version': None}, {'version': '0.0.1'}, {'tag': ROOT_TAG.lower()},
                 {'node_type': 0}, {'node_type': 2}, {'reader_word': 2}, {'reader_word': 3}, {'document': False}]
        for changes in cases:
            actual = p.header(**changes); expected = header_contract(**changes)
            self.assertEqual({k: actual[k] for k in expected}, expected)
            stop = '0x1409bb8' if changes.get('document') is False else '0x1409fc8' if expected['headerAccepted'] else '0x1409b04'
            self.assertEqual(actual['stop'], stop)
            self.assertEqual(actual['streamReferences'], 100); self.assertEqual(actual['allocatorModeAtStop'], 1)
            self.assertFalse(actual['fullParserExecuted'])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_full_original_load_and_clear_wrappers_write_driver_word_with_explicit_delegate_results(self):
        p = probe(); rng = random.Random(0x147f24c)
        for i in range(32):
            previous = rng.getrandbits(32)
            for result in (0, 1, 2, 3):
                p.init_driver(previous); actual = p.load_wrapper(result)
                self.assertEqual(actual, {'profile': profile_after_load(previous, result), 'returnWord': result & 1, 'delegateCalls': 1})
            p.init_driver(previous); self.assertEqual(p.load_wrapper(0, clear=True)['profile'], 0xffffffff)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_both_scoped_node_layouts_execute_parent_bodies_and_restore_actual_saved_storage(self):
        p = probe(); rng = random.Random(0x12fc848)
        for i in range(64):
            previous, target, restored = (rng.getrandbits(32) for _ in range(3)); kind = i & 1
            p.init_driver(previous); begin = p.push_profile(target, kind)
            self.assertEqual(begin, {'profile': target, 'saved': previous, 'parentActive': 1, 'materialReferences': 100})
            node, _ = p.scope_stack[-1]; p.write(node+(0x3c if kind == 0 else 0x40), 'I', restored)
            self.assertEqual(p.pop_profile(), {'profile': restored, 'parentActive': 0, 'materialReferences': 100})
            self.assertEqual(p.render_events, [['push', previous], ['pop', target]])

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original native/effect source stay local')
    def test_source_table_selector_consumes_nested_original_driver_writes_without_refilling_profile(self):
        from scene_effect_modifiers import source_profiles
        from scene_sky_binding_tests import source_extract
        p = probe(); source = source_profiles(source_extract())
        for profile in source['profiles']:
            p.use_source(source, profile['field'])
            inputs = [{'name': t['name'], 'passes': [{'state': p.translate(v['sourceState']),
                       'programWordE2': 0, 'programByteDF': 0} for v in t['passes']]} for t in profile['techniques']]
            p.build(inputs)
            p.register_rules([{'pattern': '*', 'profiles': [1], 'variants': [0], 'source': None, 'target': 'solid'}], 2, 2)
            for initial in (0xffffffff, 0, 1):
                p.init_driver(initial); expected = 2 if initial == 1 else 0
                self.assertEqual(p.select_current(0, 0), expected)
                p.push_profile(1, 0); self.assertEqual(p.select_current(0, 0), 2)
                p.push_profile(0, 1); self.assertEqual(p.select_current(0, 0), 0)
                p.pop_profile(); self.assertEqual(p.select_current(0, 0), 2)
                p.pop_profile(); self.assertEqual(p.select_current(0, 0), expected)
                self.assertEqual(p.render_events, [['push', initial], ['push', 1], ['pop', 0], ['pop', 1]])
            p.init_driver(1); p.load_wrapper(0); self.assertEqual(p.select_current(0, 0), 2)
            p.load_wrapper(1); self.assertEqual(p.select_current(0, 0), 0)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_original_code_keywords_and_uncovered_raw_inputs_fail_closed(self):
        p = probe()
        with self.assertRaises(ValueError): p.init_driver(True)
        p.init_driver(0)
        with self.assertRaises(ValueError): p.pop_profile()
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target, size in [*( (at, spec[0]) for at, spec in ROUTINES.items()),
                             *((at, len(value)+1) for at, value in STRINGS.items())]:
            def changed(at, count, target=target, size=size):
                raw = read(at, count)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target and count == size else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample stays local')
    def test_report_keeps_header_admission_and_delegate_fixtures_separate_from_active_device_values(self):
        from analyze_native_resources import NativeImage
        report = analyze_inputs(NativeImage(NATIVE.read_bytes()))
        self.assertEqual(report['format'], FORMAT); self.assertEqual(report['documentRoot'], ROOT_TAG)
        self.assertEqual(report['runtimeVersion'], VERSION); self.assertFalse(report['loader']['fullParserExecuted'])
        for key in ('actualDeviceRulesRecovered', 'activeSceneProfileRecovered', 'shaderCompilerExecuted', 'GPUExecuted', 'appliedAsLiveState'):
            self.assertFalse(report[key])


if __name__ == '__main__': unittest.main()
