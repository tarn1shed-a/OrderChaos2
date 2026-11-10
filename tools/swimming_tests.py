"""Original wet metadata, normal surface physics and camera numeric equivalence."""
import hashlib
import json
import random
import struct
import unittest
from pathlib import Path
from swimming_assets import ROOT,metadata,player_clips,underwater_effects
from source_physics import f32
from terrain_water_tests import javascript

RAW=ROOT/'analysis/raw/swimming-camera-20261111'
EXPORT=ROOT/'analysis/raw/swimming-final-ready-20261111'
RUNTIME=ROOT/'analysis/raw/showcase-20261110/running-preview'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'


class PublicTests(unittest.TestCase):
    def test_connector_refuses_main_and_backup_outputs(self):
        from connect_swimming import connect
        for p in [ROOT,ROOT/'backups']:
            with self.assertRaisesRegex(ValueError,'ignored'):connect(p,p)

    def test_camera_signed_coordinate_and_surface_branches(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const code=(await readFile('tools/preview/source-swimming-camera.js','utf8')).replace(/^import.*?;$/gm,'');
        const{sourceCameraWater:q}=await import('data:text/javascript,'+encodeURIComponent(code));
        const tiles=[{tile:[-1,0],chunks:Array.from({length:64},()=>({flags:65536,height:110,packedColor:0xff60400a,factor:Math.fround(.2)}))}];
        assert.equal(q(tiles,[-.25,110,4]).depth,-100); // Original float-to-int truncates to tile 0.
        assert.equal(q(tiles,[-1.25,110,4]).depth,0);assert.equal(q(tiles,[-1.25,109,4]).underwater,true);
        assert.equal(q(tiles,[-1.25,111,4]).underwater,false);assert.equal(q([],[-1,109,4]).depth,-100);
        """)

    def test_invalid_camera_input_is_not_a_default_underwater_state(self):
        javascript("""import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
        const code=(await readFile('tools/preview/source-swimming-camera.js','utf8')).replace(/^import.*?;$/gm,'');
        const{sourceCameraWater:q}=await import('data:text/javascript,'+encodeURIComponent(code));
        for(const p of [null,[0,0],[NaN,0,0],[0,Infinity,0]])assert.throws(()=>q([],p));""")


@unittest.skipUnless(NATIVE.is_file()and(EXPORT/'swimming.json').is_file(),'Original swimming inputs stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from analyze_native_resources import NativeImage
            from map_loading_evidence import Sources
            from resource_packs import DEFAULT_SOURCE
            from source_swimming import SourceSwimming
            cls.image=NativeImage(NATIVE.read_bytes());cls.sources=Sources(DEFAULT_SOURCE);cls.engine=SourceSwimming(cls.image)
        except ImportError as e:raise unittest.SkipTest(str(e))
        cls.cfg=json.loads((RUNTIME/'prototype/native-physics.json').read_text());cls.terrain=json.loads(Path(cls.cfg['terrain']).read_text())
        coll=json.loads(Path(cls.cfg['collision']).read_text());lights=json.loads(Path(cls.cfg['terrainLighting']).read_text())
        cls.meta=json.loads((EXPORT/'water-native-metadata.json').read_text());cls.public=json.loads((EXPORT/'swimming.json').read_text())
        cls.engine.load_world(cls.terrain,coll,lambda n:Path(cls.cfg['sourceFiles'][n]['path']).read_bytes(),{tuple(r['tile']):r['runtimeFlags']for r in lights['tiles']})
        cls.engine.load_water(cls.meta)

    def test_all_wet_fields_and_parent_metadata_reproduce_original_reader(self):
        self.assertEqual(metadata(self.image,self.sources,self.terrain),self.meta)
        self.assertEqual(len(self.meta['tiles']),251)
        self.assertEqual(sum(bool(c['flags']&0x10000)for t in self.meta['tiles']for c in t['chunks']),4098)
        e=self.engine
        for row in self.meta['tiles']:
            at=e.tile_objects[tuple(row['tile'])];self.assertEqual(e.r(at+0x144,'h')[0],row['waterType'])
            chunks=e.r(at+0x80,'Q')[0]
            for j,c in enumerate(row['chunks']):
                self.assertEqual(e.r(chunks+j*0xa8+0x70,'IfIf'),tuple(c[k]for k in ['flags','height','packedColor','factor']))
                self.assertEqual(e.r(chunks+j*0xa8+0x90,'Q')[0],at)

    def test_shallow_deep_queries_and_original_float_support_height(self):
        e=self.engine
        shallow=e.ground(-2324,64,120);state=e.r(e.scratch+0x2500,'Ifi')
        self.assertEqual(state,(3,110,0));self.assertGreater(shallow['height'],f32(110-self.public['swimOffset']))
        deep=e.ground(-2324,68,120);state=e.r(e.scratch+0x2500,'Ifi')
        self.assertEqual(state,(4,110,0));self.assertEqual(deep['height'],f32(110-self.public['swimOffset']))

    def test_original_surface_entry_idle_and_exit_without_fabricated_vertical_rule(self):
        e=self.engine;pos=[-2336,112.48999786376953,48];states=[]
        for i in range(160):
            r=e.actor_tick('test-entry-exit',pos,[2.4,3.2],50,False);pos=r['position'];states.append(r)
            if r['swimming']:break
        self.assertTrue(r['swimming']);self.assertEqual(r['waterState'],4)
        self.assertEqual(pos[1],f32(r['waterHeight']-self.public['swimOffset']))
        original=pos[:]
        for i in range(10):r=e.actor_tick('test-entry-exit',pos,[0,0],50,False);pos=r['position']
        self.assertEqual(pos,original)
        # That entry bank is steep. Verify a genuine moving exit at the one
        # source gentle shallows, rather than accepting a target-only state flip.
        pos=[-2235.5,f32(110-self.public['swimOffset']),12];start=pos[:]
        r=e.actor_tick('test-gentle-exit',pos,[0,0],50,False);self.assertTrue(r['swimming'])
        for i in range(40):
            r=e.actor_tick('test-gentle-exit',pos,[1,0],50,False);pos=r['position']
        self.assertFalse(r['swimming']);self.assertEqual(r['waterState'],3)
        self.assertGreater(pos[0],start[0]+1);self.assertGreater(pos[1],start[1]+.05)
        for i in range(70):
            r=e.actor_tick('test-gentle-exit',pos,[1,0],50,False);pos=r['position']
        self.assertFalse(r['swimming']);self.assertEqual(r['waterState'],0)
        self.assertGreater(pos[0],-2231);self.assertGreater(pos[1],110)
        for i in range(140):
            r=e.actor_tick('test-gentle-exit',pos,[-1,0],50,False);pos=r['position']
        self.assertTrue(r['swimming']);self.assertEqual(pos[1],f32(110-self.public['swimOffset']))

    def test_browser_camera_port_matches_original_function_at_depths_and_boundaries(self):
        rng=random.Random(73);points=[]
        wet=[(t,c,j)for t in self.meta['tiles']for j,c in enumerate(t['chunks'])if c['flags']&0x10000]
        for i in range(120):
            t,c,j=rng.choice(wet);x=t['tile'][0]*64+(j%8)*8+4.2;z=t['tile'][1]*64+(j//8)*8+4.3
            points.append([x,c['height']-[0,1e-4,1,2,40,80,-1,-20][i%8],z])
        (RAW/'camera-test-points.json').write_text(json.dumps(points))
        code="""import{readFile}from'node:fs/promises';const code=(await readFile('tools/preview/source-swimming-camera.js','utf8')).replace(/^import.*?;$/gm,'');
        const{sourceCameraWater:q}=await import('data:text/javascript,'+encodeURIComponent(code));
        const p=JSON.parse(await readFile('analysis/raw/swimming-final-ready-20261111/swimming.json'));
        const points=JSON.parse(await readFile('analysis/raw/swimming-camera-20261111/camera-test-points.json'));
        console.log(JSON.stringify(points.map(v=>q(p.tiles,v))));"""
        actual=json.loads(javascript(code))
        for point,row in zip(points,actual):
            native=self.engine.camera_water(point);self.assertEqual(row['depth'],native['depth']);self.assertEqual(row['color'],native['color'])
            self.assertEqual(row['underwater'],native['depth']>0)
            for a,b in zip(row['attenuation'],native['attenuation']):self.assertAlmostEqual(a,b,places=7)
            self.assertFalse(native['originalEffectHandleSupplied'])

    def test_original_power_alpha_and_underwater_effects_match_export(self):
        from terrain_water import NativeWater
        from PIL import Image
        n=NativeWater(self.image,host_math=True);e=n.e;p=e.alloc(256);e.set('X0',p);n.fragment(0x554540,0x554594)
        data=bytes(e.uc.mem_read(p,256));alpha=Image.open(EXPORT/'power-table.png').getchannel('A').tobytes()
        self.assertEqual(data,alpha);self.assertEqual(hashlib.sha256(data).hexdigest(),self.public['powerTable']['alphaSHA256'])
        self.assertEqual(underwater_effects(self.sources),self.public['effects'])
        for row in self.public['effects']['Terrain_Water']:
            self.assertTrue(row['state']['blendEnabled']);self.assertEqual(row['factorsGL'],[1,770]);self.assertTrue(row['sameAlphaFactors'])

    def test_metadata_is_rejected_before_mutating_the_loaded_world(self):
        broken=json.loads(json.dumps(self.meta));broken['tiles'][0]['chunks'].pop()
        before=self.engine.r(self.engine.tile_objects[tuple(self.meta['tiles'][0]['tile'])]+0x144,'h')
        with self.assertRaisesRegex(ValueError,'incomplete'):self.engine.load_water(broken)
        self.assertEqual(self.engine.r(self.engine.tile_objects[tuple(self.meta['tiles'][0]['tile'])]+0x144,'h'),before)

    def test_actual_three_material_switches_both_color_and_alpha_factors(self):
        javascript("""import assert from'node:assert/strict';import{readFileSync}from'node:fs';
        import*as THREE from'./analysis/raw/showcase-20261110/running-preview/prototype/node_modules/three/build/three.module.js';
        import{createSourceWater}from'./analysis/raw/showcase-20261110/running-preview/prototype/public/source-terrain-water-swimming.js';
        const root='analysis/raw/showcase-20261110/running-preview/game-data/converted/';
        const p=JSON.parse(readFileSync(root+'source-swimming/terrain-water.json'));p.tiles=[{...p.tiles[0],chunks:[p.tiles[0].chunks[0]]}];
        const loader=async()=>{const t=new THREE.DataTexture(new Uint8Array([255,255,255,255]),1,1);t.needsUpdate=true;return t;};
        const water=await createSourceWater(THREE,p,new THREE.Vector3(),loader,async url=>readFileSync(root+url.replace('/assets/',''),'utf8'),{},{});
        const material=water.roots[0].children[0].material;
        water.setCamera({underwater:true,depth:2,color:[.1,.2,.3],attenuation:[.01,.04,.09],factor:.025},[1,1,1]);
        assert.equal(material.blendSrc,THREE.OneFactor);assert.equal(material.blendDst,THREE.SrcAlphaFactor);
        assert.equal(material.blendSrcAlpha,THREE.OneFactor);assert.equal(material.blendDstAlpha,THREE.SrcAlphaFactor);
        assert.equal(water.state().technique,'under_water');
        water.setCamera({underwater:false,depth:-1,color:[1,1,1],attenuation:[1,1,1],factor:.025},[1,1,1]);
        assert.equal(material.blendSrc,THREE.SrcAlphaFactor);assert.equal(material.blendDst,THREE.OneMinusSrcAlphaFactor);assert.equal(water.state().technique,'default');
        """)

    def test_original_swim_tracks_keep_all_existing_player_data(self):
        old=json.loads((RUNTIME/'game-data/converted/models/elf-female.json').read_text());new=json.loads((EXPORT/'elf-female.json').read_text())
        self.assertEqual(player_clips(self.sources,old),new);self.assertEqual(new['clips'][:-2],old['clips'])
        for k,v in old.items():
            if k!='clips':self.assertEqual(new[k],v,k)
        self.assertEqual([(c['name'],c['duration'])for c in new['clips'][-2:]],[('swim_idle',2),('swim_forward',2)])

    def test_real_skeleton_shared_head_and_swim_pose_are_not_overwritten_by_idle_mixer(self):
        javascript("""import assert from'node:assert/strict';import{readFileSync}from'node:fs';
        import*as THREE from'./analysis/raw/showcase-20261110/running-preview/prototype/node_modules/three/build/three.module.js';
        import*as a from'./analysis/raw/showcase-20261110/running-preview/prototype/public/character-animation-swimming.js';
        import{characterAttachment}from'./analysis/raw/showcase-20261110/running-preview/prototype/public/character-animation.js';
        const d=JSON.parse(readFileSync('analysis/raw/swimming-final-ready-20261111/elf-female.json'));
        const root=a.createCharacterFactory(THREE,d,d.materials.map(()=>new THREE.MeshBasicMaterial()))();
        assert(characterAttachment(root,'Bip01_Head',new THREE.Vector3()));
        a.syncCharacterCombat(root,{hp:100,alive:true,swimming:true},1000,.7);
        for(let i=0;i<15;i++)a.updateCharacterAnimation(root,1/30,{moving:false,speed:0},1000+i*1000/30);
        let state=a.characterAnimationState(root);assert.equal(state.phase,'swim_idle');
        const clip=d.clips.find(c=>c.name==='swim_idle'),track=clip.tracks.find(t=>t.type==='quaternion'&&d.rig.nodes[t.node].name==='Bip01_L_UpperArm-node');
        const expected=Array.from(new THREE.QuaternionKeyframeTrack('x.quaternion',track.times,track.values).createInterpolant().evaluate(.5));
        assert(state.bones[track.node].quaternion.toArray().every((v,i)=>Math.abs(v-expected[i])<1e-6));
        a.updateCharacterAnimation(root,.1,{moving:true,speed:4.8},1600);assert.equal(a.characterAnimationState(root).phase,'swim_forward');
        a.syncCharacterCombat(root,{hp:100,alive:true,swimming:false},2000,.7);a.updateCharacterAnimation(root,.1,{moving:false,speed:0},2000);
        assert.equal(a.characterAnimationState(root).phase,'idle');assert(characterAttachment(root,'Bip01_Head',new THREE.Vector3()));
        a.disposeCharacterAnimation(root);""")

    def test_unchanged_old_art_lighting_and_main_save(self):
        assets=RUNTIME/'game-data/converted';before=json.loads((RAW/'before-assets.json').read_text())
        for name,row in before.items():self.assertEqual(hashlib.sha256((assets/name).read_bytes()).hexdigest(),row['sha256'],name)
        public=json.loads((RAW/'before-public.json').read_text())
        for name,row in public.items():
            if name in ('explore-map.js','explore-map.html'):continue
            self.assertEqual(hashlib.sha256((RUNTIME/'prototype/public'/name).read_bytes()).hexdigest(),row['sha256'],name)
        self.assertEqual(hashlib.sha256((ROOT/'runtime/characters.json').read_bytes()).hexdigest(),'8db90023214c32d3e3a6ea88fdbcf3aa144582288a4d28651398f29f296af401')
        self.assertIn('status = "PAUSED"',(Path.home()/'.codex/automations/2/automation.toml').read_text())

    def test_apk_default_underwater_setting_is_true(self):
        import zipfile
        from map_selection_evidence import apk_config,DEFAULT_APK
        apk_config(DEFAULT_APK)
        with zipfile.ZipFile(DEFAULT_APK)as z:d=json.loads(z.read('assets/GameOptions.json'))
        rows=[r for group in d['profiles']['GPU']['defaults']for label,values in group.items()if label=='Default'for r in values if r[0]=='EnableUnderwaterEffect']
        self.assertEqual(rows[0][1],True)


if __name__=='__main__':unittest.main()
