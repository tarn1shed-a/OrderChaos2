"""Source-free negative checks plus pinned original progression execution."""
import copy
import tempfile
import unittest
from pathlib import Path

from character_progression_evidence import ROOT, profession_catalog, recover, verify_native, wire_fields
from character_skill_progression import CharacterProgressionProbe, inspect_skill
from resource_packs import DEFAULT_SOURCE

LIBRARY = ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'


def fixture_tables():
    protos=[]; runes=[]; unlocks=[]; names={}
    for skill,profession,passive in [(40,1,False),(20,1,False),(50,1,True),(60,2,False)]:
        proto={'skillId':skill,'reqProfession':profession if not passive else 0,
               'filter':74 if passive else 5,'attributes':0x100 if passive else 0}
        for index in range(1 if passive else 4):
            identifier=skill*4+index; proto['rune'+str(index)]=identifier
            runes.append({'id':identifier,'nameStrId':identifier,'icon':'skill/example.png','reqLevel':0})
            names[identifier]='Fixture '+str(identifier)
            unlocks.append({'id':len(unlocks)+1,'skill_id':skill,'rune_id':index,
                'needprofession':profession,'needlevel':1 if index==0 else 7,
                'needskillpoints':0 if index==0 else 3,'category':0})
        protos.append(proto)
    return {'skill_proto':{'rows':protos},'skill_runes':{'rows':runes},
            'skill_unlock':{'rows':unlocks},'skill_tree_filter':{'rows':[
                {'Id':5,'filterName':'Warrior','filterParent':0,'type':0},
                {'Id':74,'filterName':'Passive Skills','filterParent':0,'type':0}]}},names


class ProgressionBoundaryTests(unittest.TestCase):
    def test_profession_and_rune_join_preserve_ids_and_no_learning_state(self):
        tables,names=fixture_tables(); before=copy.deepcopy(tables)
        catalog=profession_catalog(tables,names,1)
        self.assertEqual([r['skillId'] for r in catalog],[40,20,50])
        self.assertEqual(catalog[0]['runes'][2]['sourceRuneId'],162)
        self.assertNotIn(60,[r['skillId'] for r in catalog])
        self.assertTrue(all('learned' not in r and 'equipped' not in r for r in catalog))
        self.assertEqual(tables,before)

    def test_unknown_empty_learned_and_cross_profession_are_distinct(self):
        tables,names=fixture_tables(); catalog=profession_catalog(tables,names,1)
        self.assertEqual(inspect_skill(catalog,40)['learned'],None)
        self.assertEqual(inspect_skill(catalog,40,learning_fixture={})['reason'],'base-not-learned')
        self.assertEqual(inspect_skill(catalog,40,1,learning_fixture={40:[0]})['reason'],'rune-not-learned')
        self.assertEqual(inspect_skill(catalog,40,1,learning_fixture={40:[1]})['reason'],'base-not-learned')
        self.assertFalse(inspect_skill(catalog,60,learning_fixture={60:[0]})['available'])
        self.assertFalse(inspect_skill(catalog,999,learning_fixture={999:[0]})['available'])
        self.assertEqual(inspect_skill(catalog,40,2,learning_fixture={40:[0,2]})['sourceRuneId'],162)
        self.assertFalse(inspect_skill(catalog,50,1,learning_fixture={50:[0,1]})['available'])
        for bad in ({40:[0,0]},{40:[True]},{'40':[0]},{40:[4]}):
            with self.assertRaises(ValueError):inspect_skill(catalog,40,learning_fixture=bad)

    def test_missing_duplicate_or_inconsistent_source_is_rejected(self):
        for variant in ('duplicate','base','profession','rune','name'):
            tables,names=fixture_tables()
            if variant=='duplicate':tables['skill_unlock']['rows'].append(tables['skill_unlock']['rows'][0])
            elif variant=='base':tables['skill_unlock']['rows'].pop(0)
            elif variant=='profession':tables['skill_proto']['rows'][0]['reqProfession']=2
            elif variant=='rune':tables['skill_proto']['rows'][0]['rune1']=9999
            else:names.pop(160)
            with self.subTest(variant=variant),self.assertRaises(ValueError):profession_catalog(tables,names,1)
        tables,names=fixture_tables()
        for bad in (0,6,True,'2'):
            with self.assertRaises(ValueError):profession_catalog(tables,names,bad)

    def test_descriptor_truncation_and_native_identity_fail_closed(self):
        self.assertEqual(list(wire_fields(b'\x08\x01')),[ (1,0,1) ])
        for raw in (b'\x00',b'\x80'*10+b'\x02',b'\x0a\x7fA',b'\x09\x00'):
            with self.assertRaises(ValueError):list(wire_fields(raw))
        class Changed:
            def read(self,address,size):return bytes(size)
        with self.assertRaisesRegex(ValueError,'differs'):verify_native(Changed())


@unittest.skipUnless(LIBRARY.exists() and (DEFAULT_SOURCE/'tables.bin').exists() and
                     (DEFAULT_SOURCE/'ui.bin').exists(),'Original client resources stay local')
class OriginalProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(LIBRARY.read_bytes())
        (ROOT/'analysis/raw').mkdir(exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='character-progression-test-',dir=ROOT/'analysis/raw')
        cls.evidence=recover(DEFAULT_SOURCE,Path(cls.temp.name),cls.image)
        cls.tables=cls.evidence['tables']; cls.probe=CharacterProgressionProbe(cls.image)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_source_table_and_original_ui_inputs_are_not_demo_total_xp(self):
        self.assertEqual(len(self.tables['player_xp']['rows']),108)
        self.assertEqual(self.tables['player_xp']['rows'][0]['xp_levelup'],2403)
        self.assertFalse(any('xp' in c for c in self.tables['playerinfo']['columns']))
        instructions=self.evidence['methods']['ExpBar.refresh']['instructions']
        self.assertTrue(any(i['args']==['xp'] for i in instructions))
        self.assertTrue(any(i['args']==['upgradeXp'] for i in instructions))
        for level in (1,54,55,56):
            result=self.probe.xp_display_slice(level=level,xp=123,upgrade_xp=4567)
            self.assertEqual(result['xp'],4567 if level==55 else 123)
            self.assertEqual(result['upgradeXp'],4567)

    def test_original_catalog_matches_all_five_static_catalogs_and_does_not_learn(self):
        for profession in range(1,6):
            with self.subTest(profession=profession):
                native=self.probe.catalog(self.tables,profession=profession,level=1)
                catalog=self.evidence['catalogs'][str(profession)]
                self.assertEqual([r['skillId'] for r in native['active']],
                                 [r['skillId'] for r in catalog if r['kind']=='active'])
                self.assertEqual([r['skillId'] for r in native['passive']],
                                 [r['skillId'] for r in catalog if r['kind']=='passive'])
                self.assertEqual((len(native['active']),len(native['passive'])),(9,5))
                self.assertTrue(all(r['learnedBytes']==[0]*4 for r in native['active']))
                self.assertTrue(all(r['learnedByte']==0 for r in native['passive']))
                self.assertEqual(native['slots'],[4,2])
                for row,entry in zip(native['active'],[r for r in catalog if r['kind']=='active']):
                    self.assertEqual(row['requiredLevels'],[r['requirement']['needlevel'] for r in entry['runes']])
                    self.assertEqual(row['requiredPoints'],[r['requirement']['needskillpoints'] for r in entry['runes']])

    def test_original_level_boundary_missing_proto_and_slot_table_override(self):
        for level in (9,10,108,109):
            native=self.probe.catalog(self.tables,profession=2,level=level)
            frost=next(r for r in native['active'] if r['skillId']==94)
            self.assertEqual(frost['locked'][0],int(level<10))
            self.assertEqual(frost['learnedBytes'],[0]*4)
            self.assertEqual(native['slots'],[4,2])
            self.assertEqual(native['xpTableLookupFound'],level<=108)
        missing=self.probe.catalog(self.tables,profession=2,level=10,missing_proto_ids=(94,))
        self.assertNotIn(94,[r['skillId'] for r in missing['active']])
        self.assertEqual(self.probe.learned_counts([])['baseCount'],0)
        counts=self.probe.learned_counts([(1,0,1,0),(0,1,0,255)])
        self.assertEqual((counts['baseCount'],counts['runeCount']),(1,3))

    def test_original_learning_requests_are_not_success_or_eligibility(self):
        for skill,rune in ((90,0),(90,1),(24,0),(0xffffffff,99)):
            result=self.probe.learn_request(skill,rune)
            self.assertTrue(result['callbackValid'])
            self.assertEqual(result['packets'][0]['id'],0x8b)
            fields=result['packets'][0]['fields']
            self.assertEqual(fields,{'skill_proto_id':skill,'skill_rune':rune})
            self.assertNotIn('is_success',fields)
            self.assertFalse(result['learningStateChanged'])
        self.assertEqual(self.probe.learn_request(90,0,argument_count=1)['packets'],[])
        self.assertEqual(self.probe.learn_request(90,0,argument_type=5)['packets'],[])
        self.assertEqual(self.evidence['skillProtocol']['SMSG_SkillInit']['fields'][0]['name'],'learn_skills')
        nested=self.evidence['skillProtocol']['SMSG_SkillInit']['nested']
        self.assertEqual(nested[0]['name'],'Learn_skills')
        self.assertEqual([f['name'] for f in nested[0]['fields']],['skill_proto_id','skill_rune'])

    def test_original_creation_indices_and_player_class_constants_match_web(self):
        mapping=self.evidence['professionMapping']
        constants=mapping['asConstants']
        self.assertEqual([constants['PLAYER_CLASS_'+suffix]for suffix in
            ('WARRIOR','MAGE','HUNTER','PRIEST','DEMON_SLAYER')],[1,2,3,4,5])
        self.assertEqual(mapping['creation']['titlesByIndex'],['战士','游侠','法师','血骑士','僧侣'])
        self.assertEqual([self.probe.creation_class(i)['playerClass']for i in range(5)],[1,3,2,5,4])
        for i in (-1,5):
            # Original callback does not validate semantic class range; a true
            # return still leaves the class sentinel untouched for bad indices.
            result=self.probe.creation_class(i)
            self.assertTrue(result['callbackValid'])
            self.assertEqual(result['playerClass'],-99)
        for kw in ({'argument_count':0},{'argument_type':5}):
            result=self.probe.creation_class(2,**kw)
            self.assertFalse(result['callbackValid'])
            self.assertEqual(result['playerClass'],-99)


if __name__=='__main__':
    unittest.main()
