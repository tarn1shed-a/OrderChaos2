"""RGB8 scene reads must not inherit undefined source-material alpha."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT

RAW=ROOT/'analysis/raw/bridge-surfaces-20261113'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
NODE=shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')

class Public(unittest.TestCase):
    def test_only_RGB_scene_inputs_receive_opaque_sampler_semantics(self):
        if not Path(NODE).is_file(): self.skipTest('Node required')
        code="import assert from 'node:assert/strict';import {sourceRGBInputFragment,createOriginalDefaultPostprocess} from '"+(ROOT/'tools/preview/original-default-postprocess.js').as_uri()+"';"+r'''
const source='uniform lowp sampler2D sourcePicture;\nvoid main(){vec4 c=texture(sourcePicture,coord);gl_FragColor=c;}';
const result=sourceRGBInputFragment(source);
assert(result.includes('vec4(texture(sourcePicture,p).rgb,1.0)'));
assert(result.includes('vec4 c=sourceRGBPicture(coord)'));
assert.throws(()=>sourceRGBInputFragment(result));
assert.throws(()=>sourceRGBInputFragment(source.replace('coord','coord+offset')));
assert.throws(()=>sourceRGBInputFragment(source.replace('sampler2D','samplerCube')));
const materials=[];
class Target{constructor(){this.texture={};}dispose(){}}
class Geometry{getAttribute(){return{};}setAttribute(){}dispose(){}}
class Scene{add(){}}
class Material{constructor(value){Object.assign(this,value);materials.push(this);}dispose(){}}
class Mesh{constructor(geometry,material){this.geometry=geometry;this.material=material;}}
const THREE={WebGLRenderTarget:Target,PlaneGeometry:Geometry,Camera:class{},Scene,RawShaderMaterial:Material,Mesh,Matrix4:class{},Vector2:class{}};
globalThis.fetch=async url=>({ok:true,text:async()=>url.endsWith('vs')?'attribute vec4 Vertex;void main(){gl_Position=Vertex;}':source.replace('texture(sourcePicture,','texture2D(texture,').replace('sampler2D sourcePicture','sampler2D texture')});
const profile={format:'oc2-apk-default-postprocess-v1',configuration:{EnableRTTCreating:true,RTTViewportScale:1,EnableBloom:true,EnableBloomHDR:false},combine:{nativeMask:16,LUT:false},targets:{sceneSourceFormat:'RGB8',smallSourceFormat:'RGBA8'},shaders:{'pe_common_vs.glsl':'/assets/verified/APK_Default/vs','pe_common_fs.glsl':'/assets/verified/APK_Default/fs'}};
const effect=await createOriginalDefaultPostprocess(THREE,{},profile);
assert.equal(materials.length,4);
assert(materials[0].fragmentShader.includes('sourceRGBPicture(coord)'));
assert(materials[3].fragmentShader.includes('sourceRGBPicture(coord)'));
for(const index of [1,2]){
 assert(!materials[index].fragmentShader.includes('sourceRGBPicture'));
 assert(materials[index].fragmentShader.includes('texture(sourcePicture,coord)'));
}
await assert.rejects(createOriginalDefaultPostprocess(THREE,{}, {...profile,targets:{...profile.targets,sceneSourceFormat:'RGBA16F'}}));
effect.dispose();
'''
        p=subprocess.run([NODE,'--input-type=module','-e',code],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_connector_refuses_live_project(self):
        from connect_rgb_scene_target import connect
        with self.assertRaises(ValueError): connect(ROOT)

@unittest.skipUnless((RAW/'before-postprocess.js').is_file(),'Original preview evidence stays local')
class Original(unittest.TestCase):
    def test_original_format_and_source_shaders_are_still_pinned(self):
        from analyze_native_resources import NativeImage
        from default_map_lighting import verify,SHADERS
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())
        verify(image)
        sources=Sources(DEFAULT_SOURCE)
        for name,digest in SHADERS.items():
            raw=sources.read(name)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),digest)
            self.assertEqual(raw,(RUN/'game-data/converted/verified/APK_Default'/name).read_bytes())

    def test_connector_changes_one_file_and_preserves_unexplained_edits(self):
        from connect_rgb_scene_target import connect
        with tempfile.TemporaryDirectory(dir=RAW)as d:
            p=Path(d);public=p/'prototype/public';public.mkdir(parents=True)
            target=public/'original-default-postprocess-v1.js'
            shutil.copyfile(RAW/'before-postprocess.js',target)
            untouched=public/'unrelated.txt';untouched.write_text('preserve')
            self.assertEqual(connect(p)['files'],1)
            self.assertEqual(target.read_bytes(),(RUN/'prototype/public/original-default-postprocess-v1.js').read_bytes())
            self.assertEqual(untouched.read_text(),'preserve')
            before=target.read_bytes()
            with self.assertRaises(ValueError):connect(p)
            self.assertEqual(target.read_bytes(),before)
            target.write_bytes(before+b'// concurrent edit\n')
            edited=target.read_bytes()
            with self.assertRaises(ValueError):connect(p)
            self.assertEqual(target.read_bytes(),edited)

    def test_original_art_and_main_save_are_unchanged(self):
        assets=RUN/'game-data/converted'
        for name,digest in json.loads((RAW/'game-data-converted-before.json').read_text()).items():
            self.assertEqual(hashlib.sha256((assets/name).read_bytes()).hexdigest(),digest,name)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'main-before-private.json').read_bytes())

if __name__=='__main__':unittest.main()
