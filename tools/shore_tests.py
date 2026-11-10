"""Source water/shore decisions and false jump regression; private inputs optional."""
import hashlib
import json
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from terrain_water_tests import javascript

RAW=ROOT/'analysis/raw/shore-animation-20261111'
RUNTIME=ROOT/'analysis/raw/showcase-20261110/running-preview'
EXPORT=ROOT/'analysis/raw/shore-assets-ready-20261111'


class PublicTests(unittest.TestCase):
    def test_connector_refuses_main_or_backup(self):
        from connect_shore import connect
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)

    def test_vertical_speed_alone_does_not_create_a_jump(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const m=await import('data:text/javascript,'+encodeURIComponent(await readFile('tools/preview/source-shore-motion.js','utf8')));
        for(const waterState of [0,3,4])assert.equal(m.sourceAirborne({waterState,swimming:false,grounded:false,lastPosture:32,velocityY:3.4}),false);
        for(const lastPosture of [0x28,0x30,0x108,0x110])assert(m.sourceAirborne({swimming:false,grounded:false,lastPosture}));
        assert(!m.sourceAirborne({swimming:true,grounded:false,lastPosture:0x28}));
        assert(!m.sourceAirborne({swimming:false,grounded:true,lastPosture:0x28}));
        assert(m.sourceRun({locomotionPosture:32}));assert(!m.sourceRun({locomotionPosture:32,jump:{}}));
        assert(!m.sourceRun({locomotionPosture:32,swimming:true}));assert(!m.sourceRun({locomotionPosture:null}));""")


@unittest.skipUnless(EXPORT.is_dir()and(ROOT/'analysis/raw/beff-native/library.so').is_file(),'Original shore inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from source_shore import SourceShore
            from analyze_native_resources import NativeImage
        except ImportError as e:raise unittest.SkipTest(str(e))
        cfg=json.loads((RUNTIME/'prototype/native-physics.json').read_text());cls.e=SourceShore(NativeImage(Path(cfg['library']).read_bytes()))
        cls.e.load_world(json.loads(Path(cfg['terrain']).read_text()),json.loads(Path(cfg['collision']).read_text()),
            lambda n:Path(cfg['sourceFiles'][n]['path']).read_bytes(),{tuple(r['tile']):r['runtimeFlags']for r in json.loads(Path(cfg['terrainLighting']).read_text())['tiles']})
        cls.e.load_water(json.loads(Path(cfg['swimming']).read_text()));cls.e.load_diving(json.loads(Path(cfg['diving']).read_text()));cls.e.load_shore()

    def test_original_input_guard_retains_real_jump_and_fall(self):
        e=self.e;a=e.actor('guard',[-2232,109.22,12]);vt=e.r(a['address'],'Q')[0];before=e.r(vt+0x2b8,'Q')[0]
        self.assertTrue(e.input_guard(a))
        e.w(a['stateRecord']+8,'I',0x28);self.assertFalse(e.input_guard(a))
        e.w(a['stateRecord']+8,'I',32);e.w(a['address']+0x138,'f',-20);self.assertFalse(e.input_guard(a))
        e.w(a['address']+0x138,'f',0);e.w(a['address']+0x5a0,'I',1);self.assertFalse(e.input_guard(a))
        self.assertEqual(e.r(vt+0x2b8,'Q')[0],before)

    def test_recorded_shallow_boundary_no_longer_keeps_swimming_vertical_velocity(self):
        e=self.e;pos=[-2752+2841.808268229167/1280*192,108.4786376953125,128-399.8467000325521/1280*192]
        a=e.actor('old-bug',pos);at=a['address'];e.w(at+0x124,'3f',-.8,.6,0);e.w(at+0x130,'f',4.8)
        self.assertFalse(e.call(0x90e26c,{'X0':at})&1)
        r=e.actor_tick('old-bug',pos,[-4.8,0],50,False,{'forward':True})
        self.assertEqual(r['velocityY'],0);self.assertEqual(r['accelerationY'],0)
        self.assertTrue(r['grounded']);self.assertNotIn(r['lastPosture'],[0x28,0x30])

    def test_actual_gentle_shore_moves_deep_shallow_dry_and_back(self):
        e=self.e;pos=[-2235.5,108.55000305175781,12];frames=[]
        for direction,count in [(1,24),(-1,30)]:
            for i in range(count):
                r=e.actor_tick('shore-roundtrip',pos,[direction*4.8,0],50,False,{'forward':True});pos=r['position'];frames.append(r)
        self.assertEqual(set(r['waterState']for r in frames),{0,3,4})
        self.assertTrue(any(r['position'][0]>-2231 and r['waterState']==0 for r in frames))
        self.assertTrue(frames[-1]['swimming'])
        self.assertEqual({r['locomotionPosture']for r in frames},{0x20,0x50})
        self.assertFalse(any(r['lastPosture']in [0x28,0x30]for r in frames))
        (RAW/'shore-roundtrip-native.json').write_text(json.dumps(frames,indent=2))

    def test_true_jump_and_bridge_drop_are_not_flattened(self):
        e=self.e;frames=[e.actor_tick('actual-jump',[-2533,136.53165,203],[0,0],50,i==0)for i in range(80)]
        self.assertGreater(max(r['position'][1]for r in frames),138)
        self.assertTrue(any(r['velocityY']<0 for r in frames));self.assertIn(0x38,[p for r in frames for p in r['postureRequests']]);self.assertTrue(frames[-1]['grounded'])
        drops=[e.actor_tick('actual-drop',[-2533,136.53165,203],[-4.8,0],50)for _ in range(90)]
        self.assertIn(0x30,[p for r in drops for p in r['postureRequests']]);self.assertTrue(drops[-1]['grounded'])

    def test_original_run_export_preserves_all_old_data(self):
        from shore_assets import player_clips
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        old=json.loads((RUNTIME/'game-data/converted/source-swimming/elf-female.json').read_text());new=json.loads((EXPORT/'elf-female.json').read_text())
        self.assertEqual(player_clips(Sources(DEFAULT_SOURCE),old),new)
        self.assertEqual(new['clips'][:-1],old['clips'])
        for k,v in old.items():
            if k!='clips':self.assertEqual(new[k],v)
        self.assertEqual(new['clips'][-1]['name'],'run_normal')

    def test_real_skeleton_swim_run_idle_jump_transitions(self):
        javascript("""import assert from'node:assert/strict';import{readFileSync}from'node:fs';
        import*as THREE from'./analysis/raw/showcase-20261110/running-preview/prototype/node_modules/three/build/three.module.js';
        import*as a from'./analysis/raw/showcase-20261110/running-preview/prototype/public/character-animation-shore.js';
        const d=JSON.parse(readFileSync('analysis/raw/shore-assets-ready-20261111/elf-female.json'));
        const root=a.createCharacterFactory(THREE,d,d.materials.map(()=>new THREE.MeshBasicMaterial()))();
        const sync=(s,t)=>a.syncCharacterCombat(root,{hp:100,alive:true,...s},t,.7);
        sync({swimming:true,locomotionPosture:80},1000);a.updateCharacterAnimation(root,.1,{moving:true},1000);assert.equal(a.characterAnimationState(root).phase,'swim_forward');
        sync({swimming:false,locomotionPosture:32},2000);
        for(let i=0;i<5;i++)a.updateCharacterAnimation(root,.1,{moving:true,speed:4.8},2000+i*100);
        let s=a.characterAnimationState(root);assert.equal(s.phase,'run_normal');
        const clip=d.clips.find(c=>c.name==='run_normal'),track=clip.tracks.find(t=>t.type==='quaternion'&&d.rig.nodes[t.node].name==='Bip01_L_UpperArm-node');
        const expected=Array.from(new THREE.QuaternionKeyframeTrack('x.quaternion',track.times,track.values).createInterpolant().evaluate(.5));
        assert(s.bones[track.node].quaternion.toArray().every((v,i)=>Math.abs(v-expected[i])<1e-6));
        sync({swimming:false,locomotionPosture:null},3000);a.updateCharacterAnimation(root,.1,{moving:false},3000);assert.equal(a.characterAnimationState(root).phase,'idle');
        sync({jump:{physics:'source-world-v1',startedAt:4000,updatedAt:4100,endsAt:9000,height:1,moving:true,landedAt:null}},4100);
        a.updateCharacterAnimation(root,.1,{moving:true,speed:4.8},4100);assert.equal(a.characterAnimationState(root).phase,'jump_start');
        sync({swimming:true,locomotionPosture:80},5000);a.updateCharacterAnimation(root,.1,{moving:false},5000);assert.equal(a.characterAnimationState(root).phase,'swim_idle');a.disposeCharacterAnimation(root);""")

    def test_old_art_light_save_and_pause_preserved(self):
        for label,folder in [('assets','game-data/converted'),('public','prototype/public')]:
            for n,sha in json.loads((RAW/f'before-{label}.json').read_text()).items():
                if label=='public'and n in ('explore-map.js','explore-map.html'):continue
                self.assertEqual(hashlib.sha256((RUNTIME/folder/n).read_bytes()).hexdigest(),sha,n)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'before-main-private.json').read_bytes())
        self.assertIn('status = "PAUSED"',(Path.home()/'.codex/automations/2/automation.toml').read_text())


if __name__=='__main__':unittest.main()
