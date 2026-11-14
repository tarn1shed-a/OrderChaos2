"""Original airborne/jump/water reset and unchanged-worker protocol checks."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from tutorial_reentry_reset_probe import ROOT,DEFAULT_CONFIG,COURTYARD,analyze,evidence_output


class PublicTests(unittest.TestCase):
    def test_evidence_refuses_project_and_existing_files(self):
        for path in (ROOT/'runtime/characters.json',ROOT/'docs/new-report.json',ROOT/'tools/new-report.json'):
            with self.assertRaisesRegex(ValueError,'ignored'):evidence_output(path)
        with tempfile.TemporaryDirectory()as directory:
            with self.assertRaisesRegex(ValueError,'ignored'):evidence_output(Path(directory)/'report.json')


PRIVATE=DEFAULT_CONFIG.is_file()and all(importlib.util.find_spec(k)is not None for k in ('unicorn','capstone','elftools'))


@unittest.skipUnless(PRIVATE,'Original native inputs and local CPU libraries stay private')
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory=ROOT/'analysis/raw/tutorial-reentry-reset-20261114'
        directory.mkdir(parents=True,exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='reentry-tests-',dir=directory)
        cls.report=analyze(DEFAULT_CONFIG,Path(cls.temporary.name)/'report.json')

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def test_true_fall_then_original_setter_does_not_clear_vertical_motion(self):
        for case in self.report['native']['cases'][:2]:
            before=case['before'];self.assertLess(before['velocityY'],-17)
            self.assertFalse(before['hostGrounded'])
            self.assertEqual(case['afterRelocation']['position'],COURTYARD)
            self.assertEqual(case['afterRelocation']['pending'],COURTYARD)
            for key in ('velocityY','acceleration'):
                self.assertEqual(before[key],case['afterRelocation'][key])
                self.assertEqual(before[key],case['afterInitialSupport'][key])
            self.assertEqual(case['follow'][0]['velocityY'],0)
            self.assertEqual(case['follow'][0]['position'],COURTYARD)
        prefix=self.report['native']['cases'][1]
        self.assertEqual([r['entry']for r in prefix['calls'][:5]],
                         ['0x9037d4','0x9ec22c','0xa0902c','0x906ad4','0x90c348'])
        self.assertFalse(prefix['fullOriginalEnterMapExecuted'])

    def test_actual_forty_metre_fall_and_existing_lower_floor_are_retained_as_evidence(self):
        case=self.report['native']['cases'][2]
        self.assertAlmostEqual(case['fallFrames'][0]['position'][1]-case['before']['position'][1],40.01690673828125)
        self.assertEqual(case['before']['position'][1],132.34999084472656)
        self.assertTrue(case['before']['hostGrounded'])
        self.assertEqual(case['afterRelocation']['position'],COURTYARD)
        self.assertEqual(case['follow'][19]['position'],COURTYARD)

    def test_whole_original_hero_method_constructs_real_singleton_and_returns_without_clearing_velocity(self):
        case=self.report['native']['completeHeroRelocation']
        self.assertTrue(case['fullOriginalHeroMethodReturned']);self.assertFalse(case['fullOriginalEnterMapExecuted'])
        self.assertEqual(case['singletonBefore'],0);self.assertGreater(case['singletonAfter'],0)
        self.assertEqual(case['singletonVtable'],'0x2423240');self.assertEqual(case['singletonSecondaryVtable'],'0x2423280')
        first=[r['entry']for r in case['calls'][0]['trace']];second=[r['entry']for r in case['calls'][1]['trace']]
        self.assertIn('0xa2fa14',first);self.assertIn('0xa82030',first)
        self.assertNotIn('0xa2fa14',second);self.assertNotIn('0xa82030',second)
        for key in ('velocityY','acceleration'):
            self.assertEqual(case['before'][key],case['afterFirst'][key])
            self.assertEqual(case['before'][key],case['afterSecond'][key])
        self.assertEqual(case['afterFirst']['position'],COURTYARD)

    def test_original_prefix_retains_jump_and_camera_but_support_refreshes_water_contact(self):
        jump,water=self.report['native']['wetJumpPrefix']['cases']
        self.assertGreater(jump['before']['velocityY'],7)
        self.assertEqual(jump['before']['velocityY'],jump['afterInitialSupport']['velocityY'])
        self.assertGreater(jump['follow'][0]['position'][1],COURTYARD[1]+.3)
        self.assertEqual(water['before']['waterContactWords'][0],4)
        self.assertEqual(water['afterRelocation']['waterContactWords'][0],4)
        self.assertEqual(water['afterInitialSupport']['waterContactWords'][0],0)
        for case in (jump,water):
            self.assertEqual(case['before']['cameraWords'],case['afterRelocation']['cameraWords'])
            self.assertEqual(case['before']['cameraWords'],case['afterInitialSupport']['cameraWords'])
        self.assertEqual(water['follow'][0]['camera']['pitch'],315)
        self.assertFalse(water['follow'][0]['camera']['underwaterFlag'])

    def test_real_worker_cached_identity_ignores_coordinate_only_relocation(self):
        for case in self.report['worker']['cases']:
            if case['scenario']!='airborne-fall':continue
            old=case['fallFrames'][-1];stale=case['coordinateOnlyNegativeControl']
            self.assertFalse(stale['grounded']);self.assertLess(stale['velocityY'],old['velocityY'])
            self.assertEqual(stale['position'][0],old['position'][0])
            self.assertEqual(stale['position'][2],old['position'][2])
            self.assertNotEqual(stale['position'],COURTYARD)

    def test_reset_and_forget_rebuild_all_five_states_and_allow_stationary_then_walk(self):
        cases=self.report['worker']['cases'];self.assertEqual(len(cases),5)
        self.assertEqual(self.report['worker']['requestCount'],743)
        for case in cases:
            frames=case['frames'];self.assertTrue(case['response'])
            for row in frames[:20]:
                self.assertEqual(row['position'],COURTYARD)
                self.assertEqual(row['velocityY'],0);self.assertEqual(row['accelerationY'],0)
                self.assertTrue(row['grounded']);self.assertIsNone(row['jumpAge'])
                self.assertFalse(row['swimming']);self.assertFalse(row['submerged']);self.assertEqual(row['waterState'],0)
                self.assertFalse(row['camera']['underwaterFlag']);self.assertEqual(row['camera']['pitch'],355)
                self.assertEqual(row['camera']['position'][0],COURTYARD[0])
                self.assertLess(abs(row['camera']['position'][2]-COURTYARD[2]),10)
            self.assertGreater(frames[-1]['position'][0]-COURTYARD[0],2.3)
            self.assertTrue(all(row['grounded']for row in frames))
        wet=[c for c in cases if c['scenario']=='underwater']
        self.assertEqual(len(wet),2)
        for case in wet:
            before=case['diveFrames'][-1];self.assertTrue(before['submerged'])
            self.assertTrue(before['camera']['underwaterFlag']);self.assertEqual(before['waterState'],4)
        jump=next(c for c in cases if c['scenario']=='jump')['before']
        self.assertGreater(jump['velocityY'],0);self.assertIsNotNone(jump['jumpAge'])

    def test_other_actor_unchanged_and_no_original_escape_or_browser_success_claimed(self):
        control=self.report['worker']['unaffectedControl']
        for key in ('position','velocityY','accelerationY','grounded','swimming','submerged','jumpAge'):
            self.assertEqual(control['before'][key],control['after'][key])
        self.assertTrue(all(value is False for value in self.report['scope'].values()))
        self.assertTrue(self.report['native']['allSpecialMotionPointersEmpty'])
        self.assertEqual(self.report['native']['wetJumpPrefix']['sourceFilesChecked'],139)
        self.assertEqual(self.report['worker']['initialized']['shapes'],2827)

    def test_reviewed_binding_new_object_resets_without_copying_old_pending_jump_or_camera(self):
        binding=self.report['binding'];old=binding['sameObjectRestore'];new=binding['newObject']
        self.assertEqual([r['operation']for r in old],['restore-height','reset','tick'])
        self.assertTrue(old[-1]['data']['jump']);self.assertEqual(old[-1]['data']['control']['yawDelta'],19)
        self.assertEqual([r['operation']for r in new],['reset','tick'])
        self.assertFalse(new[-1]['data']['jump']);self.assertEqual(new[-1]['data']['control'],{'forward':False})
        self.assertEqual([r['operation']for r in binding['secondMove']],['tick'])
        self.assertFalse(binding['inspectedSave']);self.assertFalse(binding['changedRuntime'])


if __name__=='__main__':unittest.main()
