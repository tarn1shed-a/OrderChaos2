"""Source geometry, material, clock and map7 DAT checks for one append."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from selection_scene_inside_candidate import ROOT,MODEL,MODEL_SHA,OBJECT_ID,FORMAT
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from bdae_convert import BDAE
from scene_collision import apply_scene_transforms
from scene_sampling import material_samplers
from scene_lightmap_binding import material_request_slots
from scene_lightmaps import source_names,read_records,object_records
from tutorial_inside_models import properties

BASE=ROOT/'analysis/raw/selection-scene-candidate-20261115/v4'
CANDIDATE=ROOT/'analysis/raw/selection-scene-inside-20261115/v1'


@unittest.skipUnless((CANDIDATE/'audit.json').is_file() and(Path(DEFAULT_SOURCE)/'res_scene.bin').is_file(),
                    'Original scene model and independent material append stay private')
class SelectionInsideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Sources(DEFAULT_SOURCE)
        cls.overlay=json.loads((CANDIDATE/'assets/source-selection-inside/overlay.json').read_text())
        cls.data=json.loads((CANDIDATE/'assets/source-selection-inside/model.json').read_text())
        cls.audit=json.loads((CANDIDATE/'audit.json').read_text())

    def test_original_mesh_indices_nodes_and_all_secondary_uvs_are_retained(self):
        from tutorial_inside_models import additional_uvs
        raw=self.source.read(MODEL);self.assertEqual(hashlib.sha256(raw).hexdigest(),MODEL_SHA)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'source.bdae';p.write_bytes(raw);reader=BDAE(p)
            original=apply_scene_transforms(reader,reader.parse());additional_uvs(reader,original)
            self.assertEqual(original['materials'],self.data['materials'])
            for a,b in zip(original['meshes'],self.data['meshes']):
                for key in ('positions','normals','uvs','sourceUV1','sourceUV2','sourceUV3','indices','groups','sourceNodeTransform'):
                    self.assertEqual(a[key],b[key])
            self.assertEqual((original['meshes'][0]['vertexCount'],original['meshes'][0]['triangleCount']),(11817,7900))

    def test_original_samplers_values_and_typed_copies_have_no_missing_replacement(self):
        raw=self.source.read(MODEL)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'source.bdae';p.write_bytes(raw);reader=BDAE(p);source=material_samplers(reader);values,_=properties(reader)
            for r,s,v in zip(self.data['selectionInsideMaterials']['materials'],source,values):
                self.assertEqual(r['samplers'],s['samplers']);self.assertEqual(r['effect'],s['effectPath']);self.assertEqual(r['values'],v['values'])
                self.assertEqual(r['missingSamplers'],[])
                for name,value in r['values'].items():self.assertEqual(r['nativePropertyCopy'][name]['value'],value)
                for key,sampler in r['samplers'].items():
                    if key!='lightMap':self.assertEqual(len(self.source.candidates(sampler['texture'])),1)
        self.assertEqual([r['index']for r in self.data['selectionInsideMaterials']['materials']if r['values']],[0,1,3])

    def test_one_original_selection_dat_binding_is_shared_by_actual_part_loop(self):
        from analyze_native_resources import NativeImage
        from native_part_lightmaps import PartLightmapProbe
        from bres_world_bounds_evidence import inner_bres
        image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());probe=PartLightmapProbe(image)
        refs=probe.references(inner_bres(self.source.read(MODEL)));order=self.overlay['entry']['partToMaterial']
        self.assertEqual([r['localIndex']for r in refs],order)
        row=self.overlay['bindings'][0];records=material_request_slots(object_records(read_records(self.source.read(row['recordPath'])),OBJECT_ID))
        self.assertEqual(len(records),1)
        self.assertEqual(row['bindings'][0]['atlas'],source_names('selection',-41,-2,atlas=records[0]['atlasIndex'])['texture'])
        result=probe.bindings(order,row['bindings'])
        self.assertEqual(len(result['calls']),21);self.assertEqual({r['binding']for r in result['calls']},{0})

    def test_type2_source_trs_and_default_admission_do_not_become_inside_visibility(self):
        from terrain_convert import read_instances
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'-041_-002.itm';p.write_bytes(self.source.read(self.audit['sourceITM']))
            row,=[r for r in read_instances(p)if r['id']==OBJECT_ID]
        self.assertEqual(row,self.overlay['entry']['instances'][0]);self.assertEqual(row['sourceType'],2)
        self.assertEqual(self.audit['admission'],'admittedBeforeTypeFactory')
        self.assertFalse(self.overlay['type15VisibilityApplied']);self.assertFalse(self.overlay['companionModelAdded'])
        self.assertNotIn('sourceInsideModel',self.data)

    def test_original_clock_computation_and_source_alpha_culling_are_explicit(self):
        self.assertEqual(self.audit['originalClockSamples'],[{'ticks':0,'seconds':0.},{'ticks':1,'seconds':.0010000000474974513},{'ticks':1000,'seconds':1.}])
        self.assertEqual([r['index']for r in self.data['sceneAlpha']['materials']if r['rule']=='discard-less-equal'],[0,1,3])
        self.assertTrue(all(not r['cullEnabled']for r in self.data['sceneCulling']['materials']))
        self.assertTrue(self.overlay['clock']['hostOrigin'])

    def test_frozen_base_every_payload_is_unchanged_and_counts_are_only_a_proposal(self):
        package=json.loads((ROOT/'analysis/raw/selection-scene-candidate-20261115/candidate-package-manifest.json').read_text())
        for row in package['files']:
            raw=(BASE/row['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        self.assertEqual(self.overlay['proposedCounts'],{'models':38,'staticInstances':140,'remainingStaticInstances':11})
        self.assertFalse(self.overlay['lightingChanged']);self.assertFalse(self.overlay['savesChanged'])
        self.assertEqual(self.overlay['format'],FORMAT)


if __name__=='__main__':unittest.main(verbosity=2)
