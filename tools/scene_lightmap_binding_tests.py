import json
import math
import struct
import unittest
from pathlib import Path

from resource_packs import DEFAULT_SOURCE
from scene_lightmap_binding import (FORMAT, MACROS, ROUTINES, STRINGS, active_loaded_slot,
    analyze_bindings, fresh_model_requests, initial_model_request, material_request,
    material_request_slots, uv_parameter, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


def payload(*values): return struct.pack('<4f', *values).hex()


def request(key, atlas=0, values=(0.25, -0.1, 0.5, 0.75)):
    return {'sortKey': key, 'atlasIndex': atlas, 'payload16Hex': payload(*values),
            'texturePath': f'original-page-{atlas}', 'candidates': []}


class SceneLightmapBindingTests(unittest.TestCase):
    def test_uv_parameters_use_little_endian_float32_offset_then_scale_without_clamping(self):
        decoded = uv_parameter(payload(0.25, -0.125, 2, 0.5))
        self.assertEqual(decoded['sourceFloat4'], [0.25, -0.125, 2, 0.5])
        self.assertEqual(decoded['whenUniformPresent'], decoded['sourceFloat4'])
        self.assertFalse(decoded['resetToIdentity'])
        # A known coordinate maps using offset + uv1*scale, not the reverse.
        offset_x, offset_y, scale_x, scale_y = decoded['whenUniformPresent']
        self.assertEqual((offset_x+0.5*scale_x, offset_y+0.25*scale_y), (1.25, 0.0))

    def test_reset_compares_both_signed_float_scales_against_a_double_threshold(self):
        for scales in ((0, 0), (-3, -2), (1e-6, 9e-6), (1e-5, 1e-5)):
            # float32(1e-5) is BELOW source double1e-5, so this resets too.
            decoded = uv_parameter(payload(0.7, 0.2, *scales))
            self.assertTrue(decoded['resetToIdentity'], scales)
            self.assertEqual(decoded['whenUniformPresent'], [0, 0, 1, 1])
        next_float = struct.unpack('<f', struct.pack('<I', 0x3727c5ad))[0]
        self.assertGreater(next_float, 1e-5)
        for scales in ((next_float, next_float), (0, 1), (1, 0), (-3, 1)):
            decoded = uv_parameter(payload(0, 0, *scales))
            self.assertFalse(decoded['resetToIdentity'], scales)

    def test_invalid_uv_audit_input_is_rejected_without_reinterpreting_nan(self):
        for value in ('', '00'*15, '00'*17, 'zz'*16, None, b'0'*32,
                      payload(math.nan, 0, 1, 1), payload(0, 0, math.inf, 1)):
            with self.subTest(value=value), self.assertRaises(ValueError): uv_parameter(value)

    def test_binding_key_indexes_material_array_and_past_end_uses_entry_zero(self):
        second, first = request(1, 9), request(0, 2)
        slots = material_request_slots([second, first])
        self.assertEqual([s['atlasIndex'] for s in slots], [2, 9])
        self.assertEqual(material_request(slots, 0)['atlasIndex'], 2)
        self.assertEqual(material_request(slots, 1)['atlasIndex'], 9)
        self.assertEqual(material_request(slots, 2)['atlasIndex'], 2)
        self.assertEqual(material_request(slots, 99)['atlasIndex'], 2)
        self.assertEqual(material_request(slots, 1)['candidates'], [])
        self.assertIsNone(material_request([], 0))
        self.assertNotIn('uvParameter', first)  # Source record remains unmodified.

    def test_sparse_duplicate_and_noninteger_keys_are_explicitly_outside_this_reader(self):
        for requests in ([request(2)], [request(0), request(0)], [request(-1)],
                         [request(True)], [request(0.0)], [request(0), request(2)]):
            with self.assertRaisesRegex(ValueError, 'binding keys'): material_request_slots(requests)
        for ordinal in (-1, True, 1.0, 100001):
            with self.assertRaises(ValueError): material_request([], ordinal)

    def test_explicit_config_is_separate_from_the_incoming_slot_and_loaded_fallback(self):
        for incoming in (0, 1):
            for config in (0, 1, 2):
                self.assertEqual(initial_model_request(config, incoming), {
                    'requestedSlot': incoming if config == 2 else config, 'forceSingleSlot': config != 2})
        self.assertEqual(active_loaded_slot(1, [True, False]), 0)
        self.assertEqual(active_loaded_slot(1, [True, True]), 1)
        self.assertEqual(active_loaded_slot(0, [False, True]), 2)
        self.assertEqual(active_loaded_slot(1, [False, False], previous=0), 0)
        for config, incoming in ((-1, 0), (3, 0), (True, 0), (2, 2), (2, False)):
            with self.assertRaises(ValueError): initial_model_request(config, incoming)
        for loaded in ([1, 0], [True], [True, False, True]):
            with self.assertRaises(ValueError): active_loaded_slot(0, loaded)

    def test_forced_lower_filename_fallback_keeps_lower_record_slot(self):
        base = 'model/scene/test.bdae'
        lower = 'model/scene/test_l.bdae'
        self.assertEqual(fresh_model_requests(base, 1, True, False), [{'slot': 1, 'model': base}])
        self.assertEqual(fresh_model_requests(base, 1, True, True), [{'slot': 1, 'model': lower}])
        self.assertEqual(fresh_model_requests(base, 1, False, False), [
            {'slot': 1, 'model': lower}, {'slot': 0, 'model': base}])
        self.assertEqual(fresh_model_requests(base, 0, False, True), [{'slot': 0, 'model': base}])
        for model in ('../test.bdae', 'model/../test.bdae', 'model/test_l.bdae', 'model/test', 'model//test.bdae'):
            with self.assertRaises(ValueError): fresh_model_requests(model, 0, True, False)
        with self.assertRaises(ValueError): fresh_model_requests(base, 0, 1, False)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native evidence stays local')
    def test_native_factory_model_slots_material_parameter_and_macro_consumers_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes())
        result = verify_native(image)
        self.assertEqual(result['bindingRoutines'], 15)
        self.assertEqual(result['uvTransformFlag'], 128)
        self.assertFalse(result['appliedToRendering'])
        for changed in [*ROUTINES, *STRINGS, 0x1df7bd8, 0x1df7710, *(v[0] for v in MACROS.values())]:
            class Changed:
                elf = image.elf
                def read(self, address, size):
                    return bytes(size) if address == changed else image.read(address, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())
        for changed in (0x2424188+0xb0, *(0x250afc0+bit*8 for bit in MACROS)):
            class Relocations:
                def iter_relocations(self):
                    return [{**r.entry, 'r_addend': 0} if r['r_offset'] == changed else r
                            for r in image.elf.get_section_by_name('.rela.dyn').iter_relocations()]
            class ELF:
                def get_section_by_name(self, name): return Relocations()
            class Changed:
                elf = ELF()
                read = image.read
            with self.subTest(relocation=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    @unittest.skipUnless((DEFAULT_SOURCE/'tutorial.bin').is_file(), 'Original map evidence stays local')
    def test_current_instance_parameters_decode_while_missing_pages_and_active_state_stay_explicit(self):
        report = analyze_bindings()
        self.assertEqual(report['format'], FORMAT)
        self.assertEqual(report['instanceCount'], 39)
        primary = [b for b in report['bindings'] if b['slot'] == 0]
        secondary = [b for b in report['bindings'] if b['slot'] == 1]
        self.assertTrue(all(b['parameterStatus'] == 'decoded' for b in primary))
        self.assertEqual(sum(b['parameterStatus'] == 'decoded' for b in secondary), 38)
        slots = [s for b in report['bindings'] for s in b.get('materialRequestSlots', [])]
        self.assertEqual(len(slots), 77)
        self.assertTrue(all(s['sortKey'] == 0 and not s['uvParameter']['resetToIdentity'] for s in slots))
        self.assertEqual(sum(not s['candidates'] for s in slots), 2)
        self.assertEqual(len(report['models']), 16)
        self.assertTrue(all(next(r for r in model if r['slot'] == 0)['candidates'] for model in report['models'].values()))
        self.assertEqual(sum(bool(next(r for r in model if r['slot'] == 1)['candidates'])
                             for model in report['models'].values()), 1)
        # Fifteen missing _l files are not fifteen missing base models, and a
        # forced filename fallback must not silently switch their atlas slot.
        for base, model in report['models'].items():
            lower_exists = bool(next(r for r in model if r['slot'] == 1)['candidates'])
            forced = fresh_model_requests(base, 1, True, lower_exists)
            self.assertEqual(forced[0]['slot'], 1)
            if not lower_exists: self.assertEqual(forced[0]['model'], base)
        shader = report['shaderEvidence']
        self.assertEqual(shader['baseDefaultFlags'] & shader['uvTransformFlag'], 0)
        self.assertFalse(shader['nativeActiveStateObserved'])
        self.assertFalse(report['appliedToRendering'])
        json.dumps(report, allow_nan=False)


if __name__ == '__main__': unittest.main()
