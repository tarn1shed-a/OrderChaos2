"""Source sample preservation and conditional map inspection regressions."""
import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tutorial_map_geometry import ROOT, DEFAULT_SOURCE, local_output, raw_tile, seam_audit
from terrain_lighting import rgb565

EXPORT=ROOT/'analysis/raw/map-geometry-20261111'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'


def tile(x,z):
    return {'tile':[x,z],'heights':[0]*4225,'normals':[v for _ in range(4225)for v in (0,127,0)],'colors':[65535]*4225}


class PublicTests(unittest.TestCase):
    def test_geometry_exports_and_connector_refuse_the_active_repository(self):
        with self.assertRaisesRegex(ValueError,'ignored'):local_output(ROOT)
        from connect_map_geometry import connect
        with self.assertRaisesRegex(ValueError,'ignored'):connect(ROOT,ROOT)

    def test_duplicate_edge_samples_are_reported_and_preserved(self):
        a,b=tile(-43,2),tile(-42,2)
        b['heights'][0]=12;b['normals'][:3]=[0,126,1];b['colors'][0]=0xf800
        before=copy.deepcopy([a,b]);result=seam_audit([a,b])
        self.assertEqual(result,{'height':1,'normal':1,'color':1})
        self.assertEqual([a,b],before)

    def test_browser_source_colors_layer_masks_and_local_tile_positions(self):
        node=shutil.which('node');bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
        if not node and bundled.is_file():node=str(bundled)
        if not node:self.skipTest('Node required for the geometry adapter checks')
        expected=hashlib.sha256(bytes(c for value in range(65536)for c in rgb565(value))).hexdigest()
        script="""import assert from 'node:assert/strict';import {readFile}from'node:fs/promises';import{createHash}from'node:crypto';
          const {rgb565Bytes,sourceTileVertex,sourceLayerColor,sourceLayerShader}=await import('data:text/javascript,'+encodeURIComponent(await readFile('./tools/preview/source-map-geometry.js','utf8')));
          const bytes=Buffer.alloc(65536*4);for(let i=0;i<65536;i++)bytes.set(rgb565Bytes(i),i*4);console.log(createHash('sha256').update(bytes).digest('hex'));
          const a={tile:[-42,3],heights:Array(4225).fill(0),normals:Array(12675).fill(0),colors:Array(4225).fill(65535)};
          a.heights[64]=13235;a.colors[64]=0xf800;
          assert.deepEqual(sourceTileVertex(a,64,0).position,[-2624,Math.fround(13235*Math.fround(.01)),192]);assert.deepEqual(sourceTileVertex(a,64,0).color,[255,0,0,255]);
          assert.throws(()=>sourceTileVertex(a,65,0));assert.throws(()=>rgb565Bytes(65536));
          const colors=[[.1,.2,.3,1],[.4,.5,.6,.8],[.9,.8,.7,.6],[.2,.4,.6,.4],[.7,.3,.8,0]],weights=[.2,.3,.4,.5];
          for(let mask=1;mask<32;mask++){
            const ids=[0,1,2,3,4].map(i=>(mask&(1<<i))?i:-1);let expected;
            // Literal TerrainFP bit-mask branches: first present layer is
            // assigned directly, including layer5 with alpha=0.
            for(let i=0;i<5;i++)if(mask&(1<<i)){
              if((mask&((1<<i)-1))===0)expected=colors[i].slice(0,3);
              else{const alpha=weights[i-1]*(i===4?colors[i][3]:1);expected=expected.map((v,c)=>v*(1-alpha)+colors[i][c]*alpha);}
            }
            assert.deepEqual(sourceLayerColor(colors,weights,ids),expected);
            assert(sourceLayerShader(ids).includes('terrainLayer'+ids.findIndex(i=>i>=0)));
          }
          assert.deepEqual(sourceLayerColor(colors,weights,[-1,-1,-1,-1,4]),colors[4].slice(0,3));
          assert.throws(()=>sourceLayerShader([-1,-1,-1,-1,-1]));
        """
        result=subprocess.run([node,'--input-type=module','-e',script],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual(result.stdout.strip(),expected)


@unittest.skipUnless((EXPORT/'geometry-audit.json').is_file()and(DEFAULT_SOURCE/'tutorial.bin').is_file(),'Original geometry exports stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from map_loading_evidence import Sources
        cls.sources=Sources(DEFAULT_SOURCE)

    def test_all_25_tiles_keep_every_source_height_normal_and_color(self):
        data=json.loads((EXPORT/'base/maps/tutorial-window.json').read_text())
        for t in data['sourceTiles']:
            x,z=t['tile'];expected=raw_tile(self.sources.read(f'world/tutorial/terrain/{x:04d}_{z:04d}.trn'),x,z)
            self.assertEqual(t,expected)
        self.assertEqual(len(data['sourceTiles']),25)
        self.assertEqual(seam_audit(data['sourceTiles']),{'normal':626,'height':2})
        self.assertEqual(data['sourceVertexColorSummary']['unique16'],64)

    def test_every_model_geometry_and_node_matrix_matches_source(self):
        from bdae_convert import BDAE
        from scene_collision import apply_scene_transforms
        manifest=json.loads((EXPORT/'base/manifest.json').read_text())
        with tempfile.TemporaryDirectory()as tmp:
            for entry in manifest['scenery']:
                path=Path(tmp)/'model.bdae';path.write_bytes(self.sources.read(entry['model']))
                reader=BDAE(path);expected=apply_scene_transforms(reader,reader.parse())
                actual=json.loads((EXPORT/'base'/entry['url'].removeprefix('/assets/')).read_text())
                self.assertEqual(actual['sourceSHA256'],expected['sourceSHA256'])
                self.assertEqual(len(actual['meshes']),len(expected['meshes']))
                for a,b in zip(actual['meshes'],expected['meshes']):
                    for k in ('positions','normals','uvs','sourceUV1','indices','groups','sourceNodeTransform'):self.assertEqual(a.get(k),b.get(k))
        self.assertEqual(len(manifest['scenery']),33)

    def test_instance_trs_is_not_recentered_or_normalized_and_gaps_are_explicit(self):
        from terrain_convert import read_instances
        actual={i['id']:i for e in json.loads((EXPORT/'base/manifest.json').read_text())['scenery']for i in e['instances']}
        expected={}
        with tempfile.TemporaryDirectory()as tmp:
            for z in range(1,6):
                for x in range(-44,-39):
                    name=f'world/tutorial/items/{x:04d}_{z:04d}.itm'
                    if not self.sources.candidates(name):continue
                    p=Path(tmp)/'tile.itm';p.write_bytes(self.sources.read(name));expected.update((i['id'],i)for i in read_instances(p))
        self.assertEqual(set(actual),set(expected));self.assertEqual(len(actual),217)
        for ident in actual:
            for k in ('model','tile','position','quaternion','scale'):self.assertEqual(actual[ident][k],expected[ident][k])
        audit=json.loads((EXPORT/'geometry-audit.json').read_text())
        self.assertEqual(audit['preview']['displayedInstances'],211);self.assertEqual(len(audit['preview']['omitted']),6)
        self.assertEqual(audit['pendingWaterChunks'],32);self.assertFalse(audit['lightingSettingsChanged'])


if __name__=='__main__':unittest.main()
