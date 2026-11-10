"""Conformance checks for original Default LDR selection and arithmetic."""
import json
import math
import random
import shutil
import struct
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from default_map_lighting import ROOT,DEFAULT_APK,DEFAULT_SOURCE,NativeDefaultPostProbe,verify,export,audit_materials

NATIVE=ROOT/'analysis/raw/beff-native/library.so'
LEGACY=ROOT/'backups/prototype-withdrawal-20261108-224729/converted-preview'


class PublicTests(unittest.TestCase):
    def test_connector_cannot_restore_a_live_prototype(self):
        from connect_default_lighting import connect
        with self.assertRaisesRegex(ValueError,'ignored isolated preview'):
            connect(ROOT)

    def test_web_adapter_formula_and_translation(self):
        node=shutil.which('node')
        bundled=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
        if not node and bundled.is_file():node=str(bundled)
        if not node:self.skipTest('Node required for the pure browser-adapter checks')
        script="""import assert from 'node:assert/strict';
          import {readFile} from 'node:fs/promises';
          const {ldrCombine,ldrBloomIntensity,translateOriginalShader}=await import('data:text/javascript,'+encodeURIComponent(await readFile('./tools/preview/original-default-postprocess.js','utf8')));
          for(let k=0;k<=255;k++){
            const a=[k/255,k/255,k/255],b=[0,.1,1],out=ldrCombine(a,b);
            assert.equal(out[0],a[0]);assert.equal(out[2],1);
            assert(out[1]>=a[1]&&out[1]<=1);
          }
          assert.equal(ldrBloomIntensity(0,0),0);
          assert.equal(ldrBloomIntensity(0,1),Math.fround(.2));
          const src='uniform sampler2D texture; varying vec2 uv; void main(){gl_FragColor=texture2D(texture,uv);}';
          const t=translateOriginalShader(src,'fragment');
          assert(t.includes('uniform sampler2D sourcePicture;'));
          assert(t.includes('sourceOutput=texture(sourcePicture,uv)'));
          assert(!t.includes('gl_FragColor'));assert(t.includes('in vec2 uv'));
          assert.throws(()=>translateOriginalShader(src,'geometry'));
        """
        result=subprocess.run([node,'--input-type=module','-e',script],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


@unittest.skipUnless(NATIVE.is_file()and DEFAULT_APK.is_file(),'Original native/APK inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes())

    def test_original_combine_mask_distinguishes_default_from_hdr(self):
        probe=NativeDefaultPostProbe(self.image)
        self.assertEqual(probe.combine_mask(1,False),0x10)
        self.assertEqual(probe.combine_mask(1,True),0x6000)
        self.assertEqual(probe.combine_mask(0,False),0)
        rng=random.Random(711)
        for _ in range(64):
            flags=rng.getrandbits(16);hdr=bool(rng.randrange(2))
            expected=0 if flags&32 else (((0x6000 if hdr else 16)if flags&1 else 0)|
                      ((flags&4)<<4)|((flags<<2)&32)|((flags&16)<<5)|((flags&256)<<3)|((flags<<2)&256))
            self.assertEqual(probe.combine_mask(flags,hdr),expected)

    def test_original_bloom_setter_float32_arithmetic(self):
        f=lambda x:struct.unpack('<f',struct.pack('<f',x))[0]
        p=NativeDefaultPostProbe(self.image);rng=random.Random(56)
        for _ in range(64):
            d,i=f(rng.random()*2),f(rng.random()*4)
            self.assertEqual(p.intensity(d,i),f(f(d+f(math.sqrt(i)))*f(.2)))

    def test_changed_original_code_is_rejected(self):
        image=self.image
        class Changed:
            elf=image.elf
            def read(self,at,size):
                raw=image.read(at,size)
                return bytes([raw[0]^1])+raw[1:]if at==0x346574 else raw
        with self.assertRaisesRegex(ValueError,'postprocess code changed'):verify(Changed())

    def test_default_does_not_mean_gpu6(self):
        from native_device_selection_probe import NativeDeviceSelectionProbe
        with zipfile.ZipFile(DEFAULT_APK)as z:gpu=json.loads(z.read('assets/GameOptions.json'))['profiles']['GPU']
        original=NativeDeviceSelectionProbe(self.image)
        defaults=dict(original.updates(gpu,''));gpu6=dict(original.updates(gpu,'GPU_6'))
        self.assertTrue(defaults['EnableBloom']);self.assertFalse(defaults['EnableBloomHDR'])
        self.assertTrue(gpu6['EnableBloomHDR'])

    def test_export_preserves_original_shader_bytes(self):
        from map_loading_evidence import Sources
        with tempfile.TemporaryDirectory()as folder:
            p=Path(folder);(p/'manifest.json').write_text(json.dumps({'sourceSelection':{'profile':'APK_Default'}}))
            result=export(self.image,DEFAULT_SOURCE,DEFAULT_APK,p)
            self.assertFalse(result['combine']['HDR']);self.assertFalse(result['combine']['LUT'])
            self.assertEqual(result['combine']['defines'],['HAS_BLOOM'])
            sources=Sources(DEFAULT_SOURCE)
            for name in result['shaders']:self.assertEqual((p/name).read_bytes(),sources.read(name))

    @unittest.skipUnless(LEGACY.is_dir(),'Archived preview assets stay local')
    def test_material_and_diffuse_pixel_identity(self):
        report=audit_materials(DEFAULT_SOURCE,LEGACY)
        self.assertEqual(len(report['models']),16)
        self.assertTrue(all(m['meshCoreStreamsExact']for m in report['models']))
        self.assertEqual(sum(m['materialCount']for m in report['models']),50)
        self.assertEqual(len(report['diffuseTextures']),17)
        self.assertTrue(all(v['RGBAPixelsExact']for v in report['diffuseTextures'].values()))


if __name__=='__main__':unittest.main()
