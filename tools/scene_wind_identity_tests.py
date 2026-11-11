import hashlib,json,math,shutil,subprocess,tempfile,unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from scene_wind_identity import FORMAT,EFFECT,MODELS,NONZERO,source_properties,export,native_scalar,verify_uv2
RAW=ROOT/'analysis/raw/map-wind-20261111';RUN=ROOT/'analysis/raw/showcase-20261110/running-preview';EXP=ROOT/'analysis/raw/map-wind-ready-20261111';NATIVE=ROOT/'analysis/raw/beff-native/library.so'

class Public(unittest.TestCase):
    def test_different_native_image_rejected(self):
        class Changed:
            def read(self,a,n):return b'wrong library'
        with self.assertRaises(ValueError):native_scalar(Changed(),0)
    def test_browser_zero_branch_guards_and_instance_uniform_survival(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        code=r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';
let s=readFileSync(process.argv[1],'utf8').replace(/^import .*;$/gm,'');
s=`const baseCreate=()=>({fragmentShader:'color.rgb*=texture2D(sourceAtlas,atlasUV).rgb;',uniforms:{},userData:{}}),grayCreate=()=>({old:true}),grayBind=(T,r)=>r.traverse(o=>{o.material={...o.material,uniforms:{sourceAtlas:{value:'original selected atlas'}}}});`+s;
const a=await import('data:text/javascript;base64,'+Buffer.from(s).toString('base64'));
const row={index:0,name:'tree',enabled:true,speed:0,nativePropertyCopy:{value:0,nativeCPU:true,resourceOrGPUCreated:false}},g={index:0,name:'tree',enabled:true,color:[.7,.7,.7],rate:.2,nativePropertyCopy:{color:[.7,.7,.7],rate:.2,nativeCPU:true,resourceOrGPUCreated:false}};
const d={sourceWindIdentity:{format:a.WIND_FORMAT,zeroDisplacementVerified:true,dynamicRendererInputsRestored:false,semantic:{sourceSemantic:6,runtimeSemantic:3,runtimeName:'texcoord2',nativeCPU:true},materials:[row]},sourceGray:{format:'oc2-source-scene-gray-v1',materials:[g]},sceneAlpha:{materials:[{effectPath:'ut_lightmap_shake_gray_trans.bdae'}]},meshes:[{positions:[1,2,3],sourceUV2:[.1,.2],sourceWindAttributes:{sourceSemantic:6,runtimeSemantic:3,type:6,components:2}}]};
const T={Vector3:class{constructor(...v){this.values=v}}},src={name:'tree'};
assert(a.validateWindIdentity(d,src,0));const m=a.createBakedSceneMaterial(T,null,src,0,d,{});assert(m.fragmentShader.includes('mix(texture2D'));assert(!m.vertexShader);assert.equal(m.uniforms.sourceGrayRate.value,.2);
const o={isMesh:true,material:m},root={traverse(fn){fn(o)}};a.bindInstanceLightmap(T,root,{},null,null);assert.equal(o.material.uniforms.sourceGrayRate.value,.2);assert.equal(o.material.uniforms.sourceAtlas.value,'original selected atlas');
for(const mutate of[x=>x.sourceWindIdentity.materials[0].speed=.8,x=>x.sourceWindIdentity.materials[0].nativePropertyCopy.value=.8,x=>x.sourceWindIdentity.dynamicRendererInputsRestored=true,x=>x.meshes[0].sourceUV2.pop(),x=>x.meshes[0].sourceUV2[0]=NaN,x=>x.sourceGray.materials[0].nativePropertyCopy.rate=.15,x=>delete x.sourceWindIdentity]){const bad=structuredClone(d);mutate(bad);assert.throws(()=>a.createBakedSceneMaterial(T,null,src,0,bad,{}));}
assert.deepEqual(a.createBakedSceneMaterial(T,null,src,0,{},{}),{old:true});
'''
        r=subprocess.run([node,'--input-type=module','-e',code,str(ROOT/'tools/preview/source-wind-identity.js')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)

@unittest.skipUnless(NATIVE.is_file()and EXP.is_dir(),'Original model/native evidence stays local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes());cls.audit=json.loads((EXP/'audit.json').read_text())
    def test_actual_source_speeds_override_effect_and_nonzero_is_separate(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from bdae_convert import BDAE
        sources=Sources(DEFAULT_SOURCE)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'source.bdae'
            for name in MODELS:
                p.write_bytes(sources.read(name));rows=source_properties(BDAE(p));speeds=[r['values']['shakeSpeed'][0]for r in rows if r['effect']==EFFECT];self.assertTrue(speeds);self.assertEqual(set(speeds),{0})
                for r in rows:
                    if r['effect']==EFFECT:self.assertAlmostEqual(r['values']['lightmap_gray_rate'][0],.2,places=6)
            p.write_bytes(sources.read(NONZERO));reader=BDAE(p);n,t=reader.section(172);speeds=[]
            for i in range(n):
                at=t+i*80
                for j in range(reader.u(at+32)):
                    q=reader.rel(at+36)+j*32
                    if reader.string(reader.q(q))=='shakeSpeed':speeds.append(reader.unpack('f',reader.rel(q+28))[0])
            self.assertEqual(len(speeds),3);self.assertTrue(all(abs(v-.8)<1e-6 for v in speeds));self.assertNotIn(NONZERO,{r['model']for r in self.audit['added']})
    def test_nonzero_or_wrong_typed_model_parameter_rejected_before_render(self):
        import struct
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from bdae_convert import BDAE
        from scene_wind_identity import recover
        sources=Sources(DEFAULT_SOURCE)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'model.bdae';p.write_bytes(sources.read(MODELS[0]));r=BDAE(p);n,t=r.section(172);at=t
            q=next(r.rel(at+36)+j*32 for j in range(r.u(at+32))if r.string(r.q(r.rel(at+36)+j*32))=='shakeSpeed')
            original=r.b;b=bytearray(original);struct.pack_into('<f',b,r.rel(q+28),.8);r.b=bytes(b)
            with self.assertRaisesRegex(ValueError,'Nonzero'):recover(sources.read,r,{},self.image)
            b=bytearray(original);struct.pack_into('<I',b,q+16,10);r.b=bytes(b)
            with self.assertRaisesRegex(ValueError,'shape'):source_properties(r)
    def test_native_semantic_and_scalar_and_zero_formula(self):
        self.assertEqual(verify_uv2(self.image)['runtimeSemantic'],3)
        for speed in(0,.800000011920929):self.assertEqual(native_scalar(self.image,speed)['value'],speed)
        for time in(0,1,2.3,4294967.295):
            for uv in(-.001,0,.21447,1.5):
                for world in(-25,0,1,3.2):self.assertEqual(uv*uv*world*math.sin(time*0),0)
    def test_rebuild_source_uv2_and_old_scene_light_inputs_preserved(self):
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            export(RUN,Path(td));self.assertEqual({p.name:p.read_bytes()for p in EXP.iterdir()},{p.name:p.read_bytes()for p in Path(td).iterdir()})
        old=json.loads((RUN/'game-data/converted/source-map-gray/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text());self.assertEqual(new['scenery'][:143],old['scenery'])
        a=json.loads((RUN/'game-data/converted/source-map-gray/baked-lighting.json').read_text());b=json.loads((EXP/'baked-lighting.json').read_text())
        for k in a.keys()-{'instances','atlases'}:self.assertEqual(a[k],b[k])
        self.assertEqual(b['instances'][:1155],a['instances']);self.assertEqual(len(self.audit['added']),44);self.assertEqual(self.audit['displayedModels'],152);self.assertEqual(self.audit['displayedInstances'],1199);self.assertEqual(self.audit['omittedInstances'],59)
        strides=set()
        for p in EXP.glob('*.json'):
            d=json.loads(p.read_text())
            if 'sourceWindIdentity'not in d:continue
            for mesh in d['meshes']:
                self.assertEqual(len(mesh['sourceUV2']),mesh['vertexCount']*2);self.assertTrue(all(math.isfinite(x)for x in mesh['sourceUV2']));strides.add(mesh['sourceWindAttributes']['stride'])
        self.assertEqual(strides,{48,64})
    def test_connector_replay_repeat_and_changed_assets_rejected(self):
        from connect_scene_wind_identity import connect
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            d=Path(td);(d/'game-data/converted').mkdir(parents=True);pub=d/'prototype/public';pub.mkdir(parents=True)
            for n in('explore-map.js','explore-map.html','scene-alpha.js','scene-culling.js'):shutil.copyfile(RAW/('before-'+n),pub/n)
            asset=next(p for p in EXP.glob('*.json')if len(p.stem)==64)
            conflict=d/'game-data/converted/source-map-zero-wind'/asset.name;conflict.parent.mkdir(parents=True);conflict.write_bytes(b'previous local edit')
            before={str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()}
            with self.assertRaises(ValueError):connect(d,EXP)
            self.assertEqual(before,{str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()})
            conflict.unlink() # This test created the disposable conflicting file.
            self.assertEqual(connect(d,EXP)['files'],26)
            files={str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()}
            for n,b in files.items():self.assertEqual(b,(RUN/n).read_bytes())
            with self.assertRaises(ValueError):connect(d,EXP)
            self.assertEqual(files,{str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()})
    def test_old_assets_save_and_paused_automation_preserved(self):
        assets=RUN/'game-data/converted';old=json.loads((RAW/'before-assets.json').read_text());self.assertEqual(len(old),2327);self.assertTrue(all(hashlib.sha256((assets/n).read_bytes()).hexdigest()==s for n,s in old.items()))
        self.assertEqual(hashlib.sha256((ROOT/'runtime/characters.json').read_bytes()).hexdigest(),'8db90023214c32d3e3a6ea88fdbcf3aa144582288a4d28651398f29f296af401')
        self.assertIn('status = "PAUSED"',Path('/Users/kevin/.codex/automations/2/automation.toml').read_text())

if __name__=='__main__':unittest.main()
