"""Missing-camera data, source quest links and original post-cinematic writes."""
import json
import unittest
from pathlib import Path
from tutorial_entry_clues import camera_track

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/tutorial-entry-clues-20261113'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'

class LiteralData(unittest.TestCase):
    def test_current_camera_is_not_replaced_with_a_zero_or_character_position(self):
        r=camera_track({'w8pointcount':'1','w8point1':'CURRENT','w8dir1':'CURRENT','w8speed1':'0'},8)
        self.assertEqual(r['points'][0]['point'],'CURRENT')
        self.assertEqual(r['points'][0]['dir'],'CURRENT')
        self.assertIsNone(r['endPosition'])

    def test_incomplete_track_is_rejected_instead_of_filling_missing_source_points(self):
        with self.assertRaises(KeyError):camera_track({'w7pointcount':'2','w7point1':'1,2,3'},7)

@unittest.skipUnless((RAW/'clues-audit.json').is_file(),'Original camera, quest and native inputs stay local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tutorial_entry_clues import probe_runtime
        cls.report=probe_runtime(RUN)

    def test_original_code_and_source_inputs_replay_exactly(self):
        self.assertEqual(self.report,json.loads((RAW/'clues-audit.json').read_text()))

    def test_original_finish_moves_the_role_to_source_endpoint_with_queried_support(self):
        a,b=self.report['cases'][:2]
        self.assertEqual(a['parsedEndPosition'],[-2594,136,-64])
        self.assertEqual(a['resultPosition'],[-2594,135.72999572753906,-64])
        self.assertEqual(a['resultPosition'],a['resultPendingPosition'])
        self.assertEqual(a['resultPosition'],b['resultPosition'])
        self.assertEqual(a['endRadius'],0)
        self.assertEqual(a['explicitRandomCalls'][-1]['range'],[0,0])

    def test_camera8_absent_endpoint_does_not_create_a_role_position(self):
        r=self.report['cases'][2]
        self.assertEqual(r['originalAcceptBranch'],'0x52b2e8')
        self.assertFalse(r['endPositionEnabled'])
        self.assertEqual(r['resultPosition'],r['initialPosition'])
        self.assertEqual(r['explicitRandomCalls'],[])

    def test_task_route_is_linked_but_not_promoted_to_the_original_first_spawn(self):
        s=self.report['sources'];route=s['quest']['route']
        self.assertEqual([r['step']for r in route],list(range(1,11)))
        self.assertEqual([r['zoneId']for r in route],[341,252,644,253,253,256,1819,255,257,258])
        self.assertTrue(all(r['mapId']==5 for r in route))
        self.assertEqual(s['configs']['game.conf']['tracks']['7'],s['configs']['game_a.conf']['tracks']['7'])
        self.assertEqual(s['configs']['game.conf']['tracks']['7'],s['configs']['game_w.conf']['tracks']['7'])
        self.assertEqual(self.report['sourceEndDirectionNumericSuffix'],[-2603,138,-64])
        self.assertEqual(s['scriptBodyMatchingResourceNames'],[])
        self.assertFalse(s['originalFirstEntryKnown']);self.assertFalse(s['camera7IsProvedFirstEntry'])
        self.assertFalse(self.report['gameplayChanged'])

if __name__=='__main__':unittest.main()
