"""Original global RGB audit and paired web-frame transport regressions."""
import hashlib
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT

RAW=ROOT/'analysis/raw/temple-ambient-20261112'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'
NODE=shutil.which('node')or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')


class Public(unittest.TestCase):
    def test_known_collider_gaps_do_not_create_whole_tile_barriers(self):
        from source_physics import SourcePhysics
        from source_swimming import SourceSwimming
        for cls in (SourcePhysics,SourceSwimming):
            e=object.__new__(cls);e.tiles={(-41,0):{},(-40,0):{}}
            e.inspection_collision_gaps={(-41,0)}
            e.chunk_flags={t:[0]*64 for t in e.tiles}
            self.assertTrue(e.available(-2560.1,34));self.assertTrue(e.available(-2559.9,34))
            self.assertFalse(e.available(-2700,34))
            e.chunk_flags[(-41,0)][4*8+7]=0x20000
            self.assertFalse(e.available(-2560.1,34))

    def test_paired_transport_timing(self):
        if not Path(NODE).is_file():self.skipTest('Node required')
        r=subprocess.run([NODE,'--test',str(ROOT/'tools/frame_presentation_tests.mjs')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_connector_rejects_unknown_preview_without_writes(self):
        from connect_frame_presentation import connect
        RAW.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=RAW if RAW.exists()else ROOT/'analysis/raw')as d:
            p=Path(d);public=p/'prototype/public';public.mkdir(parents=True)
            for n in ('explore-map.js','explore-map.html'):(public/n).write_text('unexplained change')
            with self.assertRaisesRegex(ValueError,'preserve'):connect(p)
            self.assertEqual(sorted(x.name for x in public.iterdir()),['explore-map.html','explore-map.js'])
            self.assertTrue(all(x.read_text()=='unexplained change'for x in public.iterdir()))


@unittest.skipUnless(NATIVE.is_file()and(RAW/'ambient-audit.json').is_file(),'Original native/zone inputs stay local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes())

    def test_complete_source_producer_replays_all_five_settled_zones(self):
        from temple_ambient import audit
        actual=audit(self.image);self.assertEqual(actual,json.loads((RAW/'ambient-audit.json').read_text()))
        zone=next(r for r in actual['zones']if r['zone']==195)
        self.assertEqual(zone['modelLight'],[1.9950001239776611,1.932411789894104,1.9637058973312378])
        self.assertFalse(actual['lightingChanged']);self.assertFalse(actual['originalAndroidGPUObserved'])

    def test_native_setters_offsets_and_complete_RGB_producer_have_no_extra_ambient_factor(self):
        from native_temple_ambient import TempleAmbientProbe
        from scene_lighting import DEFAULTS,color_vector,f32,lightmap_global
        p=TempleAmbientProbe(self.image);rng=random.Random(712)
        for _ in range(24):
            packed=[rng.randrange(1<<24)for _ in range(2)];adds=[f32(rng.uniform(-.2,.5))for _ in range(2)]
            intensities={k:f32(rng.uniform(.1,3))for k in [*DEFAULTS,'model_intensity_lightMap']}
            got=p.produce(*packed,intensities,adds)
            a,d=map(color_vector,packed)
            self.assertEqual(got['ambient'],a);self.assertEqual(got['diffuse'],d)
            expected=lightmap_global([f32(x+adds[0])for x in a],[f32(x+adds[1])for x in d],intensities['model_intensity_lightMap'])
            self.assertEqual(got['submitted']['light_model_lightMap'],expected)

    def test_source_prefix_changes_are_rejected(self):
        from native_temple_ambient import TempleAmbientProbe
        im=self.image
        class Changed:
            elf=im.elf
            def read(self,at,n):
                b=im.read(at,n);return bytes([b[0]^1])+b[1:]if at==0x34e53c else b
        with self.assertRaises(ValueError):TempleAmbientProbe(Changed())

    def test_connector_replays_three_files_and_rejects_repeat(self):
        from connect_frame_presentation import connect
        with tempfile.TemporaryDirectory(dir=RAW)as d:
            p=Path(d);public=p/'prototype/public';public.mkdir(parents=True)
            for n in ('explore-map.js','explore-map.html'):shutil.copyfile(RAW/('before-'+n),public/n)
            self.assertEqual(connect(p)['files'],3)
            from connect_character_orientation import PINS
            for f in public.iterdir():
                if f.name in PINS:self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(),PINS[f.name])
                else:self.assertEqual(f.read_bytes(),(RUN/'prototype/public'/f.name).read_bytes())
            before={f.name:f.read_bytes()for f in public.iterdir()}
            with self.assertRaises(ValueError):connect(p)
            self.assertEqual(before,{f.name:f.read_bytes()for f in public.iterdir()})

    def test_this_turn_preserves_all_source_assets_and_main_character_save(self):
        for n,h in json.loads((RAW/'game-data-converted-before.json').read_text()).items():
            self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/n).read_bytes()).hexdigest(),h,n)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'main-before-private.json').read_bytes())
        self.assertIn('status = "PAUSED"',(Path.home()/'.codex/automations/2/automation.toml').read_text())

if __name__=='__main__':unittest.main()
