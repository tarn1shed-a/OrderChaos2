"""Source queue/finish CPU, stop interruption and real track regressions."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from terrain_water_tests import javascript

RAW=ROOT/'analysis/raw/stop-queue-20261111'
RUNTIME=ROOT/'analysis/raw/showcase-20261110/running-preview'
EXPORT=ROOT/'analysis/raw/stop-queue-assets-ready-20261111'


class PublicTests(unittest.TestCase):
    def test_connector_cannot_edit_main_or_backup(self):
        from connect_stop_queue import connect
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)

    def test_unknown_profile_does_not_write_preview_files(self):
        from connect_stop_queue import connect
        parent=ROOT/'analysis/raw';parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent)as td:
            p=Path(td);(p/'profile.json').write_text('{"format":"unknown"}');before={f.name:f.read_bytes()for f in p.iterdir()}
            with self.assertRaisesRegex(ValueError,'Unknown'):connect(p,p)
            self.assertEqual(before,{f.name:f.read_bytes()for f in p.iterdir()})


@unittest.skipUnless(EXPORT.is_dir()and(ROOT/'analysis/raw/beff-native/library.so').is_file(),'Original queue inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from source_stop_queue import SourceStopQueue
            from analyze_native_resources import NativeImage
        except ImportError as e:raise unittest.SkipTest(str(e))
        cfg=json.loads((RUNTIME/'prototype/native-physics.json').read_text());cls.image=NativeImage(Path(cfg['library']).read_bytes());cls.profile=json.loads((EXPORT/'profile.json').read_text());e=cls.e=SourceStopQueue(cls.image)
        e.load_world(json.loads(Path(cfg['terrain']).read_text()),json.loads(Path(cfg['collision']).read_text()),lambda n:Path(cfg['sourceFiles'][n]['path']).read_bytes(),{tuple(r['tile']):r['runtimeFlags']for r in json.loads(Path(cfg['terrainLighting']).read_text())['tiles']})
        e.load_water(json.loads(Path(cfg['swimming']).read_text()));e.load_diving(json.loads(Path(cfg['diving']).read_text()));e.load_animation_blending(json.loads(Path(cfg['animationBlending']).read_text()));e.load_stop_queue(cls.profile)

    def tick(self,identity,pos,direction=0):
        r=self.e.actor_tick(identity,pos,[direction*4.8,0],50,False,{'forward':bool(direction)})
        return r,r['position']

    def shore(self,identity):
        pos=[-2235.5,108.55000305175781,12]
        for _ in range(24):r,pos=self.tick(identity,pos,1)
        self.assertEqual(r['waterState'],0);self.assertEqual(r['sourceAnimation']['current']['clip'],'run_normal_front')
        return pos

    def test_original_profile_uses_source_range_not_rounded_export_duration(self):
        from stop_queue_assets import recover
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        self.assertEqual(recover(self.image,Sources(DEFAULT_SOURCE)),self.profile)
        r=self.profile['ranges']['run_idle'];self.assertEqual(r['endMs']-r['startMs'],1166)
        player=json.loads((EXPORT/'elf-female.json').read_text());duration=next(c['duration']for c in player['clips']if c['name']=='run_idle')*1000
        self.assertNotEqual(duration,1166)

    def test_real_shore_stop_native_request_finish_and_idle(self):
        pos=self.shore('stop-finish');frames=[]
        for i in range(34):
            r,pos=self.tick('stop-finish',pos);frames.append(r);p=r['sourceAnimation']
            self.assertTrue(p['nativeQueueCPU']);self.assertFalse(p['originalTwoChannelAnimation']);self.assertFalse(p['primaryQueueRestored'])
        first=frames[0]['sourceAnimation'];self.assertEqual([r['name']for r in first['requests']],['run_idle','idle']);self.assertEqual(first['requests'][0]['blend'],150)
        self.assertEqual(first['requests'][1]['flags'],0x114);self.assertEqual(first['current']['loop'],False)
        self.assertTrue(all(r['sourceAnimation']['current']['clip']=='run_idle'for r in frames[:24]))
        self.assertEqual(frames[23]['sourceAnimation']['current']['ageMs'],1166)
        self.assertEqual(frames[23]['sourceAnimation']['completionCount'],1)
        self.assertEqual(frames[24]['sourceAnimation']['current']['clip'],'idle');self.assertTrue(frames[24]['sourceAnimation']['current']['loop'])
        self.assertEqual(frames[-1]['sourceAnimation']['completionCount'],1)
        (RAW/'verified-stop-finish.json').write_text(json.dumps(frames,indent=2))

    def test_native_finish_is_strictly_after_end_and_only_once(self):
        pos=self.shore('strict-end');r,pos=self.tick('strict-end',pos);q=self.e.actors['strict-end']['stopQueue'];c=q['control'];e=self.e
        self.assertEqual(e.r(q['engine']+0x10,'B')[0]&1,0)
        e.queue_native=True
        try:
            e.call(0x11962c0,{'X0':c},{'S0':1116})
            self.assertEqual(e.r(c+8,'f')[0],self.profile['ranges']['run_idle']['endMs']);self.assertEqual(e.r(c+0x44,'B')[0],0)
            e.call(0x11962c0,{'X0':c},{'S0':1});self.assertEqual(e.r(c+0x44,'B')[0],1);self.assertEqual(e.r(q['engine']+0x10,'B')[0]&0x11,0x11)
            e.w(q['engine']+0x10,'B',0);e.call(0x11962c0,{'X0':c},{'S0':1000});self.assertEqual(e.r(q['engine']+0x10,'B')[0],0)
        finally:e.queue_native=False

    def test_changing_supplied_source_range_changes_native_completion(self):
        altered=copy.deepcopy(self.profile);altered['ranges']['run_idle']['endMs']+=100;e=self.e;old=e.stop_profile;e.stop_profile=altered
        try:
            pos=self.shore('range-shift');frames=[]
            for _ in range(29):r,pos=self.tick('range-shift',pos);frames.append(r['sourceAnimation'])
            self.assertEqual(frames[23]['completionCount'],0);self.assertEqual(frames[25]['completionCount'],1);self.assertEqual(frames[26]['current']['clip'],'idle')
        finally:e.stop_profile=old

    def test_moving_again_interrupts_stop_without_stale_finish(self):
        pos=self.shore('early-resume')
        for _ in range(4):r,pos=self.tick('early-resume',pos)
        old=self.e.actors['early-resume']['stopQueue']['control'];self.assertEqual(r['sourceAnimation']['current']['clip'],'run_idle')
        r,pos=self.tick('early-resume',pos,1);self.assertEqual(r['sourceAnimation']['current']['clip'],'run_normal_front');self.assertEqual(self.e.r(old+0x10,'2Q'),(0,0))
        for _ in range(30):r,pos=self.tick('early-resume',pos,1)
        self.assertEqual(r['sourceAnimation']['completionCount'],0)

    def test_water_roundtrip_and_no_model_success_or_binding_mutation(self):
        e=self.e;pos=self.shore('roundtrip');actor=e.actors['roundtrip'];at=actor['address'];fields={o:e.r(at+o,'Q')[0]for o in (0x3a0,0x770,0x38)}
        frames=[]
        for direction,count in [(0,30),(1,3),(0,3),(-1,36),(0,3)]:
            for _ in range(count):r,pos=self.tick('roundtrip',pos,direction);frames.append(r)
        self.assertTrue({0,3,4}.issubset({r['waterState']for r in frames}));self.assertEqual(r['sourceAnimation']['current']['clip'],'swim_idle')
        self.assertEqual({o:e.r(at+o,'Q')[0]for o in fields},fields);self.assertEqual(fields[0x38],0)
        self.assertFalse(e.load_stop_queue(self.profile)['originalModelAnimationLoader'])

    def test_real_stop_track_clamps_and_keeps_bones_and_attachments(self):
        javascript("""import assert from'node:assert/strict';import{readFileSync}from'node:fs';
        import*as THREE from'./analysis/raw/showcase-20261110/running-preview/prototype/node_modules/three/build/three.module.js';
        import*as a from'./analysis/raw/showcase-20261110/running-preview/prototype/public/source-locomotion-blending.js';
        const d=JSON.parse(readFileSync('analysis/raw/stop-queue-assets-ready-20261111/elf-female.json')),root=a.createCharacterFactory(THREE,d,d.materials.map(()=>new THREE.MeshBasicMaterial()))();
        const clip=d.clips.find(c=>c.name==='run_idle'),p={available:true,nativeStateCPU:true,nativeBlendCPU:true,nativeQueueCPU:true,sequence:3,current:{clip:'run_idle',ageMs:1166,loop:false},previous:null,weights:[1,0],completionCount:1};
        a.syncCharacterCombat(root,{hp:100,alive:true,sourceAnimation:p},1000,.7);a.updateCharacterAnimation(root,.1,{moving:false},1600);
        let s=a.characterAnimationState(root);assert.equal(s.phase,'run_idle');assert.equal(s.sourceBlend.loop,false);
        const track=clip.tracks.find(t=>t.type==='quaternion'&&d.rig.nodes[t.node].name==='Bip01_L_UpperArm-node'),q=new THREE.Quaternion().fromArray(new THREE.QuaternionKeyframeTrack('x',track.times,track.values).createInterpolant().evaluate(clip.duration));
        assert(s.bones[track.node].quaternion.angleTo(q)<.001);assert(a.characterAttachment(root,'Bip01_Head',new THREE.Vector3()));
        a.disposeCharacterAnimation(root);""")

    def test_old_art_public_main_save_and_pause_preserved(self):
        for label,folder in [('assets','game-data/converted'),('public','prototype/public')]:
            for n,sha in json.loads((RAW/f'before-{label}.json').read_text()).items():
                if label=='public'and n in ('explore-map.js','explore-map.html','source-locomotion-blending.js'):continue
                self.assertEqual(hashlib.sha256((RUNTIME/folder/n).read_bytes()).hexdigest(),sha,n)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'before-main-private.json').read_bytes())
        self.assertIn('status = "PAUSED"',(Path.home()/'.codex/automations/2/automation.toml').read_text())


if __name__=='__main__':unittest.main()
