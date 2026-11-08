import copy
import random
import struct
import unittest
from pathlib import Path

from scene_sky_assembly import (FORMAT, ROUTINES, analyze_assembly, assembly_layout,
                                source_blend, source_states, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


def source(flags=0):
    raw = bytearray(88); struct.pack_into('<I', raw, 12, flags); return bytes(raw)


def record(state=bytes(28), e2=0, df=0):
    return {'state': state, 'programWordE2': e2, 'programByteDF': df}


class SkyAssemblyTests(unittest.TestCase):
    def test_source_blend_and_header_pass_flags_are_independent(self):
        self.assertTrue(source_blend(source(1 << 19))); self.assertFalse(source_blend(source(1 << 23)))
        blob = bytearray(28); blob[6] = 1
        result = assembly_layout([{'name': 'one', 'passes': [record(bytes(blob))]},
                                  {'name': 'two', 'passes': [record(e2=0x400)]}], ['feature'])
        self.assertEqual(result['packedWord'], 0x201)
        self.assertEqual(result['techniques'][0]['headerByte11'], 0)
        self.assertEqual(result['techniques'][0]['firstPassBlendBit'], 1)
        self.assertEqual(result['techniques'][1]['headerByte11'], 1)
        self.assertEqual(result['techniques'][1]['firstPassBlendBit'], 0)
        multi = assembly_layout([{'name': 'two', 'passes': [record(e2=0x400), record(df=4)]}], [])
        self.assertEqual(multi['techniques'][0]['headerByte11'], 0)
        self.assertEqual(multi['techniques'][0]['passCopyBits'], [1, 0])

    def test_reject_unsupported_assembly_shapes_and_implicit_flags(self):
        for raw in [bytes(87), bytearray(88), 'state']:
            with self.assertRaises(ValueError): source_blend(raw)
        valid = [{'name': 'one', 'passes': [record()]}]
        for techniques, modifiers, name, index in [(valid, ['x']*6, 'fx', 0), ([], [], 'fx', 0),
                                                   (valid*9, [], 'fx', 0), (valid, [], '', 0), (valid, [], 'fx', True)]:
            with self.assertRaises(ValueError): assembly_layout(techniques, modifiers, name, index)
        for key, value in [('state', bytes(27)), ('programWordE2', 65536), ('programByteDF', True)]:
            rows = copy.deepcopy(valid); rows[0]['passes'][0][key] = value
            with self.assertRaises(ValueError): assembly_layout(rows, [])
        with self.assertRaises(ValueError): assembly_layout([{'name': 'zero', 'passes': []}], [])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_state_translation_and_full_empty_reflection_assembly(self):
        from analyze_native_resources import NativeImage
        from native_sky_assembly_probe import NativeSkyAssemblyProbe
        p = NativeSkyAssemblyProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x13feedc)
        for i in range(64):
            techniques = []
            for n in range(1+i % 4):
                rows = []
                for _ in range(1+rng.randrange(3)):
                    raw = bytearray(88)
                    for at in [0, 8, 12, 16, 36, 76, 80, 84]: struct.pack_into('<I', raw, at, rng.getrandbits(32))
                    struct.pack_into('<4f', raw, 20, *(rng.random() for _ in range(4)))
                    blob = p.translate(bytes(raw))
                    self.assertEqual(bool(blob[6] & 1), source_blend(bytes(raw)))
                    rows.append(record(blob, rng.getrandbits(16), rng.getrandbits(8)))
                techniques.append({'name': 'tech'+str(n), 'passes': rows})
            modifiers = ['feature'+str(n) for n in range(i % 6)]
            expected = assembly_layout(techniques, modifiers, index=i)
            actual = p.assemble(techniques, modifiers, index=i)
            self.assertEqual(actual['packedWord'], expected['packedWord']); self.assertEqual(actual['index'], i)
            self.assertEqual(actual['allocationBytes'], [expected['allocationBytes']])
            self.assertEqual(actual['auxAllocationBytes'], [24]); self.assertEqual(actual['references'], 1)
            self.assertEqual(actual['outputEffect'], p.BASE+0x10000); self.assertEqual(actual['effectName'], 'fixture-effect')
            self.assertEqual(actual['passCalls'], sum(len(t['passes']) for t in techniques))
            self.assertEqual(actual['entryCalls'], len(techniques)); self.assertEqual(actual['modifierCountCalls'], 2)
            for original, predicted, actual in zip(techniques, expected['techniques'], actual['techniques']):
                self.assertEqual(actual['name'], original['name']); self.assertEqual(actual['passCount'], len(original['passes']))
                self.assertEqual(actual['headerByte11'], predicted['headerByte11'])
                for src, bit, dst in zip(original['passes'], predicted['passCopyBits'], actual['passes']):
                    self.assertEqual(dst['state'], src['state']); self.assertEqual(dst['programWordE2'], src['programWordE2'])
                    self.assertEqual(dst['copyBits'], [bit, bit]); self.assertEqual(dst['programReferences'], 101)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_queue_uses_first_pass_state_not_technique_header_byte11(self):
        from analyze_native_resources import NativeImage
        from native_sky_assembly_probe import NativeSkyAssemblyProbe
        p = NativeSkyAssemblyProbe(NativeImage(NATIVE.read_bytes()))
        for blend in (False, True):
            blob = p.translate(source((1 << 19) if blend else 0))
            for e2 in (0, 0x40, 0x400, 0x440):
                for df in (0, 4):
                    for count in (1, 2):
                        actual = p.assemble([{'name': 'tech', 'passes': [record(blob, e2, df) for _ in range(count)]}])
                        self.assertEqual(actual['techniques'][0]['headerByte11'], int(count == 1 and bool(e2 & 0x400)))
                        for scene in (0, 1):
                            result = p.enqueue(0, scene); distance = blend and scene == 0
                            self.assertEqual(result['completed'], not distance)
                            self.assertEqual(result['queueOffset'], 0x160 if distance else (0x148 if e2 & 0x40 else 0x130))
                            self.assertEqual(result['selectorCalls'], 1 if distance else 2)
                            self.assertEqual(result['record'], None if distance else [p.BASE+0x1800, 1, p.BASE+0x1500, 7, 9])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_code_and_color_constant_fingerprints_fail_closed(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in [*ROUTINES, 0x1df7a84]:
            def changed(at, size, target=target):
                raw = read(at, size)
                return bytes([raw[0] ^ 1])+raw[1:] if at == target else raw
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original sky/native stay local')
    def test_actual_sky_states_through_translation_assembly_and_conditional_queue(self):
        from analyze_native_resources import NativeImage
        from native_sky_assembly_probe import NativeSkyAssemblyProbe
        from scene_sky_binding_tests import source_extract
        extract = source_extract(); image = NativeImage(NATIVE.read_bytes()); p = NativeSkyAssemblyProbe(image)
        report = analyze_assembly(image, extract)
        self.assertEqual(report['format'], FORMAT); self.assertFalse(report['appliedAsLiveState'])
        self.assertFalse(report['actualCompiledProgramFlagsRecovered']); self.assertFalse(report['activeProfileRecovered'])
        self.assertIn('72-byte pass array', report['identityCorrection']['entryPlus8'])
        for profile in source_states(extract):
            self.assertEqual([source_blend(t['sourceState']) for t in profile['techniques']], [True, True, False])
            blobs = [p.translate(t['sourceState']) for t in profile['techniques']]
            for e2 in (0, 0x440):
                techniques = [{'name': t['name'], 'passes': [record(blob, e2)]}
                              for t, blob in zip(profile['techniques'], blobs)]
                assembled = p.assemble(techniques, effect_name='sky_box-fx')
                self.assertEqual(assembled['packedWord'], 0x300)
                for index in range(3):
                    for scene in (0, 1):
                        result = p.enqueue(index, scene); distance = index < 2 and scene == 0
                        self.assertEqual(result['queueOffset'], 0x160 if distance else (0x148 if e2 & 0x40 else 0x130))
                        self.assertEqual(result['completed'], not distance)

    @unittest.skipUnless(SOURCE.is_dir(), 'Original sky sources stay local')
    def test_source_effect_state_input_hash_is_pinned(self):
        from scene_sky_binding_tests import source_extract
        extract = source_extract()
        def changed(name):
            raw = extract(name); return bytes([raw[0] ^ 1])+raw[1:]
        with self.assertRaises(ValueError): source_states(changed)


if __name__ == '__main__': unittest.main()
