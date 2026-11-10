"""Original terrain null-provider branch and source-only preview regression."""
import hashlib
import json
import struct
import unittest
from pathlib import Path
from terrain_missing_textures import ROOT,MISSING_PATH,fallback_image,texture_image

EXPORT=ROOT/'analysis/raw/map-missing-terrain-ready-20261111'
NATIVE=ROOT/'analysis/raw/beff-native/library.so'


class PublicTests(unittest.TestCase):
    def test_non_terrain_miss_never_invokes_terrain_fallback(self):
        class Missing:
            def candidates(self,name):return []
            def read(self,name):raise ValueError('provider miss')
        def forbidden(name):self.fail('Model/lightmap fallback was invoked')
        with self.assertRaisesRegex(ValueError,'provider miss'):texture_image(Missing(),MISSING_PATH,forbidden)

    def test_existing_or_ambiguous_source_is_not_overridden(self):
        class Existing:
            def candidates(self,name):return ['ambiguous-a','ambiguous-b']
            def read(self,name):raise ValueError('ambiguous or corrupt source')
        def forbidden(name):self.fail('Source failure was replaced')
        with self.assertRaisesRegex(ValueError,'ambiguous'):texture_image(Existing(),MISSING_PATH,forbidden,terrain_layer=True)

    def test_unrelated_missing_path_is_rejected_without_guessing_an_alias(self):
        for name in ('texture/tiles/textures/default.tga','model/missing.tga','world/tutorial/lightmaps/missing.tga'):
            with self.assertRaisesRegex(ValueError,'no verified'):fallback_image(name,{})

    def test_connector_cannot_touch_main_project_or_backups(self):
        from connect_missing_terrain import connect
        for path in (ROOT,ROOT/'backups'):
            with self.assertRaisesRegex(ValueError,'ignored'):connect(path,path)


@unittest.skipUnless(NATIVE.is_file()and(EXPORT/'geometry-audit.json').is_file(),'Originals and full converted evidence stay local')
class OriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from analyze_native_resources import NativeImage
            from terrain_missing_textures import recover_native_fallback
            from map_loading_evidence import Sources
            from resource_packs import DEFAULT_SOURCE
            cls.image=NativeImage(NATIVE.read_bytes());cls.proof=recover_native_fallback(cls.image)
        except ImportError as e:raise unittest.SkipTest(str(e))
        cls.sources=Sources(DEFAULT_SOURCE)
        cls.audit=json.loads((EXPORT/'geometry-audit.json').read_text())
        cls.terrain=json.loads((EXPORT/'base/maps/missing-terrain/tutorial-window.json').read_text())
        cls.mats=json.loads((EXPORT/'verified/terrain-materials.json').read_text())
        cls.lights=json.loads((EXPORT/'verified/terrain-lighting.json').read_text())
        cls.old=json.loads((ROOT/'analysis/raw/map-expanded-ready-20261111/verified/terrain-materials.json').read_text())

    def test_original_initializer_arguments_descriptor_and_pixel_fill(self):
        self.assertEqual(self.proof['pixelRGBA'],[255,0,128,255])
        self.assertEqual(self.proof['colorTableRGBA'][1],[55,215,55,255])
        self.assertEqual(self.proof['descriptor'],[1,22,0,0,1,1,1,0])
        self.assertEqual(self.proof['nativeName'],'glitch.texture-not-found-2d')
        self.assertFalse(self.proof['GPUCreationExecuted']);self.assertFalse(self.proof['originalTextureRecovered'])
        image,proof=fallback_image(MISSING_PATH,self.proof)
        self.assertEqual(image.size,(1,1));self.assertEqual(list(image.tobytes()),[255,0,128,255])
        self.assertEqual(proof['requestedPath'],MISSING_PATH)
        self.assertEqual(self.proof,self.audit['nativeMissingTextureFallback'])

    def test_all_251_source_samples_preserve_actual_height_normal_color(self):
        self.assertEqual(len(self.terrain['sourceTiles']),251)
        for tile in self.terrain['sourceTiles']:
            x,z=tile['tile'];raw=self.sources.read(f'world/tutorial/terrain/{x:04d}_{z:04d}.trn')
            version,xx,zz=struct.unpack_from('<3i',raw,4);self.assertEqual([xx,zz],[x,z]);at=24+64*(16 if version==9 else 24)
            for key,fmt,offset in [('heights','4225h',0),('colors','4225H',8450),('normals','12675b',16900)]:
                self.assertEqual(tile[key],list(struct.unpack_from('<'+fmt,raw,at+offset)))

    def test_70_literal_references_masks_and_effective_layers(self):
        from terrain_materials import tile_materials,mask_channels,effective_indices
        old={tuple(t['tile'])for t in self.old['tiles']};extra=[t for t in self.mats['tiles']if tuple(t['tile'])not in old]
        self.assertEqual(len(extra),70);counts=[0,0,0]
        self.assertFalse(self.sources.candidates(MISSING_PATH))
        self.assertTrue(self.sources.candidates('texture/tiles/textures/default.tga'))
        for tile in extra:
            x,z=tile['tile'];stem=f'{x:04d}_{z:04d}'
            raw=self.sources.read(f'world/tutorial/terrain/{stem}.trn');p=tile_materials(raw)
            self.assertEqual([t['sourcePath']for t in tile['textures']],p['textures'])
            channels=[f'world/tutorial/layers/{stem}_{i}.msk'for i in range(4)]
            mask,classes=mask_channels([self.sources.read(n)if self.sources.candidates(n)else None for n in channels])
            for a,b,c in zip(p['chunks'],tile['chunks'],classes):
                self.assertEqual(a['indices'],b['indices']);self.assertEqual(c,b['maskClasses'])
                self.assertEqual(effective_indices(a['indices'],c),b['effectiveIndices'])
                if b['sourceWaterPending']:counts[2]+=1
                else:counts[int(any(p['textures'][i]==MISSING_PATH for i in b['effectiveIndices']if i>=0))]+=1
        self.assertEqual(counts,[302,525,3653])
        self.assertEqual(self.audit['pendingWaterChunks'],5747)

    def test_lighting_configuration_old_bindings_and_assets_stay_unchanged(self):
        old_tiles={tuple(t['tile']):t for t in self.old['tiles']}
        for t in self.mats['tiles']:
            if tuple(t['tile'])in old_tiles:
                old=old_tiles[tuple(t['tile'])]
                self.assertEqual(t['chunks'],old['chunks'])
                self.assertEqual([r['sourcePath']for r in t['textures']],[r['sourcePath']for r in old['textures']])
        for name in ('terrain-lighting.json','baked-lighting.json'):
            a=json.loads((EXPORT/'verified'/name).read_text());b=json.loads((ROOT/'analysis/raw/map-expanded-ready-20261111/verified'/name).read_text())
            self.assertEqual(a['configuration'],b['configuration'])
            if 'zones'in b:self.assertEqual(a['zones'],b['zones'])
        assets=ROOT/'analysis/raw/showcase-20261110/running-preview/game-data/converted'
        for name,row in json.loads((ROOT/'analysis/raw/terrain-missing-20261111/before-assets.json').read_text()).items():
            self.assertEqual(hashlib.sha256((assets/name).read_bytes()).hexdigest(),row['sha256'],name)

    def test_native_251_tile_scene_and_new_dry_ground_walk(self):
        from source_physics import SourcePhysics
        e=SourcePhysics(self.image);profile=json.loads((EXPORT/'physics/collision.json').read_text())
        flags={tuple(t['tile']):t['runtimeFlags']for t in self.lights['tiles']}
        info=e.load_world(self.terrain,profile,self.sources.read,flags)
        self.assertEqual([info[k]for k in ('tiles','instances','shapes')],[251,1040,2702])
        self.assertLess(info['arenaBytes'],0x4000000)
        old={tuple(t['tile'])for t in self.old['tiles']};found=set()
        for tile in self.mats['tiles']:
            if tuple(tile['tile'])in old:continue
            for c in tile['chunks']:
                if c['sourceWaterPending']:continue
                kind='fallback'if any(tile['textures'][i]['sourcePath']==MISSING_PATH for i in c['effectiveIndices']if i>=0)else'real'
                if kind in found:continue
                x=tile['tile'][0]*64+c['chunk'][0]*8+4;z=tile['tile'][1]*64+c['chunk'][1]*8+4
                if not e.available(x,z):continue
                y=e.sample(x,z)['height'];frames=[e.actor_tick('new-'+kind,[x,y,z],[.5,0],50,False)for _ in range(8)]
                self.assertTrue(all(f['grounded']for f in frames));self.assertGreater(frames[-1]['position'][0],x)
                found.add(kind)
        self.assertEqual(found,{'fallback','real'})


if __name__=='__main__':unittest.main()
