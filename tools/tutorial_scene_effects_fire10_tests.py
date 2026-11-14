"""Ten source fire placements, original quality gate and isolated runtime."""
import hashlib
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from tutorial_scene_effects_assets import ROOT, LIB
from tutorial_scene_effects_fire10_assets import SOURCE, SOURCE_SHA

OUT = ROOT/'analysis/raw/tutorial-scene-effects-20261114/fire10-candidate-v1'
RUN = ROOT/'analysis/raw/showcase-20261110/running-preview'
NODE = shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')


class Public(unittest.TestCase):
    def test_import_does_not_load_native_dependencies(self):
        import tutorial_scene_effects_fire10_native
        import tutorial_scene_effects_fire10_delivery
        self.assertTrue(callable(tutorial_scene_effects_fire10_native.SceneFire10NativeProbe))
        self.assertTrue(callable(tutorial_scene_effects_fire10_delivery.additions))

    @unittest.skipUnless(Path(NODE).is_file(), 'Node unavailable')
    def test_new_modules_have_valid_syntax(self):
        for name in ['source-scene-effect-fire10-preview.js','source-scene-effect-fire10-runtime.js','source-scene-effect-fire10-overlay.mjs']:
            p = subprocess.run([NODE,'--input-type=module','--check'],input=(ROOT/'tools/preview'/name).read_text(),text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)


@unittest.skipUnless(LIB.is_file() and (OUT/'audit.json').is_file(), 'Original source assets stay private')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((OUT/'audit.json').read_text()); cls.rows = json.loads((OUT/'placements.json').read_text())

    def test_original_group_files_and_native_pose_requests_match(self):
        for name, expected in self.audit['files'].items():
            self.assertEqual(hashlib.sha256((OUT/name).read_bytes()).hexdigest(),expected)
        self.assertEqual(self.audit['sourceProofs'][SOURCE]['sha256'],SOURCE_SHA)
        self.assertEqual((len(self.rows),len(self.audit['nativeRequests'])),(10,10))
        for row in self.rows:
            self.assertEqual((row['originalLookupLevel'],row['originalAdmission'],row['sourcePhaseWord60']),
                (2,'admittedBeforeTypeFactory',0xffffffff))
            for k in ['position','quaternion','scale']:self.assertEqual(row[k],row['originalRequest'][k])

    def test_original_header_quality_and_default_clock_are_executed(self):
        rows = self.audit['nativeEmitterDefaultsAndSteps']
        self.assertEqual([e['initial']['sourceQuality20c'] for e in rows],[1,0])
        self.assertEqual([e['initial']['sourceShape238'] for e in rows],[0,0])
        self.assertEqual([e['steps'][0]['originalPointSpawnRequests'] for e in rows],[1,1])
        self.assertTrue(all([r['clockMs'] for r in e['steps']]==[0,16,49,149,182] for e in rows))
        self.assertFalse(self.audit['GPUCreatedByOriginalEngine'])

    def test_original_low_emitter_quality_still_blocks_update(self):
        from analyze_native_resources import NativeImage
        from tutorial_scene_effects_fire10_native import SceneFire10NativeProbe
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        from beff_effects import decode_effect
        raw = Sources(DEFAULT_SOURCE).read(SOURCE); definition = decode_effect(raw)
        p = SceneFire10NativeProbe(NativeImage(LIB.read_bytes())); root = p.make_root()
        em = p.make_emitter(root,raw,definition['emitters'][0]); quality = p.r(0x25046b0,'Q')[0]
        p.w(quality,'I',0); blocked = p.tick(em,16.9)
        self.assertFalse(blocked['originalClockAdvanced']); self.assertEqual(blocked['first38a'],1)
        p.w(quality,'I',2); admitted = p.tick(em,16.9)
        self.assertTrue(admitted['originalClockAdvanced']); self.assertEqual(admitted['originalPointSpawnRequests'],1)

    def test_private_delta_only_appends_nine_files_to_first43_candidate(self):
        from tutorial_scene_effects_fire10_delivery import additions, read_base
        delta = additions(); base, manifest = read_base()
        self.assertEqual((len(delta),len(base)),(9,2868)); self.assertFalse(set(delta)&set(base))
        self.assertEqual(manifest['mapIntegration']['originalRuntimePreserved'],127)
        self.assertFalse(any('audit' in name or 'save' in name for name in delta))

    @unittest.skipUnless(Path(NODE).is_file(), 'Node unavailable')
    def test_ten_original_runtime_poses_and_window_pause_without_new_light(self):
        code = r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';import{pathToFileURL}from'node:url';
const[root,run,out]=process.argv.slice(1),THREE=await import(pathToFileURL(run+'/prototype/node_modules/three/build/three.module.js'));
const uri=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64'),spec=uri(readFileSync(root+'/tools/preview/source-scene-effect-fire10-preview.js','utf8'));
const text=readFileSync(root+'/tools/preview/source-scene-effect-fire10-runtime.js','utf8').replace("'./source-scene-effect-fire10-preview.js'",JSON.stringify(spec)).replace("'./source-scene-effect-clock.mjs'",JSON.stringify(pathToFileURL(root+'/tools/preview/source-scene-effect-clock.mjs').href)).replace("'./particle-renderer.js'",JSON.stringify(pathToFileURL(run+'/prototype/public/particle-renderer.js').href));
const{createSourceSceneFire10Runtime}=await import(uri(text)),read=n=>JSON.parse(readFileSync(out+'/'+n));
const definition=read('scene-effect.json'),instances=read('placements.json'),profile=read('playback.json'),m=read('manifest.json'),maps=new Map(Object.values(m.textures).map(r=>[r.file,new THREE.Texture({width:r.width,height:r.height})]));
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(),origin=new THREE.Vector3(-2500,100,-50),objects=[];
const item=createSourceSceneFire10Runtime(THREE,{definition,instances,profile,textures:maps,camera,origin,scene,archiveObjects:objects}),all=JSON.stringify({resident:[...new Set(instances.map(i=>i.tile.join(',')))]});
assert.equal(item.update(0,undefined).archiveReady,false);item.update(10,all);assert.equal(item.update(2000,all).visible,10);
let s=item.inspect({detailed:true});assert(s.particles>0);assert(s.entries.every(r=>r.clock===1990));assert.equal(scene.children.length,10);assert(scene.children.every(c=>!c.isLight));
for(const row of objects)assert.deepEqual(row.root.position.toArray(),origin.toArray().map(v=>-v));
item.update(4000,JSON.stringify({resident:[]}));assert(item.inspect({detailed:true}).entries.every(r=>r.clock===1990));item.update(4033,all);assert(item.inspect({detailed:true}).entries.every(r=>r.clock===2023));
item.dispose();assert.equal(scene.children.length,0);assert.equal(objects.length,0);const bad=structuredClone(instances);bad[0].originalLookupLevel=5;assert.throws(()=>createSourceSceneFire10Runtime(THREE,{definition,instances:bad,profile,textures:maps,camera,origin,scene,archiveObjects:objects}));
console.log(JSON.stringify({sourcePoses:10,newLights:0,GPUCompiled:false}));
'''
        p = subprocess.run([NODE,'--input-type=module','-e',code,str(ROOT),str(RUN),str(OUT)],text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['sourcePoses'],10)


if __name__ == '__main__': unittest.main()
