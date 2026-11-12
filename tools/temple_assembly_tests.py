"""Source combination identity and original multi-height support observations."""
import copy
import json
import unittest
from pathlib import Path
from temple_assembly_evidence import in_area,transformed_box,compare_instance

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/temple-assembly-20261113'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'

class Public(unittest.TestCase):
    def test_horizontal_inspection_region_does_not_invent_a_playable_height(self):
        self.assertTrue(in_area([-2611,132,185]));self.assertTrue(in_area([-2611,172,185]))
        self.assertFalse(in_area([-2500,132,185]));self.assertFalse(in_area([-2611,132,-64]))

    def test_model_tile_rotation_scale_and_raw_flags_cannot_be_silently_substituted(self):
        row={'id':4,'model':'original','sourceType':2,'sourceWord8':0,'position':[1,2,3],
             'quaternion':[0,0,0,1],'scale':[1,1,1],'tile':[-41,2]}
        compare_instance(row,copy.deepcopy(row))
        for field,value in [('model','other'),('tile',[-40,2]),('position',[1,3,3]),
                            ('quaternion',[0,1,0,0]),('scale',[1,2,1]),('sourceWord8',1)]:
            changed=copy.deepcopy(row);changed[field]=value
            with self.assertRaises(ValueError):compare_instance(row,changed)

    def test_bounds_keep_original_translation_scale_and_reflected_extent(self):
        matrix=[-2,0,0,0,0,3,0,0,0,0,1,0,10,20,30,1]
        self.assertEqual(transformed_box([[-1,-2,-3],[4,5,6]],matrix),[2,14,27,12,35,36])

@unittest.skipUnless((RAW/'assembly-audit.json').is_file(),'Original inputs/complete evidence remain local')
class Original(unittest.TestCase):
    def test_original_defaults_gate_filename_bres_and_all_31_completions_replay(self):
        from temple_assembly_evidence import audit
        report=audit(RUN);expected=json.loads((RAW/'assembly-audit.json').read_text())
        self.assertEqual(report,expected)
        self.assertEqual(report['summary'],{'models':13,'instances':31,'missingStaticInstances':0,'extraStaticInstances':0})
        self.assertFalse(report['originalAndroidFrameObserved']);self.assertFalse(report['gameplayOrGeometryChanged'])
        self.assertEqual(len(report['requestWindow']['staticCandidates']),404)
        self.assertEqual(len(report['requestWindow']['modelRequests']),53)
        self.assertEqual(report['entryEvidence']['mapInfoEnterPosition'],[0,0,0])
        self.assertEqual(report['entryEvidence']['tutorialPlayerSpawnRows'],0)
        self.assertFalse(report['entryEvidence']['originalRuntimeEntryPositionKnown'])

    def test_native_ground_queries_keep_both_levels_and_do_not_call_one_the_original_spawn(self):
        from temple_assembly_evidence import layers
        result=layers(RUN);self.assertEqual(result,json.loads((RAW/'assembly-audit.json').read_text())['layerQueries'])
        self.assertAlmostEqual(result['results'][0]['height'],132.34999084472656)
        self.assertAlmostEqual(result['results'][1]['height'],172.3668975830078)
        self.assertIsNone(result['results'][0]['instanceId']);self.assertEqual(result['results'][1]['instanceId'],715733128)

if __name__=='__main__':unittest.main()
