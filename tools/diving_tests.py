"""Forward underwater motion and original normal-camera CPU regression checks."""
import hashlib
import json
import unittest
from pathlib import Path
from diving_controls import ROOT,recover
from terrain_water_tests import javascript

RAW=ROOT/'analysis/raw/diving-camera-20261111'
PROFILE=ROOT/'analysis/raw/diving-controls-ready-20261111/profile.json'
RUNTIME=ROOT/'analysis/raw/showcase-20261110/running-preview'


class PublicTests(unittest.TestCase):
    def test_connector_refuses_main_and_backup(self):
        from connect_diving import connect
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)

    def test_input_deltas_are_consumed_once_and_invalid_numbers_rejected(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const m=await import('data:text/javascript,'+encodeURIComponent(await readFile('tools/preview/source-diving-controls.js','utf8'))),c=m.createSourceCameraInput();
        c.rotate(10,20);c.zoom(-100);const one=c.packet(true,.1),two=c.packet(false,.1);
        assert(one.sourceCamera.yawDelta<0&&one.sourceCamera.pitchDelta<0&&one.sourceCamera.distanceScale<1);
        assert.deepEqual(two,{sourceForward:false,sourceCamera:{yawDelta:0,pitchDelta:0,distanceScale:1,near:.1}});
        assert.throws(()=>c.rotate(NaN,1));assert.throws(()=>c.zoom(Infinity));""")

    def test_render_binding_refuses_missing_native_cpu_pose(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const m=await import('data:text/javascript,'+encodeURIComponent(await readFile('tools/preview/source-diving-controls.js','utf8')));
        assert.throws(()=>m.applySourceCamera({},null,null,{position:[0,0,0],target:[0,0,1]}));
        assert.throws(()=>m.applySourceCamera({},null,null,{nativeCPU:true,position:[NaN,0,0],target:[0,0,1]}));""")


@unittest.skipUnless(PROFILE.is_file()and(ROOT/'analysis/raw/beff-native/library.so').is_file(),'Original diving/camera inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from analyze_native_resources import NativeImage
            from source_diving import SourceDiving
            from map_loading_evidence import Sources
            from resource_packs import DEFAULT_SOURCE
        except ImportError as e:raise unittest.SkipTest(str(e))
        cfg=json.loads((RUNTIME/'prototype/native-physics.json').read_text());cls.profile=json.loads(PROFILE.read_text())
        cls.image=NativeImage(Path(cfg['library']).read_bytes());cls.sources=Sources(DEFAULT_SOURCE);cls.e=SourceDiving(cls.image)
        terrain=json.loads(Path(cfg['terrain']).read_text());coll=json.loads(Path(cfg['collision']).read_text());light=json.loads(Path(cfg['terrainLighting']).read_text())
        cls.e.load_world(terrain,coll,lambda n:Path(cfg['sourceFiles'][n]['path']).read_bytes(),{tuple(r['tile']):r['runtimeFlags']for r in light['tiles']})
        cls.e.load_water(json.loads(Path(cfg['swimming']).read_text()));cls.e.load_diving(cls.profile)

    def test_profile_matches_original_node_constants_and_initial_spring(self):
        self.assertEqual(recover(self.image,self.sources),self.profile)
        a=self.e.actor('spring',[-2324,108.55000305175781,68]);c=a['camera']
        self.assertAlmostEqual(self.e.r(c+0x1b4,'f')[0],.15,places=6)
        self.assertAlmostEqual(self.e.r(c+0x1bc,'f')[0],.005,places=7)
        self.assertGreater(self.e.r(c+0x1b8,'f')[0],.7)
        self.assertAlmostEqual(self.profile['lookAtOffset'][1],2.3001477866,places=7)

    def test_original_surface_direction_guard_is_strict_at_thirty_degrees(self):
        a=self.e.actor('pitch-boundary',[-2324,108.55000305175781,68])
        self.assertIsNone(self.e.forward_direction(a,0,330))
        self.assertIsNone(self.e.forward_direction(a,0,355))
        d=self.e.forward_direction(a,0,329.9);self.assertLess(d[1],-.5)
        self.assertAlmostEqual(sum(v*v for v in d),1,places=6)

    def test_original_dive_stop_camera_and_rise_without_new_vertical_formula(self):
        e=self.e;pos=[-2324,108.55000305175781,68];start=pos[:];frames=[]
        for j in range(30):
            r=e.actor_tick('dive-rise',pos,[4.8,0],50,False,{'forward':True,'pitchDelta':-40 if j==0 else 0,'yawDelta':-90 if j==0 else 0});pos=r['position'];frames.append(r)
            self.assertGreaterEqual(pos[1]+.001,e.sample(pos[0],pos[2])['height'])
        self.assertLess(pos[1],start[1]-4);self.assertTrue(r['submerged']);self.assertTrue(r['camera']['underwaterFlag'])
        self.assertNotEqual(frames[0]['camera']['position'],frames[-1]['camera']['position'])
        stopped=pos[:]
        for j in range(40):
            r=e.actor_tick('dive-rise',pos,[0,0],50,False,{'pitchDelta':40 if j==0 else 0});pos=r['position']
        self.assertEqual(pos,stopped);self.assertEqual(r['velocityY'],0)
        self.assertGreater(e.camera_water(r['camera']['position'])['depth'],0)
        self.assertEqual(e.restore_height(pos)['height'],pos[1])
        for j in range(55):
            r=e.actor_tick('dive-rise',pos,[-4.8,0],50,False,{'forward':True,'pitchDelta':45 if j==0 else 0,'yawDelta':180 if j==0 else 0});pos=r['position']
        self.assertFalse(r['submerged']);self.assertGreater(pos[1],108.5)
        self.assertEqual(r['camera']['pitch'],355);self.assertFalse(r['camera']['underwaterFlag'])
        (RAW/'native-dive-frames.json').write_text(json.dumps(frames,separators=(',',':')))

    def test_original_pitch_clamp_and_bad_input_before_camera_mutation(self):
        e=self.e;a=e.actor('clamp',[-2324,108.55000305175781,68]);c=a['camera']
        e.set_camera_input(a,{'pitchDelta':-900});self.assertEqual(e.r(c+0x6c,'f')[0],280)
        e.set_camera_input(a,{'pitchDelta':900});self.assertEqual(e.r(c+0x6c,'f')[0],420)
        before=e.r(c+0x68,'4f')
        for bad in [{'yawDelta':float('nan')},{'distanceScale':0},{'near':2},{'pitchDelta':1001}]:
            with self.assertRaises(ValueError):e.set_camera_input(a,bad)
            self.assertEqual(e.r(c+0x68,'4f'),before)

    def test_existing_art_lighting_main_save_and_paused_automation_are_preserved(self):
        for n,sha in json.loads((RAW/'before-assets.json').read_text()).items():
            self.assertEqual(hashlib.sha256((RUNTIME/'game-data/converted'/n).read_bytes()).hexdigest(),sha,n)
        for n,sha in json.loads((RAW/'before-public.json').read_text()).items():
            if n not in ('explore-map.js','explore-map.html'):
                self.assertEqual(hashlib.sha256((RUNTIME/'prototype/public'/n).read_bytes()).hexdigest(),sha,n)
        self.assertEqual(hashlib.sha256((ROOT/'runtime/characters.json').read_bytes()).hexdigest(),'8db90023214c32d3e3a6ea88fdbcf3aa144582288a4d28651398f29f296af401')
        self.assertIn('status = "PAUSED"',(Path.home()/'.codex/automations/2/automation.toml').read_text())


if __name__=='__main__':unittest.main()
