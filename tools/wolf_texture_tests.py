"""Source wolf identity, row-order correction and private connector checks."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/temple-display-fix-20261113'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
NODE=shutil.which('node')or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')

class Public(unittest.TestCase):
    def test_texture_cache_and_other_models_keep_their_orientation_and_color_space(self):
        if not Path(NODE).is_file():self.skipTest('Node required')
        code="import assert from'node:assert/strict';import{sourceWolfTexture,WOLF_SOURCE,WOLF_SHA}from'"+(ROOT/'tools/preview/source-wolf-texture.js').as_uri()+"';"+r'''
const original={isTexture:true,flipY:true,colorSpace:'existing-color-space',clone(){return {...this}}};
const entry={model:WOLF_SOURCE},data={sourceSHA256:WOLF_SHA},material={name:'wolf',diffuse:'texture/wolf_d.tga'},T={RepeatWrapping:'repeat'};
const fixed=sourceWolfTexture(T,entry,data,material,original);
assert.notEqual(fixed,original);assert.equal(fixed.flipY,false);assert.equal(original.flipY,true);
assert.equal(fixed.colorSpace,original.colorSpace);assert.equal(fixed.needsUpdate,true);
assert.equal(fixed.wrapS,'repeat');assert.equal(fixed.wrapT,'repeat');assert.equal(original.wrapS,undefined);
assert.equal(sourceWolfTexture(T,{model:'other'},data,material,original),original);
for(const [e,d,m,t]of [[entry,{sourceSHA256:'0'.repeat(64)},material,original],[entry,data,{...material,diffuse:'other'},original],[entry,data,material,null]])assert.throws(()=>sourceWolfTexture(T,e,d,m,t));
'''
        r=subprocess.run([NODE,'--input-type=module','-e',code],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)

    def test_unexplained_runtime_is_rejected_before_any_writes(self):
        from connect_wolf_texture import connect
        (ROOT/'analysis/raw').mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'analysis/raw')as tmp:
            runtime=Path(tmp);public=runtime/'prototype/public';public.mkdir(parents=True)
            for n in ('explore-map.js','explore-map.html'):(public/n).write_text('unexplained change')
            before={p.name:p.read_bytes()for p in public.iterdir()}
            with self.assertRaisesRegex(ValueError,'Preserve'):connect(runtime)
            self.assertEqual(before,{p.name:p.read_bytes()for p in public.iterdir()})

@unittest.skipUnless((RAW/'wolf-audit.json').is_file(),'Original wolf/source preview stays local')
class Original(unittest.TestCase):
    def test_source_model_shader_sampler_and_decoded_rows_replay(self):
        from wolf_texture_evidence import audit
        self.assertEqual(audit(RUN),json.loads((RAW/'wolf-audit.json').read_text()))

    def test_connector_replays_exact_files_and_refuses_repeat(self):
        from connect_wolf_texture import connect
        with tempfile.TemporaryDirectory(dir=RAW)as tmp:
            runtime=Path(tmp);public=runtime/'prototype/public';public.mkdir(parents=True)
            for n in ('explore-map.js','explore-map.html'):shutil.copyfile(RAW/('before-'+n),public/n)
            result=connect(runtime);self.assertEqual(result['files'],3);self.assertFalse(result['geometryOrUVChanged'])
            self.assertIn('sourceWolfTexture(THREE,entry,data,mat,cached)',(public/'explore-map.js').read_text())
            before={p.name:p.read_bytes()for p in public.iterdir()}
            with self.assertRaisesRegex(ValueError,'Preserve'):connect(runtime)
            self.assertEqual(before,{p.name:p.read_bytes()for p in public.iterdir()})

    @unittest.skipUnless((RAW/'temple-native-audit.json').is_file(),'Temple source audit stays local')
    def test_temple_geometry_placement_and_original_coordinate_code_replay(self):
        from temple_display_evidence import audit
        result=audit(RUN)
        self.assertEqual(result,json.loads((RAW/'temple-native-audit.json').read_text()))
        self.assertEqual((len(result['models']),len(result['instances'])),(5,8))
        self.assertFalse(result['templeHolesFixed'])

if __name__=='__main__':unittest.main()
