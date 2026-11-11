import hashlib,io,json,shutil,struct,subprocess,tempfile,unittest,zipfile
from pathlib import Path
from tutorial_map_geometry import ROOT
from scene_zero_planes import FORMAT,MODEL,EFFECT,TEXTURE,all_mip_zero_alpha,export,verify_native,native_state,source_material
RAW=ROOT/'analysis/raw/map-planes-20261112';EXP=ROOT/'analysis/raw/map-planes-ready-20261112';RUN=ROOT/'analysis/raw/showcase-20261110/running-preview';NATIVE=ROOT/'analysis/raw/beff-native/library.so'

class Public(unittest.TestCase):
    def test_wrong_native_image_rejected(self):
        class Wrong:
            def read(self,a,n):return bytes(n)
        with self.assertRaises(ValueError):verify_native(Wrong())
    def test_incomplete_non_split_texture_does_not_hide_geometry(self):
        for raw in(b'',b'not a PVR',b'PK\x03\x04broken'):
            with self.assertRaises((ValueError,zipfile.BadZipFile)):all_mip_zero_alpha(raw)
    def test_browser_contract_zero_alpha_guard_and_draw_binding(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        code=r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';
const api=await import('data:text/javascript;base64,'+Buffer.from(readFileSync(process.argv[1],'utf8')).toString('base64'));
const mips=[8,4,2,1].map((n,i)=>({level:i,width:n,height:n,alphaRange:[0,0],alphaSHA256:'0'.repeat(64)}));
const p={format:api.ZERO_PLANE_FORMAT,model:'model/scene/plane.bdae',effect:'ut_trans.bdae',texture:'texture/plane.tga',allMipAlphaZero:true,alphaReference:0,colorAndDepthWrites:false,lightMapConsumed:false,fullQueueOrderRecovered:false,rgbLightingRestored:false,splitBranch:'fresh-project-default-0x800;successful-original-texture',actualOriginalDeviceObserved:false,mips,native:[0,1].map(()=>({nativeCPU:true,alphaReference:0,compiledProgramAndQueueFlagsObserved:false}))};
const src={name:'plane',diffuse:p.texture},data={source:p.model,sourceZeroPlane:p,materials:[src],sceneAlpha:{materials:[{index:0,name:'plane',texture:p.texture,effectPath:p.effect,rule:'discard-less-equal',reference:0}]},sceneCulling:{materials:[{index:0,name:'plane',effectPath:p.effect,cullEnabled:false}]}};
const T={NoColorSpace:'raw',DoubleSide:2,LessEqualDepth:3,ShaderMaterial:class{constructor(v){Object.assign(this,v);this.userData={}}}},map={image:{width:8,height:8},colorSpace:T.NoColorSpace,flipY:false},rgba=new Uint8Array(256);
const m=api.createZeroPlaneMaterial(T,map,src,0,data,()=>rgba);assert.equal(m.fragmentShader,'void main(){discard;}');assert.equal(m.depthWrite,true);assert.equal(m.depthTest,true);assert.equal(m.transparent,false);assert(!m.lights);assert(!m.uniforms.sourceAtlas);
const visible=rgba.slice();visible[3]=1;assert.throws(()=>api.createZeroPlaneMaterial(T,map,src,0,data,()=>visible));
for(const mutate of[x=>x.sourceZeroPlane.alphaReference=.5,x=>x.sourceZeroPlane.mips[3].alphaRange[1]=1,x=>x.sceneBakedLighting={},x=>x.sourceZeroPlane.lightMapConsumed=true,x=>x.sourceZeroPlane.native[0].alphaReference=.5]){const bad=structuredClone(data);mutate(bad);assert.throws(()=>api.createZeroPlaneMaterial(T,map,src,0,bad,()=>rgba));}
const o={isMesh:true,castShadow:true,onBeforeRender(){this.sourceOrientationChecked=true}},root={userData:{sourceZeroPlane:{format:api.ZERO_PLANE_FORMAT}},traverse(fn){fn(o)}},canvas={dataset:{}};api.bindZeroPlaneInstance(root,{id:9,tile:[1,2],model:p.model},canvas);o.onBeforeRender();assert(o.sourceOrientationChecked);assert.equal(o.castShadow,false);assert.equal(JSON.parse(canvas.dataset.sourceZeroPlaneDrawState).submittedUnique,1);
'''
        r=subprocess.run([node,'--input-type=module','-e',code,str(ROOT/'tools/preview/source-zero-planes.js')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)

@unittest.skipUnless(NATIVE.is_file()and EXP.is_dir(),'Original model/native evidence stays local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes());cls.audit=json.loads((EXP/'audit.json').read_text())
    def test_all_four_original_mips_zero_and_changed_alpha_rejected(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        raw=Sources(DEFAULT_SOURCE).read(TEXTURE);self.assertEqual([r['width']for r in all_mip_zero_alpha(raw)],[8,4,2,1])
        with zipfile.ZipFile(io.BytesIO(raw))as z:files={n:z.read(n)for n in z.namelist()}
        alpha=bytearray(files['alpha.pvr']);alpha[52:60]=b'\xff'*8;files['alpha.pvr']=bytes(alpha);out=io.BytesIO()
        with zipfile.ZipFile(out,'w')as z:
            for n,b in files.items():z.writestr(n,b)
        with self.assertRaisesRegex(ValueError,'Nonzero'):all_mip_zero_alpha(out.getvalue())
    def test_native_reference_zero_depth_state_and_uniform_sink_from_both_profiles(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from bdae_convert import BDAE
        source=Sources(DEFAULT_SOURCE)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'fx.bdae';p.write_bytes(source.read(EFFECT));r=BDAE(p);_,t=r.section(164)
            for field in(32,36):
                profile=r.rel(t+field);tech=r.rel(profile+4);ps=r.rel(tech+12);proof=native_state(self.image,r.b[ps+72:ps+160]);calls=proof['glCallsRecordedNotExecuted'];self.assertEqual(proof['alphaReference'],0);self.assertTrue(any(x['name']=='glDepthMask'and x['arguments'][0]==1 for x in calls));self.assertTrue(any(x['name']=='glDepthFunc'and x['arguments'][0]==0x203 for x in calls));self.assertEqual([x['value']for x in calls if x['name']=='glUniform1f'],[0])
    def test_original_queue_does_not_infer_final_order_from_trans_name(self):
        from scene_zero_planes import queue_boundaries
        data=json.loads((EXP/'30587a9eeffa0f307612023bbdbc2e997ada4d6a0ddcaa3ecb10aa9ced5a9599.json').read_text());state=bytes.fromhex(data['sourceZeroPlane']['native'][0]['state28']);cases=queue_boundaries(self.image,state)
        self.assertEqual([r['queueOffset']for r in cases],[0x130,0x148]);self.assertTrue(all(r['completed']and not r['actualProgramFlagsObserved']for r in cases))
    def test_one_sampler_material_does_not_require_lightmap(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from bdae_convert import BDAE
        source=Sources(DEFAULT_SOURCE)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'m.bdae';p.write_bytes(source.read(MODEL));r=BDAE(p);self.assertEqual(source_material(r)['name'],'tech0');n,t=r.section(172);b=bytearray(r.b);struct.pack_into('<I',b,t+32,3);r.b=bytes(b)
            with self.assertRaises(ValueError):source_material(r)
    def test_rebuild31_placements_preserves_old_scene_and_lightmap_profile(self):
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            export(RUN,Path(td));self.assertEqual({p.name:p.read_bytes()for p in EXP.iterdir()},{p.name:p.read_bytes()for p in Path(td).iterdir()})
        old=json.loads((RUN/'game-data/converted/source-map-dynamic-wind/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text());self.assertEqual(old['scenery'],new['scenery'][:-1]);self.assertEqual(old['sceneBakedLighting'],new['sceneBakedLighting']);self.assertEqual(len(new['scenery'][-1]['instances']),31);self.assertEqual(self.audit['sceneInstances'],1231);self.assertEqual(self.audit['zeroAlphaInstances'],31);self.assertEqual(self.audit['omittedInstances'],27);self.assertEqual(self.audit['lightmapBindingPresentButNotConsumed'],20)
    def test_connector_replay_and_repeat_rejection(self):
        from connect_zero_planes import connect
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            d=Path(td);(d/'game-data/converted').mkdir(parents=True);pub=d/'prototype/public';pub.mkdir(parents=True)
            for n in('explore-map.js','explore-map.html','scene-culling.js'):shutil.copyfile(RAW/('before-'+n),pub/n)
            self.assertEqual(connect(d,EXP)['files'],9);files={str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()}
            for n,b in files.items():self.assertEqual(b,(RUN/n).read_bytes())
            with self.assertRaises(ValueError):connect(d,EXP)
            self.assertEqual(files,{str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()})
    def test_old_assets_main_save_and_pause_preserved(self):
        old=json.loads((RAW/'before-assets.json').read_text());self.assertEqual(len(old),2356);self.assertTrue(all(hashlib.sha256((RUN/'game-data/converted'/n).read_bytes()).hexdigest()==h for n,h in old.items()));self.assertEqual(hashlib.sha256((ROOT/'runtime/characters.json').read_bytes()).hexdigest(),'8db90023214c32d3e3a6ea88fdbcf3aa144582288a4d28651398f29f296af401');self.assertIn('status = "PAUSED"',Path('/Users/kevin/.codex/automations/2/automation.toml').read_text())

if __name__=='__main__':unittest.main()
