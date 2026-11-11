"""Original model mode, two queues, source priority and conservative pose binding."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from terrain_water_tests import javascript

RAW=ROOT/'analysis/raw/multilayer-20261111';EXPORT=ROOT/'analysis/raw/layer-queue-assets-ready-20261111';RUNTIME=ROOT/'analysis/raw/showcase-20261110/running-preview'


class PublicTests(unittest.TestCase):
    def test_connector_is_restricted_to_ignored_runtime(self):
        from connect_layer_queue import connect
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)

    def test_renderer_rejects_unrecovered_layer_disagreement(self):
        javascript(r"""import assert from'node:assert/strict';import{readFileSync}from'node:fs';
        const code=readFileSync('tools/preview/source-locomotion-blending.js','utf8').replace(/^import.*;$/gm,'').replace(/^export \*.*;$/gm,'');const{checkedBlend}=await import('data:text/javascript,'+encodeURIComponent(code));
        const layer={current:{clip:'idle',ageMs:50,loop:true},previous:null,weights:[1,0],remainingMs:0};
        const packet={...layer,available:true,sequence:1,nativeStateCPU:true,nativeBlendCPU:true,nativeLayerQueueCPU:true,sourceChannels:2,layerPoseAgreement:true,layers:[{...layer,channel:0},{...layer,channel:1}]};assert.equal(checkedBlend(packet),packet);
        for(const p of [{...packet,sourceChannels:1},{...packet,layerPoseAgreement:false},{...packet,layers:[packet.layers[0],{...layer,channel:1,current:{clip:'run_idle',ageMs:50}}]},{...packet,current:{clip:'run_idle',ageMs:50}}])assert.throws(()=>checkedBlend(p));""")


@unittest.skipUnless(EXPORT.is_dir()and(ROOT/'analysis/raw/beff-native/library.so').is_file(),'Original model/layer inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from source_layer_queue import SourceLayerQueue
            from analyze_native_resources import NativeImage
        except ImportError as e:raise unittest.SkipTest(str(e))
        cfg=json.loads((RUNTIME/'prototype/native-physics.json').read_text());cls.image=NativeImage(Path(cfg['library']).read_bytes());e=cls.e=SourceLayerQueue(cls.image);cls.profile=json.loads((EXPORT/'profile.json').read_text())
        e.load_world(json.loads(Path(cfg['terrain']).read_text()),json.loads(Path(cfg['collision']).read_text()),lambda n:Path(cfg['sourceFiles'][n]['path']).read_bytes(),{tuple(r['tile']):r['runtimeFlags']for r in json.loads(Path(cfg['terrainLighting']).read_text())['tiles']})
        e.load_water(json.loads(Path(cfg['swimming']).read_text()));e.load_diving(json.loads(Path(cfg['diving']).read_text()));e.load_animation_blending(json.loads(Path(cfg['animationBlending']).read_text()));e.load_stop_queue(json.loads(Path(cfg['stopQueue']).read_text()));e.load_layer_queue(cls.profile)

    def tick(self,name,pos,direction=0):
        r=self.e.actor_tick(name,pos,[direction*4.8,0],50,False,{'forward':bool(direction)});return r,r['position']

    def shore(self,name):
        p=[-2235.5,108.55000305175781,12]
        for _ in range(24):r,p=self.tick(name,p,1)
        self.assertEqual(r['waterState'],0);return p

    def test_source_model_rows_all_derive_two_channels(self):
        from layer_queue_assets import recover,model_flags
        from map_loading_evidence import Sources
        from resource_packs import DEFAULT_SOURCE
        self.assertEqual(recover(self.image,Sources(DEFAULT_SOURCE)),self.profile)
        self.assertEqual({r['ID']for r in self.profile['modelRows']},{2,62,351,407});self.assertEqual({r['engineFlags']for r in self.profile['modelRows']},{3})
        self.assertEqual(model_flags(self.e,1),1);self.assertEqual(model_flags(self.e,4),3)

    def test_both_source_channels_complete_stop_and_resume(self):
        pos=self.shore('two-stop');frames=[]
        for direction,count in [(0,32),(1,4),(0,3),(1,8),(-1,38),(0,3)]:
            for _ in range(count):r,pos=self.tick('two-stop',pos,direction);frames.append(r)
        for r in frames:
            p=r['sourceAnimation'];self.assertTrue(p['available']);self.assertEqual(p['sourceChannels'],2);self.assertTrue(p['layerPoseAgreement']);self.assertEqual(p['layerRootWeights'],[0,1]);self.assertEqual([l['completionCount']for l in p['layers']],[p['completionCount']]*2)
        self.assertEqual(frames[23]['sourceAnimation']['current']['ageMs'],1166);self.assertEqual(frames[24]['sourceAnimation']['current']['clip'],'idle')
        self.assertEqual(r['sourceAnimation']['current']['clip'],'swim_idle');(RAW/'verified-roundtrip.json').write_text(json.dumps(frames,indent=2))

    def test_priority_query_reads_actual_channel_names_and_row_mode(self):
        pos=self.shore('priority-check');r,pos=self.tick('priority-check',pos);e=self.e;actor=e.actors['priority-check'];q=actor['stopQueue'];saved=e.r(q['controller']+0xa8,'Q')[0];observed=[]
        try:
            for cached,mode,expected in [('',0,0xffffffff),('run_idle',0,0),('run_idle',1,0),('run_idle',2,0xfffffffe),('idle',0,0xffffffff)]:
                e.w(q['controller']+0xa8,'Q',e.string(cached.encode()));e.w(q['controller']+0x70,'I',mode);result=e.priority_query(actor,q);observed.append(result);self.assertEqual(result,expected)
        finally:e.w(q['controller']+0xa8,'Q',saved);e.w(q['controller']+0x70,'I',0)
        self.assertEqual(e.r(actor['address']+0x38,'Q')[0],0)

    def test_distinct_track_layers_remain_unknown(self):
        pos=self.shore('different');e=self.e;actor=e.actors['different'];q=actor['stopQueue'];config=e.alloc(0x30);e.w(config,'QI3f3Q',e.string(b'idle'),3,1,0,150,0,0,0)
        e.queue_native=True
        try:e.original_fragment(0xa2dd68,0xa2dd78,{'X21':config+8});e.call(0x331a28,{'X0':q['view'],'W1':1,'X2':config})
        finally:e.queue_native=False
        r,pos=self.tick('different',pos,1);self.assertFalse(r['sourceAnimation']['available']);self.assertEqual(r['sourceAnimation']['reason'],'distinct-track-bone-composition-not-recovered')

    def test_original_callbacks_are_separate_for_each_channel(self):
        pos=self.shore('channel-callbacks');r,pos=self.tick('channel-callbacks',pos);e=self.e;q=e.actors['channel-callbacks']['stopQueue'];c0,c1=[v['control']for v in q['layers']]
        self.assertEqual(e.r(c0+0x10,'Q')[0],0x32b210);self.assertEqual(e.r(c1+0x10,'Q')[0],0x32b24c)
        e.queue_native=True
        try:e.call(0x11962c0,{'X0':c1},{'S0':1200})
        finally:e.queue_native=False
        self.assertEqual(e.r(q['engine']+0x10,'B')[0]&1,0);self.assertEqual(e.r(q['engine']+0x14,'B')[0]&1,1)

    def test_prepared_scalar_views_do_not_allocate_every_idle_tick(self):
        e=self.e;r,pos=self.tick('stable-memory',[-2235.5,108.55000305175781,12]);r,pos=self.tick('stable-memory',pos);before=e.cursor
        for _ in range(200):r,pos=self.tick('stable-memory',pos)
        self.assertEqual(e.cursor,before)

    def test_original_model_data_and_old_track_geometry_are_unchanged(self):
        old=json.loads((RUNTIME/'game-data/converted/source-stop-queue/elf-female.json').read_text());new=json.loads((EXPORT/'elf-female.json').read_text())
        for k,v in old.items():self.assertEqual(new[k],v)
        self.assertFalse(new['sourceLayerQueueBinding']['distinctPoseCompositionRestored'])

    def test_old_art_main_save_and_pause_remain(self):
        for n,sha in json.loads((RAW/'before-assets.json').read_text()).items():self.assertEqual(hashlib.sha256((RUNTIME/'game-data/converted'/n).read_bytes()).hexdigest(),sha,n)
        self.assertEqual((ROOT/'runtime/characters.json').read_bytes(),(RAW/'before-main-private.json').read_bytes());self.assertIn('status = "PAUSED"',(Path.home()/'.codex/automations/2/automation.toml').read_text())


if __name__=='__main__':unittest.main()
