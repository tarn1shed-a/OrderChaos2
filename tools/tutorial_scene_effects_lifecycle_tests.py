"""Original emitter lifecycle and append-only browser integration checks."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from tutorial_scene_effects_assets import ROOT, LIB

RAW = ROOT/'analysis/raw/tutorial-scene-effects-20261114'
NODE = shutil.which('node') or str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')
RUN = ROOT/'analysis/raw/showcase-20261110/running-preview'


def node(script, *args):
    p = subprocess.run([NODE, '--input-type=module', '-e', script, *map(str, args)], text=True, capture_output=True)
    if p.returncode: raise AssertionError(p.stderr)
    return p.stdout


class Public(unittest.TestCase):
    def test_probe_and_packaging_import_without_original_analysis_dependencies(self):
        import tutorial_scene_effects_lifecycle_probe
        import tutorial_scene_effects_delivery
        self.assertTrue(callable(tutorial_scene_effects_lifecycle_probe.playback_profile))
        self.assertTrue(callable(tutorial_scene_effects_delivery.additions))

    @unittest.skipUnless(Path(NODE).is_file(), 'Node unavailable')
    def test_original_clock_defaults_pause_big_frames_and_over_ten_minutes(self):
        result = node(r'''
import assert from'node:assert/strict';import{pathToFileURL}from'node:url';
const{createSourceSceneEffectClock}=await import(pathToFileURL(process.argv[1]));const c=createSourceSceneEffectClock();
assert.deepEqual([16.9,16.9,33,100,2001].map(n=>c.advance(n)),[0,16,49,149,182]);
assert.equal(c.advance(500,{paused:true}),182);assert.equal(c.advance(33),215);
assert.equal(c.advance(1000,{visible:false}),215);assert.equal(c.advance(1000),1215);
for(let i=0;i<601;i++)c.advance(1000);assert.equal(c.inspect().milliseconds,602215);assert.equal(c.inspect().automaticRestart,false);
for(const delta of[4294967295,4294967296,4294967297,1e20]){const huge=createSourceSceneEffectClock();huge.advance(0);assert.equal(huge.advance(delta),33);}
assert.throws(()=>c.advance(-1));console.log('clock-checked');
''', ROOT/'tools/preview/source-scene-effect-clock.mjs')
        self.assertIn('clock-checked', result)

    @unittest.skipUnless(Path(NODE).is_file(), 'Node unavailable')
    def test_overlay_is_guarded_and_preserves_existing_plan_members(self):
        node(r'''
import assert from'node:assert/strict';import{pathToFileURL}from'node:url';
const{stageSceneEffectsEntry,stageSceneEffectsPlan,SCENE_EFFECT_MANIFEST}=await import(pathToFileURL(process.argv[1]));
const base="if(!sceneStages.present(windowChange)){}\n    requestAnimationFrame(draw);sceneStages.start();\n  sourceWater?.update(now);";
const staged=stageSceneEffectsEntry(base);assert(staged.includes('loadSourceSceneEffectRuntime'));assert(staged.includes('sourceSceneEffects.update(now,canvas.dataset.sourceArchiveWindow)'));assert(staged.includes('now-sourceSceneEffectDiagnosticAt>=1000'));
assert.throws(()=>stageSceneEffectsEntry(staged));assert.throws(()=>stageSceneEffectsEntry('wrong'));
const m={effect:'effect.json',placements:'placements.json',textures:{a:{file:'a.png'},b:{file:'b.png'},c:{file:'c.png'}}};
const t=new Map([[SCENE_EFFECT_MANIFEST,JSON.stringify(m)],['/assets/source-scene-effects/effect.json','{}'],['/assets/source-scene-effects/placements.json','[]'],['/assets/source-scene-effects/playback.json','{}']]);
const plan={critical:['/old.js','/map.json'],background:['/far.json'],scope:{keep:true}},next=stageSceneEffectsPlan(plan,t);
assert.deepEqual(next.critical,plan.critical);assert(next.background.includes('/far.json'));assert(next.background.includes('/assets/source-scene-effects/playback.json'));assert.equal(next.scope.keep,true);
''', ROOT/'tools/preview/source-scene-effect-overlay.mjs')


@unittest.skipUnless(LIB.is_file() and (RAW/'lifecycle-v3/lifecycle.json').is_file(), 'Original materials stay private')
class Original(unittest.TestCase):
    def test_native_three_emitter_clock_and_cancel_are_reproducible(self):
        from tutorial_scene_effects_lifecycle_probe import analyze, playback_profile
        r = analyze(); expected = json.loads((RAW/'lifecycle-v3/lifecycle.json').read_text())
        self.assertEqual(r, expected)
        self.assertEqual(playback_profile(r), json.loads((RAW/'lifecycle-v3/playback.json').read_text()))
        self.assertEqual([r['rawConvertedStepMs'] for r in r['numericBoundaries']][-4:], [0xffffffff]*4)
        self.assertEqual([r['scaledStepMs'] for r in r['numericBoundaries']], [2000,2000,33,33,33,33,33])
        self.assertFalse(r['originalResourceIOLoaded']); self.assertFalse(r['originalParticleAllocationExecuted'])

    def test_append_payload_does_not_replace_any_pinned_base_file(self):
        from tutorial_scene_effects_delivery import additions, read_base
        delta = additions(); base, manifest = read_base()
        self.assertEqual(len(base), 2857); self.assertEqual(len(delta), 11); self.assertFalse(set(base)&set(delta))
        self.assertEqual(manifest['mapIntegration']['originalRuntimePreserved'], 127)
        self.assertFalse(any('audit' in name or 'save' in name for name in delta))

    @unittest.skipUnless(Path(NODE).is_file(), 'Node unavailable')
    def test_existing_host_waits_then_produces_resident_window_before_effect_frame(self):
        node(r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';import{pathToFileURL}from'node:url';
const[root,run]=process.argv.slice(1),data=readFileSync(root+'/deploy/staged_scene.mjs','utf8')
 .replace("'/source-archive-window.js'",JSON.stringify(pathToFileURL(run+'/prototype/public/source-archive-window.js').href))
 .replace("'/__delivery/streaming_window.mjs'",JSON.stringify(pathToFileURL(root+'/deploy/streaming_window.mjs').href));
const{createSceneStages}=await import('data:text/javascript;base64,'+Buffer.from(data).toString('base64'));
const m=JSON.parse(readFileSync(run+'/game-data/converted/source-temple-sampling/manifest.json')),tile=[-39,-1],canvas={dataset:{}};
const stages=createSceneStages({canvas,scene:{},archiveObjects:[],terrain:{sourceTiles:[{tile}]},offsets:m.mapWindow.originalRequestOffsets,radius:m.mapWindow.radius,initial:{x:-2463.7,z:-40.5}});
assert.equal(stages.present(null),false);assert.equal(canvas.dataset.sourceArchiveWindow,undefined);
assert.equal(stages.present({center:tile,resident:new Set([tile.join(',')])}),true);
assert.deepEqual(JSON.parse(canvas.dataset.sourceArchiveWindow).resident,[tile.join(',')]);
''', ROOT, RUN)

    @unittest.skipUnless(Path(NODE).is_file(), 'Node unavailable')
    def test_actual_adapter_source_pose_window_pause_reentry_and_disposal(self):
        result = node(r'''
import assert from'node:assert/strict';import{readFileSync}from'node:fs';import{pathToFileURL}from'node:url';
const[root,run,raw]=process.argv.slice(1),THREE=await import(pathToFileURL(run+'/prototype/node_modules/three/build/three.module.js'));
const rendererURL=pathToFileURL(run+'/prototype/public/particle-renderer.js').href;
const importText=s=>'data:text/javascript;base64,'+Buffer.from(s).toString('base64');
const frozen=importText(readFileSync(root+'/tools/preview/source-scene-effect-preview.js','utf8').replace("'./particle-renderer.js'",JSON.stringify(rendererURL)));
const source=readFileSync(root+'/tools/preview/source-scene-effect-runtime.js','utf8').replace("'./source-scene-effect-preview.js'",JSON.stringify(frozen)).replace("'./source-scene-effect-clock.mjs'",JSON.stringify(pathToFileURL(root+'/tools/preview/source-scene-effect-clock.mjs').href)).replace("'./particle-renderer.js'",JSON.stringify(rendererURL));
const{createSourceSceneEffectRuntime}=await import(importText(source)),get=name=>JSON.parse(readFileSync(raw+'/'+name));
const d=get('candidate-v3/scene-effect.json'),instances=get('candidate-v3/placements.json'),m=get('candidate-v3/manifest.json'),profile=get('lifecycle-v3/playback.json');
const maps=new Map(Object.values(m.textures).map(r=>[r.file,new THREE.Texture({width:r.width,height:r.height})]));
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(),origin=new THREE.Vector3(-2500,100,-50),archiveObjects=[];
const r=createSourceSceneEffectRuntime(THREE,{definition:d,instances,profile,textures:maps,camera,origin,scene,archiveObjects});assert.equal(archiveObjects.length,43);
assert.equal(r.update(0,undefined).archiveReady,false);assert.equal(r.inspect({detailed:true}).entries[0].clock,0);assert.equal(r.update(500,'{}').archiveReady,false);
const all=JSON.stringify({resident:[...new Set(instances.map(i=>i.tile.join(',')))]});r.update(1000,all);r.update(1149,all);let s=r.inspect({detailed:true});assert.equal(s.visible,43);assert(s.particles>0);
for(let i=0;i<43;i++){const row=archiveObjects[i];assert.deepEqual(row.tile,instances[i].tile);assert.deepEqual(row.root.position.toArray(),origin.toArray().map(v=>-v));assert.equal(s.entries[i].clock,149);}
assert(!('entries'in r.inspect()));const none=JSON.stringify({resident:[]});r.update(2149,none);s=r.inspect({detailed:true});assert.equal(s.visible,0);assert(s.entries.every(i=>i.clock===149));
const selected=instances[0].tile.join(','),one=JSON.stringify({resident:[selected]});r.update(2182,one);s=r.inspect({detailed:true});assert(s.visible>0);assert.equal(s.entries[0].clock,182);assert(s.entries.filter(i=>i.tile.join(',')!==selected).every(i=>i.clock===149));
assert.equal(scene.children.length,43);r.dispose();assert.equal(scene.children.length,0);assert.equal(archiveObjects.length,0);r.dispose();assert.throws(()=>r.update(1200,one));
const second=createSourceSceneEffectRuntime(THREE,{definition:d,instances,profile,textures:maps,camera,origin,scene,archiveObjects});second.update(5000000,one);assert.equal(second.inspect({detailed:true}).entries[0].clock,0);second.dispose();
console.log(JSON.stringify({originalPoses:43,oldEntriesReplaced:0,unloadReentryChecked:true,GPUCompiled:false}));
''', ROOT, RUN, RAW)
        self.assertEqual(json.loads(result)['originalPoses'], 43)


if __name__ == '__main__': unittest.main()
