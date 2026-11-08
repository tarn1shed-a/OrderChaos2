"""Original model worker, callback and bounds positive/negative branches."""
import unittest
from pathlib import Path

from model_completion_evidence import analyze, verify_native
from resource_packs import DEFAULT_SOURCE

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(NATIVE.is_file(), 'Original ARM64 image stays local')
class CompletionNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from native_model_completion_probe import NativeModelCompletionProbe
        cls.image = NativeImage(NATIVE.read_bytes())
        cls.p = NativeModelCompletionProbe(cls.image)

    def test_identity_guards_task_bodies_and_dispatch(self):
        image = self.image
        self.assertEqual(verify_native(image)['virtualRoutes'], 7)
        for changed in (0x33cfe4, 0x337c98, 0x1df7cc0, 0x1132470):
            class Changed:
                elf = image.elf
                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == changed else raw
            with self.subTest(changed=hex(changed)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_all_acquisitions_missing_finish_with_negative_index_without_construction(self):
        r = self.p.worker(['model/a_l.bdae', 'model/a.bdae'], [])
        self.assertEqual(r['states'], [0, 4])
        self.assertEqual((r['selectedIndex'], r['finishedByte'], r['modelPresent']), (-1, 1, False))
        self.assertEqual(r['events'], [['acquire', 'model/a_l.bdae'], ['acquire', 'model/a.bdae']])

    def test_candidates_stop_at_first_acquired_resource_not_two_successful_models(self):
        names = ['model/a_l.bdae', 'model/a.bdae']
        for available, expected, acquisitions in ((names, 0, names[:1]), (names[1:], 1, names)):
            r = self.p.worker(names, available)
            self.assertEqual(r['states'], [0, 1, 2, 4])
            self.assertEqual(r['selectedIndex'], expected)
            self.assertEqual([v[1] for v in r['events'] if v[0] == 'acquire'], acquisitions)
            self.assertEqual(sum(v[0] == 'constructModel' for v in r['events']), 1)
        null = self.p.worker(names, names, return_model=False)
        self.assertEqual((null['selectedIndex'], null['finishedByte'], null['modelPresent']), (0, 1, False))
        self.assertEqual([v for v in null['events'] if v[0] == 'acquire'], [['acquire', names[0]]])

    def test_texture_wait_is_separate_from_model_construction(self):
        for status in (None, 'ready', 'skip'):
            r = self.p.worker(['model/a.bdae'], ['model/a.bdae'], textures=[status])
            self.assertEqual((r['finishedByte'], r['states'][-1]), (1, 4))
        pending = self.p.worker(['model/a.bdae'], ['model/a.bdae'], textures=['pending'])
        self.assertEqual((pending['finishedByte'], pending['states'][-1], pending['waitStamp']), (0, 3, 1000))
        self.assertTrue(pending['modelPresent'])
        self.assertTrue(self.p.wait_gate(1079))
        self.assertFalse(self.p.wait_gate(1080))

    def test_notification_finished_flag_does_not_assert_successful_model(self):
        for state, index, present, done in ((4, -1, False, 1), (4, 0, False, 1),
                                             (4, 1, True, 1), (3, 0, True, 0)):
            self.assertEqual(self.p.notification(state, index, present),
                             dict(taskId=17, selectedIndex=index, modelPresent=present, finishedByte=done))

    def test_consumer_guards_clear_pending_task_before_ignoring_notification(self):
        for done, index, blocked in ((0, 0, False), (1, -1, False), (1, 0, True)):
            packet = dict(taskId=17, selectedIndex=index, modelPresent=True, finishedByte=done)
            r = self.p.consume(packet, [1], blocked=blocked)
            self.assertEqual((r['taskId'], r['completionMask'], r['slotsPresent']), (0, 0, [False, False]))
            self.assertEqual(r['radiusCenterScale'][-1], -1)

    def test_completion_maps_candidate_index_to_slot_and_rechecks_requested_state(self):
        packet = self.p.notification(4, 1, True)
        r = self.p.consume(packet, [1, 0])
        self.assertEqual((r['completionMask'], r['slotsPresent'], r['active']), (1, [True, False], 2))
        self.assertEqual(r['refreshCalls'], [])
        r = self.p.consume(packet, [1, 0], requested=1)
        self.assertEqual((r['requested'], r['active']), (1, 0))
        self.assertEqual(r['refreshCalls'], [1])
        self.assertEqual(r['renderApplyBoundaryCalls'], 1)

    def test_null_model_can_mark_attempted_slot_without_loaded_object_or_bounds(self):
        packet = self.p.notification(4, 0, False)
        r = self.p.consume(packet, [1])
        self.assertEqual((r['completionMask'], r['slotsPresent']), (2, [False, False]))
        self.assertEqual(r['radiusCenterScale'][-1], -1)

    def test_bounds_union_filters_flags_and_invalid_boxes_and_caches_first_result(self):
        packet = self.p.notification(4, 0, True)
        boxes = [(0x18, [0, 0, 0, 2, 4, 6]), (0x18, [-2, -1, -4, 0, 1, 2]),
                 (0, [-100, -100, -100, 100, 100, 100]), (0x18, [2, 0, 0, 1, 1, 1])]
        r = self.p.consume(packet, [1], boxes=boxes)
        self.assertEqual(r['radiusCenterScale'][1:4], [0, 1.5, 1])
        cached = self.p.consume(packet, [1], boxes=boxes, cache=7)
        self.assertEqual(cached['radiusCenterScale'][-1], 7)
        self.assertFalse(any(v[0] == 'sceneEnumerationBoundary' for v in cached['events']))
        preferred = self.p.consume(packet, [1], boxes=boxes, existing=(True, False))
        enumerated = [v[1] for v in preferred['events'] if v[0] == 'sceneEnumerationBoundary']
        self.assertEqual(set(enumerated), {self.p.SELF+0x17000})

    def test_bounds_empty_union_and_named_exception_use_root_box(self):
        packet = self.p.notification(4, 0, True)
        for kwargs in (dict(boxes=()), dict(model_name='model/hum_other_flag006')):
            r = self.p.consume(packet, [0], root_box=[10, 20, 30, 12, 24, 36], **kwargs)
            self.assertEqual(r['radiusCenterScale'][1:4], [11, 22, 33])

    def test_original_world_box_transforms_negative_scale_and_translation(self):
        matrix = [-2, 0, 0, 0, 0, 3, 0, 0, 0, 0, 1, 0, 10, 20, 30, 1]
        self.assertEqual(self.p.world_box([-1, -2, -3, 1, 2, 3], matrix), [8, 14, 27, 12, 26, 33])


@unittest.skipUnless(NATIVE.is_file() and (DEFAULT_SOURCE/'tutorial.bin').is_file(),
                     'Original model/library inputs stay local')
class CompletionSourceTests(unittest.TestCase):
    def test_six_original_models_and_twelve_instances_retain_runtime_gaps(self):
        from analyze_native_resources import NativeImage
        r = analyze(NativeImage(NATIVE.read_bytes()), DEFAULT_SOURCE)
        self.assertEqual((len(r['models']), len(r['sourceInstances']), len(r['conditionalSourceCases'])), (6, 12, 18))
        self.assertTrue(all(not v['sourceBoundsCandidates'][0]['mappingToNativeBufferPlus60FullyProven']
                            for v in r['models']))
        for row in r['conditionalSourceCases']:
            expected_slot = 1 if row['explicitForceModelLodLevel'] == 1 else 0
            self.assertEqual(row['callback']['slotsPresent'][expected_slot], True)
            self.assertEqual(row['callback']['active'], 2)
        self.assertFalse(r['native']['originalResourceConstructionExecuted'])
        self.assertFalse(r['appliedToGame'])


if __name__ == '__main__':
    unittest.main()
