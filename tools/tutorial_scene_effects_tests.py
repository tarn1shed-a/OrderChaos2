"""Type8 source inventory, original parameter dispatch and isolated rendering."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tutorial_scene_effects_assets import ROOT, FOCUS, FOCUS_SHA, output_path

LIB = ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
OUT = ROOT/'analysis/raw/tutorial-scene-effects-20261114/candidate-v3'
RUN = ROOT/'analysis/raw/showcase-20261110/running-preview'
NODE = shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')


class Public(unittest.TestCase):
    def test_private_export_cannot_overwrite_existing_work_or_publish_assets(self):
        with self.assertRaises(ValueError): output_path(ROOT/'prototype/public/source-effects')
        base = ROOT/'analysis/raw'; base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as td:
            (Path(td)/'keep').write_text('keep')
            with self.assertRaises(ValueError): output_path(td)

    def test_new_adapter_syntax(self):
        if not Path(NODE).is_file(): self.skipTest('Node unavailable')
        r = subprocess.run([NODE, '--input-type=module', '--check'], input=(ROOT/'tools/preview/source-scene-effect-preview.js').read_text(), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipUnless(LIB.is_file() and (OUT/'audit.json').is_file(), 'Original assets remain private')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        cls.image = NativeImage(LIB.read_bytes()); cls.audit = json.loads((OUT/'audit.json').read_text())
        cls.manifest = json.loads((OUT/'manifest.json').read_text())
        cls.placements = json.loads((OUT/cls.manifest['placements']).read_text())

    def test_all_92_are_counted_and_two_unsupported_resources_remain_gaps(self):
        groups = self.audit['inventory']['groups']
        self.assertEqual(sum(r['placements'] for r in groups), 92); self.assertEqual(len(groups), 14)
        self.assertEqual((groups[0]['resource'], groups[0]['placements']), (FOCUS, 43))
        gaps = {Path(r['resource']).name: r['gap'] for r in groups if not r.get('decoded')}
        self.assertEqual(set(gaps), {'scene_torch001.beff', 'scene_sunshine001.beff'})
        self.assertIn('test_UV.JPG', gaps['scene_torch001.beff'])

    def test_candidate_hashes_and_original_placement_parameters_match(self):
        for name, digest in self.audit['files'].items():
            self.assertEqual(hashlib.sha256((OUT/name).read_bytes()).hexdigest(), digest)
        self.assertEqual(self.audit['sourceProofs'][FOCUS]['sha256'], FOCUS_SHA)
        self.assertEqual(len(self.audit['nativeRequests']), 43); self.assertEqual(len(self.placements), 43)
        for r in self.placements:
            self.assertEqual(r['sourcePhaseWord60'], 0xffffffff)
            self.assertEqual(r['sourceQualityWord56']&3, 3)
            self.assertTrue(r['nativeRequestParametersExecuted'])
            for k in ('position', 'quaternion', 'scale'): self.assertEqual(r[k], r['originalRequest'][k])
        self.assertFalse(self.manifest['insertIntoDefaultScene']); self.assertFalse(self.manifest['automaticRestart'])

    def test_original_switch_selects_sync_provider_not_hidden_effect(self):
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from tutorial_scene_effects_native import SceneEffectRequestProbe
        r = self.placements[0]; p = SceneEffectRequestProbe(self.image)
        proof = p.request(Sources(DEFAULT_SOURCE).read(r['sourceITM']), r['sourceRecordIndex'], async_loading=False)
        self.assertEqual(proof['requests'][0]['kind'], 'original-sync-scene-effect-request')
        self.assertEqual(proof['requests'][0]['source'], FOCUS)
        self.assertFalse(proof['sourceSceneCompletionExecuted'])

    def test_original_local_flags_are_not_called_a_complete_effect(self):
        f = self.audit['nativeLocalConstructor']
        self.assertEqual([f[k] for k in ('byte218', 'byte219', 'visible21a', 'byte21b', 'time250')], [0, 1, 1, 0, 0])
        self.assertTrue(f['nativeLocalInitializerExecuted']); self.assertFalse(f['wholeEffectConstructed'])

    def test_private_package_is_deterministic_and_keeps_evidence_out_of_public(self):
        import tarfile
        from tutorial_scene_effects_package import package
        with tempfile.TemporaryDirectory(dir=ROOT/'analysis/raw') as td:
            first = package(OUT, Path(td)/'a'); second = package(OUT, Path(td)/'b')
            self.assertEqual(first['sha256'], second['sha256'])
            with tarfile.open(Path(td)/'a'/first['archive']) as tar:
                names = tar.getnames()
                self.assertIn('private-evidence/audit.json', names)
                self.assertNotIn('public/source-scene-effects/audit.json', names)
                self.assertEqual(sum(n.startswith('public/source-scene-effects/') for n in names), 6)
            with self.assertRaises(ValueError): package(OUT, Path(td)/'a')

    def test_web_candidate_preserves_materials_source_pose_and_explicit_time(self):
        three = (RUN/'prototype/node_modules/three/build/three.module.js').resolve()
        if not Path(NODE).is_file() or not three.is_file(): self.skipTest('Private Three runtime unavailable')
        script = r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';import{pathToFileURL}from'node:url';
const[root,run,out,three]=process.argv.slice(1),THREE=await import(pathToFileURL(three));
let source=readFileSync(root+'/tools/preview/source-scene-effect-preview.js','utf8').replace("'./particle-renderer.js'",JSON.stringify(pathToFileURL(run+'/prototype/public/particle-renderer.js').href));
const api=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const manifest=JSON.parse(readFileSync(out+'/manifest.json')),definition=JSON.parse(readFileSync(out+'/'+manifest.effect));
const rows=JSON.parse(readFileSync(out+'/'+manifest.placements)),maps=new Map(Object.values(manifest.textures).map(r=>[r.file,new THREE.Texture({width:r.width,height:r.height})]));
const camera=new THREE.PerspectiveCamera(45,1,.1,300);camera.position.set(...rows[0].position);camera.position.z+=30;
const item=api.createSourceSceneEffect(THREE,{definition,instance:rows[0],textures:maps,camera});
assert.equal(item.group.children.length,0);let count=0;
for(const ms of[0,500,1500,3000]){count=item.update(ms);assert(count>0);assert(count<256);
 item.group.traverse(o=>{if(!o.isMesh)return;assert(o.position.toArray().every(Number.isFinite));assert(o.material.depthTest);
  assert.equal(o.material.depthWrite,false);assert.equal(o.material.toneMapped,false);assert([THREE.AdditiveBlending,THREE.NormalBlending].includes(o.material.blending));});}
assert.equal(item.group.userData.sourceSceneEffect.automaticRestart,false);assert.equal(item.group.userData.sourceSceneEffect.insertIntoDefaultScene,false);
assert.throws(()=>item.update(-1));const wrong=structuredClone(rows[0]);wrong.position[1]+=1;assert.throws(()=>api.validateSourceSceneEffect(definition,wrong));
const bad=structuredClone(definition);bad.sourceSceneEffect.lightsAdded=true;assert.throws(()=>api.validateSourceSceneEffect(bad,rows[0]));
item.dispose();assert.equal(item.group.children.length,0);console.log(JSON.stringify({particlesAt3000:count,GPUCompiled:false}));
'''
        r = subprocess.run([NODE, '--input-type=module', '-e', script, str(ROOT), str(RUN), str(OUT), str(three)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertGreater(json.loads(r.stdout)['particlesAt3000'], 0)


if __name__ == '__main__': unittest.main()
