"""Source regression checks for the isolated map7 background.

Private source/candidate data are optional; absence is an explicit skip. These
checks do not render an Android frame or mutate any character/server state.
"""
import collections
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from selection_scene_candidate import ROOT, FORMAT, binding_rows, settings, splash_configs
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from terrain_convert import read_instances
from tutorial_map_geometry import raw_tile
from terrain_materials import tile_materials, mask_channels, effective_indices

DEFAULT_CANDIDATE=ROOT/'analysis/raw/selection-scene-candidate-20261115/v4'


class SelectionSceneSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(os.environ.get('OC2_SELECTION_CANDIDATE',DEFAULT_CANDIDATE))
        manifest=cls.path/'assets/source-selection-scene/manifest.json'
        if not manifest.exists() or not Path(DEFAULT_SOURCE).is_dir():
            raise unittest.SkipTest('Private original map7 source/candidate is not included in Git')
        cls.manifest=json.loads(manifest.read_text())
        cls.audit=json.loads((cls.path/'audit.json').read_text())
        cls.source=Sources(DEFAULT_SOURCE)
        cls.assets=cls.path/'assets/source-selection-scene'
        cls.placements=[]
        with tempfile.TemporaryDirectory()as td:
            for name in sorted(n for n in cls.source.lookup if n.startswith('world/selection/items/')and n.endswith('.itm')):
                p=Path(td)/Path(name).name;p.write_bytes(cls.source.read(name));cls.placements+=read_instances(p)

    def test_complete_population_is_accounted_without_filling_gaps(self):
        p=self.manifest
        self.assertEqual((p['format'],p['world'],p['mapId']),(FORMAT,'selection',7))
        static={r['id']:r for r in self.placements if r['sourceType']==2}
        shown=[r for m in p['models']for r in m['instances']]
        omitted=[i for g in p['gaps']for i in g.get('ids',[g['id']]if'id'in g else[])]
        self.assertEqual((len(p['models']),len(shown),len(omitted),len(static)),(37,139,12,151))
        self.assertEqual(collections.Counter([r['id']for r in shown]+omitted),collections.Counter(static.keys()))
        for row in shown:self.assertEqual(row,static[row['id']])
        self.assertFalse(p['conditionalWindow']['originalLiveCenterProven'])
        self.assertFalse(p['inventedLights']);self.assertFalse(p['inventedGeometry']);self.assertFalse(p['savesChanged'])

    def test_only_selection_dat_and_original_part_ordinals_are_bound(self):
        by={r['id']:r for r in self.placements}
        for r in self.manifest['bindings']:
            path,expected=binding_rows(self.source,by[r['objectId']])
            self.assertEqual(r['recordPath'],path)
            self.assertEqual(r['bindings'],expected)
            self.assertTrue(all(b['atlas'].startswith('texture/lightmap/selection/')for b in expected))
        missing,= [g for g in self.manifest['gaps']if g.get('id')==1014080736]
        path,records=binding_rows(self.source,by[1014080736])
        self.assertEqual(missing['record'],path);self.assertEqual(records,[])

    def test_original_trn_samples_mask_channels_and_water_flags_preserved(self):
        g=json.loads((self.assets/'terrain.json').read_text())
        m=json.loads((self.assets/'terrain-materials.json').read_text())
        self.assertEqual(len(g['sourceTiles']),25)
        materials={tuple(r['tile']):r for r in m['tiles']}
        for tile in g['sourceTiles']:
            x,z=tile['tile'];stem=f'{x:04d}_{z:04d}'
            raw=self.source.read(f'world/selection/terrain/{stem}.trn')
            self.assertEqual(tile,raw_tile(raw,x,z))
            original=tile_materials(raw);actual=materials[(x,z)]
            self.assertEqual(original['textures'],[r['sourcePath']for r in actual['textures']])
            names=[f'world/selection/layers/{stem}_{k}.msk'for k in range(4)]
            channels=[self.source.read(n)if self.source.candidates(n)else None for n in names]
            _,classes=mask_channels(channels)
            for a,b,cl in zip(original['chunks'],actual['chunks'],classes):
                self.assertEqual(a['indices'],b['indices']);self.assertEqual(a['flags'],b['flags'])
                self.assertEqual(b['effectiveIndices'],effective_indices(a['indices'],cl))
        self.assertEqual(len(self.manifest['pendingWaterChunks']),344)

    def test_original_models_geometry_and_source_node_matrix(self):
        from bdae_convert import BDAE
        from scene_collision import apply_scene_transforms
        from bres_world_bounds_evidence import inner_bres
        from native_part_lightmaps import PartLightmapProbe
        from analyze_native_resources import NativeImage
        probe=PartLightmapProbe(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
        with tempfile.TemporaryDirectory()as td:
            for e in self.manifest['models']:
                raw=self.source.read(e['model']);self.assertEqual(e['sourceSHA256'],hashlib.sha256(raw).hexdigest())
                p=Path(td)/'source.bdae';p.write_bytes(raw);reader=BDAE(p);original=apply_scene_transforms(reader,reader.parse())
                data=json.loads((self.path/e['url'].lstrip('/')).read_text())
                self.assertEqual(original['materials'],data['materials']);self.assertEqual(original['sceneNodes'],data['sceneNodes'])
                for a,b in zip(original['meshes'],data['meshes']):
                    for key in ('positions','normals','uvs','sourceUV1','indices','groups','sourceNodeTransform'):
                        self.assertEqual(a[key],b[key])
                self.assertEqual(e['partToMaterial'],[r['localIndex']for r in probe.references(inner_bres(raw))])

    def test_source_profile_clamp_and_effect_rejections_are_recorded(self):
        from analyze_native_resources import NativeImage
        im=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())
        actual,_=settings(im)
        self.assertEqual(actual,self.manifest['originalSettings']);self.assertEqual(actual['DeviceLayer'],4)
        self.assertEqual(splash_configs(self.source),self.manifest['originalSplashConfigs'])
        counts=collections.Counter((r['sourceType'],r['admission'])for r in self.audit['admissions'])
        self.assertEqual(counts,{(2,'admittedBeforeTypeFactory'):151,(8,'admittedBeforeTypeFactory'):10,(8,'detailOrLevelRejected'):2})
        self.assertTrue(self.manifest['environment']['skyNotRestored'])


if __name__=='__main__':unittest.main(verbosity=2)
