"""Regression fixtures for original ARM64 static physics, not an Android session."""
import json
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT,source_coordinates

NATIVE=ROOT/'analysis/raw/beff-native/library.so'
GEOMETRY=ROOT/'analysis/raw/map-geometry-20261111'
COLLISION=ROOT/'analysis/raw/walk-collision-20261111/final-export/collision.json'


class PublicTests(unittest.TestCase):
    def test_atlas_enumeration_preserves_missing_cells_and_negative_coordinates(self):
        class Archive:
            lookup={'world/tutorial/terrain/-004_0002.trn':[],
                    'world/tutorial/terrain/-002_0002.trn':[],
                    'world/other/terrain/0000_0000.trn':[],
                    'world/tutorial/items/-003_0002.itm':[]}
        self.assertEqual(source_coordinates(Archive()),[[-4,2],[-2,2]])

    def test_no_original_files_are_required_for_enumeration(self):
        class Archive:lookup={}
        with self.assertRaisesRegex(ValueError,'No original'):source_coordinates(Archive())


@unittest.skipUnless(NATIVE.is_file()and COLLISION.is_file(),'Original binary and source files stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from source_physics import SourcePhysics
            from analyze_native_resources import NativeImage
            from map_loading_evidence import Sources
            from resource_packs import DEFAULT_SOURCE
            cls.e=SourcePhysics(NativeImage(NATIVE.read_bytes()))
        except ImportError as e:raise unittest.SkipTest('Native dependencies unavailable: '+str(e))
        terrain=json.loads((GEOMETRY/'base/maps/tutorial-window.json').read_text())
        profile=json.loads(COLLISION.read_text())
        flags={tuple(t['tile']):t['runtimeFlags']for t in json.loads((GEOMETRY/'verified/terrain-lighting.json').read_text())['tiles']}
        cls.info=cls.e.load_world(terrain,profile,Sources(DEFAULT_SOURCE).read,flags)

    def run_motion(self,name,start,velocity,count=80,jump=False):
        return [self.e.actor_tick(name,start,velocity,50,jump and i==0)for i in range(count)]

    def test_original_reader_transform_and_scene_container_cover_source_instances(self):
        self.assertEqual([self.info[k]for k in ('tiles','instances','shapes')],[25,217,639])

    def test_body_stops_before_source_wall_without_triangle_or_ray_substitution(self):
        frames=self.run_motion('wall',[-2617,143.68184,173],[0,4.8])
        end=frames[-1]['position']
        self.assertAlmostEqual(end[2],174.5400390625,delta=.001)
        self.assertAlmostEqual(end[1],143.68184,delta=.001)

    def test_stationary_jump_impulse_gravity_and_landing_are_original_instructions(self):
        frames=self.run_motion('jump',[-2533,136.53165,203],[0,0],jump=True)
        self.assertAlmostEqual(max(f['position'][1]for f in frames),138.02565,delta=.001)
        self.assertTrue(any(f['velocityY']<0 for f in frames));self.assertTrue(frames[-1]['grounded'])
        self.assertAlmostEqual(frames[-1]['position'][1],136.53166,delta=.001)
        self.assertIn(0x38,[p for f in frames for p in f['postureRequests']])

    def test_source_stair_edge_blocks_ground_motion_and_jump_crosses_it(self):
        walk=self.run_motion('stair-walk',[-2617,141.759,162],[0,4.8])
        self.assertAlmostEqual(walk[-1]['position'][2],166.2301025,delta=.001)
        jump=self.run_motion('stair-jump',walk[-1]['position'],[0,4.8],jump=True)
        self.assertGreater(jump[-1]['position'][2],173)
        self.assertAlmostEqual(jump[-1]['position'][1],143.68184,delta=.001)
        self.assertTrue(jump[-1]['grounded'])

    def test_bridge_exit_falls_and_source_consumer_returns_to_ground(self):
        frames=self.run_motion('fall',[-2533,136.53165,203],[-4.8,0],count=90)
        self.assertIn(0x30,[p for f in frames for p in f['postureRequests']])
        self.assertTrue(any(not f['grounded']for f in frames));self.assertTrue(frames[-1]['grounded'])
        self.assertAlmostEqual(frames[-1]['position'][1],132.35,delta=.001)
        self.assertEqual(frames[-1]['lastPosture'],0x20) # This source branch requests idle, not jump-land.

    def test_airborne_repeat_request_does_not_create_second_impulse(self):
        a=self.e.actor_tick('repeat',[-2533,136.53165,203],[0,0],50,True)
        b=self.e.actor_tick('repeat',a['position'],[0,0],50,True)
        self.assertGreater(a['velocityY'],b['velocityY'])
        self.assertFalse(b['grounded'])

    def test_missing_and_pending_water_cells_are_explicitly_unavailable(self):
        self.assertFalse(self.e.available(0,0))
        pending=[(t,i)for t,row in self.e.chunk_flags.items()for i,f in enumerate(row)if f&0x10000]
        self.assertTrue(pending)
        (x,z),i=pending[0]
        self.assertFalse(self.e.available(x*64+i%8*8+1,z*64+i//8*8+1))


if __name__=='__main__':unittest.main()
