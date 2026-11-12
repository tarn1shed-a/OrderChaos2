import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT

RAW=ROOT/'analysis/raw/temple-ambient-20261112'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
NODE=shutil.which('node')or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')

class Public(unittest.TestCase):
    def test_character_rows_do_not_flip_or_mutate_the_shared_texture(self):
        if not Path(NODE).is_file():self.skipTest('Node required')
        code="import assert from'node:assert/strict';import{sourceCharacterTexture}from'"+(ROOT/'tools/preview/source-character-textures.js').as_uri()+"';"+r'''
const image={data:new Uint8Array([255,0,0,255,0,0,255,255])};
const old={isTexture:true,colorSpace:'none',flipY:true,image,clone(){return{...this};}};
const result=sourceCharacterTexture({NoColorSpace:'none'},old);
assert.notEqual(result,old);assert.equal(result.flipY,false);assert.equal(old.flipY,true);
assert.equal(result.image,old.image);assert.deepEqual([...image.data],[255,0,0,255,0,0,255,255]);
assert.equal(result.needsUpdate,true);assert.throws(()=>sourceCharacterTexture({NoColorSpace:'none'},{...old,colorSpace:'sRGB'}));
'''
        r=subprocess.run([NODE,'--input-type=module','-e',code],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)

@unittest.skipUnless((RAW/'character-orientation-audit.json').is_file(),'Original character/texture inputs stay local')
class Original(unittest.TestCase):
    def test_source_model_head_UV_and_all_seven_body_sampler_images_match(self):
        from character_orientation import audit
        result=audit(RUN);self.assertEqual(result,json.loads((RAW/'character-orientation-audit.json').read_text()))
        self.assertEqual(len(result['textures']),7);self.assertTrue(result['originalHeadUVPreserved'])

    def test_connector_replays_final_entry_and_refuses_repeat(self):
        from connect_character_orientation import connect
        with tempfile.TemporaryDirectory(dir=RAW)as d:
            p=Path(d);public=p/'prototype/public';public.mkdir(parents=True)
            for n in ['explore-map.js','explore-map.html']:shutil.copyfile(RAW/('before-character-'+n),public/n)
            self.assertEqual(connect(p)['files'],3)
            before={x.name:x.read_bytes()for x in public.iterdir()}
            for n,b in before.items():self.assertEqual(b,(RUN/'prototype/public'/n).read_bytes())
            with self.assertRaises(ValueError):connect(p)
            self.assertEqual(before,{x.name:x.read_bytes()for x in public.iterdir()})

if __name__=='__main__':unittest.main()
