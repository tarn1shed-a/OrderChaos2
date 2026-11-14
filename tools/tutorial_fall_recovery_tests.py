"""Actual original-CPU edge loss, gravity and lower-floor reentry fixtures."""
import unittest
from tutorial_fall_recovery_probe import DEFAULT_CONFIG, analyze, fall_probe_type


class Public(unittest.TestCase):
    def test_original_execution_dependencies_are_optional_at_import(self):
        self.assertTrue(callable(analyze));self.assertTrue(callable(fall_probe_type))


class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DEFAULT_CONFIG.exists():raise unittest.SkipTest('Original runtime inputs stay private')
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
            import elftools  # noqa: F401
        except ImportError:raise unittest.SkipTest('Optional original execution dependencies unavailable')
        cls.result=analyze(temple_edges=True)
        cls.motions={r['name']:r for r in cls.result['motions']}
        cls.roof={r['axis']:r['motion']for r in cls.result['templeEdges']['rows']}

    def test_source_centres_keep_their_existing_support_not_a_new_safe_floor(self):
        self.assertEqual([self.result['loaded'][k]for k in ('tiles','instances','shapes')],[251,1044,2827])
        for name in ('bridge-center-hold','old-upper-hold','old-lower-hold','w7-courtyard-hold'):
            r=self.motions[name];self.assertIsNone(r['firstAirborneFrame']);self.assertTrue(r['finalGrounded'])
            self.assertLess(abs(r['finalPosition'][1]-r['start'][1]),.00001)
            self.assertFalse(r['newRescueOrSafeFloorApplied'])

    def test_bridge_support_changes_inside_one_resident_tile_before_original_fall(self):
        r=self.motions['bridge-edge-minus-x'];i=r['firstAirborneFrame'];self.assertEqual(i,34)
        frame=r['frames'][i]
        self.assertEqual(frame['supportBefore']['instanceId'],274022992)
        self.assertIsNone(frame['supportAfter']['instanceId'])
        self.assertTrue(frame['supportBefore']['sourceCellAvailable']);self.assertTrue(frame['supportAfter']['sourceCellAvailable'])
        witness=r['firstEdgeWitness'];self.assertEqual(witness['beforeTile'],witness['afterTile'])
        self.assertEqual(witness['beforeVerticalRay']['instanceId'],274022992)
        self.assertIsNone(witness['afterVerticalRay']['instanceId'])
        self.assertFalse(witness['sourceRegistrationChangedDuringPath'])
        self.assertIn(0x30,frame['postureRequests']);self.assertLess(frame['velocityY'],0)
        call=r['fallConsumerEntries'][0];self.assertEqual(call['originalCaller'],'0x90cd14')
        self.assertGreater(call['heightDifferenceS9'],1)
        self.assertAlmostEqual(call['restoredPriorHeightS10'],136.531662,places=5)
        self.assertAlmostEqual(r['finalPosition'][1],132.349991,places=5)

    def test_temple_roof_edge_falls_and_settles_through_original_gravity(self):
        r=self.roof['plusZ'];self.assertEqual(r['firstAirborneFrame'],248)
        edge=r['firstEdgeWitness'];self.assertEqual(edge['beforeTile'],edge['afterTile'])
        self.assertEqual(edge['beforeVerticalRay']['instanceId'],715733128)
        self.assertIsNone(edge['afterVerticalRay']['instanceId'])
        self.assertAlmostEqual(r['fallConsumerEntries'][0]['heightDifferenceS9'],40.0169067,places=5)
        self.assertTrue(r['finalGrounded']);self.assertAlmostEqual(r['finalPosition'][1],132.349991,places=5)
        self.assertEqual(r['settleFrames'],80)
        self.assertTrue(all(f['inputVelocityXZ']==[0,0]for f in r['frames'][-80:]))
        self.assertTrue(any(f['velocityY']<0 for f in r['frames']))
        self.assertFalse(r['newRescueOrSafeFloorApplied'])

    def test_same_roof_wall_blocks_a_different_direction(self):
        r=self.roof['plusX'];self.assertIsNone(r['firstAirborneFrame']);self.assertTrue(r['finalGrounded'])
        self.assertAlmostEqual(r['finalPosition'][1],172.366898,places=5)
        self.assertLess(r['finalPosition'][0]-r['start'][0],1)
        self.assertEqual(r['fallConsumerEntries'],[])

    def test_saved_lower_height_is_preserved_by_original_entry_and_initial_support(self):
        for r in (self.result['postFallReentryFixture'],self.result['templeEdges']['postFallReentry']):
            y=r['explicitSavedPositionFixture'][1]
            self.assertAlmostEqual(y,132.349991,places=5)
            self.assertEqual(r['entry']['currentPosition'],r['explicitSavedPositionFixture'])
            self.assertEqual(r['initialSupport']['pendingPosition'],r['explicitSavedPositionFixture'])
            self.assertAlmostEqual(r['initialSupport']['cachedSupport'],y,places=6)
            self.assertFalse(r['userSaveReadOrWritten'])
        cases=self.result['sameXZInitialFloorCases']
        self.assertEqual([r['initialSupport']['pendingPosition'][1]for r in cases],
                         [132.34999084472656,132.34999084472656,172.3668975830078,172.3668975830078])
        self.assertTrue(all(v is False for v in self.result['scope'].values()))


if __name__=='__main__':unittest.main()
