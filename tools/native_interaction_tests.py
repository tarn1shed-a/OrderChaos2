import hashlib,unittest
from pathlib import Path
from native_interaction import recover_interactions,verify_interaction_native,NATIVE_ROUTINES
from resource_packs import DEFAULT_SOURCE,ResourceArchive
ROOT=Path(__file__).resolve().parents[1]

class NativeInteractionTests(unittest.TestCase):
    def test_changed_descriptor_requires_retrace(self):
        class Changed:
            def read(self,a,n):return bytes(n)
        with self.assertRaisesRegex(ValueError,'retrace'):verify_interaction_native(Changed())

    @unittest.skipUnless((ROOT/'analysis/raw/beff-native/library.so').is_file(),'Native library stays local')
    def test_pinned_interaction_dispatch_and_distinct_loot_messages(self):
        from analyze_native_resources import NativeImage
        image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())
        p=verify_interaction_native(image)
        self.assertEqual([(f['name'],f['number'],f['type']) for f in p['C2GS_Loot']['fields']],[('guid',1,4),('loot',2,8)])
        self.assertEqual([f['name'] for f in p['C2GS_PickLootItem']['fields']],['guid','item_id'])
        self.assertEqual([f['name'] for f in p['C2GS_Interactive']['fields']],['guid','interactive_id','skill_id'])
        for address,(size,digest) in NATIVE_ROUTINES.items():self.assertEqual(hashlib.sha256(image.read(address,size)).hexdigest(),digest)

    @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(),'Original tables stay local')
    def test_source_objects_quest_links_and_counts_are_evidence_without_activated_scripts(self):
        archive=ResourceArchive(DEFAULT_SOURCE/'tables.bin');p=recover_interactions(archive.read)
        self.assertEqual(p['npcInteractionCount'],134);self.assertEqual(p['lootRecordCount'],4566)
        self.assertEqual({s['id'] for s in p['previewObjectSpawns']},{2971,3064,3065})
        objects={v['entry']:v for v in p['previewObjectProtos']}
        self.assertEqual(objects[610]['script'],'quest572_obj610');self.assertEqual(objects[621]['script'],'quest632_obj621')
        self.assertEqual({v['entry'] for v in p['questReferences']['quests']},{572,632})
        self.assertTrue(p['button']['nonemptyFunctionReplacesJump'])
        self.assertTrue(any('not activated' in v for v in p['limitations']))

if __name__=='__main__':unittest.main()
