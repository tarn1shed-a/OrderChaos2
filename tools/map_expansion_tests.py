"""Supported source atlas, sparse coverage and conditional window regressions."""
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT

EXPORT=ROOT/'analysis/raw/map-expanded-ready-20261111'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'
NODE=shutil.which('node')or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')


class PublicTests(unittest.TestCase):
    def test_sparse_tile_validation_does_not_fill_rectangular_holes(self):
        code="""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const{validateSourceTileCoverage}=await import('data:text/javascript,'+encodeURIComponent(await readFile('./tools/preview/source-archive-window.js','utf8')));
        const terrain={sourceTiles:[{tile:[-4,2]},{tile:[-2,2]}],tileCount:[3,1]};
        assert(validateSourceTileCoverage(terrain,{tiles:[{tile:[-2,2]},{tile:[-4,2]}]}));
        assert.throws(()=>validateSourceTileCoverage(terrain,{tiles:[{tile:[-4,2]},{tile:[-3,2]}]}));
        assert.throws(()=>validateSourceTileCoverage(terrain,{tiles:[{tile:[-4,2]},{tile:[-4,2]}]}));
        """
        r=subprocess.run([NODE,'--input-type=module','-e',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_original_window_distance_inputs_do_not_create_missing_source_tiles(self):
        code="""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const{sourceArchiveWindow,sourceTileCenter}=await import('data:text/javascript,'+encodeURIComponent(await readFile('./tools/preview/source-archive-window.js','utf8')));
        assert.deepEqual(sourceTileCenter(-64.001,-.01),[-2,-1]);assert.deepEqual(sourceTileCenter(-64,64),[-1,1]);
        const offsets=[];for(let z=-2;z<=2;z++)for(let x=-2;x<=2;x++)offsets.push([x,z]);
        const tiles=[];for(let z=-6;z<=6;z++)for(let x=-6;x<=6;x++)if(x!==0||z!==0)tiles.push([x,z]);
        const window=sourceArchiveWindow(tiles,offsets,2);let w=window.update(1,1);assert.equal(w.resident.size,24);assert(!w.resident.has('0,0'));
        assert.equal(window.update(2,2),null);w=window.update(64,1);assert(w.resident.has('-2,0'));w=window.update(128,1);assert(!w.resident.has('-2,0'));
        assert.throws(()=>sourceArchiveWindow(tiles,offsets.slice(1),2));
        """
        r=subprocess.run([NODE,'--input-type=module','-e',code],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_connector_refuses_main_project_and_backups(self):
        from connect_map_expansion import connect
        for p in (ROOT,ROOT/'backups'):
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)


@unittest.skipUnless((EXPORT/'geometry-audit.json').is_file()and NATIVE.is_file(),'Original files and converted atlas stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        cls.sources=Sources(DEFAULT_SOURCE);cls.audit=json.loads((EXPORT/'geometry-audit.json').read_text())
        cls.terrain=json.loads((EXPORT/'base/maps/expansion/tutorial-window.json').read_text())
        cls.manifest=json.loads((EXPORT/'verified/manifest.json').read_text())

    def test_all_supported_tiles_preserve_source_samples_without_filled_cells(self):
        for tile in self.terrain['sourceTiles']:
            x,z=tile['tile'];raw=self.sources.read(f'world/tutorial/terrain/{x:04d}_{z:04d}.trn')
            version,xx,zz=struct.unpack_from('<3i',raw,4);self.assertEqual([xx,zz],[x,z]);at=24+64*(16 if version==9 else 24)
            for key,fmt,offset in [('heights','4225h',0),('colors','4225H',8450),('normals','12675b',16900)]:
                self.assertEqual(tile[key],list(struct.unpack_from('<'+fmt,raw,at+offset)))
        self.assertEqual(len(self.terrain['sourceTiles']),181)
        self.assertEqual(len(self.audit['archiveTileGaps']),70)

    def test_every_displayed_model_and_world_placement_has_original_geometry(self):
        from bdae_convert import BDAE
        from scene_collision import apply_scene_transforms
        selection=json.loads((EXPORT/'verified/selection.json').read_text())
        source={(tuple(i['tile']),i['id']):i for i in selection['instances']if i['sourceType']==2}
        with tempfile.TemporaryDirectory()as d:
            p=Path(d)/'model.bdae'
            for item in self.manifest['scenery']:
                p.write_bytes(self.sources.read(item['model']));reader=BDAE(p);original=apply_scene_transforms(reader,reader.parse())
                converted=json.loads((EXPORT/'base'/item['url'].removeprefix('/assets/')).read_text())
                self.assertEqual(original['sourceSHA256'],converted['sourceSHA256'])
                for a,b in zip(original['meshes'],converted['meshes']):
                    for key in ('positions','normals','indices','uvs','sourceUV1','groups','sourceNodeTransform'):self.assertEqual(a.get(key),b.get(key))
                self.assertTrue(all(k in converted for k in ('sceneSampling','sceneAlpha','sceneCulling','sceneBakedLighting')))
                for instance in item['instances']:
                    expected=source[(tuple(instance['tile']),instance['id'])]
                    for key in ('model','position','quaternion','scale'):self.assertEqual(instance[key],expected[key])
                    self.assertEqual(expected['admission'],'admittedBeforeTypeFactory')
        self.assertEqual(sum(len(i['instances'])for i in self.manifest['scenery']),1125)

    def test_reused_object_id_keeps_its_distinct_tile_transform_and_lightmap(self):
        placements=[i for m in self.manifest['scenery']for i in m['instances']if i['id']==717067712]
        baked=json.loads((EXPORT/'verified/baked-lighting.json').read_text())
        bindings=[i for i in baked['instances']if i['objectId']==717067712]
        self.assertEqual({tuple(i['tile'])for i in placements},{(-40,-4),(-39,-4)})
        self.assertEqual(len(bindings),2);self.assertNotEqual(placements[0]['position'],placements[1]['position'])
        self.assertNotEqual(bindings[0]['recordPath'],bindings[1]['recordPath'])

    def test_global_light_weather_and_postprocess_are_not_retuned(self):
        current=ROOT/'analysis/raw/showcase-20261110/running-preview/game-data/converted'
        old=json.loads((current/'geometry-map/baked-lighting.json').read_text())
        new=json.loads((EXPORT/'verified/baked-lighting.json').read_text())
        self.assertEqual(old['configuration'],new['configuration']);self.assertEqual(old['zones'],new['zones'])
        before=json.loads((ROOT/'analysis/raw/map-expansion-20261111/before-assets.json').read_text())
        import hashlib
        for name,item in before.items():self.assertEqual(hashlib.sha256((current/name).read_bytes()).hexdigest(),item['sha256'],name)

    def test_native_center_and_distance_branch_match_browser_adapter(self):
        try:
            from analyze_native_resources import NativeImage
            from native_map_streaming_probe import NativeMapStreamingProbe
            p=NativeMapStreamingProbe(NativeImage(NATIVE.read_bytes()))
        except ImportError as e:raise unittest.SkipTest(str(e))
        offsets=p.offsets(2)['offsets'];self.assertEqual(offsets,self.manifest['mapWindow']['originalRequestOffsets'])
        points=[[-2700,58],[-2700,64],[-.01,-64.001],[-3072,-448],[-2496,0],[-64.0000001,-.00000001]]
        points.extend([[-3199+i*7.31,-350+i*5.73]for i in range(100)])
        code="""import{readFile}from'node:fs/promises';
          const{sourceTileCenter}=await import('data:text/javascript,'+encodeURIComponent(await readFile('./tools/preview/source-archive-window.js','utf8')));
          console.log(JSON.stringify(JSON.parse(process.argv[1]).map(p=>sourceTileCenter(...p))));"""
        result=subprocess.run([NODE,'--input-type=module','-e',code,json.dumps(points)],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),[p.center(x,z)for x,z in points])
        for dx in range(-5,6):self.assertEqual(p.retain_distance_branch([-43,0],[-43+dx,0],2)['distanceAllowsRetain'],abs(dx)<=3)


if __name__=='__main__':unittest.main()
