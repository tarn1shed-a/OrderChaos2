"""Source-boundary checks; public copies explicitly skip unavailable originals."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path

from tutorial_npc_inventory import selected_names

ROOT=Path(__file__).resolve().parents[1]
NATIVE=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
RAW=ROOT/'analysis/raw/tutorial-npc-recovery-20261114'


def name_fixture():
    schema=b'CREATE TABLE `fixture` (\n`ID` int,\n`SC` text\n);\0'
    identifiers=[10,20];ids=44+len(schema);types=ids+8;rows=types+3;pool=rows+20
    data=bytearray(b'FTABLE\0\0'+struct.pack('<9I',0x100000,2,2,ids,types,rows,10,pool,0)+schema)
    data+=struct.pack('<2I',*identifiers)+b'us\0'
    data+=struct.pack('<IIH',10,pool,4)+struct.pack('<IIH',20,pool+4,2)
    data+='名'.encode()+b'\0\xed\0'
    return bytes(data)


class PublicBoundaryTests(unittest.TestCase):
    def test_unrelated_bad_utf8_is_never_substituted_or_decoded(self):
        values,proof=selected_names(name_fixture(),{0,10})
        self.assertEqual(values,{10:'名'})
        self.assertTrue(proof['allPhysicalSpansChecked'])
        self.assertFalse(proof['allTextDecoded'])
        with self.assertRaises(UnicodeDecodeError):selected_names(name_fixture(),{20})

    def test_missing_or_invalid_selected_span_is_refused(self):
        with self.assertRaisesRegex(ValueError,'missing'):selected_names(name_fixture(),{30})
        raw=bytearray(name_fixture());rows=struct.unpack_from('<I',raw,28)[0]
        struct.pack_into('<I',raw,rows+4,len(raw)+10)
        with self.assertRaisesRegex(ValueError,'span'):selected_names(bytes(raw),{10})


@unittest.skipUnless(NATIVE.exists(),'Original pinned library/source assets are private and unavailable')
class OriginalSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from tutorial_npc_native_probe import TutorialNPCProbe
        cls.image=NativeImage(NATIVE.read_bytes());cls.sources=Sources(DEFAULT_SOURCE)
        cls.probe=TutorialNPCProbe(cls.image,cls.sources)

    def test_default_and_attribute_display_are_separate_native_branches(self):
        a=self.probe.entry_selection(750)['result']
        b=self.probe.entry_selection(750,742)['result']
        self.assertEqual((a['keyAtF20'],a['appearanceKeyAtD2c'],a['protoKeyAtDc8']),(750,750,750))
        self.assertEqual((a['nameIdAtD30'],a['defaultDisplayAtD40'],a['selectedDisplayAtD60']),(786,741,741))
        self.assertEqual((b['defaultDisplayAtD40'],b['selectedDisplayAtD60']),(741,742))
        absent=self.probe.entry_selection(0x7fffffff)
        self.assertIsNone(absent['result']);self.assertEqual(absent['originalReturnWhenNoHandoff'],0)

    def test_original_parts_and_default_idle_do_not_include_a_quest_state(self):
        parts=self.probe.parts(741);idle=self.probe.idle(750,741)
        self.assertEqual(parts['slots'][:3],[2,2,1])
        self.assertEqual([(i,n)for i,n in enumerate(parts['slots'])if n],[(0,2),(1,2),(2,1),(11,100037),(14,100038)])
        self.assertEqual((idle['request'],idle['arg2'],idle['engineFlags']),('idle',1,3))
        self.assertFalse(idle['modelLoaderExecuted']);self.assertNotIn('questAvailability',idle)

    def test_original_race_and_feature_path_recipe(self):
        from tutorial_npc_candidate import MODEL
        self.assertEqual(self.probe.model_race_gender(MODEL),[0,0])
        self.assertEqual(self.probe.feature_path(1,0,0,2,2),'model/item/armor/7_hair/hair_human_male_002_002.bdae')
        self.assertEqual(self.probe.feature_path(0,0,0,2,2),'model/item/armor/9_face/face_human_male_002.bdae')
        self.assertEqual(self.probe.feature_path(9,0,0,2,2),'')

    def test_original_name_mapping_replacement_and_mask_counters(self):
        from tutorial_npc_native_probe import TutorialNPCVisibilityProbe
        p=TutorialNPCVisibilityProbe(self.image)
        body=['arm','chest','crus','foot','hand','head','hip','knee','neck','shoulder','thigh','upper_arm','waist']
        names=p.bind_source_names(body)
        self.assertEqual((names[0],names[10],names[18]),('head','chest','foot'))
        for slot,name in [(0,'source-face'),(1,'source-hair'),(2,'source-beard')]:p.replace_feature(slot,name)
        self.assertFalse(p.visibility()['head']);self.assertTrue(p.visibility()['source-beard'])
        self.assertEqual(p.apply_item_mask(1061146560,768),0x3cff3f00030)
        self.assertEqual(p.apply_item_mask(15728640,0),0x3c00000000)
        self.assertEqual({name for name,visible in p.visibility().items() if visible},{'hand','neck','source-face','source-hair'})

    def test_inventory_retains_unknown_activity_and_source_counts(self):
        from tutorial_npc_inventory import audit
        result=audit();row=next(r for r in result['creatures']if r['entry']==750)
        self.assertEqual(result['summary']['spawns'],67);self.assertEqual(result['summary']['entries'],22)
        self.assertEqual(row['name'],'烈焰骑士治疗师');self.assertEqual(row['questStartReferences'],[202])
        self.assertIsNone(row['runtimeExistence']);self.assertIsNone(row['runtimeGUID']);self.assertIsNone(row['questAvailability'])
        self.assertEqual(row['spawns'][0]['id'],2482)

    @unittest.skipUnless((RAW/'candidate-v3/package-files.json').exists(),'Private visible candidate not generated')
    def test_private_bundle_integrity_and_binding(self):
        output=RAW/'candidate-v3';manifest=json.loads((output/'manifest.json').read_text())
        record=json.loads((output/'package-files.json').read_text())
        for name,expected in record['files'].items():
            raw=(output/name).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),expected['sha256'],name)
        model=json.loads((output/'assets/npc750.json').read_text())
        self.assertEqual(len(model['meshes']),18);self.assertEqual(len(model['rig']['skins']),18)
        self.assertEqual(len(model['clips']),1);self.assertEqual(model['clips'][0]['duration'],4)
        self.assertEqual(len(manifest['visibleMeshIndices']),6)
        self.assertIsNone(manifest['runtimeGUID']);self.assertFalse(manifest['liveActor'])
        chest=next(m for m in model['meshes']if m['name']=='oc2_human_m_npc_flame_knight_villager_chest-mesh')
        self.assertEqual(chest['sourceTangentBindings']['sourceTangents']['stride'],64)
        self.assertEqual(chest['sourceTangentBindings']['sourceTangents']['offset'],40)
        self.assertEqual(chest['sourceTangentBindings']['sourceBinormals']['offset'],52)
        for skin in model['rig']['skins']:
            self.assertLess(skin['verification']['maximumRestBindShapeError'],.002)


if __name__=='__main__':unittest.main()
