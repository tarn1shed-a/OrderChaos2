"""Original incoming skill-record semantics; never use an existing role/save."""
import copy
import tempfile
import unittest
from pathlib import Path

from character_learning_state import CharacterLearningProbe, project_learning_records, skill_init_fixture, varint
from character_progression_evidence import ROOT, recover
from character_progression_tests import LIBRARY, fixture_tables
from character_progression_evidence import profession_catalog
from resource_packs import DEFAULT_SOURCE


class LearningBoundaryTests(unittest.TestCase):
    def test_unknown_snapshot_empty_snapshot_and_source_rune_index(self):
        tables,names=fixture_tables();catalog=profession_catalog(tables,names,1)
        self.assertEqual(project_learning_records(catalog)['skills'],None)
        empty=project_learning_records(catalog,[])
        self.assertTrue(empty['known']);self.assertEqual(empty['skills'][40],[])
        records=[(40,2),(40,2),(20,0),(60,0),(999,0)];before=copy.deepcopy(records)
        projected=project_learning_records(catalog,records)
        self.assertEqual(projected['skills'][40],[2])
        self.assertEqual(projected['skills'][20],[0])
        self.assertEqual(projected['ignoredSkillIds'],[60,999])
        self.assertEqual(records,before)

    def test_adapter_refuses_unbounded_or_unverified_indices_without_mutation(self):
        tables,names=fixture_tables();catalog=profession_catalog(tables,names,1)
        for records in ([(40,4)],[(40,-1)],[(40,True)],[('40',0)],[(50,1)],[(40,0,1)],{},[(40,0)]*257):
            with self.subTest(records=str(records)[:50]),self.assertRaises(ValueError):
                project_learning_records(catalog,records)
        for value in (-1,True,1<<32,'1'):
            with self.assertRaises(ValueError):varint(value)

    def test_fixture_encoder_uses_original_groups_and_explicit_page(self):
        self.assertEqual(skill_init_fixture([(90,2)],3).hex(),'0b105a18020c6803')
        self.assertEqual(skill_init_fixture([],0),b'\x68\x00')
        for records in ({},[(90,)],[(90,0,1)],[(90,0)]*257):
            with self.assertRaises(ValueError):skill_init_fixture(records)


@unittest.skipUnless(LIBRARY.exists()and(DEFAULT_SOURCE/'tables.bin').exists()and
                     (DEFAULT_SOURCE/'ui.bin').exists(),'Original client remains local')
class OriginalLearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.temp=tempfile.TemporaryDirectory(prefix='character-learning-test-',dir=ROOT/'analysis/raw')
        image=NativeImage(LIBRARY.read_bytes());cls.probe=CharacterLearningProbe(image)
        cls.evidence=recover(DEFAULT_SOURCE,Path(cls.temp.name),image);cls.tables=cls.evidence['tables']

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_actual_original_parse_and_group_records_are_indices_not_bitmasks(self):
        records=[(90,0),(90,2),(94,0),(404,0)]
        result=self.probe.receive_init(self.tables,records,skill_page=2)
        self.assertTrue(result['parserSucceeded'])
        self.assertEqual(result['streamBytesConsumed'],4+len(skill_init_fixture(records,2)))
        self.assertEqual(result['skillPage'],2)
        arcane=next(r for r in result['active']if r['skillId']==90)
        self.assertEqual(arcane['learningBytes'],[1,0,1,0])
        frost=next(r for r in result['active']if r['skillId']==94)
        self.assertEqual(frost['learningBytes'],[1,0,0,0])
        self.assertEqual(frost['locked'][0],1)  # Learned incoming state does not erase level lock.
        passive=next(r for r in result['passive']if r['skillId']==404)
        self.assertEqual(passive['learningByte'],1)
        self.assertEqual(result['counts'],[2,1])  # Passive is not counted as an active base skill.
        projected=project_learning_records(self.evidence['catalogs']['2'],records)
        for row in result['active']:
            self.assertEqual(projected['skills'][row['skillId']],
                             [i for i,b in enumerate(row['learningBytes'])if b])

    def test_original_cross_profession_unknown_and_duplicate_records(self):
        result=self.probe.receive_init(self.tables,[(24,0),(90,0),(0xffffffff,0),(24,0)],profession=1)
        self.assertEqual(result['counts'],[1,0])
        self.assertEqual([(r['skillId'],r['learningBytes'])for r in result['active']if any(r['learningBytes'])],
                         [(24,[1,0,0,0])])
        empty=self.probe.receive_init(self.tables,[])
        self.assertEqual(empty['counts'],[0,0])
        result=self.probe.receive_init(self.tables,[(90,2)])
        self.assertEqual(result['counts'],[0,1])
        self.assertEqual(next(r for r in result['active']if r['skillId']==90)['learningBytes'],[0,0,1,0])

    def test_only_explicit_success_receipt_runs_original_learning_write(self):
        for success in (None,False,True):
            result=self.probe.receive_receipt(self.tables,90,1,success=success,initial=[(90,0)])
            self.assertTrue(result['parserSucceeded'])
            self.assertEqual(result['cacheChanged'],success is True)
            self.assertEqual(result['learnedRuneIndices'][90],[0,1]if success is True else[0])
            self.assertEqual(len(result['appliedInputs']),int(success is True))
        wrong=self.probe.receive_receipt(self.tables,90,0,success=True,profession=1)
        self.assertFalse(wrong['cacheChanged'])
        unknown=self.probe.receive_receipt(self.tables,0xffffffff,0,success=True)
        self.assertFalse(unknown['cacheChanged'])


if __name__=='__main__':
    unittest.main()
