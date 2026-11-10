"""Underwater CPU geometry/material evidence and isolated browser adapters."""
import hashlib
import json
import unittest
from pathlib import Path
from terrain_water_floor import ROOT,FORMAT,NativeFloor,border_effect
from terrain_water_tests import javascript

EXPORT=ROOT/'analysis/raw/map-water-floor-ready-20261111'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'


class PublicTests(unittest.TestCase):
    def test_connector_refuses_main_and_backups(self):
        from connect_water_floor import connect
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)

    def test_floor_adapter_changes_only_vertex_interface(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const code=(await readFile('tools/preview/source-water-floor.js','utf8')).replace(/^import.*?;$/gm,'');
        const{adaptFloorVertex}=await import('data:text/javascript,'+encodeURIComponent(code));
        const s='attribute highp vec4 Vertex;attribute mediump vec2 TexCoord0;attribute mediump vec2 TexCoord1;attribute lowp vec4 Color0;void main(){gl_Position=WorldViewProjectionMatrix * Vertex;float a=waterHeight-Vertex.y;vec2 uv0=TexCoord0;vec2 uv1=TexCoord1;vec3 c=Color0.rgb;}';
        const o=adaptFloorVertex(s);assert(o.includes('waterHeight-vec4(position,1.0).y'));assert(o.includes('vec2 uv0=uv;'));assert(o.includes('vec2 uv1=terrainMaskUV;'));assert(o.includes('attribute lowp vec4 terrainSourceColor;'));assert.throws(()=>adaptFloorVertex('void main(){}'));
        """)

    def test_border_adapter_preserves_far_depth_operation(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const code=(await readFile('tools/preview/source-water-floor.js','utf8')).replace(/^import.*?;$/gm,'');
        const{adaptBorderVertex}=await import('data:text/javascript,'+encodeURIComponent(code));
        const s='attribute highp vec4 Vertex;attribute highp vec4 Color0;void main(){gl_Position=M*Vertex;gl_Position.z = gl_Position.w;color=Color0;}';
        const o=adaptBorderVertex(s);assert(o.includes('gl_Position.z = gl_Position.w;'));assert(o.includes('color=terrainSourceColor;'));assert.throws(()=>adaptBorderVertex('void main(){}'));
        """)


@unittest.skipUnless(NATIVE.is_file()and(EXPORT/'audit.json').is_file(),'Original floor/border inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from analyze_native_resources import NativeImage
            from map_loading_evidence import Sources
            from resource_packs import DEFAULT_SOURCE
            cls.image=NativeImage(NATIVE.read_bytes());cls.native=NativeFloor(cls.image);cls.sources=Sources(DEFAULT_SOURCE)
        except ImportError as e:raise unittest.SkipTest(str(e))
        cls.profile=json.loads((EXPORT/'terrain-water-floor.json').read_text())

    def test_native_full_resolution_indices_cover_both_parities_and_every_cell_once(self):
        actual=self.native.triangle_indices();self.assertEqual(actual,self.profile['triangleIndices'])
        for parity,chunks in actual.items():
            for j,indices in enumerate(chunks):
                self.assertEqual(len(indices),384);area=0;faces=set()
                for k in range(0,len(indices),3):
                    a,b,c=indices[k:k+3];ax,az=a%65,a//65;bx,bz=b%65,b//65;cx,cz=c%65,c//65
                    area+=(bz-az)*(cx-ax)-(bx-ax)*(cz-az)
                    self.assertGreater((bz-az)*(cx-ax)-(bx-ax)*(cz-az),0)
                    faces.add(tuple(sorted((a,b,c))))
                self.assertEqual(area,128);self.assertEqual(len(faces),128)
        self.assertNotEqual(actual['0'][0],actual['1'][0])

    def test_all_original_wet_descriptors_and_source_tiles_match(self):
        water=json.loads((ROOT/'analysis/raw/map-water-ready-20261111/terrain-water.json').read_text())
        self.assertEqual([t['tile']for t in water['tiles']],[t['tile']for t in self.profile['tiles']]);count=0
        for row in self.profile['tiles']:
            raw=self.sources.read('world/tutorial/terrain/%04d_%04d.trn'%tuple(row['tile']))
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sourceSHA256']);cs=self.native.read(raw)
            for chunk in row['chunks']:
                j=chunk['chunk'][1]*8+chunk['chunk'][0];self.assertTrue(cs[j]['flags']&0x10000)
                self.assertEqual(self.native.descriptor(j),{k:v for k,v in chunk.items()if k!='chunk'});count+=1
        self.assertEqual(count,4098)

    def test_original_color_table_pixels_not_painted(self):
        from PIL import Image
        self.assertEqual(len(self.profile['tables']),2)
        for packed,row in self.profile['tables'].items():
            data=self.native.color_table(int(packed));png=Image.open(EXPORT/Path(row['url']).name)
            self.assertEqual(png.size,(256,1));self.assertEqual(png.tobytes(),data)
            self.assertEqual(hashlib.sha256(data).hexdigest(),row['rgbaSHA256'])
            self.assertEqual(data[:4],bytes([255]*4));self.assertEqual(data[-1],0)
            self.assertTrue(all(data[k+3]>=data[k+7]for k in range(0,1016,4)))

    def test_original_border_state_buffer_and_shader_identity(self):
        self.assertEqual(border_effect(self.sources),self.profile['borderProfiles'])
        q=self.native.quad();actual={k:v for k,v in self.profile['quad'].items()if k!='colors'}
        self.assertEqual(q,actual);self.assertEqual(self.profile['quad']['colors'],[0,0,0,255]*4)
        for name,row in self.profile['shaders'].items():
            raw=self.sources.read(name);self.assertEqual((EXPORT/name).read_bytes(),raw)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])

    def test_old_assets_lights_physics_and_main_save_are_preserved(self):
        runtime=ROOT/'analysis/raw/showcase-20261110/running-preview'
        before=json.loads((ROOT/'analysis/raw/water-floor-border-20261111/before-assets.json').read_text())
        for name,row in before.items():self.assertEqual(hashlib.sha256((runtime/'game-data/converted'/name).read_bytes()).hexdigest(),row['sha256'],name)
        old=json.loads((ROOT/'analysis/raw/water-floor-border-20261111/before-public.json').read_text())
        for name,row in old.items():
            if name in ('explore-map.html','explore-map.js'):continue
            digest=row['sha256']if isinstance(row,dict)else row
            self.assertEqual(hashlib.sha256((runtime/'prototype/public'/name).read_bytes()).hexdigest(),digest,name)
        cfg=json.loads((runtime/'prototype/native-physics.json').read_text())
        self.assertTrue(cfg['terrainLighting'].endswith('map-water-ready-20261111/terrain-lighting.json'))
        self.assertEqual(hashlib.sha256((ROOT/'runtime/characters.json').read_bytes()).hexdigest(),'8db90023214c32d3e3a6ea88fdbcf3aa144582288a4d28651398f29f296af401')
        self.assertIn('status = "PAUSED"',(Path.home()/'.codex/automations/2/automation.toml').read_text())


if __name__=='__main__':unittest.main()
