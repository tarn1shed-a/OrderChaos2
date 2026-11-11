"""Blended-wall admission, source state, transparency and preservation checks."""
import copy
import hashlib
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tutorial_map_geometry import ROOT
from scene_mixed_walls import export, recover, MODEL, IDS

RAW = ROOT/'analysis/raw/mixed-walls-20261112'
RUN = ROOT/'analysis/raw/showcase-20261110/running-preview'
EXP = RAW/'export'
NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class Public(unittest.TestCase):
    def test_other_models_do_not_gain_blended_wall_admission(self):
        class Wrong:
            b = b'unverified model'
        with self.assertRaisesRegex(ValueError, 'Unverified'):
            recover(None, Wrong(), {}, None)

    def test_browser_adapter_has_valid_module_syntax(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node unavailable')
        result = subprocess.run([node, '--check', str(ROOT/'tools/preview/source-mixed-walls.js')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(NATIVE.is_file() and (EXP/'audit.json').is_file(), 'Original files, native image and converted assets stay local')
class Original(unittest.TestCase):
    def model(self):
        manifest = json.loads((EXP/'manifest.json').read_text())
        row = next(r for r in manifest['scenery'] if r['model'] == MODEL)
        return json.loads((EXP/Path(row['url']).name).read_text())

    def test_original_source_state_matches_recorded_gl_not_normal_blending(self):
        data = self.model()
        p = data['sourceMixedWall']
        self.assertEqual(p['blend'], {'equation': 32774, 'src': 770, 'dst': 771, 'separateAlpha': False})
        self.assertFalse(p['alphaTest'])
        self.assertFalse(p['depthWrite'])
        self.assertFalse(p['cull'])
        self.assertEqual(len(p['nativeStateProof']['profiles']), 2)
        for row in p['nativeStateProof']['profiles']:
            gl = {x['name']: x['args'] for x in row['calls']}
            self.assertEqual(gl['glBlendFunc'][:2], [770, 771])
            self.assertEqual(gl['glDepthMask'][0], 0)
            self.assertEqual(gl['glDepthFunc'][0], 515)
        self.assertEqual(p['alpha']['mode'], 'split-red')
        from texture_decode import decode
        self.assertEqual(decode((RAW/'wall-texture.tga').read_bytes()).getchannel('A').getextrema(), (0, 255))

    def test_original_distance_inputs_and_heap_order(self):
        from analyze_native_resources import NativeImage
        from native_mixed_walls import Probe
        probe = Probe(NativeImage(NATIVE.read_bytes()))
        rng = random.Random(731)
        for _ in range(24):
            eye = [rng.randint(-20, 20) for _ in range(3)]
            position = [rng.randint(-50, 50) for _ in range(3)]
            bias, priority = rng.randint(-4, 4), rng.randint(-5, 5)
            expected = sum((a-b)**2 for a, b in zip(position, eye))+bias
            for mode in ('explicit', 'matrix', 'box'):
                self.assertEqual(probe.distance(eye, position, mode=mode, bias=bias, priority=priority),
                                 {'priority': priority, 'tag': 17, 'distance': expected})
        # Nullable material fixtures exercise the source fallback, not the
        # unresolved original program/material equivalence comparator.
        for n in (2, 3, 7, 16, 31):
            for _ in range(5):
                rows = [{'id': i+100, 'priority': rng.randrange(3), 'distance': float(rng.randrange(8))} for i in range(n)]
                rng.shuffle(rows)
                expected = [r['id'] for r in sorted(rows, key=lambda r: (-r['priority'], -r['distance'], r['id']))]
                self.assertEqual(probe.sort(rows), expected)

    def test_only_two_original_trs_and_lightmap_bindings_added(self):
        old = json.loads((RUN/'game-data/converted/source-map-flags/manifest.json').read_text())
        new = json.loads((EXP/'manifest.json').read_text())
        audit = json.loads((EXP/'audit.json').read_text())
        self.assertEqual(new['scenery'][:156], old['scenery'])
        self.assertEqual({r['id'] for r in audit['added']}, IDS)
        self.assertEqual(len(new['scenery']), 157)
        self.assertEqual(sum(len(r['instances']) for r in new['scenery']), 1250)
        self.assertEqual(audit['omittedInstances'], 8)
        before = json.loads((RUN/'game-data/converted'/old['sceneBakedLighting']['url'].removeprefix('/assets/')).read_text())
        after = json.loads((EXP/'baked-lighting.json').read_text())
        self.assertEqual(after['instances'][:1217], before['instances'])
        self.assertEqual(len(after['instances']), 1219)
        for key in before.keys()-{'instances', 'atlases'}:
            self.assertEqual(before[key], after[key])
        self.assertFalse(audit['lightsChanged'])

    def test_rebuild_is_identical_and_old_resources_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=RAW) as tmp:
            export(RUN, Path(tmp))
            self.assertEqual({p.name: p.read_bytes() for p in EXP.iterdir()}, {p.name: p.read_bytes() for p in Path(tmp).iterdir()})
        for name, digest in json.loads((RAW/'before-assets.json').read_text()).items():
            self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/name).read_bytes()).hexdigest(), digest, name)

    def test_connector_replay_and_repeat_refusal(self):
        from connect_mixed_walls import connect
        with tempfile.TemporaryDirectory(dir=RAW) as tmp:
            runtime = Path(tmp)
            (runtime/'game-data/converted').mkdir(parents=True)
            public = runtime/'prototype/public'
            public.mkdir(parents=True)
            for name in ('explore-map.js', 'explore-map.html'):
                shutil.copyfile(RAW/('before-'+name), public/name)
            self.assertEqual(connect(runtime, EXP)['files'], 11)
            files = {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob('*') if p.is_file()}
            stage_hashes = {'prototype/public/explore-map.js': '76b88d8650754d45b0cb8bc49f6d71dd0c56545e5b2fbe401e539654d0cb4e98',
                            'prototype/public/explore-map.html': 'bfcdc1b38faa495022768ff2b44c97551f6229092851f5634510db48f5624498'}
            for name, content in files.items():
                if name in stage_hashes:
                    self.assertEqual(hashlib.sha256(content).hexdigest(), stage_hashes[name])
                    continue
                self.assertEqual((RUN/name).read_bytes(), content)
            with self.assertRaises(ValueError):
                connect(runtime, EXP)
            self.assertEqual(files, {str(p.relative_to(runtime)): p.read_bytes() for p in runtime.rglob('*') if p.is_file()})

    def test_changed_original_effect_is_refused(self):
        from bdae_convert import BDAE
        from scene_collision import apply_scene_transforms
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from analyze_native_resources import NativeImage
        reader = BDAE(RAW/'wall.bdae')
        source = Sources(DEFAULT_SOURCE)
        def wrong(name):
            return b'changed' if name == 'ut_lightmap_blend.bdae' else source.read(name)
        with self.assertRaises((ValueError, OSError)):
            recover(wrong, reader, apply_scene_transforms(reader, reader.parse()), NativeImage(NATIVE.read_bytes()))


if __name__ == '__main__':
    unittest.main()
