"""Quest227 source/strict asset review checks; no task, server or browser."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import ordinary_quest_227_probe as probe

PUBLIC='--public-only'in sys.argv or os.environ.get('PUBLIC_ONLY')=='1'
if'--public-only'in sys.argv:sys.argv.remove('--public-only')
SOURCE=probe.AREA/'candidate-v2/source-v1.json'
PROFILE=probe.AREA/'resource-review-v4/profile.json'
PRIVATE=not PUBLIC and SOURCE.is_file()and PROFILE.is_file()and probe.SO.is_file()
sha=lambda raw:hashlib.sha256(raw).hexdigest()


class PublicBoundary(unittest.TestCase):
    def test_private_engines_are_lazy(self):
        p=subprocess.run([sys.executable,'-S','-c',"import sys;sys.path.insert(0,'tools');import ordinary_quest_227_probe,ordinary_quest_227_assets;assert 'capstone' not in sys.modules;assert 'unicorn' not in sys.modules"],cwd=probe.ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_unique_original_key_required(self):
        self.assertEqual(probe.only([{'id':7,'v':'a'}],'id',7)['v'],'a')
        for rows,key in[([],7),([{'id':7},{'id':7}],7),([{'id':8}],7)]:
            with self.assertRaises(ValueError):probe.only(rows,'id',key)


@unittest.skipUnless(PRIVATE,'Private original source/library unavailable or public-only')
class Source227(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads(SOURCE.read_text());cls.p=json.loads(PROFILE.read_text())

    def test_quest_is_independent_with_real_minimum_level(self):
        d=self.d;q=d['quest'];self.assertEqual((q['entry'],q['ZoneId'],q['Type'],q['MinLevel'],q['questlevel']),(227,1,2,1,4))
        self.assertEqual((q['RequiredQuest'],q['RequiredOneOfQuest'],q['RemoveQuests'],q['script']),('0','','186',''))
        self.assertEqual([x['entry']for x in d['siblingContext']['ordinaryType2Rows']],[225,226,227,461])
        self.assertEqual(d['siblingContext']['edgesTouchingOrdinary'],[])
        self.assertFalse(d['siblingContext']['questTableHasNextQuestColumn'])
        self.assertTrue(d['siblingContext']['notSuccessorOf461'])

    def test_objective_and_takeback_are_not_gather_461(self):
        self.assertEqual([(x['obj_idx'],x['obj_type'],x['step'],x['value'])for x in self.d['objectives']],[(1,2,1,4),(2,6,2,0)])
        self.assertEqual([(x['type'],x['entry'],x['zone'])for x in self.d['logic']],[(4,50051,0),(1,638,285)])
        self.assertEqual([(x['item_id'],x['count'],x['type'],x['takeback_all'])for x in self.d['takeback']],[(50051,4,2,1)])

    def test_complete_original_loot_reference_is_preserved(self):
        path,=self.d['loot']['sourceItemPaths']
        self.assertEqual(path['victimRows'],[{'id':88,'VictimID':638,'VictimType':1,'LootFilterID':63}])
        self.assertEqual((path['displayFilter']['ID'],path['displayFilter']['filterParent']),(63,51))
        self.assertEqual((path['feature']['FeatureID'],path['feature']['DisplayFilter'],path['feature']['BoxValue']),(74,63,1.0))
        item=path['item'];self.assertEqual((item['id'],item['FeatureID'],item['LootItemID'],item['Chance'],item['CountMin'],item['CountMax']),(89,74,50051,1.,1,1))
        self.assertFalse(self.d['loot']['originalDropRollOrKillApprovalRecovered'])

    def test_text_numeric_reward_and_no_item_reward(self):
        self.assertEqual(self.d['localized']['Title'],'抓鳄鱼');self.assertEqual(self.d['item50051']['name'],'鳄鱼肉')
        self.assertEqual([self.d['quest'][k]for k in ['RewMoney','RewXP','RewFavor']],[15,1075,6])
        self.assertEqual(self.d['itemRewards'],[])
        self.assertIn('死去的丈夫',self.d['localized']['CompletionText'])

    def test_npc_default_appearance_and_non_activity_input(self):
        n=self.d['npcAndMonster']['872'];self.assertEqual((n['appearance']['name'],n['display']['ID'],n['model']['ID'],n['extra']['ID']),(925,852,32,720))
        spawn,=n['spawns'];self.assertEqual((spawn['id'],spawn['phase'],spawn['phasing_id'],spawn['manual_spawn']),(2535,0,0,0))
        self.assertEqual((n['proto']['script'],n['proto']['quest_visible_id'],n['proto']['InteractiveRadius']),('',0,0))
        native=self.d['nativeDefaultRequests'];self.assertFalse(native['actorOrModelCompleted'])
        parts=native['npc872']['parts'];self.assertEqual((parts['slots'][0],parts['slots'][1],parts['slots'][11],parts['slots'][14]),(1,1,100009,100012))

    def test_monster_static_zone_input_is_not_activity(self):
        n=self.d['npcAndMonster']['638'];self.assertEqual((n['display']['ID'],n['display']['Model'],n['model']['Flags']),(630,49,1))
        self.assertEqual(len(n['spawns']),11)
        self.assertTrue(all((x['phase'],x['phasing_id'],x['manual_spawn'])==(0,0,0)for x in n['spawns']))
        spawn=probe.only(n['spawns'],'id',2576);self.assertEqual(spawn['movetype'],0)
        zone=probe.only(self.d['zones'],'ID',285)
        self.assertLess(abs(spawn['position_x']-zone['x']),zone['box_x']/2)
        self.assertLess(abs(spawn['position_z']-zone['z']),zone['box_z']/2)

    def test_finish_object_preserves_scale_and_phase_alternative(self):
        f=self.d['finishObject'];q=self.d['quest']
        self.assertEqual((q['FinishGiverType'],q['FinishGiverID'],f['proto']['Type'],f['proto']['spellid']),(2,218,6,0))
        self.assertEqual((f['proto']['script'],f['proto']['interactiveRange'],f['proto']['display_filter']),('',300.,221))
        a=probe.only(f['spawns'],'id',783);b=probe.only(f['spawns'],'id',1795)
        self.assertEqual((a['phasing_id'],b['phasing_id']),(0,2));self.assertAlmostEqual(a['scale_x'],1.4025800228118896)
        self.assertEqual(f['display']['scale'],0.)

    def test_override_stem_is_formatted_by_original_code(self):
        requests=self.d['nativeDefaultRequests']['npc872']['requests'];r=probe.only(requests,'slot',11);o,=r['overrideResources']
        self.assertEqual(o['path'],'texture/oc2_human_f_npc_villager_chest_d.tga')
        self.assertIn(o['path'],self.d['resources']);self.assertNotIn(o['stem'],self.d['resources'])
        self.assertFalse(o['compiledReflectionObserved']);self.assertFalse(o['originalRequest']['textureSet'])
        self.assertEqual(o['originalRequest']['overrideCachePointer'],0)

    def test_all_original_copies_have_archive_crc_and_sha(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE,read_entry
        s=Sources(DEFAULT_SOURCE)
        for name,record in self.d['resources'].items():
            with self.subTest(resource=name):
                candidates=s.candidates(name);self.assertEqual(len(candidates),record['candidateCount'])
                for e,p in zip(candidates,record['candidates']):
                    raw=read_entry(e,s.root);self.assertEqual((e['pack'],sha(raw),len(raw),f"{e['crc']:08x}"),(p['pack'],p['sha256'],p['bytes'],p['crc32']))
                if record['selected']:
                    copy=SOURCE.parent/record['copiedTo'];self.assertEqual(sha(copy.read_bytes()),record['selected']['sha256'])
        for name,p in self.d['sourceProofs'].items():self.assertEqual(sha(s.read(name)),p['sha256'])

    def test_source_cpu_replay(self):
        from analyze_native_resources import NativeImage
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        actual=probe.original_requests(NativeImage(probe.SO.read_bytes()),Sources(DEFAULT_SOURCE),self.d['npcAndMonster']['872']['model']['ModelPath'])
        self.assertEqual(actual,self.d['nativeDefaultRequests'])

    def test_model_geometry_skins_and_reused_original_cpu_are_separate(self):
        self.assertEqual(len(self.p['models']),7)
        rows={x['source']:x for x in self.p['models']};base=rows[self.d['npcAndMonster']['872']['model']['ModelPath']]
        self.assertFalse(base['strictSkin']['accepted']);self.assertEqual(base['nativeBaseReuse']['meshCount'],12)
        self.assertTrue(base['nativeBaseReuse']['allSourceGeometryAndTRSEqual']);self.assertTrue(base['nativeBaseReuse']['noPlayerOutfitCopied'])
        for f in base['nativeBaseReuse']['files'].values():self.assertEqual(sha((probe.ROOT/f['path']).read_bytes()),f['sha256'])
        croc=rows[self.d['npcAndMonster']['638']['model']['ModelPath']];self.assertEqual((croc['vertices'],croc['nodes']),(1266,37));self.assertTrue(croc['strictSkin']['sourceFloatWeightsRetained'])
        for m in rows.values():
            self.assertFalse(m['renderAdmitted']);self.assertEqual(sha((PROFILE.parent/m['parsed']['path']).read_bytes()),m['parsed']['sha256'])

    def test_original_cold_res_t_choice_and_decoded_pngs(self):
        from PIL import Image
        choice=self.p['coldArchiveChoices']['texture/lightmap.tga'];self.assertEqual(choice['trace']['selected'],'res_t_upd10.bin')
        self.assertEqual(choice['trace']['attempts'],['res_t_upd10.bin']);self.assertTrue(choice['emptyNameCache']);self.assertFalse(choice['actualAndroidVFSObserved'])
        self.assertEqual(len(self.p['textures']),30)
        for r in self.p['textures'].values():
            file=PROFILE.parent/r['png'];self.assertEqual(sha(file.read_bytes()),r['pngSHA256'])
            with Image.open(file)as im:self.assertEqual(list(im.size),r['size'])

    def test_animation_gap_is_not_silently_skipped(self):
        a,b=self.p['animations'];self.assertEqual((a['entry'],a['tracks'],a['unboundNodes']),(872,131,[]))
        self.assertEqual(b['entry'],638);self.assertIn('readerRejected',b);self.assertIn('rangeReaderRejected',b)
        self.assertEqual({x['node']for x in b['uncoveredSourceChannels']},{'Camera01-node'})
        self.assertEqual(len(b['uncoveredSourceChannels']),2)
        self.assertFalse(self.p['renderAdmitted']);self.assertFalse(self.p['runtimeEnabled'])
        self.assertIsNone(self.p['actualActivityOrQuestState'])


if __name__=='__main__':unittest.main(verbosity=2)
