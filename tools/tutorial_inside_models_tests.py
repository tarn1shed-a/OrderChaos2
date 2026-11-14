"""Check source type15 requests, candidate preservation and browser material glue."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tutorial_inside_models import FORMAT, MODELS, ROOT, NativeInsideFactoryProbe, verify

RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
EXP=ROOT/'analysis/raw/map-specialist-20261114/inside-visible-candidate-v6'
LIB=ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
NODE=shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')


class Public(unittest.TestCase):
    def test_output_cannot_overwrite_a_reviewed_runtime(self):
        from tutorial_inside_models import export
        raw=ROOT/'analysis/raw';raw.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=raw)as directory:
            with self.assertRaisesRegex(ValueError,'existing work'):
                export(Path(directory),Path(directory))

    def test_adapter_syntax(self):
        if not Path(NODE).is_file():self.skipTest('Node unavailable')
        r=subprocess.run([NODE,'--input-type=module','--check'],input=(ROOT/'tools/preview/source-inside-models.js').read_text(),capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)


@unittest.skipUnless(LIB.is_file() and (EXP/'audit.json').is_file(),'Original research assets remain local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image=NativeImage(LIB.read_bytes());cls.audit=json.loads((EXP/'audit.json').read_text())
        cls.manifest=json.loads((EXP/'manifest.json').read_text())

    def test_original_factory_requests_two_models_and_initially_hides_companion(self):
        probe=NativeInsideFactoryProbe(self.image);verify(self.image)
        for m in self.audit['added']:
            result=probe.requests(m);trace=result['trace']
            init=[e for e in trace if e['kind']=='model-owner-initialize-boundary']
            self.assertEqual([e['source']for e in init],[m['model'],m['model'][:-5]+'_inside.bdae'])
            self.assertTrue(all(e['position']==m['position'] and e['quaternion']==m['quaternion'] and e['scale']==m['scale']for e in init))
            self.assertEqual([e['visible']for e in trace if e['kind']=='model-visibility-boundary'],[False])
            self.assertEqual(m['companionCandidates'],0)
            self.assertFalse(result['asyncModelAndGPUExecuted'])

    def test_four_source_TRS_and_existing_1258_are_preserved(self):
        original=json.loads((RUN/'game-data/converted/source-temple-sampling/manifest.json').read_text())
        self.assertEqual(self.manifest['scenery'][:158],original['scenery'])
        self.assertEqual(len(self.manifest['scenery']),162)
        self.assertEqual(sum(len(m['instances'])for m in self.manifest['scenery']),1262)
        self.assertEqual({m['model']for m in self.manifest['scenery'][158:]},set(MODELS))
        for m in self.manifest['scenery'][158:]:
            self.assertEqual(m['instances'][0]['flags'],15)
            self.assertEqual(m['instances'][0]['scale'],[1.,1.,1.])
            self.assertEqual(m['instances'][0]['quaternion'],[0.,0.7071068286895752,0.,0.7071068286895752])
        self.assertEqual(hashlib.sha256((RUN/'game-data/converted/source-temple-sampling/manifest.json').read_bytes()).hexdigest(),self.audit['originalPreviewManifestSHA256'])
        self.assertFalse(self.audit['wholeMapAccepted']);self.assertFalse(self.audit['browserAccepted'])

    def test_only_unavailable_material_is_omitted_and_not_renamed(self):
        pending=[(m['model'],p)for m in self.audit['added']for p in m['pendingMaterialParts']]
        self.assertEqual(len(pending),1)
        self.assertTrue(pending[0][0].endswith('god_underground_palace02_02.bdae'))
        self.assertEqual(pending[0][1]['missingSamplers'],[{'sampler':'texture2Mask','path':'texture/hum_portal005.tga','candidateCount':0}])
        self.assertNotIn('texture/hum_portal005.tga',self.manifest['textures'])
        self.assertEqual([m['materials']for m in self.audit['added']],[21,17,11,16])

    def test_original_part_loop_and_light_targets_are_unchanged(self):
        old=json.loads((RUN/'game-data/converted/source-temple-sampling/manifest.json').read_text())
        a=json.loads((RUN/'game-data/converted'/old['sceneBakedLighting']['url'][8:]).read_text())
        b=json.loads((EXP/'baked-lighting.json').read_text())
        for k in a.keys()-{'instances','atlases'}:self.assertEqual(a[k],b[k])
        self.assertEqual(a['instances'],b['instances'][:len(a['instances'])])
        for m in self.audit['added']:
            self.assertTrue(m['originalPartBindingCPU']['bindingLoopExecuted'])
            self.assertEqual(len(m['originalPartBindingCPU']['calls']),m['materials'])
            self.assertTrue(all(r['binding']==0 for r in m['originalPartBindingCPU']['calls']))

    def test_browser_full_source_materials_rebind_after_original_part_binding(self):
        if not Path(NODE).is_file():self.skipTest('Node unavailable')
        three=(RUN/'prototype/node_modules/three/build/three.module.js').resolve()
        if not three.is_file():self.skipTest('Private three runtime unavailable')
        script=r'''
import assert from 'node:assert/strict';import{readFileSync}from'node:fs';import{pathToFileURL}from'node:url';
const [root,run,exp,three]=process.argv.slice(1);const THREE=await import(pathToFileURL(three));
const bakedURL=pathToFileURL(run+'/prototype/public/scene-baked-lighting.js').href+'?source-selection=1';
let source=readFileSync(root+'/tools/preview/source-inside-models.js','utf8').replace("'./scene-baked-lighting.js?source-selection=1'",JSON.stringify(bakedURL));
const api=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const{createBakedLighting}=await import(bakedURL);const{createPartLightmapContext}=await import(pathToFileURL(run+'/prototype/public/source-part-lightmaps.js'));
const manifest=JSON.parse(readFileSync(exp+'/manifest.json')),lighting=createBakedLighting(THREE,JSON.parse(readFileSync(exp+'/baked-lighting.json')),{
 sourceFogColor:{value:new THREE.Vector3()},sourceFogNear:{value:0},sourceFogSpan:{value:10}});
const context=createPartLightmapContext(JSON.parse(readFileSync(exp+'/part-lightmaps.json')));
const atlases=new Map(lighting.profile.atlases.map(a=>{const t=new THREE.Texture({width:a.width,height:a.height});t.colorSpace=THREE.NoColorSpace;t.flipY=false;return[a.sourcePath,t]}));
let omitted=0,created=0;const clock={value:()=>2.5};
for(const entry of manifest.scenery.slice(158)){
 const data=JSON.parse(readFileSync(exp+'/'+entry.url.split('/').at(-1))),mesh=data.meshes[0];
 await api.prepareInsideSource(THREE,data,manifest.textures,async()=>new THREE.Texture({width:512,height:512}));
 const materials=data.materials.map((mat,i)=>{const a=data.sceneAlpha.materials[i].sourceAlpha,t=new THREE.Texture({width:a.width,height:a.height});t.colorSpace=THREE.NoColorSpace;t.flipY=false;return api.createInsideSceneMaterial(THREE,t,mat,i,data,lighting)});
 const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(mesh.positions,3));g.setAttribute('sourceUV1',new THREE.Float32BufferAttribute(mesh.sourceUV1,2));
 api.prepareInsideGeometry(THREE,g,mesh);assert.equal(g.getAttribute('sourceUV3').count,mesh.positions.length/3);
 for(const group of mesh.groups)g.addGroup(group.start,group.count,group.material);
 const root3=new THREE.Group();root3.add(new THREE.Mesh(g,materials));api.prepareInsideRoot(root3,data);context.prepare(root3,entry,data);
 const clone=root3.clone(true);context.bind(THREE,clone,entry.instances[0],lighting,atlases);api.bindInsideInstance(THREE,clone,clock);
 clone.traverse(o=>{if(!o.isMesh)return;for(const m of o.material){created++;assert(m.uniforms.sourceAtlas.value);const r=data.sourceInsideMaterials.materials[m.userData.sourceInsideMaterial.index];
  if(r.missingSamplers.length){assert.equal(m.visible,false);omitted++;continue;}
  assert.equal(m.uniforms.sourceInsideTime.value,2.5);o.onBeforeRender(null,null,null,g,m,null);
  if(r.effect==='u2t_lightmap_trans_uv_lumin.bdae'){assert(m.uniforms.sourceInsideMask.value);assert(m.fragmentShader.indexOf('color.rgb*=vertexLight;')<m.fragmentShader.indexOf('color.rgb+=second.rgb'));}
 }});
 const bad=structuredClone(data);bad.sourceInsideMaterials.materials[0].missingSamplers=[{sampler:'texture2Mask',path:'invented.tga',candidateCount:0}];assert.throws(()=>api.validateInsideModel(bad));
}
assert.equal(created,65);assert.equal(omitted,1);console.log(JSON.stringify({sourceMaterials:created,omittedParts:omitted,partRebind:true,hostClockOrigin:true,GPUCompiled:false}));
'''
        r=subprocess.run([NODE,'--input-type=module','-e',script,str(ROOT),str(RUN),str(EXP),str(three)],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        result=json.loads(r.stdout);self.assertEqual(result['sourceMaterials'],65);self.assertEqual(result['omittedParts'],1)


if __name__=='__main__':unittest.main()
