"""Source conformance and the previously mismatched environment-zone regression."""
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from default_environment import (ROOT, DEFAULT_APK, DEFAULT_SOURCE, FORMAT,
    NativeDefaultFogProbe, export, fog_target, verify)

NATIVE = ROOT/'analysis/raw/beff-native/library.so'


class PublicTests(unittest.TestCase):
    def test_fog_inheritance_uses_half_span_and_color_separately(self):
        base = {'ID': 1, 'fog_near': 45., 'fog_half': 89., 'fog_color': 0xffffff}
        row = {'ID': 2, 'fog_near': 17., 'fog_half': 0., 'fog_color': 0x804020}
        result = fog_target(row, base, far_plane=240., coefficient=1.)
        self.assertEqual((result['distanceOwner'], result['colorOwner']), (1, 2))
        self.assertEqual((result['near'], result['halfSpan']), (45., 89.))
        row.update(fog_half=101., fog_color=0)
        result = fog_target(row, base, far_plane=80., coefficient=.5)
        self.assertEqual((result['distanceOwner'], result['colorOwner']), (2, 1))
        self.assertEqual((result['near'], result['halfSpan']), (8.5, 24.25))

    def test_one_selected_pair_drives_all_environment_and_no_base_retains(self):
        node = shutil.which('node')
        bundled = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
        if not node and bundled.is_file(): node = str(bundled)
        if not node: self.skipTest('Node required for the public adapter check')
        script = """import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
          const {ENVIRONMENT_FORMAT,environmentZone,createOriginalDefaultEnvironment}=await import('data:text/javascript,'+encodeURIComponent(await readFile('./tools/preview/original-default-environment.js','utf8')));
          const rows=[194,195,196,197,199].map(id=>({id,fog:{near:id,halfSpan:89,color:[.1,.2,.3]},weather:{id:0},sourceLighting:{}}));
          const profile={format:ENVIRONMENT_FORMAT,zones:rows,configuration:{EnableFogDistanceLimit:false},knownWeatherRGB:{tutorialLightning:false}};
          for(const row of rows)assert.equal(environmentZone(profile,{baseId:194,overlayId:row.id}).id,row.id);
          assert.equal(environmentZone(profile,null,rows[2]),rows[2]);assert.equal(environmentZone(profile,null),null);
          assert.throws(()=>environmentZone(profile,{baseId:200}));
          let pair={baseId:194,overlayId:196},updates=0;
          const lighting={profile:{zones:rows,configuration:{environmentMode:0,rgbAdds:[0,0]}},update(){updates++},state:()=>({pair})};
          const legacy={prepare(){},fogUniforms:{sourceFogNear:{},sourceFogSpan:{},sourceFogColor:{value:{fromArray(a){this.rgb=a}}}}};
          const env=createOriginalDefaultEnvironment({},profile,lighting,legacy);
          assert.equal(env.update(0,0,null,0).id,196);assert.equal(legacy.fogUniforms.sourceFogNear.value,196);
          pair=null;assert.equal(env.update(999,999,null,501).id,196);assert.equal(env.state().pair,null);
          pair={baseId:194,overlayId:199};assert.equal(env.update(0,0,null,501).id,199);assert.equal(updates,3);
          assert.equal(env.state().weatherEffectsApplied,false);
          assert.throws(()=>createOriginalDefaultEnvironment({}, {...profile,zones:rows.slice(0,2)},lighting,legacy));
        """
        result = subprocess.run([node, '--input-type=module', '-e', script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


@unittest.skipUnless(NATIVE.is_file(), 'Original ARM64 evidence stays local')
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(NATIVE.read_bytes())

    def test_weather_extra_four_is_the_red_sky_effect_not_lightning(self):
        names = verify(self.image)
        self.assertEqual(names[4], 'effects/scene/scene_weather_vortex_red.beff')
        self.assertEqual(names[1], '')

    def test_changed_weather_consumer_is_rejected(self):
        image = self.image
        class Changed:
            elf = image.elf
            def read(self, at, size):
                return bytes(size) if at == 0x36ffd4 else image.read(at, size)
        with self.assertRaisesRegex(ValueError, 'weather sky consumer'): verify(Changed())

    def test_native_fog_clamp_inheritance_and_float32_match(self):
        p = NativeDefaultFogProbe(self.image); rng = random.Random(195)
        for k in range(40):
            base = {'ID': 194, 'fog_near': 45., 'fog_half': 89., 'fog_color': rng.randrange(1 << 24)}
            row = {'ID': 195, 'fog_near': float(rng.randrange(120)),
                   'fog_half': 0. if k % 3 == 0 else float(rng.randrange(1, 200)),
                   'fog_color': 0 if k % 4 == 0 else rng.randrange(1 << 24)}
            fallback = base if k % 5 else None
            inputs = dict(far_plane=float(rng.randrange(100, 260)), coefficient=[.5, 1., 1.5][k % 3])
            expected = fog_target(row, fallback, **inputs)
            self.assertEqual(p.run_fog(row, fallback, **inputs), {k: expected[k] for k in ('near', 'halfSpan', 'color')})

    @unittest.skipUnless(DEFAULT_APK.is_file() and (DEFAULT_SOURCE/'tables.bin').is_file(), 'Original resource/APK inputs stay local')
    def test_five_original_zone_targets_and_weather_payloads(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'analysis/raw', prefix='environment-test-') as folder:
            output = Path(folder)
            (output/'manifest.json').write_text(json.dumps({'sourceSelection': {'profile': 'APK_Default'}}))
            result = export(self.image, DEFAULT_SOURCE, DEFAULT_APK, output)
            self.assertEqual(result['format'], FORMAT)
            self.assertEqual([z['id'] for z in result['zones']], [194, 195, 196, 197, 199])
            zone = result['zones'][1]
            self.assertEqual((zone['fog']['near'], zone['fog']['halfSpan']), (89., 101.))
            self.assertEqual((zone['weather']['id'], zone['weather']['extraMode']), (6, 4))
            self.assertFalse(zone['weather']['lightning'])
            self.assertEqual(len(result['effects']), 2)
            self.assertTrue(all(e['completePayload'] for e in result['effects'].values()))
            self.assertFalse(result['knownWeatherRGB']['allOtherWritersRecovered'])


if __name__ == '__main__': unittest.main()
