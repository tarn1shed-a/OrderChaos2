"""Water evidence, original CPU output, browser binding and preserved inputs."""
import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from terrain_water import ROOT,FORMAT

EXPORT=ROOT/'analysis/raw/map-water-ready-20261111'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'
NODE=shutil.which('node')or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')


def javascript(code):
    r=subprocess.run([NODE,'--input-type=module','-e',code],cwd=ROOT,capture_output=True,text=True)
    if r.returncode:raise AssertionError(r.stdout+r.stderr)
    return r.stdout


class PublicTests(unittest.TestCase):
    def test_connector_cannot_modify_main_or_backup(self):
        from connect_terrain_water import connect
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)

    def test_vertex_adapter_preserves_source_body_and_rejects_unknown_source(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const code=(await readFile('tools/preview/source-terrain-water.js','utf8')).replace(/^import .*?;$/m,'');
        const m=await import('data:text/javascript,'+encodeURIComponent(code));
        const source='attribute highp   vec4 Vertex;attribute highp vec2 TexCoord0;void main(){vec4 Vertex1=Vertex;gl_Position=WorldViewProjectionMatrix * Vertex1;vec2 p=TexCoord0;}';
        const out=m.adaptWaterVertex(source);assert(!out.includes('attribute '));assert(out.includes('vec4 Vertex1=vec4(position,1.0)'));assert(out.includes('vec2 p=uv;'));assert(out.includes('WorldViewProjectionMatrix * Vertex1'));
        assert.throws(()=>m.adaptWaterVertex('void main(){}'));""")

    def test_clock_input_is_bounded_and_negative_scroll_uses_floor(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const code=(await readFile('tools/preview/source-terrain-water.js','utf8')).replace(/^import .*?;$/m,'');
        const{waterBumpOffset}=await import('data:text/javascript,'+encodeURIComponent(code));
        const s={scale:1,rates:[0,.25,-.25,1]};assert.deepEqual(waterBumpOffset(1,s),[-1,-.75,-.25,-1]);
        assert.deepEqual(waterBumpOffset(2**32+1,s),waterBumpOffset(1,s));assert.throws(()=>waterBumpOffset(NaN,s));""")


@unittest.skipUnless(NATIVE.is_file()and(EXPORT/'water-audit.json').is_file(),'Original water inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from analyze_native_resources import NativeImage
            from terrain_water import NativeWater
            from map_loading_evidence import Sources
            from resource_packs import DEFAULT_SOURCE
            cls.image=NativeImage(NATIVE.read_bytes());cls.native=NativeWater(cls.image)
        except ImportError as e:raise unittest.SkipTest(str(e))
        cls.sources=Sources(DEFAULT_SOURCE);cls.profile=json.loads((EXPORT/'terrain-water.json').read_text())
        cls.audit=json.loads((EXPORT/'water-audit.json').read_text())
        cls.mats=json.loads((EXPORT/'terrain-materials.json').read_text());cls.lights=json.loads((EXPORT/'terrain-lighting.json').read_text())

    def test_original_reader_proves_all_chunk_bounds_flags_and_water_heights(self):
        total=0
        for row,light in zip(self.audit['nativeProofs'],self.lights['tiles']):
            raw=self.sources.read('world/tutorial/terrain/%04d_%04d.trn'%tuple(row['tile']))
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sourceSHA256'])
            cs=self.native.read(raw);self.assertEqual(cs,row['chunks'])
            self.assertEqual([r['flags']for r in cs],light['runtimeFlags']);total+=sum(bool(r['flags']&0x10000)for r in cs)
        self.assertEqual(total,4098);self.assertEqual(self.audit['dryChunksPreviouslyHidden'],1649)
        self.assertEqual(len(self.profile['tiles']),105)

    def test_native_depth_bytes_and_png_alpha_are_equal_for_every_water_tile(self):
        from PIL import Image
        for tile in self.profile['tiles']:
            self.native.read(self.sources.read('world/tutorial/terrain/%04d_%04d.trn'%tuple(tile['tile'])))
            depth=self.native.depth();self.assertEqual(hashlib.sha256(depth).hexdigest(),tile['depth']['cpuSHA256'])
            png=Image.open(EXPORT/Path(tile['depth']['url']).name).convert('RGBA')
            self.assertEqual(png.size,(128,128));self.assertEqual(png.getchannel('A').tobytes(),depth)

    def test_quad_effect_blend_and_raw_shader_identity_are_original(self):
        from terrain_water import effect_state
        self.assertEqual(self.native.quad(),self.profile['quad'])
        self.assertEqual(effect_state(self.image,self.sources),self.profile['effectState'])
        for name,row in self.profile['shaders'].items():
            raw=self.sources.read(name);self.assertEqual(raw,(EXPORT/name).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        self.assertEqual(self.profile['effectState']['factorsGL'],[770,771])
        self.assertFalse(self.audit['originalGPUCreationExecuted'])

    def test_browser_scroll_matches_original_instructions_at_boundaries(self):
        values=[0,1,1000,123456,4294967295]
        code="""import{readFile}from'node:fs/promises';
        const code=(await readFile('tools/preview/source-terrain-water.js','utf8')).replace(/^import .*?;$/m,'');
        const{waterBumpOffset}=await import('data:text/javascript,'+encodeURIComponent(code));
        const p=JSON.parse(await readFile('analysis/raw/map-water-ready-20261111/terrain-water.json','utf8'));
        console.log(JSON.stringify([0,1,1000,123456,4294967295].map(t=>waterBumpOffset(t,p.scroll))));"""
        self.assertEqual(json.loads(javascript(code)),[self.native.bump(t)for t in values])

    def test_no_old_asset_or_light_parameter_was_changed(self):
        assets=ROOT/'analysis/raw/showcase-20261110/running-preview/game-data/converted'
        before=json.loads((ROOT/'analysis/raw/water-20261111/before-assets.json').read_text())
        for name,row in before.items():self.assertEqual(hashlib.sha256((assets/name).read_bytes()).hexdigest(),row['sha256'],name)
        old=json.loads((ROOT/'analysis/raw/map-missing-terrain-ready-20261111/verified/terrain-lighting.json').read_text())
        self.assertEqual(self.lights['configuration'],old['configuration'])
        oldm=json.loads((ROOT/'analysis/raw/map-missing-terrain-ready-20261111/verified/terrain-materials.json').read_text())
        changed=0
        for a,b in zip(self.mats['tiles'],oldm['tiles']):
            self.assertEqual(a['textures'],b['textures']);self.assertEqual(a['mask'],b['mask'])
            for x,y in zip(a['chunks'],b['chunks']):
                xx={k:v for k,v in x.items()if k!='sourceWaterPending'};yy={k:v for k,v in y.items()if k!='sourceWaterPending'}
                self.assertEqual(xx,yy);changed+=int(x['sourceWaterPending']!=y['sourceWaterPending'])
        self.assertEqual(changed,1649)


if __name__=='__main__':unittest.main()
