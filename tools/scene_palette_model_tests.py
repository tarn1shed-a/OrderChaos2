"""Original palette inputs, source refusal, preservation and connector checks."""
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from scene_palette_model import recover, export, MODEL

RAW = ROOT/'analysis/raw/map-palette-20261112'
RUN = ROOT/'analysis/raw/showcase-20261110/running-preview'
EXP = RAW/'export'
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class Public(unittest.TestCase):
    def test_other_source_models_are_refused(self):
        class Wrong:
            b = b'not the verified original model'
        with self.assertRaisesRegex(ValueError, 'Unverified'):
            recover(None, Wrong(), {}, None)

    def test_browser_module_syntax(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node unavailable')
        r = subprocess.run([node, '--check', str(ROOT/'tools/preview/source-scene-palette.js')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipUnless(NATIVE.is_file() and (EXP/'audit.json').is_file(), 'Original native/model/texture fixtures stay local')
class Original(unittest.TestCase):
    def model(self):
        m = json.loads((EXP/'manifest.json').read_text())
        return json.loads((EXP/Path(m['scenery'][-1]['url']).name).read_text())

    def probe(self):
        from analyze_native_resources import NativeImage
        from native_scene_palette import PaletteProbe
        return PaletteProbe(NativeImage(NATIVE.read_bytes()))

    def test_original_default_macros_and_blend_write_not_omitted(self):
        p = self.probe()
        self.assertEqual(p.factory_flags(2)['loaderFlags'], 0x807)
        self.assertEqual(p.default_blend()['writes'], [{'index': 3, 'element': 0, 'value': [1., 1., 1., 1.]}])
        self.assertEqual(p.default_blend(False)['writes'], [])
        result = p.default_blend(True, False)
        self.assertEqual(result['writes'], [])
        self.assertEqual(result['lookup'], [])
        self.assertIn('BLEND_COLOR', self.model()['sourcePalette']['defines'])

    def test_original_missing_attributes_and_light_under_actual_rotation(self):
        p = self.probe()
        self.assertEqual([r['value'] for r in p.missing_attributes()['calls']], [[1, 0, 0, 1], [0, 1, 0, 1]])
        world = [0, 0, -1, 0, 0, 1, 0, 0, 1, 0, 0, 0, -2691, 107, -63, 1]
        direction = p.default_light(world)['uploadedObjectDirection']
        for a, b in zip(direction, [1/math.sqrt(3), 1/math.sqrt(3), -1/math.sqrt(3)]):
            self.assertAlmostEqual(a, b, places=6)

    def test_original_global_rgb_writer_uses_separate_character_intensities(self):
        p = self.probe()
        for a, d, intensity in [([1, .5, .25], [.2, .4, .8], [1.36, .7, 1.9]), ([.3, .6, .9], [.8, .2, .1], [.4, 1.2, .8])]:
            actual = p.colors(a, d, intensity)
            for key, values, scale in [('ambient', a, intensity[0]), ('diffuse', d, intensity[1]), ('specular', d, intensity[2])]:
                for v, expected in zip(actual[key], [x*scale for x in values]):
                    self.assertAlmostEqual(v, expected, places=6)

    def test_no_atlas_or_generated_tangent_was_added(self):
        d = self.model(); p = d['sourcePalette']; mesh = d['meshes'][0]
        self.assertFalse(p['lightmapConsumed'])
        self.assertNotIn('sceneBakedLighting', d)
        self.assertNotIn('sourceUV1', mesh)
        self.assertNotIn('sourceTangents', mesh)
        self.assertEqual(set(p['samplers']), {'texture', 'normalMap', 'maskMap', 'diffusePal', 'specularPal', 'specularPalBack'})
        self.assertEqual(p['samplers']['specularPal']['url'], p['samplers']['specularPalBack']['url'])
        self.assertEqual(p['samplers']['diffusePal']['encoding']['container'], 'TGA24')
        self.assertEqual(p['samplers']['normalMap']['encoding']['encoding'], 'ETC1')

    def test_only_one_original_instance_and_no_lighting_changes(self):
        old = json.loads((RUN/'game-data/converted/source-map-mixed-walls/manifest.json').read_text())
        new = json.loads((EXP/'manifest.json').read_text())
        self.assertEqual(new['scenery'][:157], old['scenery'])
        self.assertEqual(len(new['scenery']), 158)
        self.assertEqual(sum(len(r['instances']) for r in new['scenery']), 1251)
        self.assertEqual(new['scenery'][-1]['instances'][0]['id'], 742862992)
        before = json.loads((RUN/'game-data/converted'/old['sceneBakedLighting']['url'].removeprefix('/assets/')).read_text())
        self.assertEqual(before, json.loads((EXP/'baked-lighting.json').read_text()))
        self.assertEqual(len(before['instances']), 1219)
        self.assertEqual(json.loads((EXP/'audit.json').read_text())['omittedInstances'], 7)

    def test_rebuild_exact_and_all_old_assets_preserved(self):
        with tempfile.TemporaryDirectory(dir=RAW) as t:
            export(RUN, Path(t))
            self.assertEqual({p.name: p.read_bytes() for p in EXP.iterdir()}, {p.name: p.read_bytes() for p in Path(t).iterdir()})
        for name, digest in json.loads((RAW/'before-assets.json').read_text()).items():
            self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/name).read_bytes()).hexdigest(), digest, name)

    def test_connector_replay_and_repeat_refusal(self):
        from connect_scene_palette import connect
        with tempfile.TemporaryDirectory(dir=RAW) as t:
            runtime = Path(t); public = runtime/'prototype/public'; public.mkdir(parents=True)
            (runtime/'game-data/converted').mkdir(parents=True)
            for n in ('explore-map.js', 'explore-map.html'):
                shutil.copyfile(RAW/('before-'+n), public/n)
            self.assertEqual(connect(runtime, EXP)['paletteInstances'], 1)
            files = {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob('*') if p.is_file()}
            stage_hashes = {'prototype/public/explore-map.js':'2c3b008bbb4ca0142c211695b3c60f0950743d37fb90b88daf07ffcde1687294',
                            'prototype/public/explore-map.html':'7aebe3501d237dd23cb0837e6fbb466a3a15eead72234cca547d17ac184a0f63'}
            for name, content in files.items():
                if name in stage_hashes:
                    self.assertEqual(hashlib.sha256(content).hexdigest(),stage_hashes[name])
                    continue
                self.assertEqual((RUN/name).read_bytes(), content)
            with self.assertRaises(ValueError):
                connect(runtime, EXP)
            self.assertEqual(files, {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
