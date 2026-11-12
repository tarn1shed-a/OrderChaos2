"""Original temple identity/mips, GL request boundaries and browser isolation."""
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from temple_sampling import export,mip_chain,verify

RAW=ROOT/'analysis/raw/temple-sampling-20261112'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
EXP=RAW/'export'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'
NODE=shutil.which('node')or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')

def pvr(mips=True):
    blocks=bytes(32)+bytes([0xff])*8+bytes([0x55])*8
    if not mips:blocks=blocks[:32]
    return struct.pack('<13I',52,8,8,3 if mips else 0,0x136 if mips else 0x36,len(blocks)+(8 if mips else 0),4,0,0,0,0,0x21525650,1)+blocks+(bytes([0x77])*8 if mips else b'')

class Public(unittest.TestCase):
    def test_complete_original_blocks_and_distinct_file_levels_retained(self):
        raw=pvr();meta,levels,pixels,_=mip_chain(raw)
        self.assertEqual(meta['fileMipLevels'],4);self.assertEqual([r['sourceOffset']for r in levels],[52,84,92,100])
        self.assertEqual([r['sourceBytes']for r in levels],[32,8,8,8]);self.assertEqual(len(pixels),(64+16+4+1)*4)
        self.assertEqual(hashlib.sha256(raw[84:92]).hexdigest(),levels[1]['sourceBlockSHA256'])
        for changed in(raw[:-1],raw+b'\0',raw[:12]+struct.pack('<I',2)+raw[16:]):
            with self.assertRaises(ValueError):mip_chain(changed)

    def test_browser_validates_complete_chain_hash_and_does_not_change_other_models(self):
        if not Path(NODE).is_file():self.skipTest('Node required')
        code="import assert from'node:assert/strict';import{createHash}from'node:crypto';import{createTempleSampling,validateTempleSampling}from'"+(ROOT/'tools/preview/source-temple-sampling.js').as_uri()+"';"+r'''
const bytes=new Uint8Array(84),sha=createHash('sha256').update(bytes).digest('hex');const policy={format:'oc2-source-temple-sampling-v1',profile:'APK_Default',originalDeviceObserved:false,lightingChanged:false,configuration:{Anisotropy:4,EnableSkipMoreMipmapLevel:false,TextureSkippedMipmaps:0,LightmapSkippedMipmaps:0,DisableAnisotropy:false},models:[{model:'temple',sourceSHA256:'a'.repeat(64),diffuse:['color']}],instances:[{id:7,model:'temple',tile:[-41,2],atlases:['color']}],textures:[{source:'color',sourceSHA256:'b'.repeat(64),sha256:sha,url:'/assets/source-temple-sampling/test.rgba',width:4,height:4,bytes:84,levels:[{level:0,width:4,height:4,offset:0,bytes:64},{level:1,width:2,height:2,offset:64,bytes:16},{level:2,width:1,height:1,offset:80,bytes:4}],sampler:{minGL:9985,magGL:9729,wrapSGL:10497,wrapTGL:10497,anisotropy:4}}]};
const T={NoColorSpace:'none',RepeatWrapping:'repeat',LinearMipmapNearestFilter:'source-min3',LinearFilter:'linear',DataTexture:class{constructor(data,w,h){this.image={data,width:w,height:h};this.userData={};}}};
const gl={getExtension:()=>null},renderer={getContext:()=>gl};const c=await createTempleSampling(T,renderer,null,policy,async()=>bytes.buffer),old={colorSpace:T.NoColorSpace};const tex=c.diffuse('temple','color',old);assert.notEqual(tex,old);assert.equal(c.diffuse('unrelated','anything',old),old);assert.equal(tex.generateMipmaps,false);assert.equal(tex.minFilter,'source-min3');assert.deepEqual(tex.mipmaps.map(x=>x.data.byteLength),[64,16,4]);assert.equal(old.minFilter,undefined);
const material={uniforms:{sourceAtlas:{value:old}}},root={traverse(fn){fn({isMesh:true,material})}};c.bindAtlases(root,{id:7,model:'temple',tile:[-41,2]},new Map([['color',old]]));assert.equal(material.uniforms.sourceAtlas.value,tex);
await assert.rejects(createTempleSampling(T,renderer,null,policy,async()=>new Uint8Array(84).fill(1).buffer));
for(const mutate of[p=>p.textures[0].levels.pop(),p=>p.textures[0].levels[1].offset++,p=>p.configuration.Anisotropy=8,p=>p.textures[0].sampler.minGL=9987,p=>p.textures.push(p.textures[0])]){const p=structuredClone(policy);mutate(p);assert.throws(()=>validateTempleSampling(p));}
assert.throws(()=>c.validateModel({model:'temple'},{sourceSHA256:'0'.repeat(64),materials:[{diffuse:'color'}]}));
'''
        r=subprocess.run([NODE,'--input-type=module','-e',code],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)

    def test_public_reader_does_not_import_native_dependencies(self):
        import sys
        r=subprocess.run([sys.executable,'-c',"import sys;sys.path.insert(0,sys.argv[1]);import temple_sampling;assert not {'unicorn','capstone','elftools'}&set(sys.modules)",str(ROOT/'tools')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)

@unittest.skipUnless(NATIVE.is_file()and(EXP/'policy.json').is_file(),'Original source/native bytes stay local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes())

    def test_original_pvr_and_gl_requests_include_capability_and_pending_mip_branches(self):
        from native_temple_sampling import TempleSamplingProbe
        p=TempleSamplingProbe(self.image)
        for kind in('diffuse','atlas'):
            for aniso,cap,extension,ready in((4,16,True,True),(4,2,True,True),(0,16,True,True),(4,16,False,True),(4,16,True,False)):
                r=p.sampler(pvr(),kind=kind,anisotropy=aniso,maximum=cap,extension=extension,mips_ready=ready);calls={x['parameter']:x['value']for x in r['calls']}
                self.assertEqual(r['descriptor']['freshManagerFlags'],'0x22');self.assertTrue(r['descriptor']['mipsAfterLoaderGate'])
                self.assertEqual(calls[10241],9985 if ready else 9729);self.assertEqual(calls[10242],10497);self.assertEqual(calls[10243],10497)
                # A request clamped to the existing constructor value 1 is
                # unchanged; the source setter does not mark it dirty.
                self.assertEqual(calls.get(34046),min(aniso,cap)if extension and aniso>1 else None);self.assertFalse(r['GLExecuted'])
        r=p.sampler(pvr(False));self.assertEqual(next(x['value']for x in r['calls']if x['parameter']==10241),9729)

    def test_source_sampler_code_change_is_rejected(self):
        im=self.image
        class Changed:
            elf=im.elf
            def read(self,at,n):
                raw=im.read(at,n);return bytes([raw[0]^1])+raw[1:]if at==0x14320d4 else raw
        with self.assertRaisesRegex(ValueError,'temple sampling'):verify(Changed())

    def test_every_level_redecodes_from_original_blocks_and_base_png_is_identical(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from PIL import Image
        source=Sources(DEFAULT_SOURCE);policy=json.loads((EXP/'policy.json').read_text());assets=RUN/'game-data/converted';manifest=json.loads((assets/'source-map-part-lightmaps/manifest.json').read_text());baked=json.loads((assets/manifest['sceneBakedLighting']['url'][8:]).read_text())
        self.assertEqual(sum(len(t['levels'])for t in policy['textures']),230)
        for t in policy['textures']:
            raw=source.read(t['source']);meta,levels,rgba,_=mip_chain(raw);self.assertEqual(levels,t['levels']);self.assertEqual(rgba,(EXP/Path(t['url']).name).read_bytes());self.assertEqual(hashlib.sha256(rgba).hexdigest(),t['sha256'])
            url=next(r['url']for r in baked['atlases']if r['sourcePath']==t['source'])if t['source'].startswith('texture/lightmap/')else manifest['textures'][t['source']]
            self.assertEqual(Image.open(assets/url[8:]).convert('RGBA').tobytes(),rgba[:levels[0]['bytes']])

    def test_rebuild_and_connector_replay_are_exact_and_repeat_refused(self):
        from connect_temple_sampling import connect
        with tempfile.TemporaryDirectory(dir=RAW)as t:
            p=Path(t);out=p/'export';export(RUN,out);self.assertEqual({x.name:x.read_bytes()for x in EXP.iterdir()},{x.name:x.read_bytes()for x in out.iterdir()})
            runtime=p/'runtime';pub=runtime/'prototype/public';pub.mkdir(parents=True);(runtime/'game-data/converted').mkdir(parents=True)
            for n in('explore-map.js','explore-map.html'):shutil.copyfile(RAW/('before-'+n),pub/n)
            self.assertEqual(connect(runtime,out)['files'],30);files={str(x.relative_to(runtime)):x.read_bytes()for x in runtime.rglob('*')if x.is_file()}
            # Pin this historical connector stage; later presentation adapters
            # legitimately change the live entry, not the sampling export.
            pins={'prototype/public/explore-map.js':'bbbe7e6fbfbf45ffa281cb7f08410099285afb8c62ca14522f9d387f4d1f1c60',
                  'prototype/public/explore-map.html':'890166e4e31864e62de8ee193f0acc5d83a0eeefd52e4e1c7f615193db0bdd70'}
            for n,b in files.items():
                if n in pins:self.assertEqual(hashlib.sha256(b).hexdigest(),pins[n])
                else:self.assertEqual((RUN/n).read_bytes(),b)
            with self.assertRaises(ValueError):connect(runtime,out)
            self.assertEqual(files,{str(x.relative_to(runtime)):x.read_bytes()for x in runtime.rglob('*')if x.is_file()})

    def test_geometry_placements_lights_old_assets_and_private_saves_preserved(self):
        for n,sha in json.loads((RAW/'before-assets.json').read_text()).items():self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/n).read_bytes()).hexdigest(),sha,n)
        old=json.loads((RUN/'game-data/converted/source-map-part-lightmaps/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text());new.pop('sourceTempleSampling');self.assertEqual(old,new)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'before-main-private.json').read_bytes());self.assertEqual((RUN/'runtime/showcase-characters.json').read_bytes(),(RAW/'before-demo-private.json').read_bytes());self.assertIn('status = "PAUSED"',Path('/Users/kevin/.codex/automations/2/automation.toml').read_text())

if __name__=='__main__':unittest.main()
