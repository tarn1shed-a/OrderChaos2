"""Independent sky retention/gating checks and source-dependent CPU evidence."""
import copy
import json
import subprocess
import shutil
import unittest
from pathlib import Path
from tutorial_sky_candidate import ROOT, MODELS, NativeSkyTargets, source_sky_request, target_writes


def row(**extra):
    return {'ID': 1, 'skybox': 'model\\sky.bdae', 'skybox_hill': 'model\\hill.bdae',
            'sky_near': 0., 'sky_half': 0., 'sky_color_near': 0xffffff, 'sky_color_far': 0xffffff,
            'skybox_saturation': 0., 'skybox_fog_intensity': 0., 'skyhill_fog_intensity': 0., **extra}


class Public(unittest.TestCase):
    def test_empty_sky_path_falls_back_while_hill_zero_disables(self):
        base = row()
        self.assertEqual(source_sky_request(row(skybox=''), base), 'model/sky.bdae')
        self.assertEqual(source_sky_request(row(skybox_hill=''), base, hill=True), 'model/hill.bdae')
        self.assertIsNone(source_sky_request(row(skybox_hill='0'), base, hill=True))
        self.assertIsNone(source_sky_request(row(skybox=''), None))

    def test_nonpositive_sky_half_skips_distance_instead_of_inventing_default(self):
        self.assertIsNone(target_writes(row(sky_near=90, sky_half=0), row())['distance'])
        self.assertEqual(target_writes(row(sky_near=90, sky_half=0), row(sky_near=2, sky_half=6))['distance'], [2, 6])
        self.assertEqual(target_writes(row(sky_near=-5, sky_half=3), row())['distance'], [-5, 3])

    def test_fog_intensity_uses_base_row_and_original_fallback_not_selected_row(self):
        self.assertEqual(target_writes(row(skybox_fog_intensity=90, skyhill_fog_intensity=99), row())['mainFog'], [8])
        self.assertEqual(target_writes(row(skybox_fog_intensity=90, skyhill_fog_intensity=99), row())['hillFog'], [4])
        self.assertEqual(target_writes(row(), row(skybox_fog_intensity=2, skyhill_fog_intensity=3))['hillFog'], [3])

    def test_source_rgb_low_byte_is_first_and_zero_retains(self):
        t = target_writes(row(sky_color_near=0x0000ff, sky_color_far=0), None)
        self.assertEqual(t['near'], [1, 0, 0]); self.assertIsNone(t['far'])

    def test_source_writes_never_mutate_original_rows(self):
        a, b = row(), row(sky_half=9)
        before = copy.deepcopy([a, b]); target_writes(a, b); source_sky_request(a, b)
        self.assertEqual([a, b], before)

    def test_browser_sky_state_retains_skipped_distance_and_rejects_unknown_zone(self):
        node = shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
        if not Path(node).is_file(): self.skipTest('Node runtime absent')
        script = r'''
import assert from 'node:assert/strict';
import {createSkyState,translateSkyShader,TUTORIAL_SKY_FORMAT} from './tools/preview/source-tutorial-sky.js';
import {stageTutorialSkyEntry,stageTutorialSkyPlan,SKY_MANIFEST} from './tools/preview/source-tutorial-sky-overlay.mjs';
const initial={distance:[0,50],near:[1,1,1],far:[1,1,1],saturation:[0],mainFog:[8],hillFog:[4]};
const profile={format:TUTORIAL_SKY_FORMAT,sourceMapId:5,configuration:{profile:'APK_Default',ShowHillInSky:true},initialEnvironment:initial,
zones:[{id:1,writes:{distance:[42,43],near:[.5,.4,.3]}},{id:2,writes:{distance:null,near:[1,1,1]}}]};
const state=createSkyState(profile);
assert.deepEqual(state.update({baseId:1,overlayId:null}).distance,[42,43]);
assert.deepEqual(state.update({baseId:2,overlayId:null}).distance,[42,43]);
assert.deepEqual(state.state().near,[1,1,1]);assert.deepEqual(initial.distance,[0,50]);
assert.throws(()=>state.update({baseId:999,overlayId:null}));
assert.throws(()=>createSkyState({...profile,configuration:{...profile.configuration,ShowHillInSky:false}}));
assert.throws(()=>translateSkyShader('void main(){}','compute'));
assert.match(translateSkyShader('attribute vec4 Vertex; varying vec2 uv;','vertex'),/in vec4 Vertex; out vec2 uv;/);
assert.match(translateSkyShader('varying vec2 uv;void main(){gl_FragColor=texture2D(s,uv);}','fragment'),/sourceSkyOutput=texture\(s,uv\)/);
const original="const viewport = $('viewport'), canvas = $('scene');environment=createOriginalDefaultEnvironment(THREE,await json(assets.defaultEnvironment),bakedLighting,environment);hdrRenderer.render(scene,camera,zone);";
const patched=stageTutorialSkyEntry(original);assert.match(patched,/createTutorialSky/);assert.match(patched,/environment\.state\(\)\.pair/);
assert.throws(()=>stageTutorialSkyEntry(patched));assert.throws(()=>stageTutorialSkyEntry('changed archived entry'));
const metadata={format:TUTORIAL_SKY_FORMAT,sourceMapId:5,models:{},shaders:{}};
const texts=new Map([[SKY_MANIFEST,JSON.stringify(metadata)]]),plan={critical:[SKY_MANIFEST,'/source-tutorial-sky.js'],scope:{}};
assert.equal(stageTutorialSkyPlan(plan,texts).scope.wholeMapAccepted,false);
assert.throws(()=>stageTutorialSkyPlan({...plan,critical:[]},texts));
console.log('Browser sky retention, rejection and GLSL translation checks passed');
'''
        completed = subprocess.run([node, '--input-type=module', '-e', script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)


PRIVATE = ROOT/'analysis/raw/tutorial-sky-candidate-20261114/v3'
LIB = ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(LIB.is_file() and (PRIVATE/'evidence.json').is_file(), 'Private original library and candidate assets absent')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from skill_attachments import decode_ftable
        cls.image = NativeImage(LIB.read_bytes()); cls.probe = NativeSkyTargets(cls.image)
        cls.rows = {r['ID']: r for r in decode_ftable(Sources(DEFAULT_SOURCE).read('tables/zones.tbl'), id_column='ID')['rows']}
        cls.evidence = json.loads((PRIVATE/'evidence.json').read_text())
        cls.profile = json.loads((PRIVATE/'game-data/converted/source-tutorial-sky/manifest.json').read_text())

    def test_original_constructor_and_selected_target_bytes_execute_for_each_map5_zone(self):
        for ident in [194, 195, 196, 197, 199]:
            with self.subTest(zone=ident):
                result = self.probe.run_sky(self.rows[ident], None if ident == 194 else self.rows[194])
                self.assertEqual(result['initial']['distance'], [0, 50])
                self.assertEqual(result['result']['mainFog'], [8]); self.assertEqual(result['result']['hillFog'], [4])

    def test_original_195_to_194_skipped_distance_retains_previous_values(self):
        previous = self.probe.run_sky(self.rows[195], self.rows[194])['result']
        result = self.probe.run_sky(self.rows[194], None, previous)['result']
        self.assertEqual(result['distance'], [42, 43]); self.assertEqual(result['near'], [1, 1, 1])

    def test_zone_requests_and_apk_gate_are_source_links_not_filename_guesses(self):
        self.assertTrue(self.evidence['defaultHillGate'])
        for r in self.profile['zones']: self.assertEqual(r['requests'], MODELS)
        self.assertEqual(self.profile['sourceMapId'], 5)
        self.assertFalse(self.profile['webAdapter']['changesFogLightingWeatherOrHDR'])

    def test_original_hill_blend_factor_emission_is_recorded_and_depth_is_disabled(self):
        main, hill = self.profile['models']['main'], self.profile['models']['hill']
        self.assertEqual(main['technique']['name'], 'solid'); self.assertEqual(hill['technique']['name'], 'tech0')
        for info in [main, hill]:
            self.assertFalse(info['technique']['state']['depthTestEnabled'])
            self.assertFalse(info['technique']['state']['depthWriteEnabled'])
        calls = {v['name']: v['args'] for v in hill['technique']['state']['originalGLCallsRecordedWithoutGPU']}
        self.assertEqual(calls['glBlendFunc'][:2], [770, 771])

    def test_append_asset_names_do_not_replace_existing_public_resources(self):
        import tarfile
        with tarfile.open(PRIVATE/'tutorial-sky-append.tar.gz') as t:
            names = [v.name for v in t.getmembers()]
            self.assertEqual(len(names), 7)
            self.assertTrue(all(n.startswith('game-data/converted/source-tutorial-sky/') for n in names))
            self.assertFalse(any('characters' in n or 'native-inputs' in n for n in names))


if __name__ == '__main__': unittest.main()
