"""Original map7 caller, region selection and environment-state checks."""
import unittest
from pathlib import Path

from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from selection_scene_environment_probe import (ROOT,report,export_inputs,
    SelectionEnvironmentProbe,INPUT_FORMAT)
from scene_zone_selection import ZoneCatalog
from scene_environment_state import initial_environment,sample
from scene_lighting import f32
from skill_attachments import decode_ftable

NATIVE=ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(NATIVE.is_file() and (Path(DEFAULT_SOURCE)/'tables.bin').is_file(),
                     'Original client/table evidence stays private')
class SelectionEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes());cls.evidence=report(cls.image)

    def test_original_caller_passes_camera_zero_delta_and_force_not_environment_mode(self):
        calls=self.evidence['originalCaller']
        self.assertEqual([r['entry']for r in calls],['0x4c1ac4','0x4c4cd0'])
        self.assertEqual((calls[1]['positionPointer'],calls[1]['deltaMs'],calls[1]['forceFlags']),('0x252773c',0,1))
        self.assertEqual(calls[1]['position'],[f32(v)for v in self.evidence['sourceSplashConfigs'][0]['cameraPosition']])
        self.assertEqual([r['entry']for r in self.evidence['conditionalOriginalRefresh']['trace']],['0x4c4de4','0x4c53f0','0x4c5550'])
        self.assertEqual(self.evidence['conditionalOriginalRefresh']['elapsedAfter'],0)

    def test_actual_source_rectangle_includes_boundaries_ignores_y_and_omits_outside(self):
        source=Sources(DEFAULT_SOURCE);rows=decode_ftable(source.read('tables/zones.tbl'),'ID')['rows'];catalog=ZoneCatalog(rows,7)
        probe=SelectionEnvironmentProbe(self.image)
        self.assertEqual([r['ID']for r in catalog.base],[211,422,453,463])
        for point,expected in [([-2688,0,-384],211),([-2432,9000000,64],211),([-2559.42,-9000000,-16.42],211),
                               ([-2688.01,0,-384],None),([-2431.99,0,0],None)]:
            with self.subTest(point=point):self.assertEqual(probe.base_choice(catalog.base,point)['baseId'],expected)
        self.assertEqual(self.evidence['directChildIds'],[])

    def test_original_refresh_force_bit_and_upload_byte_remain_independent(self):
        probe=SelectionEnvironmentProbe(self.image);p=[-2559.42,140.26,-16.42]
        noforce=probe.refresh(p,0,0,elapsed=500,upload_enabled=False)
        force=probe.refresh(p,0,1,elapsed=500,upload_enabled=False)
        upload=probe.refresh(p,0,1,elapsed=500,upload_enabled=True)
        self.assertEqual([r['entry']for r in noforce['trace']],['0x4c5550'])
        self.assertEqual([r['entry']for r in force['trace']],['0x4c4de4','0x4c53f0','0x4c5550'])
        self.assertEqual([r['entry']for r in upload['trace']],['0x4c4de4','0x4c53f0','0x4c5550','0x4bf458'])

    def test_original_conditional_timing_retains_initial_state_then_settles_to_same_source_values(self):
        cases={r['explicitWorldMode']:r for r in self.evidence['targetCases']}
        self.assertEqual(cases[4]['durationMs'],2000)
        self.assertEqual(cases[4]['initial']['values'],sample(initial_environment())['values'])
        self.assertNotEqual(cases[4]['initial']['values'],cases[0]['initial']['values'])
        self.assertEqual(cases[4]['settled'],cases[0]['settled'])
        self.assertEqual(cases[None]['settled'],cases[0]['settled'])
        state=cases[0]['settled']['values']
        self.assertEqual(state['toneDistance'],[0.,17.])
        self.assertEqual(state['intensity_lightMap'],[f32(1.33)])

    def test_original_region_fog_and_rgb_producer_match_source_without_claiming_history(self):
        e=self.evidence;fog=e['fog']['native']
        self.assertEqual((fog['near'],fog['halfSpan']),(58.,148.))
        self.assertFalse(e['nativeRGBBeforeRuntimeAdds']['actualRuntimeAddsObserved'])
        self.assertEqual(e['nativeRGBBeforeRuntimeAdds']['result']['submitted']['light_model_lightMap'],e['targetCases'][0]['settled']['modelLightBeforeRuntimeRGBAdds'])
        self.assertEqual(e['weather']['sourceWeatherId'],0)
        self.assertFalse(e['weather']['previousWeatherAndRendererRGBHistoryObserved'])

    def test_minimal_export_refuses_to_claim_complete_runtime_context(self):
        p=export_inputs(self.evidence)
        self.assertEqual(p['format'],INPUT_FORMAT);self.assertEqual(p['sourceRegion'],211)
        self.assertFalse(p['originalRuntimeContextReady'])
        self.assertTrue(any('RGB' in text for text in p['requiredRuntimeInputs']))
        self.assertTrue(any('mode' in text for text in p['requiredRuntimeInputs']))
        self.assertFalse(self.evidence['previewChanged']);self.assertFalse(self.evidence['savesChanged'])


if __name__=='__main__':unittest.main(verbosity=2)
