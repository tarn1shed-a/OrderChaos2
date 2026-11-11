import hashlib,json,math,shutil,subprocess,tempfile,unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from scene_dynamic_wind import FORMAT,EFFECT,NativeWind,verify_native,export,source_speeds,shader_block
RAW=ROOT/'analysis/raw/map-dynamic-wind-20261112';RUN=ROOT/'analysis/raw/showcase-20261110/running-preview';EXP=ROOT/'analysis/raw/map-dynamic-wind-ready-20261112';NATIVE=ROOT/'analysis/raw/beff-native/library.so'
NODE=r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';
let source=readFileSync(process.argv[1],'utf8').replace(/^import .*;$/gm,'').replace('export {bindInstanceLightmap};','');
source=`const oldCreate=()=>({old:true}),baseCreate=()=>({vertexShader:'void main(){vec4 view=modelViewMatrix*vec4(position,1.0);gl_Position=projectionMatrix*view;}',uniforms:{},defines:{},userData:{}});`+source;
const api=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
'''
class Public(unittest.TestCase):
    def node(self,body):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        r=subprocess.run([node,'--input-type=module','-e',NODE+body,str(ROOT/'tools/preview/source-dynamic-wind.js')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
    def test_wrong_image_rejected_before_execution(self):
        class Wrong:
            def read(self,a,n):return b'changed original'
        with self.assertRaises(ValueError):verify_native(Wrong())
    def test_host_clock_preserves_source_integer_milliseconds_float32_and_bounds(self):
        self.node(r'''
const a=api.createWindClock(987654),b=api.createWindClock(0);assert.equal(a.update(987654),0);assert.equal(b.update(1234567),1.2340000867843628);assert.equal(a.update(988999),Math.fround(.001));
assert.throws(()=>a.update(987000));assert.throws(()=>b.update(1.2));assert.throws(()=>b.update((0x100000000)*1000));assert.throws(()=>api.createWindClock(-1));assert.equal(b.update(0xffffffff*1000),Math.fround(Math.fround(0xffffffff)*Math.fround(.001)));
''')
    def test_browser_guard_shader_insertion_and_rebinding(self):
        self.node(r'''
const native={value:Math.fround(.8),nativeCPU:true,resourceOrGPUCreated:false},r={index:0,name:'leaves',enabled:true,speed:native.value,nativePropertyCopy:native};
const p={format:api.DYNAMIC_WIND_FORMAT,effect:'ut_lightmap_shake_trans.bdae',fullOriginalFrameRestored:false,materials:[r],quality:{profile:'APK_Default',ShadersLevel:2,qualityMask:0,DCC_MAX:false,actualDeviceObserved:false},clock:{initialBase:0,initialPauseCount:0,scale:1,secondsScale:Math.fround(.001),hostOrigin:true},matrix:{semantic:87,operation:'transpose-full-world-matrix',nativeCPU:true,hostMatrixSubmission:true},vertexBlock:'vert.xyz += t1 * t1 * wind_off;'};
const data={source:'model/scene/region_whitepike/wp_plant_pinetree001.bdae',sourceDynamicWind:p,sceneAlpha:{materials:[{effectPath:p.effect}]},meshes:[{positions:[1,2,3],sourceUV2:[.1,.2],sourceWindAttributes:{sourceSemantic:6,runtimeSemantic:3,type:6,components:2}}]};
const T={Matrix4:class{constructor(){this.elements=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}copy(m){this.elements=[...m.elements];return this}transpose(){const a=this.elements;this.elements=a.map((v,i)=>a[(i%4)*4+Math.floor(i/4)]);return this}}},src={name:'leaves'};
const m=api.createBakedSceneMaterial(T,null,src,0,data,{});assert(m.vertexShader.indexOf('vert.xyz +=')<m.vertexShader.indexOf('vec4 view='));assert.equal(m.uniforms.shakeSpeed.value,native.value);assert.equal(m.defines.VERTEX_ANIM,1);
const clone={...m,uniforms:{sourceAtlas:{value:'original selected atlas'}}},geo={getAttribute:()=>({count:2,getY:i=>i*.2})},o={isMesh:true,material:clone,matrixWorld:new T.Matrix4(),onBeforeRender(){this.orientationChecked=true}},root={traverse(fn){fn(o)}},canvas={dataset:{}},clock=api.createWindClock(0);clock.update(1234567);
api.bindDynamicWind(T,root,{x:100,y:200,z:300},clock,canvas);o.onBeforeRender(null,null,null,geo,clone,null);assert(o.orientationChecked);assert.equal(clone.uniformsNeedUpdate,true);assert.equal(clone.uniforms.time.value,clock.value());assert.equal(clone.uniforms.sourceAtlas.value,'original selected atlas');assert.equal(JSON.parse(canvas.dataset.sourceDynamicWind).hostClockOrigin,true);
for(const mutate of[x=>delete x.sourceDynamicWind,x=>x.sourceDynamicWind.materials[0].speed=0,x=>x.sourceDynamicWind.materials[0].nativePropertyCopy.value=1,x=>x.sourceDynamicWind.quality.ShadersLevel=1,x=>x.sourceDynamicWind.clock.hostOrigin=false,x=>x.meshes[0].sourceUV2.pop(),x=>x.sourceDynamicWind.vertexBlock='unknown']){const bad=structuredClone(data);mutate(bad);assert.throws(()=>api.createBakedSceneMaterial(T,null,src,0,bad,{}));}
assert.deepEqual(api.createBakedSceneMaterial(T,null,src,0,{},{}),{old:true});
''')

@unittest.skipUnless(NATIVE.is_file()and EXP.is_dir(),'Original native/model files stay local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes());cls.audit=json.loads((EXP/'audit.json').read_text())
    def test_original_default_quality_and_source_clock_vs_browser_bridge(self):
        p=NativeWind(self.image);self.assertEqual([p.quality(x)for x in range(3)],[0x8000,0x4000,0]);self.assertEqual(p.quality(2,0x108),0x108)
        cases=[{'us':u,**p.time(u)}for u in[0,999,1000,1234567,9876543,16777217000,0xffffffff*1000]]
        Public().node('const cases='+json.dumps(cases)+r''';for(const c of cases){const x=api.createWindClock(0);assert.equal(x.update(c.us),c.seconds);}''')
    def test_original_world_setter_and_transpose_keep_rotation_scale_and_translation(self):
        p=NativeWind(self.image)
        for i in range(24):
            angle=i*.17;s=1+i*.01;c=math.cos(angle)*s;t=math.sin(angle)*s;m=[c,0,-t,0,0,s,0,0,t,0,c,0,100+i,3,-45,1];out=p.world_t(m)
            import struct
            f=lambda v:struct.unpack('<f',struct.pack('<f',v))[0]
            self.assertEqual(out,[f(m[(j%4)*4+j//4])for j in range(16)])
    def test_model_three_active_materials_extra_uv_and_original_shader_block(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from bdae_convert import BDAE
        from scene_wind_identity import NONZERO
        sources=Sources(DEFAULT_SOURCE)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'model.bdae';p.write_bytes(sources.read(NONZERO));r=BDAE(p);rows=source_speeds(r);self.assertEqual(sum(x['enabled']for x in rows),3)
            self.assertTrue(all(abs(x['speed']-.8)<1e-6 for x in rows if x['enabled']))
        block=shader_block(sources.read);self.assertEqual(block,(EXP/'wind-block.glsl').read_text());self.assertIn('WorldT * vec4(1.0, 0.0, 0.0, 0.0)',block)
        model=json.loads(next(p for p in EXP.glob('*.json')if len(p.stem)==64).read_text());self.assertGreater(max(v for m in model['meshes']for v in m['sourceUV2'][1::2]),.2)
    def test_rebuild_and_old_light_targets_and_instances_preserved(self):
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            export(RUN,Path(td));self.assertEqual({p.name:p.read_bytes()for p in EXP.iterdir()},{p.name:p.read_bytes()for p in Path(td).iterdir()})
        old=json.loads((RUN/'game-data/converted/source-map-zero-wind/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text());self.assertEqual(old['scenery'],new['scenery'][:152]);a=json.loads((RUN/'game-data/converted/source-map-zero-wind/baked-lighting.json').read_text());b=json.loads((EXP/'baked-lighting.json').read_text())
        for k in a.keys()-{'instances','atlases'}:self.assertEqual(a[k],b[k])
        self.assertEqual(a['instances'],b['instances'][:1199]);self.assertEqual(self.audit['displayedInstances'],1200);self.assertEqual(self.audit['omittedInstances'],58)
    def test_connector_replay_and_repeat_rejection_preserves_existing_files(self):
        from connect_dynamic_wind import connect
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            d=Path(td);(d/'game-data/converted').mkdir(parents=True);pub=d/'prototype/public';pub.mkdir(parents=True)
            for n in('explore-map.js','explore-map.html','scene-alpha.js','scene-culling.js'):shutil.copyfile(RAW/('before-'+n),pub/n)
            self.assertEqual(connect(d,EXP)['files'],13);files={str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()}
            for n,b in files.items():self.assertEqual(b,(RUN/n).read_bytes())
            with self.assertRaises(ValueError):connect(d,EXP)
            self.assertEqual(files,{str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()})
    def test_old_assets_main_save_and_pause_preserved(self):
        old=json.loads((RAW/'before-assets.json').read_text());self.assertEqual(len(old),2348);self.assertTrue(all(hashlib.sha256((RUN/'game-data/converted'/n).read_bytes()).hexdigest()==h for n,h in old.items()))
        self.assertEqual(hashlib.sha256((ROOT/'runtime/characters.json').read_bytes()).hexdigest(),'8db90023214c32d3e3a6ea88fdbcf3aa144582288a4d28651398f29f296af401');self.assertIn('status = "PAUSED"',Path('/Users/kevin/.codex/automations/2/automation.toml').read_text())

if __name__=='__main__':unittest.main()
