"""Source-cache projection negatives plus pinned original getter/update execution."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from resource_packs import DEFAULT_SOURCE

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/character-equipped-20261114'
LIBRARY=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
NODE=shutil.which('node')or'/Users/kevin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'


@unittest.skipUnless(Path(NODE).is_file(),'Node unavailable')
class EquippedProjectionTests(unittest.TestCase):
    def run_js(self,body):
        script='import assert from "node:assert/strict";import{projectSourceEquipped}from '+json.dumps((ROOT/'tools/preview/source-equipped-state.mjs').as_uri())+';\n'+body
        result=subprocess.run([NODE,'--input-type=module','-e',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_unknown_identity_and_bank_never_trigger_empty_init_fallback(self):
        self.run_js('''
const role={id:'explicit-fixture',profession:2},catalog=[];
assert.deepEqual(projectSourceEquipped(role,catalog),{known:false,reason:'source-cache-unknown',slots:null,secondarySlots:null});
assert.equal(projectSourceEquipped(role,catalog,{roleId:'other',profession:2}).known,false);
assert.equal(projectSourceEquipped(role,catalog,{roleId:role.id,profession:1}).known,false);
const cache={format:'oc2-original-equipped-cache-v1',roleId:role.id,profession:2,skillPage:2};
assert.equal(projectSourceEquipped(role,catalog,cache).reason,'operation-bank-unknown');
assert.equal(projectSourceEquipped(role,catalog,cache).slots,null);
''')

    def test_equipped_learning_profession_and_basic_attack_stay_separate(self):
        self.run_js('''
const role={id:'explicit-fixture',profession:2};const catalog=[{skillId:90,profession:2,kind:'active',runes:[{index:0,sourceRuneId:100},{index:2,sourceRuneId:102}]}];
const snapshot={format:'oc2-original-equipped-cache-v1',roleId:role.id,profession:2,operationBank:0,skillPage:2,operationBanks:[[-1,90,243,0,0],...[0,1,2,3].map(()=>[0,0,0,0,0])],actorSlots11To20:Array(10).fill(0),selectedRunes:[[90,2]],learningRecords:null,fixture:true};
const before=JSON.stringify(snapshot),out=projectSourceEquipped(role,catalog,snapshot);
assert.equal(out.operationBank,0);assert.equal(out.skillPageRaw,2);assert.equal(out.slots[0].state,'basic-attack-sentinel');assert.equal(out.slots[0].resolvedAttackId,null);
assert.equal(out.slots[1].rawSkillId,90);assert.equal(out.slots[1].baseLearned,null);assert.equal(out.slots[1].castPermission,null);
assert.equal(out.slots[2].catalogKnown,false);assert.equal(out.slots[2].reason,'outside-profession-catalog');
const unlearned=projectSourceEquipped(role,catalog,{...snapshot,learningRecords:[]});assert.equal(unlearned.slots[1].baseLearned,false);assert.equal(unlearned.slots[1].state,'equipped-cache-value');
const selectedOnly=projectSourceEquipped(role,catalog,{...snapshot,learningRecords:[[90,2]]});assert.equal(selectedOnly.slots[1].baseLearned,false);assert.equal(selectedOnly.slots[1].selectedRuneLearned,true);
const learned=projectSourceEquipped(role,catalog,{...snapshot,learningRecords:[[90,0],[90,2]]});assert.equal(learned.slots[1].sourceRuneId,102);assert.equal(learned.slots[1].castPermission,null);
assert.equal(JSON.stringify(snapshot),before);assert(!('icon'in learned.slots[1]));
''')

    def test_malformed_cache_and_cross_profession_catalog_are_rejected(self):
        self.run_js('''
const role={id:'fixture',profession:3},cache={format:'oc2-original-equipped-cache-v1',roleId:'fixture',profession:3,operationBank:0,operationBanks:Array.from({length:5},()=>Array(5).fill(0)),actorSlots11To20:Array(10).fill(0)};
assert.throws(()=>projectSourceEquipped(role,[{skillId:90,profession:2}],cache));
assert.throws(()=>projectSourceEquipped(role,[],{...cache,operationBanks:[[0]]}));
assert.throws(()=>projectSourceEquipped(role,[],{...cache,learningRecords:[[190,4]]}));
assert.throws(()=>projectSourceEquipped(role,[],{...cache,selectedRunes:[[190,-1]]}));
assert.equal(projectSourceEquipped(role,[],cache).slots.length,5);assert.equal(projectSourceEquipped(role,[],cache).secondarySlots.length,10);
''')


@unittest.skipUnless(LIBRARY.is_file()and all((DEFAULT_SOURCE/n).is_file()for n in ['tables.bin','ui.bin','conf.bin']),'Original APK/download inputs remain private')
class OriginalEquippedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from character_equipped_evidence import recover,load_tables
        from character_equipped_probe import CharacterEquippedProbe
        RAW.mkdir(parents=True,exist_ok=True);cls.temp=tempfile.TemporaryDirectory(prefix='test-',dir=RAW)
        cls.report=recover(Path(cls.temp.name)/'evidence');cls.tables,_=load_tables();cls.probe=CharacterEquippedProbe(NativeImage(LIBRARY.read_bytes()))

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_getter_executes_type4_actual_slots_and_type5_selection_distinctly(self):
        values=self.report['samples']['getters'];self.assertEqual([v['returned']for v in values],[94.0,90.0,0.0,0.0])
        p=self.probe
        self.assertEqual(p.get_slot(5,0,entries=[(5,0,90)],argument_count=1)['returned'],0.0)
        self.assertEqual(p.get_slot(5,0,entries=[(5,0,999999)])['returned'],999999.0)
        self.assertEqual(p.get_slot(4,0,entries=[(4,0,6)],active_slots=[-1,94,17,0,0])['returned'],0.0)

    def test_init_page_field_is_not_operation_bank_and_invalid_active_slot_is_ignored(self):
        state=self.report['samples']['explicitEquip']['state']
        self.assertEqual(state['skillPage'],2);self.assertEqual(state['operationBanks'][0],[0,90,0,0,0]);self.assertEqual(state['operationBanks'][3],[0]*5)
        self.assertEqual(state['actorSlots11To20'][0],404);self.assertEqual(state['activeLearning'][0],[1,0,1,0]);self.assertEqual(state['selectedRunes'][0],2)

    def test_original_empty_equip_fallback_does_not_grant_learning_for_any_profession(self):
        for profession in range(1,6):
            report=self.report['samples']['emptyEquip'][str(profession)];catalog=self.report['catalogs'][str(profession)]
            first=[s['skillId']for s in catalog if s['kind']=='active'][:4]
            self.assertEqual(report['state']['operationBanks'][0],[-1,*first])
            self.assertTrue(all(v==[0]*4 for v in report['state']['activeLearning']))
            self.assertEqual(report['configReads'],[{'section':'test','key':'NumOfSkillToShow','default':6}])
        a=self.report['samples']['emptyEquip']['2']['state'];b=self.report['samples']['configFour']['state'];self.assertEqual(a['operationBanks'],b['operationBanks'])
        one=self.probe.receive_init_equipped(self.tables,num_skills=1)
        self.assertEqual(one['state']['operationBanks'][0],[-1,90,0,0,0])

    def test_receipt_consumer_trusts_fields_without_learning_or_success_bool_validation(self):
        for report in self.report['samples']['equipReceipts']:
            self.assertEqual(report['state']['operationBanks'][2],[0,90,0,0,0]);self.assertTrue(all(v==[0]*4 for v in report['state']['activeLearning']))
        foreign=self.probe.receive_equip(self.tables,243,0,2,profession=2)
        self.assertEqual(foreign['state']['operationBanks'][0][1],243)
        ignored=self.probe.receive_equip(self.tables,94,0,6)
        self.assertEqual(ignored['state']['operationBanks'][0],[0]*5)
        secondary=self.probe.receive_equip(self.tables,404,0,11)
        self.assertEqual(secondary['state']['actorSlots11To20'][0],404)

    def test_original_outgoing_serializers_do_not_acknowledge_or_grant_equipment(self):
        requests=self.report['samples']['requests']
        self.assertEqual(requests['page']['packets'][0]['id'],0xac);self.assertEqual(requests['page']['packets'][0]['fields'],{'page':2});self.assertEqual(requests['page']['storedPage'],0)
        self.assertEqual(requests['active']['packets'][0]['id'],0x47);self.assertEqual(requests['active']['packets'][0]['fields'],{'skill_proto_id':90,'skill_rune':0,'slot':2})
        self.assertEqual(requests['invalidActiveSlot']['packets'],[])

    def test_source_schema_constants_and_android_config_selection_are_kept_explicit(self):
        schema=self.report['schema'];init=schema['SMSG_SkillInit']
        self.assertEqual([(f['name'],f['number'])for f in init['fields']],[('learn_skills',1),('equip_skills',4),('shortcut_infos',8),('skill_page',13)])
        self.assertEqual([f['name']for f in schema['CMSG_EquipSkill']['fields']],['skill_proto_id','skill_rune','slot','is_success'])
        for constants in self.report['constants'].values():self.assertEqual(constants['OPIT_SLOTSKILLSLOT'],4);self.assertEqual(constants['OPIT_SLOTSKILLITEM'],5)
        configs=self.report['configs'];self.assertEqual(configs['game_a.conf']['NumOfSkillToShowLines'],[]);self.assertEqual(configs['game.conf']['NumOfSkillToShowLines'],[]);self.assertEqual(configs['game_w.conf']['NumOfSkillToShowLines'],['NumOfSkillToShow = 4'])
        self.assertIn('conf/game_a.conf',self.report['configSelection']['boot']);self.assertIn('not audited',self.report['configSelection']['boundary'])

    def test_actual_original_cache_output_feeds_readonly_projection_without_promoting_learning(self):
        if not Path(NODE).is_file():self.skipTest('Node unavailable')
        module=(ROOT/'tools/preview/source-equipped-state.mjs').as_uri();evidence=Path(self.temp.name)/'evidence/evidence.json'
        script='import assert from "node:assert/strict";import fs from "node:fs";import{projectSourceEquipped}from '+json.dumps(module)+';const report=JSON.parse(fs.readFileSync('+json.dumps(str(evidence))+',"utf8"));'+'''
const snapshot=report.mappingSnapshot,before=JSON.stringify(snapshot),out=projectSourceEquipped({id:snapshot.roleId,profession:2},report.catalogs['2'],snapshot);
assert(out.known);assert.equal(out.operationBank,0);assert.equal(out.skillPageRaw,2);
assert.equal(out.slots[1].rawSkillId,90);assert.equal(out.slots[1].selectedRuneIndex,2);assert.equal(out.slots[1].baseLearned,true);assert.equal(out.slots[1].selectedRuneLearned,true);
assert.equal(out.secondarySlots[0].rawSkillId,404);assert.equal(out.secondarySlots[0].catalogKind,'passive');assert.equal(out.secondarySlots[0].baseLearned,false);assert.equal(out.secondarySlots[0].castPermission,null);
assert.equal(out.slots[2].state,'empty');assert.equal(JSON.stringify(snapshot),before);assert(out.fixture);
'''
        result=subprocess.run([NODE,'--input-type=module','-e',script],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
