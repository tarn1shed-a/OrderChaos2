import hashlib,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from scene_gray_materials import FORMAT,EFFECT,EXTRAS,MODELS,native_values,typed_values,export

RAW=ROOT/'analysis/raw/map-remaining-20261111';RUN=ROOT/'analysis/raw/showcase-20261110/running-preview';EXP=ROOT/'analysis/raw/map-gray-ready-20261111';NATIVE=ROOT/'analysis/raw/beff-native/library.so'

class Public(unittest.TestCase):
    def test_native_guard_rejects_a_different_image(self):
        class Changed:data=b'wrong library'
        with self.assertRaises(ValueError):native_values(Changed(),[.7]*3,.15)
    def test_browser_gray_formula_validation_and_instance_uniform_survival(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node unavailable')
        code=r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';
let source=readFileSync(process.argv[1],'utf8');source=source.replace(/^import .*;$/m,`const baseCreate=()=>({fragmentShader:'void main(){color.rgb*=texture2D(sourceAtlas,atlasUV).rgb;}',uniforms:{sourceAtlas:{value:'old'}},userData:{}}); const baseBind=(T,r)=>r.traverse(o=>{o.material={...o.material,uniforms:{sourceAtlas:{value:'selected original atlas'}}}});`);
const api=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));const{grayLight,createBakedSceneMaterial,bindInstanceLightmap,GRAY_FORMAT}=api;
assert.deepEqual(grayLight([.2,.4,.6],[.7,.6,.5],0),[.2,.4,.6]);assert.deepEqual(grayLight([.2,.4,.6],[.7,.6,.5],1),[.7,.6,.5]);
const a=grayLight([.2,.4,.6],[.7,.7,.7],.15);assert(a.every((v,i)=>Math.abs(v-[.275,.445,.615][i])<1e-10));
const row={index:0,name:'source grass',enabled:true,color:[.7,.7,.7],rate:.15,nativePropertyCopy:{color:[.7,.7,.7],rate:.15,nativeCPU:true,resourceOrGPUCreated:false}};
const data={sourceGray:{format:GRAY_FORMAT,materials:[row]},sceneAlpha:{materials:[{effectPath:'ut_lightmap_gray_trans.bdae'}]}},T={Vector3:class{constructor(...v){this.values=v}}};
const m=createBakedSceneMaterial(T,null,{name:row.name},0,data,{});assert(m.fragmentShader.includes('mix(texture2D(sourceAtlas,atlasUV).rgb,sourceGrayColor,sourceGrayRate)'));assert.equal(m.uniforms.sourceGrayRate.value,.15);
const o={isMesh:true,material:m},root={traverse(fn){fn(o)}};bindInstanceLightmap(T,root,{},null,null);assert.equal(o.material.uniforms.sourceGrayRate.value,.15);assert.equal(o.material.uniforms.sourceAtlas.value,'selected original atlas');
for(const bad of[{...row,rate:NaN},{...row,color:[1,1]},{...row,enabled:false},{...row,nativePropertyCopy:{...row.nativePropertyCopy,rate:.8}}])assert.throws(()=>createBakedSceneMaterial(T,null,{name:row.name},0,{...data,sourceGray:{format:GRAY_FORMAT,materials:[bad]}},{}));
assert(!createBakedSceneMaterial(T,null,{name:'old'},0,{},{}).uniforms.sourceGrayRate);
'''
        r=subprocess.run([node,'--input-type=module','-e',code,str(ROOT/'tools/preview/source-gray-materials.js')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
@unittest.skipUnless(NATIVE.is_file()and EXP.is_dir(),'Original map/model evidence stays local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes());cls.audit=json.loads((EXP/'audit.json').read_text())
    def test_original_scalar_vector_copy_uses_typed_source_payload(self):
        for color,rate in [([.7]*3,.15),([.125,.25,.5],0),([1,0,.25],1)]:
            r=native_values(self.image,color,rate);self.assertTrue(r['nativeCPU']);self.assertFalse(r['resourceOrGPUCreated']);self.assertAlmostEqual(r['rate'],rate,places=6)
            for x,y in zip(r['color'],color):self.assertAlmostEqual(x,y,places=6)
    def test_gray_source_material_properties_and_both_fx_profiles(self):
        import tempfile
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from bdae_convert import BDAE
        from scene_sampling import effect_profile_samplers
        sources=Sources(DEFAULT_SOURCE)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'source.bdae';p.write_bytes(sources.read(EFFECT));fx=BDAE(p)
            with self.assertRaises(ValueError):effect_profile_samplers(fx)
            self.assertEqual(len(effect_profile_samplers(fx,extra_properties=EXTRAS[EFFECT])['profiles']),2)
            for name in MODELS:
                p.write_bytes(sources.read(name));reader=BDAE(p);rows=typed_values(reader)
                self.assertEqual(sum(r['enabled']for r in rows),1)
                active=next(r for r in rows if r['enabled']);self.assertAlmostEqual(active['rate'],.2 if name.endswith('conifers001.bdae')else .15,places=6)
                n,t=reader.section(172);b=bytearray(reader.b);at=t+32;prop=reader.rel(at+4)
                # A scalar with the wrong source type must not be interpreted by length.
                import struct
                for j in range(reader.u(at)):
                    q=prop+j*32
                    if reader.string(reader.q(q))=='lightmap_gray_rate':struct.pack_into('<I',b,q+16,10)
                reader.b=bytes(b)
                with self.assertRaises(ValueError):typed_values(reader)
    def test_original_112_ledger_flags_and_selected_slot_gaps_are_distinct(self):
        inv=json.loads((RAW/'omissions.json').read_text());self.assertEqual(inv['omittedInstances'],112);self.assertEqual(inv['uniqueModels'],20);self.assertEqual(len(inv['ledger']),112)
        keys=[(tuple(r['tile']),r['id'])for r in inv['ledger']];self.assertEqual(len(set(keys)),112)
        self.assertEqual(len(inv['recordGaps']),7)
        for gap in inv['recordGaps']:
            self.assertEqual(gap['selectedSlot'],0);self.assertEqual(gap['selectedObjectRecords'],0);self.assertEqual(gap['slotChecks'][1]['objectRecords'],1);self.assertFalse(gap['appliedAlternative'])
        flags=[m for m in inv['models'].values()if m['nodeGap']];self.assertEqual(sum(m['instances']for m in flags),17)
        self.assertTrue(all(any(a['type']==2 and a['reference'].endswith('-skin')for n in m['nodes']for a in n['attachments'])for m in flags))
    def test_rebuild_old_instances_and_light_targets_preserved(self):
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            export(RUN,Path(td));self.assertEqual({p.name:p.read_bytes()for p in EXP.iterdir()},{p.name:p.read_bytes()for p in Path(td).iterdir()})
        old=json.loads((RUN/'game-data/converted/source-map-trees/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text());self.assertEqual(new['scenery'][:140],old['scenery']);self.assertEqual(new['sourceTreeRecovery'],old['sourceTreeRecovery'])
        ob=json.loads((RUN/'game-data/converted'/old['sceneBakedLighting']['url'].removeprefix('/assets/')).read_text());nb=json.loads((EXP/'baked-lighting.json').read_text())
        for k in ob.keys()-{'instances','atlases'}:self.assertEqual(ob[k],nb[k])
        self.assertEqual(nb['instances'][:1146],ob['instances']);self.assertEqual(self.audit['displayedInstances'],1155);self.assertEqual(self.audit['omittedInstances'],103);self.assertEqual(len(self.audit['added']),9)
    def test_connector_replay_and_repeat_rejection(self):
        from connect_scene_gray import connect
        with tempfile.TemporaryDirectory(dir=RAW)as td:
            d=Path(td);(d/'game-data/converted').mkdir(parents=True);pub=d/'prototype/public';pub.mkdir(parents=True)
            for n in('explore-map.js','explore-map.html','scene-alpha.js','scene-culling.js'):shutil.copyfile(RAW/('before-'+n),pub/n)
            self.assertEqual(connect(d,EXP)['files'],12)
            files={str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()}
            for n,b in files.items():self.assertEqual(b,(RUN/n).read_bytes())
            with self.assertRaises(ValueError):connect(d,EXP)
            self.assertEqual(files,{str(p.relative_to(d)):p.read_bytes()for p in d.rglob('*')if p.is_file()})
    def test_old_assets_main_save_and_paused_automation(self):
        assets=RUN/'game-data/converted';old=json.loads((RAW/'before-assets.json').read_text());self.assertTrue(all(hashlib.sha256((assets/n).read_bytes()).hexdigest()==s for n,s in old.items()))
        self.assertEqual(hashlib.sha256((ROOT/'runtime/characters.json').read_bytes()).hexdigest(),'8db90023214c32d3e3a6ea88fdbcf3aa144582288a4d28651398f29f296af401')
        self.assertIn('status = "PAUSED"',Path('/Users/kevin/.codex/automations/2/automation.toml').read_text())

if __name__=='__main__':unittest.main()
