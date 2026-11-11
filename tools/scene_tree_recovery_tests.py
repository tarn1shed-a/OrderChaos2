import hashlib,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from scene_tree_recovery import MODELS,native_check,export
from scene_texture_sampling import repeat_override,recover_scene_sampling
from tutorial_map_geometry import ROOT

RAW=ROOT/'analysis/raw/map-tree-samplers-20261111'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
EXP=ROOT/'analysis/raw/map-trees-ready-20261111'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'

class Public(unittest.TestCase):
    def test_override_is_exact_and_not_a_generic_permission(self):
        self.assertTrue(repeat_override(dict(zip(('addressU','addressV','minFilter','magFilter'),(0,0,0,1)))))
        for r in [{},dict.fromkeys(('addressU','addressV','minFilter','magFilter')),{'addressU':0,'addressV':1,'minFilter':0,'magFilter':1}]:self.assertFalse(repeat_override(r))
    def test_wrong_native_evidence_fails_before_execution(self):
        class Changed:
            def read(self,a,n):return bytes(n)
            data=b'changed'
        with self.assertRaises(ValueError):native_check(Changed())
    def test_browser_only_accepts_evidenced_requests_and_owns_its_sampler(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        code=r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';
const{sceneDiffuseTexture}=await import('data:text/javascript;base64,'+Buffer.from(readFileSync(process.argv[1])).toString('base64'));
let clones=0;const texture={image:{width:512,height:512},minFilter:'unchanged-min',magFilter:'unchanged-mag',clone(){clones++;return{...this}}};
const mat={name:'tree',diffuse:'original'};const source={index:0,name:mat.name,texture:mat.diffuse,sourceTexture:{width:512,height:512,typeId:1},addressU:0,addressV:0,sourceRequest:{addressU:0,addressV:0,minFilter:0,magFilter:1}};
const p={format:'oc2-scene-sampling-v2',materials:[source]},T={RepeatWrapping:1000};
const owned=sceneDiffuseTexture(T,texture,mat,0,p);assert.notEqual(owned,texture);assert.equal(owned.wrapS,1000);assert.equal(owned.minFilter,'unchanged-min');assert.equal(owned.magFilter,'unchanged-mag');assert.equal(texture.wrapS,undefined);
for(const request of[{...source.sourceRequest,addressV:1},{...source.sourceRequest,minFilter:2}])assert.throws(()=>sceneDiffuseTexture(T,texture,mat,0,{...p,materials:[{...source,sourceRequest:request}]}));
assert.throws(()=>sceneDiffuseTexture(T,texture,mat,0,{...p,format:'oc2-scene-sampling-v1'}));assert.equal(clones,1);
'''
        subprocess.run([node,'--input-type=module','-e',code,str(ROOT/'tools/preview/scene-sampling.js')],check=True,capture_output=True)

@unittest.skipUnless(NATIVE.is_file()and EXP.is_dir(),'Original map/model data stays local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes());cls.audit=json.loads((EXP/'audit.json').read_text())
    def test_original_repeat_setter_and_lightmap_reference_exchange(self):
        self.assertEqual(native_check(self.image),{'addressU':0,'addressV':0,'placeholderSamplerCopiedToAtlas':False,'nativeCPU':True,'activeMinFilterRecovered':False})
    def test_source_model_and_instance_counts_without_filling_other_gaps(self):
        self.assertEqual({a['model']for a in self.audit['added']},set(MODELS));self.assertEqual(len(self.audit['added']),21);self.assertEqual(self.audit['displayedInstances'],1146);self.assertEqual(self.audit['omittedInstances'],112);self.assertFalse(self.audit['activeFilterRecovered']);self.assertFalse(self.audit['lightsChanged'])
    def test_rebuild_and_existing_geometry_lighting_preserved(self):
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            export(RUN,Path(td));self.assertEqual({p.name:p.read_bytes()for p in EXP.iterdir()},{p.name:p.read_bytes()for p in Path(td).iterdir()})
        assets=RUN/'game-data/converted';old=json.loads((assets/'source-layers/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text());self.assertEqual(new['scenery'][:len(old['scenery'])],old['scenery'])
        ob=json.loads((assets/old['sceneBakedLighting']['url'].removeprefix('/assets/')).read_text());nb=json.loads((EXP/'baked-lighting.json').read_text());self.assertEqual(nb['instances'][:len(ob['instances'])],ob['instances'])
        for k in ob.keys()-{'instances','atlases'}:self.assertEqual(nb[k],ob[k])
        for k in old.keys()-{'scenery','sceneBakedLighting','textures','sourceSelection'}:self.assertEqual(new[k],old[k])
    def test_connector_replay_is_atomic_on_repeat(self):
        from connect_scene_trees import connect
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            p=Path(td);(p/'game-data/converted').mkdir(parents=True);pub=p/'prototype/public';pub.mkdir(parents=True)
            for n in('explore-map.js','explore-map.html','scene-sampling.js'):shutil.copyfile(RAW/('before-'+n),pub/n)
            self.assertEqual(connect(p,EXP)['files'],14)
            before={str(f.relative_to(p)):f.read_bytes()for f in p.rglob('*')if f.is_file()}
            stage_hashes={'prototype/public/explore-map.js':'2c7f14d679c0ebac0552685ff4da6c4f4e6738bffd0f122d9e06fee9beaa9d24',
                          'prototype/public/explore-map.html':'1cb4ad143fc460123836b3291401996c22d809832c36001ffdc4e02d892f9fca'}
            for n,b in before.items():
                if n in stage_hashes:self.assertEqual(hashlib.sha256(b).hexdigest(),stage_hashes[n])
                else:self.assertEqual(b,(RUN/n).read_bytes())
            with self.assertRaises(ValueError):connect(p,EXP)
            self.assertEqual(before,{str(f.relative_to(p)):f.read_bytes()for f in p.rglob('*')if f.is_file()})
    def test_private_assets_and_main_save_remain_unchanged(self):
        old=json.loads((RAW/'before-assets.json').read_text());assets=RUN/'game-data/converted'
        self.assertTrue(all(hashlib.sha256((assets/n).read_bytes()).hexdigest()==s for n,s in old.items()))
        self.assertEqual(hashlib.sha256((ROOT/'runtime/characters.json').read_bytes()).hexdigest(),'8db90023214c32d3e3a6ea88fdbcf3aa144582288a4d28651398f29f296af401')

if __name__=='__main__':unittest.main()
