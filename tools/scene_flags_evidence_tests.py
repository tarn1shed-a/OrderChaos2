"""Flag evidence and refusal checks; these are not playback/rendering tests."""
import hashlib,json,struct,tempfile,unittest
from pathlib import Path
from scene_flags_evidence import audit,literal_nodes,controller_evidence,animation_evidence,MODELS
from tutorial_map_geometry import ROOT
from bdae_convert import BDAE

RAW=ROOT/'analysis/raw/map-flags-20261112'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'

class Public(unittest.TestCase):
    def test_missing_node_scene_cannot_become_an_identity_transform(self):
        class Empty:
            def section(self,offset):return 0,0
        with self.assertRaises(ValueError):literal_nodes(Empty())
    def test_missing_controller_cannot_be_replaced_with_a_static_mesh(self):
        class Empty:
            def section(self,offset):return 0,0
        with self.assertRaises(ValueError):controller_evidence(Empty(),{},[])

@unittest.skipUnless((RAW/'fk_flag.bdae').is_file()and (RAW/'verified/flags-evidence.json').is_file(),'Original flag resources and native evidence stay local')
class Original(unittest.TestCase):
    def test_both_raw_skins_keep_original_nonidentity_rest_and_raw_weights(self):
        from bdae_skin import recover_skin
        for stem,count in [('fk_flag',9),('fk_flag_01',7)]:
            b=BDAE(RAW/(stem+'.bdae'));model=b.parse();skin=controller_evidence(b,model,literal_nodes(b))
            self.assertEqual(len(skin['bones']),count);self.assertFalse(skin['runtimePoseAccepted']);self.assertFalse(skin['normalizationApplied'])
            self.assertGreater(max(x['restProductErrorDiagnosticOnly']for x in skin['bones']),.1)
            with self.assertRaisesRegex(ValueError,'bind shape'):recover_skin(b,model)
    def test_original_kind_and_weight_bounds_are_not_relaxed(self):
        b=BDAE(RAW/'fk_flag.bdae');model=b.parse();nodes=literal_nodes(b);_,t=b.section(188);raw=b.b;changed=bytearray(raw);struct.pack_into('<I',changed,t,1);b.b=bytes(changed)
        with self.assertRaisesRegex(ValueError,'kind0'):controller_evidence(b,model,nodes)
        b.b=raw;wr=b.rel(t+16);data=b.q(wr+8)+((b.u(wr+4)&0xffffff)-1)*8;changed=bytearray(raw);struct.pack_into('<Q',changed,data+112,4);b.b=bytes(changed)
        with self.assertRaisesRegex(ValueError,'length'):controller_evidence(b,model,nodes)
    def test_byte_time_is_retained_without_claiming_native_playback(self):
        for stem,count in [('fk_flag',27),('fk_flag_01',21)]:
            b=BDAE(RAW/(stem+'.bdae'));result=animation_evidence(b);self.assertEqual(len(result['channels']),count);self.assertEqual(result['ranges'][0]['endMs'],4000)
            self.assertFalse(result['runtimeTracksCreated']);self.assertFalse(result['originalTimeConsumerVerified']);self.assertFalse(result['autoplayLoopAndPhaseVerified'])
            # The previous uint16 time reader rejects these actual descriptors.
            from bdae_animation import BDAEAnimation
            with self.assertRaisesRegex(ValueError,'encoding'):BDAEAnimation(b.path).channels()
    def test_rebuild_and_original_cpu_boundary_without_changing_preview(self):
        before={str(p.relative_to(RUN/'game-data/converted')):hashlib.sha256(p.read_bytes()).hexdigest()for p in (RUN/'game-data/converted').rglob('*')if p.is_file()};public={str(p.relative_to(RUN/'prototype/public')):hashlib.sha256(p.read_bytes()).hexdigest()for p in (RUN/'prototype/public').rglob('*')if p.is_file()}
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            result=audit(RUN,Path(td));self.assertEqual((Path(td)/'flags-evidence.json').read_bytes(),(RAW/'verified/flags-evidence.json').read_bytes())
        self.assertEqual(len(result['placements']),17);self.assertTrue(all(not p['admittedToPreview']for p in result['placements']));self.assertFalse(result['previewSceneChanged'])
        for m in result['models']:
            boundary=m['nativeBoundary'];self.assertEqual(boundary['entry'],'0x5519cc');self.assertTrue(boundary['originalCPU']);self.assertFalse(boundary['factoryExecuted']);self.assertFalse(boundary['GPUResultSupplied'])
        for name,digest in before.items():self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/name).read_bytes()).hexdigest(),digest)
        for name,digest in public.items():self.assertEqual(hashlib.sha256((RUN/'prototype/public'/name).read_bytes()).hexdigest(),digest)

if __name__=='__main__':unittest.main()
