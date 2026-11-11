"""Part ordinal vs material index, original DAT and unchanged lighting checks."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from scene_part_lightmaps import export,verify

RAW=ROOT/'analysis/raw/map-lighting-bindings-20261112'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
EXP=RAW/'export'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'

class Public(unittest.TestCase):
    def test_part_permutation_preserves_draw_groups_and_shared_templates(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        with tempfile.TemporaryDirectory()as t:
            p=Path(t);(p/'package.json').write_text('{"type":"module"}')
            shutil.copyfile(ROOT/'tools/preview/source-part-lightmaps.js',p/'source-part-lightmaps.js')
            (p/'source-dynamic-wind.js').write_text('export function bindInstanceLightmap(T,r,i,l,a){r.traverse(o=>{if(o.isMesh)o.material=o.material.map(m=>{const n=m.clone();n.selected=l[m.userData.sceneBakedLighting.index]??l[0];return n;});});r.userData.sceneLightmap={};return r;}')
            code=r'''import assert from 'node:assert/strict';import{createPartLightmapContext,validatePartLightmaps}from './source-part-lightmaps.js';
const row={model:'original',sourceSHA256:'a'.repeat(64),partToMaterial:[2,0,1]},policy={format:'oc2-source-part-lightmaps-v1',slot:0,profile:'APK_Default',originalDeviceObserved:false,models:[row]};
const make=i=>({userData:{sceneBakedLighting:{format:'oc2-scene-baked-lighting-v1',index:i},sourceGray:{rate:.5}},clone(){return{...this,userData:structuredClone(this.userData)}}});
const templates=[0,1,2].map(make),group={isMesh:true,geometry:{groups:[2,0,1].map(materialIndex=>({materialIndex}))},material:templates};const root={userData:{},traverse(fn){fn(group)}};
const data={sourceSHA256:row.sourceSHA256,materials:[0,1,2],meshes:[{groups:[2,0,1].map(material=>({material}))}]},canvas={dataset:{}},ctx=createPartLightmapContext(policy,canvas);ctx.prepare(root,{model:'original'},data);ctx.bind(null,root,{model:'original'},['A','B','C'],null);
assert.deepEqual(group.material.map(m=>m.selected),['B','C','A']);assert.deepEqual(group.material.map(m=>m.userData.sceneBakedLighting.index),[0,1,2]);assert.deepEqual(group.material.map(m=>m.userData.sceneBakedLighting.sourcePartOrdinal),[1,2,0]);
assert.deepEqual(group.geometry.groups.map(g=>g.materialIndex),[2,0,1]);assert.deepEqual(templates.map(m=>m.userData.sceneBakedLighting.index),[0,1,2]);assert(templates.every(m=>m.selected===undefined));assert(group.material.every(m=>m.userData.sourceGray.rate===.5));assert.equal(canvas.dataset.sourcePartLightmapInstances,'1');
const other={userData:{},traverse(fn){fn({isMesh:false})}};ctx.bind(null,other,{model:'unlisted'},[],null);assert.equal(other.userData.sourcePartLightmaps,undefined);
for(const mutate of[p=>p.models.push(row),p=>p.models[0].partToMaterial=[0,0,1],p=>p.slot=1,p=>p.originalDeviceObserved=true]){const p=structuredClone(policy);mutate(p);assert.throws(()=>validatePartLightmaps(p));}
assert.throws(()=>ctx.prepare(root,{model:'original'},{...data,sourceSHA256:'b'.repeat(64)}));assert.throws(()=>ctx.prepare(root,{model:'original'},{...data,meshes:[{groups:[0,1,2].map(material=>({material}))}]}));
'''
            r=subprocess.run([node,'--input-type=module','-e',code],cwd=p,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)

    def test_public_import_needs_no_native_runtime(self):
        import sys
        r=subprocess.run([sys.executable,'-c',"import sys;sys.path.insert(0,sys.argv[1]);import scene_part_lightmaps;assert not {'unicorn','capstone','elftools'}&set(sys.modules)",str(ROOT/'tools')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)

@unittest.skipUnless(NATIVE.is_file()and(EXP/'audit.json').is_file(),'Original map/native bytes stay local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(NATIVE.read_bytes())

    def test_original_loop_selects_part_and_first_binding_past_end(self):
        from native_part_lightmaps import PartLightmapProbe
        p=PartLightmapProbe(self.image)
        for order in ([2,0,1],[1,0],list(reversed(range(16)))):
            for n in (1,2,len(order)):
                bindings=[{'uvTransform':[float(i),float(i+1),.5,.25]}for i in range(n)];r=p.bindings(order,bindings)
                self.assertEqual([c['material']for c in r['calls']],list(order));self.assertEqual([c['binding']for c in r['calls']],[i if i<n else 0 for i in range(len(order))]);self.assertFalse(r['GPUCreated']);self.assertFalse(r['parameterSetterExecuted'])

    def test_changed_original_part_getter_is_rejected(self):
        im=self.image
        class Changed:
            elf=im.elf
            def read(self,at,n):
                b=im.read(at,n);return bytes([b[0]^1])+b[1:]if at==0x1132284 else b
        with self.assertRaisesRegex(ValueError,'part consumer'):verify(Changed())

    def test_original_all_model_order_and_dat_rebuild_is_exact(self):
        with tempfile.TemporaryDirectory(dir=RAW)as t:
            a=export(RUN,Path(t));self.assertEqual(a['changedInstances'],17);self.assertEqual(a['nonIdentityInstances'],306)
            self.assertEqual({p.name:p.read_bytes()for p in EXP.iterdir()},{p.name:p.read_bytes()for p in Path(t).iterdir()})

    def test_real_browser_binder_keeps_material_table_and_selects_verified_atlases(self):
        node=shutil.which('node')
        if not node:self.skipTest('Node required')
        code="import{readFile}from'node:fs/promises';import assert from'node:assert/strict';const T=await import('"+(RUN/'prototype/node_modules/three/build/three.module.js').as_uri()+"');const{createPartLightmapContext}=await import('"+(RUN/'prototype/public/source-part-lightmaps.js').as_uri()+"');const policy=JSON.parse(await readFile('"+str(EXP/'policy.json')+"'));const audit=JSON.parse(await readFile('"+str(EXP/'audit.json')+"'));"+r'''
for(const row of audit.changes){const p=policy.models.find(m=>m.model===row.model),group=new T.Group(),root=new T.Group(),geo=new T.BufferGeometry(),order=p.partToMaterial;geo.setAttribute('position',new T.Float32BufferAttribute([0,0,0],3));geo.setAttribute('sourceUV1',new T.Float32BufferAttribute([0,0],2));for(const i of order)geo.addGroup(0,0,i);
const materials=order.map((_,i)=>{const m=new T.ShaderMaterial({uniforms:{sourceDiffuse:{value:'diffuse-'+i}}});m.userData.sceneBakedLighting={format:'oc2-scene-baked-lighting-v1',index:i};return m;});const mesh=new T.Mesh(geo,materials);group.add(mesh);root.add(group);const ctx=createPartLightmapContext(policy);ctx.prepare(root,{model:row.model},{sourceSHA256:p.sourceSHA256,materials,meshes:[{groups:order.map(material=>({material}))}]});
const atlases=new Map(row.bindings.map(b=>{const tex=new T.Texture();tex.colorSpace=T.NoColorSpace;tex.flipY=false;return[b.atlas,tex];}));const lighting={uniforms:{},profile:{instances:[{objectId:row.id,model:row.model,tile:row.tile,bindings:row.bindings}],configuration:{modelSlot:0}}};ctx.bind(T,root,{id:row.id,model:row.model,tile:row.tile},lighting,atlases);
order.forEach((mat,part)=>{const b=row.bindings[part]??row.bindings[0],m=mesh.material[mat];assert.equal(m.uniforms.sourceAtlas.value,atlases.get(b.atlas));assert.deepEqual(m.uniforms.sourceUVTransform.value.toArray(),b.uvTransform);assert.equal(m.uniforms.sourceDiffuse.value,'diffuse-'+mat);assert.equal(materials[mat].uniforms.sourceAtlas,undefined);assert.equal(m.userData.sceneBakedLighting.index,mat);});}
'''
        r=subprocess.run([node,'--input-type=module','-e',code],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)

    def test_connector_replay_and_repeat_refusal(self):
        from connect_part_lightmaps import connect
        with tempfile.TemporaryDirectory(dir=RAW)as t:
            r=Path(t);pub=r/'prototype/public';pub.mkdir(parents=True);(r/'game-data/converted').mkdir(parents=True)
            for n in('explore-map.js','explore-map.html'):shutil.copyfile(RAW/('before-'+n),pub/n)
            self.assertEqual(connect(r,EXP)['files'],6);files={str(p.relative_to(r)):p.read_bytes()for p in r.rglob('*')if p.is_file()}
            for n,b in files.items():self.assertEqual((RUN/n).read_bytes(),b)
            with self.assertRaises(ValueError):connect(r,EXP)
            self.assertEqual(files,{str(p.relative_to(r)):p.read_bytes()for p in r.rglob('*')if p.is_file()})

    def test_old_assets_light_values_and_private_main_save_preserved(self):
        for n,h in json.loads((RAW/'before-assets.json').read_text()).items():self.assertEqual(hashlib.sha256((RUN/'game-data/converted'/n).read_bytes()).hexdigest(),h,n)
        old=json.loads((RUN/'game-data/converted/source-map-record-gaps/manifest.json').read_text());new=json.loads((EXP/'manifest.json').read_text());new.pop('sourcePartLightmaps');self.assertEqual(new,old)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'before-main-private.json').read_bytes());self.assertIn('status = "PAUSED"',Path('/Users/kevin/.codex/automations/2/automation.toml').read_text())

if __name__=='__main__':unittest.main()
