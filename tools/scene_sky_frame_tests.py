import copy
import math
import random
import struct
import unittest
from pathlib import Path

from scene_lighting import f32
from scene_sky_frame import FORMAT, ROUTINES, followed_positions, update_schedule, verify_native, analyze_frame

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class SkyFrameTests(unittest.TestCase):
    def test_main_and_hill_follow_all_three_camera_coordinates_without_mutating_inputs(self):
        camera = [18, -3, 42]; main = [0, 0, 0]; hill = [18, -3, 42]
        before = copy.deepcopy([camera, main, hill]); result = followed_positions(camera, main, hill)
        self.assertEqual(result, {'positions': {'main': camera, 'hill': camera}, 'dirtyNodes': ['main']})
        self.assertEqual([camera, main, hill], before)
        result['positions']['main'][0] = 999
        self.assertEqual(result['positions']['hill'][0], 18)
        self.assertEqual(followed_positions(camera), {'positions': {'main': None, 'hill': None}, 'dirtyNodes': []})

    def test_float32_equal_and_signed_zero_positions_skip_setter_preserving_old_bits(self):
        result = followed_positions([0, .1, 0], [-0.0, f32(.1), 0])
        self.assertEqual(result['dirtyNodes'], [])
        self.assertEqual(struct.pack('<f', result['positions']['main'][0]), struct.pack('<f', -0.0))
        self.assertEqual(followed_positions([0, 1.0000001192092896, 0], [0, 1, 0])['dirtyNodes'], ['main'])

    def test_update_order_is_primary_then_sky_then_scene_with_signed_float_clock(self):
        self.assertEqual(update_schedule(500), [{'target': 'primary+0x38', 'deltaWord': 500},
            {'target': 'sky+0x48', 'deltaWord': 500}, {'target': 'scene+0xb8', 'deltaFloat': 500, 'argument1': 0}])
        self.assertEqual(update_schedule(0xffffffff, False, False), [{'target': 'scene+0xb8', 'deltaFloat': -1, 'argument1': 0}])
        self.assertEqual(update_schedule(0x80000000)[-1]['deltaFloat'], -2147483648)

    def test_invalid_camera_node_clock_and_presence_inputs_are_rejected(self):
        for value in (None, [0, 1], [math.nan, 0, 1], [0, True, 0], [math.inf, 0, 0]):
            with self.assertRaises(ValueError): followed_positions(value)
        with self.assertRaises(ValueError): followed_positions([0]*3, [0, 1])
        for clock in (-1, 1 << 32, True, 1.0):
            with self.assertRaises(ValueError): update_schedule(clock)
        with self.assertRaises(ValueError): update_schedule(1, primary=1)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_original_full_sky_frame_and_wrapper_position_path_with_synthetic_receivers(self):
        from analyze_native_resources import NativeImage
        from native_sky_frame_probe import NativeSkyFrameProbe
        p = NativeSkyFrameProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(347)
        for _ in range(100):
            camera = [f32(rng.uniform(-4000, 4000)) for _ in range(3)]
            main = [0, 0, 0] if rng.randrange(2) else None
            hill = camera.copy() if rng.randrange(2) else None
            self.assertEqual(p.follow(camera, main, hill), followed_positions(camera, main, hill))
        equal = p.follow([0]*3, [-0.0, 0, 0])
        self.assertEqual(equal, followed_positions([0]*3, [-0.0, 0, 0]))
        self.assertEqual(struct.pack('<f', equal['positions']['main'][0]), struct.pack('<f', -0.0))
        self.assertEqual(p.follow([1, 2, 3], [0]*3, [0]*3, unloaded=('main', 'hill')),
                         {'positions': {'main': None, 'hill': None}, 'dirtyNodes': []})
        self.assertEqual(p.follow([1, 2, 3], [0]*3, [0]*3, unloaded=('main',)), followed_positions([1, 2, 3], None, [0]*3))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_original_renderer_prefix_records_order_and_clock_without_executing_callbacks(self):
        from analyze_native_resources import NativeImage
        from native_sky_frame_probe import NativeSkyFrameProbe
        p = NativeSkyFrameProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(3473)
        clocks = [0, 1, 500, 0x7fffffff, 0x80000000, 0xffffffff]+[rng.randrange(1 << 32) for _ in range(50)]
        for clock in clocks:
            for primary, sky in ((False, False), (False, True), (True, False), (True, True)):
                self.assertEqual(p.schedule(clock, primary, sky), update_schedule(clock, primary, sky))

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_new_native_routing_and_consumer_fingerprints_reject_changed_bytes(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); self.assertEqual(verify_native(image)['vtableSlots'], 5)
        for changed in ROUTINES:
            class Changed:
                elf = image.elf
                def read(self, at, size): return bytes(size) if at == changed else image.read(at, size)
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError): verify_native(Changed())

    @unittest.skipUnless(NATIVE.is_file(), 'Original native source stays local')
    def test_evidence_report_preserves_camera_dispatch_and_unresolved_draw_boundary(self):
        from analyze_native_resources import NativeImage
        report = analyze_frame(NativeImage(NATIVE.read_bytes()))
        self.assertEqual(report['format'], FORMAT)
        self.assertFalse(report['appliedAsLiveState']); self.assertFalse(report['sceneAttachment']['drawOrderEstablished'])
        self.assertEqual(report['frame']['cameraPath'][-2:], ['scene+0x238', 'camera virtual+0x170'])
        self.assertEqual(report['frame']['modelWrapperOffsets'], [0x10, 0x18])
        self.assertEqual(report['owner']['skyOtherCallbacks'], {'0x20': 'empty', '0x28': 'empty'})


if __name__ == '__main__': unittest.main()
