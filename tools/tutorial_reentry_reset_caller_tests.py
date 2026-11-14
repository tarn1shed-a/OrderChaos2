"""Original post-relocation heading/camera calls, independent of web reset."""
import importlib.util
import math
import unittest
from tutorial_reentry_reset_caller_probe import DEFAULT_CONFIG,COURTYARD,analyze

PRIVATE=DEFAULT_CONFIG.is_file()and all(importlib.util.find_spec(k)is not None for k in ('unicorn','capstone','elftools'))


@unittest.skipUnless(PRIVATE,'Original caller/PHY inputs and CPU libraries stay private')
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.report=analyze()

    def test_real_virtual_consumer_sets_heading_without_changing_movement(self):
        for case in self.report['cases']:
            self.assertEqual(case['actualDirectionConsumerEntries'],[{'entry':'0xa2b7d8','modeW2':0xffffffff,
                'flagsW3':0,'direction':case['explicitDecodedDirection']}])
            norm=math.sqrt(sum(x*x for x in case['explicitDecodedDirection']))
            expected=[x/norm for x in case['explicitDecodedDirection']]
            for x,y in zip(case['afterDirectionCaller']['headingDirection140'],expected):self.assertAlmostEqual(x,y,places=6)
            self.assertEqual(case['afterDirectionCaller']['headingDirection140'],case['afterDirectionCaller']['pendingHeading174'])
            for key in ('velocityY','acceleration','direction','speed'):
                for stage in ('afterFullHeroRelocation','afterDirectionCaller','afterCameraCaller'):
                    self.assertEqual(case['before'][key],case[stage][key])
            self.assertEqual(case['afterCameraCaller']['position'],COURTYARD)
        self.assertLess(self.report['cases'][0]['before']['velocityY'],-17)

    def test_original_camera_consumer_changes_yaw_and_dirty_but_preserves_pitch(self):
        expected=[0,-90,-143.13009643554688]
        for case,yaw in zip(self.report['cases'],expected):
            after=case['afterCameraCaller'];self.assertAlmostEqual(after['cameraYaw68'],yaw,places=5)
            self.assertEqual(after['cameraPitch6c'],case['before']['cameraPitch6c'])
            self.assertEqual(after['cameraDirty18c'],1);self.assertEqual(after['cameraByte2a9'],0)
        self.assertEqual(self.report['cases'][2]['before']['cameraYaw68'],-90)
        self.assertEqual(self.report['cases'][2]['before']['cameraPitch6c'],315)

    def test_split_original_ranges_do_not_claim_complete_packet_or_cleanup(self):
        for case in self.report['cases']:
            self.assertEqual(case['sourceCallerSlices'],[['0xa356d0','0xa3571c'],['0xa3574c','0xa35814']])
            self.assertFalse(case['interveningSpecialQueueAndUIExecuted']);self.assertFalse(case['realOriginalEnterMapReceived'])
        self.assertTrue(all(value is False for value in self.report['scope'].values()))

    def test_source_pins_and_complete_collision_set(self):
        self.assertEqual(self.report['identity']['sourceFilesChecked'],139)
        self.assertEqual(self.report['identity']['loaded']['shapes'],2827)
        self.assertEqual(self.report['nativeRoutines'],[
            {'address':'0xa2b7d8','size':536,'sha256':'3d0c3eddfda0beb7a61ca8ec3417d2f3f34b4d0581fe0180378d60145d5bc9da'},
            {'address':'0xa34f28','size':6120,'sha256':'696fe369680d77e7d54a7553d7909072e37ccd76f5c45192b96be5bbc9d96c38'}])


if __name__=='__main__':unittest.main()
