import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from resource_packs import DEFAULT_SOURCE, ResourceArchive
from skill_ui_assets import mage_catalog, recover_skill_ui


def fixtures():
    protos=[{'skillId':10,'reqProfession':2,'filter':4,'editName':'sample',
        **{'rune'+str(i):100+i for i in range(4)},
        **dict.fromkeys(['powerCost','coolDownTime','chantTime','channelTime'],0)},
        {'skillId':11,'reqProfession':0,'filter':74,'editName':'shared-passive',
         'rune0':104,**dict.fromkeys(['powerCost','coolDownTime','chantTime','channelTime'],0)}]
    runes=[{'id':100+i,'icon':'skill/example.png','nameStrId':i*2+1,'descStrId':i*2+2} for i in range(5)]
    unlocks=[{'id':i,'needprofession':2,'skill_id':10 if i<4 else 11,'rune_id':i if i<4 else 0,
              'category':0,'needlevel':1+i,'needskillpoints':i} for i in range(5)]
    names={i:'Example '+str(i) for i in range(1,11)}
    return protos,runes,unlocks,names


class SkillUITests(unittest.TestCase):
    def test_join_follows_unlock_and_rune_ids_including_shared_passive(self):
        result=mage_catalog(*fixtures())
        self.assertEqual([s['id'] for s in result],[10,11])
        self.assertEqual([s['kind'] for s in result],['active','passive'])
        self.assertEqual([r['runeId'] for r in result[0]['runes']],[101,102,103])
        self.assertEqual(result[0]['runes'][1]['requirement'],{'level':3,'points':2,'sourceRowId':2})
        self.assertNotIn('learned',result[0])

    def test_incomplete_or_duplicate_unlocks_cannot_silently_build_a_catalog(self):
        for variant in ('missing-rune','duplicate','unsafe-icon','missing-name','profession'):
            protos,runes,unlocks,names=copy.deepcopy(fixtures())
            if variant=='missing-rune':unlocks.pop(1)
            elif variant=='duplicate':unlocks.append(unlocks[0])
            elif variant=='unsafe-icon':runes[0]['icon']='../../secret.png'
            elif variant=='missing-name':names.pop(1)
            else:protos[0]['reqProfession']=3
            with self.subTest(variant=variant),self.assertRaises(ValueError):
                mage_catalog(protos,runes,unlocks,names)

    @unittest.skipUnless(all((DEFAULT_SOURCE/(name+'.bin')).is_file()
        for name in ('ui','conf','tables','ui_icon_1')), 'Original art remains local-only')
    def test_real_config_display_lists_and_catalog_image_bytes(self):
        packs={name:ResourceArchive(DEFAULT_SOURCE/(name+'.bin')) for name in ('ui','conf','tables','ui_icon_1')}
        def read(path):
            pack='conf' if '/Config/' in path else 'tables' if path.startswith('tables/') else 'ui_icon_1' if path.startswith('ui/icons/') else 'ui'
            return packs[pack].read(path)
        with tempfile.TemporaryDirectory() as td:
            profile=recover_skill_ui(read,td)
            active=[s for s in profile['skills'] if s['kind']=='active']
            self.assertEqual(len(active),9);self.assertEqual(len(profile['skills']),14)
            self.assertFalse(profile['provenance']['nativeProgressionImplemented'])
            self.assertFalse(profile['provenance']['swfScriptExecution'])
            frost=next(s for s in active if s['id']==94)
            self.assertEqual(frost['base']['requirement']['level'],10)
            self.assertEqual(frost['base']['requirement']['points'],1)
            self.assertEqual([r['requirement']['level'] for r in frost['runes']],[22]*3)
            field=profile['layouts']['active']['fields']['_RuneList.item_0.btnItemX']
            self.assertEqual(field['leafCharacterId'],1683)
            self.assertAlmostEqual(field['matrixPixels'][4],547.6)
            for skill in profile['skills']:
                for entry in [skill['base'],*skill['runes']]:
                    icon=entry['icon'];raw=(Path(td)/icon['url'].removeprefix('/assets/')).read_bytes()
                    self.assertEqual(raw,read(icon['sourcePath']))
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),icon['sourceSHA256'])
                    with Image.open(Path(td)/icon['url'].removeprefix('/assets/')) as image:self.assertEqual(image.size,(96,96))


if __name__=='__main__':unittest.main()
