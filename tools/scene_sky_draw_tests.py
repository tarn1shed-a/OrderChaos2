import unittest
import random
from pathlib import Path

from scene_sky_draw import (FORMAT, ROUTINES, SCENE_SLOTS, attachment_append,
                            pass_stages, analyze_scene, verify_native)

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class SkySceneDispatchTests(unittest.TestCase):
    def test_attachment_preserves_raw_order_duplicates_and_grows_only_when_full(self):
        nodes = [11, 22]
        self.assertEqual(attachment_append(nodes, 2, 11), {'nodes': [11, 22, 11], 'capacity': 4, 'allocated': True})
        self.assertEqual(nodes, [11, 22])
        self.assertEqual(attachment_append([], 0, 0), {'nodes': [0], 'capacity': 1, 'allocated': True})
        self.assertEqual(attachment_append([], 8, 9), {'nodes': [9], 'capacity': 8, 'allocated': False})

    def test_pass_mode_selects_pointer_or_reference_and_skip_uses_low_bit(self):
        self.assertEqual(pass_stages('direct')['slots'], [0x88, 0x98, 0x60, 0x90, 0xb0, 0xa0])
        self.assertEqual(pass_stages('reference')['slots'], [0x88, 0x98, 0x58, 0x90, 0xb0, 0xa0])
        self.assertEqual(pass_stages('direct', 1)['slots'], [0x88, 0x90, 0xb0, 0xa0])
        self.assertEqual(pass_stages('direct', 2), pass_stages('direct', 0))
        self.assertEqual(pass_stages('reference', 0, 2)['finalCallbackBit'], 0)

    def test_invalid_research_state_is_rejected_without_mutation(self):
        for capacity, node in ((-1, 1), (1, 1), (True, 1), (2, -1), (2, 1 << 64)):
            with self.assertRaises(ValueError): attachment_append([1, 2], capacity, node)
        for word in (-1, 1 << 32, True, 0.0):
            with self.assertRaises(ValueError): pass_stages('direct', word)
        with self.assertRaises(ValueError): pass_stages('new-mode')

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_original_append_executes_growth_copy_and_free_with_explicit_duplicate_pointers(self):
        from analyze_native_resources import NativeImage
        from native_sky_draw_probe import NativeSkyDrawProbe
        p = NativeSkyDrawProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(402)
        for _ in range(100):
            count = rng.randrange(33); nodes = [rng.randrange(9) for _ in range(count)]
            capacity = count if rng.randrange(2) else count+rng.randrange(1, 8); node = rng.randrange(9)
            result = p.append(nodes, capacity, node); expected = attachment_append(nodes, capacity, node)
            self.assertEqual({k: result[k] for k in expected}, expected)
            self.assertEqual(result['allocationBytes'], [expected['capacity']*8] if expected['allocated'] else [])
            self.assertEqual(result['freedOld'], expected['allocated'] and capacity > 0)
        self.assertEqual(p.append([], 0, 0)['nodes'], [0])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_original_both_pass_dispatchers_record_actual_order_arguments_and_fallback(self):
        from analyze_native_resources import NativeImage
        from native_sky_draw_probe import NativeSkyDrawProbe
        p = NativeSkyDrawProbe(NativeImage(NATIVE.read_bytes()))
        for mode in ('direct', 'reference'):
            for skip in (0, 1, 2, 3, 0xffffffff):
                for clear in (0, 1, 2, 3, 0xffffffff):
                    for node in (0, 0x12345678):
                        result = p.scene_pass(mode, skip, clear, node); events = result['events']
                        expected = pass_stages(mode, skip, clear)
                        self.assertEqual([e['slot'] for e in events if 'slot' in e], expected['slots'])
                        self.assertEqual(events[0], {'boundary': 'enter'}); self.assertEqual(events[-1], {'boundary': 'leave'})
                        self.assertEqual(result['finalPassWord'], 16)
                        last = events[-2]; self.assertEqual(last['bit'], clear & 1); self.assertEqual(last['driver'], p.BASE+0x4000)
                        if not skip & 1:
                            gather = next(e for e in events if e.get('slot') in (0x58, 0x60))
                            if mode == 'direct': self.assertEqual(gather['listAddress'], node)
                            else: self.assertEqual(gather['node'], node or 0x87654321)
                            if mode == 'reference': self.assertEqual(gather['referenceAddress'], p.BASE+0x3000 if node else p.BASE+8)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_factory_constructor_and_concrete_dispatch_bytes_are_pinned(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); self.assertTrue(verify_native(image)['defaultFactoryOnly'])
        for changed in ROUTINES:
            class Changed:
                elf = image.elf
                def read(self, at, size): return bytes(size) if at == changed else image.read(at, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_report_keeps_custom_factory_and_gpu_callback_boundaries_unresolved(self):
        from analyze_native_resources import NativeImage
        r = analyze_scene(NativeImage(NATIVE.read_bytes())); self.assertEqual(r['format'], FORMAT)
        self.assertFalse(r['appliedAsLiveState']); self.assertFalse(r['passDispatch']['callbacksExecutedByProbe'])
        self.assertTrue(r['native']['defaultFactoryOnly'])
        self.assertEqual(r['dispatch']['0xd0'], '0x12f9ea8'); self.assertFalse(r['attachment']['duplicateCheck'])
        self.assertFalse(r['attachment']['tutorialSkyAttachmentPath'])
        self.assertEqual(r['native']['sceneVirtualSlots'], len(SCENE_SLOTS))


if __name__ == '__main__': unittest.main()
