"""747/970 source checks; unavailable original inputs are explicitly skipped."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tutorial_npc_additional_package import package,FORMAT,ROOT

RAW=ROOT/'analysis/raw/tutorial-npc-additional-20261114'
NATIVE=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
CANDIDATE=RAW/'candidate-v2'


class PublicPackageTests(unittest.TestCase):
    def fixture(self,root):
        c=root/'candidate';c.mkdir();(c/'one.json').write_text('{}')
        record={'bytes':2,'sha256':hashlib.sha256(b'{}').hexdigest()}
        (c/'package-files.json').write_text(json.dumps({'format':FORMAT,'privateOnly':True,'files':{'one.json':record}}))
        return c

    def setUp(self):
        RAW.mkdir(parents=True,exist_ok=True)

    def test_private_roundtrip_and_overwrite_refusal(self):
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            root=Path(td);c=self.fixture(root);output=root/'candidate.tar.gz';r=package(c,output)
            self.assertEqual(r['files'],2);self.assertTrue(r['privateOnly'])
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),r['sha256'])
            with self.assertRaisesRegex(ValueError,'preserved'):package(c,output)

    def test_changed_or_additional_inputs_cannot_be_packaged(self):
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            root=Path(td);c=self.fixture(root);output=root/'candidate.tar.gz'
            (c/'one.json').write_text('{ }')
            with self.assertRaisesRegex(ValueError,'SHA'):package(c,output)
            (c/'one.json').write_text('{}');(c/'unexpected.bin').write_bytes(b'x')
            with self.assertRaisesRegex(ValueError,'additional'):package(c,output)
            self.assertFalse(output.exists())


@unittest.skipUnless(NATIVE.exists(),'Original pinned library and resource packs are private')
class OriginalAdditionalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from tutorial_npc_additional_probe import AdditionalNPCProbe
        cls.sources=Sources(DEFAULT_SOURCE);cls.image=NativeImage(NATIVE.read_bytes())
        cls.probe=AdditionalNPCProbe(cls.image,cls.sources)

    def test_actual_original_appearance_keys_and_default_displays(self):
        for entry,name,display in [(747,783,738),(970,1023,949)]:
            r=self.probe.entry_selection(entry)['result']
            self.assertEqual((r['keyAtF20'],r['appearanceKeyAtD2c'],r['protoKeyAtDc8']),(entry,entry,entry))
            self.assertEqual((r['nameIdAtD30'],r['defaultDisplayAtD40'],r['selectedDisplayAtD60']),(name,display,display))
            alternate=self.probe.entry_selection(entry,741)['result']
            self.assertEqual(alternate['selectedDisplayAtD60'],741);self.assertEqual(alternate['defaultDisplayAtD40'],display)

    def test_single_model_branch_does_not_use_human_part_rules(self):
        for display,model in [(738,52),(949,55)]:
            r=self.probe.single_model_request(display)
            self.assertEqual(r['request']['modelId'],model);self.assertEqual(r['request']['modelFlags'],1)
            self.assertFalse(r['request']['part37LoopReached']);self.assertFalse(r['request']['modelLoaderExecuted'])
        self.assertEqual(self.probe.single_model_request(738)['weapons'],[])

    def test_original_idle_requests_have_one_channel_flags(self):
        for entry,display in [(747,738),(970,949)]:
            r=self.probe.idle(entry,display)
            self.assertEqual((r['request'],r['arg2'],r['engineFlags']),('idle',1,1))
            self.assertTrue(r['actorInputsAreFixtures']);self.assertFalse(r['modelLoaderExecuted'])

    def test_970_weapon_request_remains_separate_from_attachment(self):
        r=self.probe.single_model_request(949)['weapons']
        self.assertEqual([(p['mainHand'],p['offHand'],p['arg3'])for p in r],[(200010,0,1)])
        pair=self.probe.weapon_pair(200010,0,1)
        self.assertEqual([(p['itemKey'],p['arg2'],p['arg3'])for p in pair['calls']],[(200010,0,1),(0,1,1)])
        self.assertIsNone(pair['mountOrPostureDecision']);self.assertFalse(pair['resourceAndAttachmentExecuted'])

    @unittest.skipUnless((CANDIDATE/'package-files.json').exists(),'Private candidates not generated')
    def test_visible_candidates_keep_full_source_rigs_idle_and_fx(self):
        manifest=json.loads((CANDIDATE/'manifest.json').read_text())
        self.assertEqual([e['entry']for e in manifest['entries']],[747,970])
        self.assertFalse(manifest['liveActor'])
        for e,expected_nodes,duration,triangles in zip(manifest['entries'],[33,42],[4,2],[2574,794]):
            model=json.loads((CANDIDATE/e['model'].lstrip('/')).read_text())
            self.assertEqual(len(model['meshes']),1);self.assertEqual(len(model['rig']['skins']),1)
            self.assertEqual(len(model['rig']['nodes']),expected_nodes);self.assertEqual(model['clips'][0]['duration'],duration)
            self.assertEqual(e['triangles'],triangles);self.assertIsNone(e['runtimeGUID']);self.assertIsNone(e['worldPlacement'])
            self.assertLess(model['rig']['skins'][0]['verification']['maximumRestBindShapeError'],.002)
        self.assertEqual(manifest['entries'][0]['materials'][0]['alphaTest'],.5)
        self.assertFalse(manifest['entries'][1]['weapon']['mounted'])
        self.assertEqual([(e['questObjectiveRelationship']['objectiveIndex'],e['questObjectiveRelationship']['orderedStep'])
            for e in manifest['entries']],[(7,9),(9,2)])

    @unittest.skipUnless((CANDIDATE/'package-files.json').exists(),'Private candidates not generated')
    def test_candidate_files_and_frozen750_sources_are_unchanged(self):
        files=json.loads((CANDIDATE/'package-files.json').read_text())['files']
        for name,expected in files.items():
            self.assertEqual(hashlib.sha256((CANDIDATE/name).read_bytes()).hexdigest(),expected['sha256'],name)
        old=ROOT/'analysis/raw/tutorial-npc-recovery-20261114/frozen-sha.json'
        if old.exists():
            for name,expected in json.loads(old.read_text()).items():
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected['sha256'],name)


if __name__=='__main__':unittest.main()
