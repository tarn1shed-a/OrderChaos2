"""Compare the bounded adapter against original instructions and source files."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from tutorial_walk_collision import phy_candidates

HERE=ROOT/'analysis/raw/walk-collision-20261111'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'
EXPORT=HERE/'final-export'
NODE=shutil.which('node')or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')


class PublicTests(unittest.TestCase):
    def test_normal_small_and_h_model_paths_follow_source_filename_rules(self):
        self.assertEqual(phy_candidates('model/bridge.bdae'),('model/bridge_s.phy','model/bridge.phy'))
        self.assertEqual(phy_candidates('model/bridge_h.bdae'),('model/bridge_s.phy','model/bridge.phy'))

    def test_source_exports_refuse_repository_and_backup_mutation(self):
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):local_output(p)

    def test_source_height_checkerboard_negative_coordinates_and_missing_tiles(self):
        code="""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
          const{sourceTerrainSample}=await import('data:text/javascript,'+encodeURIComponent(await readFile('./tools/preview/source-height.js','utf8')));
          const t={tile:[-1,0],heights:Array(4225).fill(0)};t.heights[66]=1000;
          assert.equal(sourceTerrainSample([t],-63.75,.25).height,2.5);
          assert.equal(sourceTerrainSample([t],-63.25,.75).height,7.5);
          assert.throws(()=>sourceTerrainSample([t],1,1),RangeError);
        """
        r=subprocess.run([NODE,'--input-type=module','-e',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)


@unittest.skipUnless(NATIVE.is_file()and(EXPORT/'collision.json').is_file(),'Original instructions/assets stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from analyze_native_resources import NativeImage
            from native_walk_probe import NativeWalkProbe
            cls.probe=NativeWalkProbe(NativeImage(NATIVE.read_bytes()))
        except ImportError as e:raise unittest.SkipTest('Private native probe dependencies: '+str(e))
        r=subprocess.run([NODE,'tools/walk_collision_cases.mjs'],cwd=ROOT,capture_output=True,text=True)
        if r.returncode:raise AssertionError(r.stdout+r.stderr)
        cls.data=json.loads((HERE/'cases.json').read_text())
        tiles=json.loads((ROOT/'analysis/raw/map-geometry-20261111/base/maps/tutorial-window.json').read_text())['sourceTiles']
        cls.probe.set_source_tiles(tiles)

    def test_source_terrain_samples_match_original_height_and_normal_instructions(self):
        for s in self.data['samples']:
            actual=self.probe.sample(s['x'],s['z']);expected=s['result']
            self.assertAlmostEqual(actual['height'],expected['height'],delta=3e-5,msg=str(s))
            for a,b in zip(actual['normal'],expected['normal']):self.assertAlmostEqual(a,b,delta=2e-6,msg=str(s))

    def test_grounded_walk_query_sequence_and_results_match_original_code(self):
        worst=0
        for case in self.data['cases']:
            pending=list(case['queries'])
            def intersect(a,b):
                self.assertTrue(pending,'Native issued an extra intersection query: '+case['name'])
                q=pending.pop(0)
                for actual,expected in zip([*a,*b],q['from']+q['to']):
                    self.assertAlmostEqual(actual,expected,delta=6e-4,msg=case['name'])
                return q['hit']
            r=self.probe.move(case['position'],case['delta'],None,intersect)
            self.assertFalse(pending,'Adapter issued an extra query: '+case['name'])
            self.assertEqual(r['code'],case['result']['code'],case['name'])
            for a,b in zip(r['position'],case['result']['position']):
                worst=max(worst,abs(a-b));self.assertAlmostEqual(a,b,delta=6e-4,msg=case['name'])
        self.assertLessEqual(worst,6e-4)
        (HERE/'native-check.json').write_text(json.dumps({'movesCompared':len(self.data['cases']),
            'heightSamplesCompared':len(self.data['samples']),'maximumMoveDifference':worst,
            'scope':'Original grounded consumer, forward ray wrapper and ground-height code; geometric intersections supplied by host; dry loaded-tile fixtures.'},indent=2)+'\n')

    def test_original_shape_selection_and_instance_counts_are_not_render_hull_guesses(self):
        p=json.loads((EXPORT/'collision.json').read_text());self.assertEqual(len(p['instances']),217)
        self.assertEqual(len(p['sources']),33);self.assertEqual(sum(len(s['shapes'])for s in p['sources'].values()),175)
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from scene_collision import decode_phy
        s=Sources(DEFAULT_SOURCE)
        for row in p['selection']:
            self.assertFalse(s.candidates(row['missingSimplified']));raw=s.read(row['selected'])
            self.assertEqual(p['sources'][row['selected']],decode_phy(raw))


if __name__=='__main__':unittest.main()
