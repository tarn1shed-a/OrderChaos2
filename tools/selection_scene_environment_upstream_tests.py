"""Original registry, complete catalog and fresh selection environment checks."""
import json
import unittest
from pathlib import Path

from resource_packs import DEFAULT_SOURCE
from map_loading_evidence import Sources
from scene_active_lighting import NativeTargetProbe
from scene_environment_state import initial_environment,sample
from skill_attachments import decode_ftable
from selection_scene_environment_upstream_probe import ROOT,UpstreamProbe,investigate,fresh_inputs

NATIVE=ROOT/'analysis/raw/beff-native/library.so'
EVIDENCE=ROOT/'analysis/raw/selection-scene-environment-20261115/v3/evidence.json'


@unittest.skipUnless(NATIVE.is_file()and EVIDENCE.is_file()and(Path(DEFAULT_SOURCE)/'tables.bin').is_file(),
                    'Original client/map7 environment data stays private')
class SelectionEnvironmentUpstreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes());cls.result=investigate(cls.image)

    def test_registered_login_and_selection_factories_produce_distinct_real_current_stages(self):
        for stage,factory in [(0,'0x54b1e0'),(1,'0x54b2a8')]:
            result=UpstreamProbe(self.image).startup_dispatch(stage)
            self.assertTrue(result['initialCurrentStateNull']);self.assertTrue(result['outerInstalledByOriginalFunction'])
            self.assertEqual(result['factory'],factory)
            self.assertEqual(result['parentCurrentStage'],stage)
            self.assertEqual(result['worldModeAtFactoryBoundary'],stage)
            self.assertEqual(result['parentRequestedStage'],-1)
            self.assertFalse(result['factoryExecuted']);self.assertFalse(result['loginApprovalTriggerExecuted'])

    def test_full_original_catalog_rebuild_does_not_clear_preexisting_environment_queue(self):
        q=self.result['mapAndQueues']
        self.assertEqual(q['mapAfter'],7);self.assertEqual(q['nativeCatalogIds'],[211,422,453,463])
        self.assertTrue(q['originalCatalogRebuildExecuted']);self.assertTrue(q['originalDerivedCatalogPostprocessExecuted'])
        self.assertTrue(q['environmentObjectSame']);self.assertTrue(q['environmentBytesUnchanged'])
        self.assertTrue(q['queuedTargetBytesUnchanged']);self.assertTrue(q['queueExistsAfterRebuild'])
        self.assertEqual(q['environmentWrites'],[])

    def test_original_immediate_target_writer_clears_stale_queues_in_the_covered_thirteen_channels(self):
        source=Sources(DEFAULT_SOURCE)
        region,=[r for r in decode_ftable(source.read('tables/zones.tbl'),'ID')['rows']if r['ID']==211]
        env=initial_environment()
        for value in env.values():value.set([.125]*len(value.base),2000)
        self.assertTrue(all(v.pending for v in env.values()))
        actual=NativeTargetProbe(self.image).run(env,region,None,1)
        self.assertTrue(all(not v.pending for v in actual.values()))
        self.assertEqual(sample(actual),self.result['freshStart']['immediateValuesFromOriginalTargetWriter'])

    def test_fresh_original_environment_renderer_and_weather_producers_close_field_inputs(self):
        f=self.result['freshStart']
        self.assertEqual(f['initialValuesFromOriginalConstructor'],sample(initial_environment()))
        self.assertFalse(f['catalog']['queueExistsAfterRebuild'])
        self.assertEqual(f['selectedBaseIdFromOriginalRebuiltCatalog'],211)
        self.assertEqual(f['rendererRGBAddsFromOriginalConstructor'],[0.,0.])
        self.assertEqual(f['weatherFirst72BytesBeforeRequest'],[0]*18)
        self.assertEqual(f['weatherFirst72BytesAfterOriginalZeroRequest'],[0]*18)
        self.assertEqual(f['nativeRGB']['submitted']['light_model_lightMap'],[1.9950001239776611,1.9245884418487549,1.8202745914459229])
        self.assertFalse(f['originalCompleteFrameOrGPUClaimed'])

    def test_fresh_input_bridge_is_explicitly_scoped_and_does_not_activate_reentry_sky_or_bloom(self):
        e=json.loads(EVIDENCE.read_text());p=fresh_inputs(self.result,e)
        self.assertEqual((p['world'],p['mapId'],p['sourceSelectionRegion']),('selection',7,211))
        self.assertTrue(p['fieldInputsReady']);self.assertTrue(p['freshStartOnly'])
        self.assertFalse(p['reentrySupported']);self.assertFalse(p['skyActivated']);self.assertFalse(p['bloomActivated'])
        self.assertEqual((p['uniformInputs']['sourceFogNear'],p['uniformInputs']['sourceFogSpan']),(58.,148.))
        e['region']['ID']=194
        with self.assertRaises(ValueError):fresh_inputs(self.result,e)
        self.assertFalse(self.result['previewChanged']);self.assertFalse(self.result['savesChanged'])


if __name__=='__main__':unittest.main(verbosity=2)
