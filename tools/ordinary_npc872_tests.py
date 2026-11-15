"""Original872 source composition and deterministic private export checks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import ordinary_npc872_candidate as candidate

PUBLIC='--public-only'in sys.argv or os.environ.get('PUBLIC_ONLY')=='1'
if'--public-only'in sys.argv:sys.argv.remove('--public-only')
DIR=candidate.AREA/'candidate-v2';ASSETS=DIR/'assets'/candidate.NAMESPACE
PRIVATE=not PUBLIC and(ASSETS/'profile.json').is_file()and candidate.SOURCE.is_file()
sha=lambda raw:hashlib.sha256(raw).hexdigest()


class PublicImport(unittest.TestCase):
    def test_private_engines_stay_lazy(self):
        p=subprocess.run([sys.executable,'-S','-c',"import sys;sys.path.insert(0,'tools');import ordinary_npc872_candidate;assert 'capstone' not in sys.modules;assert 'unicorn' not in sys.modules"],cwd=candidate.ROOT,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)


@unittest.skipUnless(PRIVATE,'Original private872 source/library/assets unavailable or public-only')
class Original872(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=json.loads((ASSETS/'profile.json').read_text());cls.d=json.loads((ASSETS/'npc872.json').read_text());cls.c=json.loads((DIR/'composition-private.json').read_text())
        cls.source=json.loads(candidate.SOURCE.read_text());cls.review=json.loads(candidate.REVIEW.read_text())

    def test_frozen_original_inputs_and_all_exported_files(self):
        for name,digest in candidate.PINS.items():self.assertEqual(sha((candidate.ROOT/name).read_bytes()),digest)
        for name,r in json.loads((DIR/'package-files.json').read_text())['files'].items():
            p=DIR/name;self.assertTrue(p.resolve().is_relative_to(DIR.resolve()));self.assertEqual((p.stat().st_size,sha(p.read_bytes())),(r['bytes'],r['sha256']))

    def test_original872_default_parts_no_player_clothes(self):
        p=self.p;self.assertEqual((p['entry'],p['defaultDisplay'],p['sourceModelId'],p['sourceExtraId']),(872,852,32,720))
        self.assertEqual(p['sourceSlots'][:3],[1,1,0]);self.assertEqual([r['itemKey']for r in self.c['garments']],[100009,100012])
        self.assertEqual(p['name'],'卢西安哪');self.assertFalse(self.c['playerOutfitCopied'])
        paths={m['sourceModel']for m in self.d['materials']}
        self.assertEqual(paths,{candidate.BASE,*[r['path']for r in self.c['nativeDefault']['requests']if r.get('path')]})
        self.assertFalse(any('consortium'in p or'underwear'in p for p in paths))

    def test_base_geometry_nodes_rig_match_exact_native_reuse(self):
        r=next(x for x in self.review['models']if x['source']==candidate.BASE);original=json.loads((candidate.REVIEW.parent/r['parsed']['path']).read_text())
        self.assertEqual(self.d['rig']['nodes'],original['rig']['nodes']);self.assertEqual(self.d['rig']['skins'][:12],original['rig']['skins'])
        for a,b in zip(self.d['meshes'][:12],original['meshes']):
            for key in['name','positions','normals','uvs','indices']:self.assertEqual(a[key],b[key])
        for f in self.c['baseCPUReuse']['files'].values():self.assertEqual(sha((candidate.ROOT/f['path']).read_bytes()),f['sha256'])

    def test_each_selected_piece_retains_original_float_skin(self):
        self.assertEqual((len(self.d['meshes']),len(self.d['rig']['nodes']),len(self.d['rig']['skins'])),(16,116,16))
        for skin in self.d['rig']['skins']:
            self.assertFalse(skin['verification']['normalizationApplied']);self.assertTrue(skin['verification']['sourceFloatWeightsRetainedAfterStrictValidation'])
        for request in self.c['nativeDefault']['requests']:
            if not request.get('path'):continue
            record=next(x for x in self.review['models']if x['source']==request['path']);piece=json.loads((candidate.REVIEW.parent/record['parsed']['path']).read_text())
            match=[s for s in self.d['rig']['skins']if s['name']==piece['rig']['skins'][0]['name']]
            self.assertEqual(len(match),1)
            for key in['skinWeights','skinIndices','inverseBindMatrices','bindShapeMatrix']:self.assertEqual(match[0][key],piece['rig']['skins'][0][key])

    def test_masks_are_original_cpu_results_not_hand_hiding(self):
        from analyze_native_resources import NativeImage
        from tutorial_npc_catalog_probe import CatalogVisibilityProbe
        image=NativeImage((candidate.ROOT/'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so').read_bytes());p=CatalogVisibilityProbe(image)
        names=[x['name'].removesuffix('-mesh')for x in self.d['meshes'][:12]];self.assertEqual(p.bind_original_parts(names),{int(k):v for k,v in self.c['mapping'].items()})
        for r in self.c['nativeDefault']['requests']:
            if r['slot']<7:p.feature_request(r['slot'],'feature:'+str(r['slot'])if r.get('path')else None)
        for r in self.c['garments']:
            self.assertEqual(str(p.apply_item_mask(r['sourceModel']['Flags0'],r['sourceModel']['Flags1'])),r['originalRemappedMask'])
        self.assertEqual(p.visibility(),self.c['visibleNames']);self.assertEqual(self.p['visibleMeshIndices'],[0,1,2,4,6,7,10,12,13,14,15])
        self.assertTrue(self.c['sceneHandlesAreHostInterfaces'])

    def test_source_materials_are_complete_no_scalar_fallback(self):
        from character_materials import SCALARS,SHADER_SHA256
        self.assertEqual((len(self.p['materials']),self.p['materialSlotCount']),(5,5))
        for m in self.p['materials']:
            self.assertEqual(set(m['scalars']),set(SCALARS));self.assertNotIn('scalarDefaultInheritance',m)
            self.assertEqual(m['sourceEffectProfiles']['profiles'][0]['state'],m['sourceEffectProfiles']['profiles'][1]['state'])
            self.assertFalse(m['sourceEffectProfiles']['profiles'][0]['state']['blendEnabled'])
        for name,digest in SHADER_SHA256.items():self.assertEqual(sha((DIR/self.p['shaders'][name]['url'].lstrip('/')).read_bytes()),digest)

    def test_only_original_diffuse_override_changes(self):
        override,=self.c['overrides'];self.assertEqual(override['path'],'texture/oc2_human_f_npc_villager_chest_d.tga')
        self.assertFalse(override['compiledReflectionObserved']);self.assertFalse(override['originalRequest']['textureSet'])
        chest=next(x for x in self.d['materials']if x['sourceModel'].endswith('oc2_human_f_npc_villager_chest.bdae'))
        self.assertEqual(chest['sourceOriginalSamplerPaths']['texture'],'texture/oc2_elf_f_npc_villager_chest_d.tga')
        changed=[k for k,v in chest['samplers'].items()if v!=chest['sourceOriginalSamplerPaths'][k]]
        self.assertEqual(changed,['texture']);self.assertEqual(chest['samplers']['texture'],override['path'])

    def test_exact_source_images_decode_to_matching_png_and_rgba(self):
        from PIL import Image
        self.assertEqual(len(self.p['textures']),23)
        for r in self.p['textures'].values():
            png=DIR/r['url'].lstrip('/');rgba=(DIR/r['rgbaURL'].lstrip('/')).read_bytes()
            self.assertEqual(sha(png.read_bytes()),r['pngSHA256']);self.assertEqual(sha(rgba),r['rgbaSHA256'])
            with Image.open(png)as im:self.assertEqual(list(im.size),r['size']);self.assertEqual(im.convert('RGBA').tobytes(),rgba)

    def test_original_idle_has_no_extra_motion_policy(self):
        c,=self.d['clips'];self.assertEqual((c['name'],len(c['tracks']),c['duration']),('idle',131,4.266666666666667))
        self.assertTrue(all(type(t['node'])is int and 0<=t['node']<116 for t in c['tracks']))
        self.assertEqual(self.c['nativeDefault']['idle']['request'],'idle')
        self.assertEqual(self.d['visibleMeshIndices'],self.p['visibleMeshIndices'])

    def test_assets_do_not_supply_world_or_task_identity(self):
        self.assertTrue(self.p['sourceAssetOnly']);self.assertFalse(self.p['browserVerified']);self.assertFalse(self.p['originalGPUOrLiveCacheObserved'])
        for key in['actorGUID','questState','worldPlacement']:self.assertIsNone(self.p[key])
        for key in['actualGUID','questState','worldPlacement']:self.assertIsNone(self.d['sourceNPC872'][key])

    def test_reexport_is_exact_not_a_new_appearance(self):
        with tempfile.TemporaryDirectory(prefix='replay-check-',dir=candidate.AREA)as tmp:
            out=Path(tmp)/'candidate';candidate.build(out)
            self.assertEqual(json.loads((out/'package-files.json').read_text()),json.loads((DIR/'package-files.json').read_text()))


if __name__=='__main__':unittest.main(verbosity=2)
