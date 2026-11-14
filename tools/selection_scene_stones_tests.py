"""Original U2T source, UV and selection-DAT tests; no GPU or gameplay writes."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from bdae_convert import BDAE
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from scene_collision import apply_scene_transforms
from scene_sampling import material_samplers,effect_profile_samplers
from scene_wind_identity import uv2_streams
from scene_render_state import effect_render_state
from selection_scene_stones_candidate import ROOT,MODELS,EFFECT,EFFECT_SHA,EFFECT_BRES_SHA,ITM
from selection_scene_candidate import binding_rows
from terrain_convert import read_instances

CANDIDATE=ROOT/'analysis/raw/selection-scene-stones-20261115/v4'


@unittest.skipUnless((CANDIDATE/'audit.json').is_file()and(Path(DEFAULT_SOURCE)/'res_scene.bin').is_file(),
                    'Original stone archives and candidate remain private')
class SelectionStonesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Sources(DEFAULT_SOURCE)
        cls.overlay=json.loads((CANDIDATE/'assets/source-selection-stones/overlay.json').read_text())
        cls.audit=json.loads((CANDIDATE/'audit.json').read_text())

    def model(self,e):return json.loads((CANDIDATE/e['url'].lstrip('/')).read_text())

    def test_raw_mesh_nodes_indices_and_different_second_uv_are_retained(self):
        for e in self.overlay['models']:
            raw=self.source.read(e['model']);self.assertEqual(hashlib.sha256(raw).hexdigest(),MODELS[e['model']]['sha256'])
            with tempfile.TemporaryDirectory()as td:
                p=Path(td)/'s.bdae';p.write_bytes(raw);r=BDAE(p);data=apply_scene_transforms(r,r.parse());uv2_streams(r,data)
            exported=self.model(e);self.assertEqual(data['materials'],exported['materials'])
            for mesh,written in zip(data['meshes'],exported['meshes']):
                for key in('positions','normals','uvs','sourceUV1','sourceUV2','indices','groups','sourceNodeTransform'):
                    self.assertEqual(mesh[key],written[key])
                self.assertNotEqual(mesh['sourceUV2'],mesh['uvs'])
                self.assertEqual(written['selectionStoneUV']['sourceSemantic'],6)
                self.assertEqual(written['selectionStoneUV']['runtimeSemantic'],3)

    def test_three_actual_samplers_and_original_rgba_product_have_no_blend_variant(self):
        raw=self.source.read(EFFECT);self.assertEqual(hashlib.sha256(raw).hexdigest(),EFFECT_SHA)
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/'e.bdae';p.write_bytes(raw);r=BDAE(p);self.assertEqual(hashlib.sha256(r.b).hexdigest(),EFFECT_BRES_SHA)
            state=effect_render_state(r);samplers=effect_profile_samplers(r)
            for p in state['profiles']:
                self.assertEqual(p['fragmentShader']['defines'],{'LIGHTMAP':'','TWO_TEXTURE':''})
                self.assertFalse(p['state']['blendEnabled']);self.assertFalse(p['state']['cullEnabled'])
            for p in samplers['profiles']:
                self.assertEqual(set(p['samplers']),{'texture','lightMap','texture2'})
                for s in p['samplers'].values():self.assertEqual(s['request'],{'addressU':0,'addressV':0,'minFilter':None,'magFilter':None})
            for e in self.overlay['models']:
                p=Path(td)/'s.bdae';p.write_bytes(self.source.read(e['model']));records=material_samplers(BDAE(p))
                for source,written in zip(records,self.model(e)['selectionStones']['materials']):
                    self.assertEqual(source['samplers'],written['samplers'])
                    self.assertEqual(written['operation'],'component-wise-RGBA-multiply-before-lightMap')
        original=self.source.read('ut_common_fs.glsl').decode().replace('\r\n','\n')
        self.assertTrue('#else\n\tcolor *= color2;\n #endif'in original,'Original TWO_TEXTURE default multiply branch changed')
        self.assertLess(original.index('color *= color2;'),original.index('lowp vec3 colorLightMap'))

    def test_all_six_original_type2_placements_and_one_record_per_object(self):
        with tempfile.TemporaryDirectory()as td:
            p=Path(td)/Path(ITM).name;p.write_bytes(self.source.read(ITM));rows=read_instances(p)
        for e in self.overlay['models']:
            selected=[r for r in rows if r['id']in MODELS[e['model']]['ids']]
            self.assertEqual(selected,e['instances'])
            for item in selected:
                record,bindings=binding_rows(self.source,item)
                written,=[b for b in self.overlay['bindings']if b['objectId']==item['id']]
                self.assertEqual(written['recordPath'],record);self.assertEqual(written['bindings'],bindings)
                self.assertEqual(len(bindings),1);self.assertTrue(bindings[0]['atlas'].startswith('texture/lightmap/selection/'))
                self.assertEqual(item['sourceType'],2)

    def test_actual_part_binding_calls_keep_all_nine_parts_and_use_each_object_own_record(self):
        from analyze_native_resources import NativeImage
        from native_part_lightmaps import PartLightmapProbe
        from bres_world_bounds_evidence import inner_bres
        image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());probe=PartLightmapProbe(image);count=0
        for e in self.overlay['models']:
            refs=probe.references(inner_bres(self.source.read(e['model'])))
            self.assertEqual([r['localIndex']for r in refs],e['partToMaterial'])
            for b in self.overlay['bindings']:
                if b['model']!=e['model']:continue
                actual=probe.bindings(e['partToMaterial'],b['bindings']);count+=len(actual['calls'])
                self.assertEqual({c['binding']for c in actual['calls']},{0})
                for c in actual['calls']:self.assertEqual(c['uvTransform'],b['bindings'][0]['uvTransform'])
        self.assertEqual(count,9)

    def test_base_and_independent_inside_payloads_remain_unchanged(self):
        for folder,version in [('selection-scene-candidate-20261115','v4'),('selection-scene-inside-20261115','v1')]:
            root=ROOT/'analysis/raw'/folder;manifest=json.loads((root/'candidate-package-manifest.json').read_text())
            for r in manifest['files']:
                raw=(root/version/r['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),r['sha256'])
        self.assertFalse(self.overlay['lightsChanged']);self.assertFalse(self.overlay['savesChanged']);self.assertFalse(self.overlay['geometryChanged'])
        self.assertEqual(self.overlay['proposedCounts']['withIndependentInsideAppend'],{'models':40,'staticInstances':146,'remaining':5})


if __name__=='__main__':unittest.main(verbosity=2)
