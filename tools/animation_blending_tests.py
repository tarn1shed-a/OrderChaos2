"""Original normal state commits, action lookup and scalar blend regressions."""
import hashlib
import json
import random
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from terrain_water_tests import javascript

RAW=ROOT/'analysis/raw/shore-blending-20261111'
RUNTIME=ROOT/'analysis/raw/showcase-20261110/running-preview'
EXPORT=ROOT/'analysis/raw/blending-assets-ready-20261111'


class PublicTests(unittest.TestCase):
    def test_connector_cannot_edit_main_or_backup(self):
        from connect_animation_blending import connect
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)

    def test_only_checked_native_blend_packets_are_accepted(self):
        javascript(r"""import assert from'node:assert/strict';import{readFileSync}from'node:fs';
        const code=readFileSync('tools/preview/source-locomotion-blending.js','utf8').replace(/^import.*;$/gm,'').replace(/^export \*.*;$/gm,'');
        const {checkedBlend}=await import('data:text/javascript,'+encodeURIComponent(code));
        assert.equal(checkedBlend({available:false,reason:'missing-primary-queue'}),null);
        const p={available:true,nativeStateCPU:true,nativeBlendCPU:true,sequence:1,current:{clip:'swim_forward',ageMs:50},previous:{clip:'swim_idle',ageMs:100},weights:[1/3,2/3]};assert.equal(checkedBlend(p),p);
        for(const bad of [{nativeStateCPU:false},{nativeBlendCPU:false},{weights:[-.1,1.1]},{weights:[.2,.2]},{sequence:0},{current:{ageMs:NaN}},{previous:null}])assert.throws(()=>checkedBlend({...p,...bad}));""")


@unittest.skipUnless(EXPORT.is_dir()and(ROOT/'analysis/raw/beff-native/library.so').is_file(),'Original animation inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from source_animation_blending import SourceAnimationBlending
            from analyze_native_resources import NativeImage
        except ImportError as e:raise unittest.SkipTest(str(e))
        cfg=json.loads((RUNTIME/'prototype/native-physics.json').read_text());cls.image=NativeImage(Path(cfg['library']).read_bytes());cls.profile=json.loads((EXPORT/'profile.json').read_text());cls.e=SourceAnimationBlending(cls.image)
        cls.e.load_world(json.loads(Path(cfg['terrain']).read_text()),json.loads(Path(cfg['collision']).read_text()),lambda n:Path(cfg['sourceFiles'][n]['path']).read_bytes(),
            {tuple(r['tile']):r['runtimeFlags']for r in json.loads(Path(cfg['terrainLighting']).read_text())['tiles']})
        cls.e.load_water(json.loads(Path(cfg['swimming']).read_text()));cls.e.load_diving(json.loads(Path(cfg['diving']).read_text()));cls.e.load_animation_blending(cls.profile)

    def test_original_initializer_and_table_disprove_cached_run_clip_selection(self):
        from animation_blending import recover,action_map
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        self.assertEqual(recover(self.image,Sources(DEFAULT_SOURCE)),self.profile)
        self.assertEqual(len(action_map(self.image)),168)
        self.assertEqual(self.profile['stateActions']['34'],[-1,426])
        self.assertEqual(self.profile['actions']['426']['anim_name'],'run_normal_front')
        self.assertEqual(self.profile['stateActions']['82'],[-1,35]);self.assertEqual(self.profile['stateActions']['85'],[-1,36])
        self.assertEqual(self.profile['stateActions']['10'],[24,1])

    def test_original_blend_initialization_and_weight_fragment_match_float32_reference(self):
        from source_physics import f32
        e=self.e;d=e.display_actor(e.actor('weights',[-2235.5,108.55000305175781,12]));rng=random.Random(1982)
        for _ in range(80):
            raw=rng.choice([-1,0,.5,1,50,150,200,333.9]);children=rng.choice([1,2]);duration=150 if raw<0 else int(raw)
            e.blend_start(d,raw,children);remaining=duration if duration>0 and children>1 else 0
            self.assertEqual(e.r(d['blendNode']+0xb8,'I')[0],remaining)
            expected=[0,1]if remaining else[1,0]
            for dt in [0,1,17,50,100,200]:
                if remaining:
                    remaining=max(0,remaining-dt);old=min(f32(remaining/duration),self.profile['blendOldWeightCap']);expected=[f32(1-old),old]
                self.assertEqual(e.blend_tick(d,dt),expected)
        e.blend_start(d,150,2);self.assertGreater(e.blend_tick(d,50)[1],0)
        e.blend_start(d,150,1);self.assertEqual(e.blend_tick(d,0),[1,0])
        # Original successful actor-model initialization always enables bit0,
        # including both one-channel and two-channel configurations.
        actor=e.actors['weights']
        for flags in list(range(8))+[rng.getrandbits(32)for _ in range(24)]:
            e.original_fragment(0x9e96e8,0x9e9704,{'X19':actor['address']},stack=(0,)*60+(flags<<32,))
            w21,w24=e.get('W21'),e.get('W24')
            e.original_fragment(0x9e9798,0x9e97b0,{'W21':w21,'W24':w24,'X29':e.STACK+0xd0})
            self.assertIn(e.get('W3'),[1,3])

    def test_actual_source_state_roundtrip_and_blend_leave_primary_queue_explicit(self):
        e=self.e;pos=[-2235.5,108.55000305175781,12];frames=[]
        for direction,count in [(0,4),(1,24),(0,5),(-1,30),(0,5)]:
            for i in range(count):
                r=e.actor_tick('real-roundtrip',pos,[direction*4.8,0],50,False,{'forward':direction!=0});pos=r['position'];frames.append(r)
        self.assertEqual({r['waterState']for r in frames},{0,3,4})
        plans=[r['sourceAnimation']for r in frames];self.assertEqual({p['posture']for p in plans},{8,32,80})
        blends=[p for p in plans if p.get('available')and p['previous']and p['current']['clip']=='run_normal_front']
        self.assertTrue(any(0<p['weights'][0]<1 for p in blends));self.assertTrue(any(p['weights']==[1,0]for p in blends))
        missing=[p for p in plans if not p['available']];self.assertTrue(missing)
        self.assertTrue(all(p['actionPair']==[24,1]and p['primaryQueueRestored']is False for p in missing))
        (RAW/'verified-roundtrip.json').write_text(json.dumps(frames,indent=2))

    def test_native_state_does_not_replace_physics_binding_or_report_resource_success(self):
        e=self.e;actor=e.actor('binding',[-2235.5,108.55000305175781,12]);at=actor['address'];before={off:e.r(at+off,'Q')[0]for off in (0x3a0,0x770)}
        r=e.actor_tick('binding',[-2235.5,108.55000305175781,12],[4.8,0],50,False,{'forward':True})
        self.assertEqual({off:e.r(at+off,'Q')[0]for off in before},before)
        self.assertTrue(r['sourceAnimation']['nativeStateCPU']);self.assertFalse(e.load_animation_blending(self.profile)['originalModelAnimationLoader'])
        self.assertEqual(e.r(at+0x38,'Q')[0],0)

    def test_original_jump_drop_and_unrecovered_direction_keep_existing_playback(self):
        e=self.e;start=[-2533,136.53165,203]
        jump=e.actor_tick('jump-scope',start,[0,0],50,True,{'forward':False})
        self.assertFalse(jump['sourceAnimation']['available']);self.assertGreater(jump['velocityY'],0)
        sideways=e.actor_tick('sideways-scope',[-2235.5,108.55000305175781,12],[0,4.8],50,False,{'forward':False})
        self.assertFalse(sideways['sourceAnimation']['available']);self.assertIn('direction',sideways['sourceAnimation']['reason'])

    def test_new_source_tracks_preserve_old_model_and_actions(self):
        old=json.loads((RUNTIME/'game-data/converted/source-shore/elf-female.json').read_text());new=json.loads((EXPORT/'elf-female.json').read_text())
        for k,v in old.items():self.assertEqual(new[k][:-2]if k=='clips'else new[k],v)
        self.assertEqual({c['name']for c in new['clips'][-2:]},{'run_normal_front','run_idle'})
        self.assertFalse(new['sourceBlendBinding']['primaryRunIdleQueueRestored'])

    def test_actual_skeleton_uses_both_native_weights_and_preserves_fallback_and_attachments(self):
        javascript("""import assert from'node:assert/strict';import{readFileSync}from'node:fs';
        import*as THREE from'./analysis/raw/showcase-20261110/running-preview/prototype/node_modules/three/build/three.module.js';
        import*as a from'./analysis/raw/showcase-20261110/running-preview/prototype/public/source-locomotion-blending.js';
        const d=JSON.parse(readFileSync('analysis/raw/blending-assets-ready-20261111/elf-female.json'));
        const root=a.createCharacterFactory(THREE,d,d.materials.map(()=>new THREE.MeshBasicMaterial()))();
        const packet={available:true,nativeStateCPU:true,nativeBlendCPU:true,sequence:3,current:{clip:'run_normal_front',ageMs:50},previous:{clip:'swim_forward',ageMs:200},weights:[Math.fround(1-Math.fround(2/3)),Math.fround(2/3)],remainingMs:100,posture:32,movement:2};
        a.syncCharacterCombat(root,{hp:100,alive:true,swimming:false,locomotionPosture:32,sourceAnimation:packet},1000,.7);a.updateCharacterAnimation(root,.1,{moving:true,speed:4.8},1000);
        let s=a.characterAnimationState(root);assert.equal(s.phase,'run_normal_front');assert.deepEqual(s.sourceBlend.weights,packet.weights);
        const pose=(name,time)=>{const c=d.clips.find(c=>c.name===name),t=c.tracks.find(t=>t.type==='quaternion'&&d.rig.nodes[t.node].name==='Bip01_L_UpperArm-node');return{t,q:new THREE.Quaternion().fromArray(new THREE.QuaternionKeyframeTrack('x',t.times,t.values).createInterpolant().evaluate(time))};};
        const fresh=pose('run_normal_front',.05),old=pose('swim_forward',.2),expected=fresh.q.slerp(old.q,packet.weights[1]);
        assert(s.bones[fresh.t.node].quaternion.angleTo(expected)<.001);
        assert(a.characterAttachment(root,'Bip01_Head',new THREE.Vector3()));
        a.syncCharacterCombat(root,{hp:100,alive:true,locomotionPosture:null,sourceAnimation:{available:false,reason:'primary-queue'}},2000,.7);a.updateCharacterAnimation(root,.1,{moving:false},2000);assert.equal(a.characterAnimationState(root).phase,'idle');assert(!a.characterAnimationState(root).sourceBlend);
        a.disposeCharacterAnimation(root);""")

    def test_old_art_lighting_main_save_and_pause_are_unchanged(self):
        for label,folder in [('assets','game-data/converted'),('public','prototype/public')]:
            for n,sha in json.loads((RAW/f'before-{label}.json').read_text()).items():
                if label=='public'and n in ('explore-map.js','explore-map.html'):continue
                self.assertEqual(hashlib.sha256((RUNTIME/folder/n).read_bytes()).hexdigest(),sha,n)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'before-main-private.json').read_bytes())
        self.assertIn('status = "PAUSED"',(Path.home()/'.codex/automations/2/automation.toml').read_text())


if __name__=='__main__':unittest.main()
