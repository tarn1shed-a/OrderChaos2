"""Actual representative selection, full copy and exactly3 bound-material fixes."""
import copy,hashlib,json,unittest
from selection_scene_candidate import ROOT
from selection_scene_water_floor_group_copy import analyze,uniform_names
RAW=ROOT/'analysis/raw/selection-scene-water-floor-groups-20261115';OUT=RAW/'v2'
OLD=ROOT/'analysis/raw/selection-scene-water-20261115/floor-v4'
@unittest.skipUnless((OUT/'evidence.json').is_file(),'Private original group-copy candidate required')
class GroupCopyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from analyze_native_resources import NativeImage
  cls.image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());cls.e=analyze(cls.image);cls.p=json.loads((OUT/'assets/source-selection-water-floor-groups/overlay.json').read_text());cls.old=json.loads((OLD/'assets/source-selection-water-floor/overlay.json').read_text())
 def test_original_layer_ordinals_resolve_to_texture1_through5(self):
  self.assertEqual(uniform_names(self.image)['names'],['texture1','texture2','texture3','texture4','texture5'])
 def test_all9_original_group_lists_and152_water_descriptors(self):
  self.assertEqual(self.e,json.loads((OUT/'evidence.json').read_text()));self.assertEqual(self.e['wetMembersChecked'],152);self.assertTrue(self.e['representativeWaterUniformsAndColorTableEqual'])
  for t in self.e['tiles']:
   self.assertEqual(sorted(t['groupOrder']),list(range(64)));self.assertEqual(t['groupOffsets'][-1],64)
   self.assertTrue(all(r['source35650cExecuted']for r in t['representatives']))
 def test_full35127c_copies_bindings_not_member_index_fields(self):
  r=self.e['copyEvidence'];self.assertTrue(r['fullOriginal35127cExecuted']);self.assertEqual(r['effectRefcount'],[100,101]);self.assertEqual(r['tableRefcount'],[100,101])
  self.assertEqual(r['copiedSamplerBytes'],r['controlledSamplerBytes']);self.assertTrue(r['memberIndexFieldsUnchanged']);self.assertFalse(r['resourceOrGPUCreated']);self.assertFalse(r['actualAndroidSamplerSlotsObserved'])
 def test_corrected_profile_changes_exactly3_member_material_vectors(self):
  p=copy.deepcopy(self.p)
  for key in('nativeGroupRepresentativeMaterials','priorFloorV4SHA256','sourceMaterialCopyFields','correctedMaterialGroups','groupCopyEvidenceSHA256'):p.pop(key)
  self.assertEqual(len(self.e['fixes']),3)
  for r in self.e['fixes']:
   t=next(t for t in p['tiles']if t['tile']==r['tile']);c=next(c for c in t['chunks']if c['chunk']==r['chunk'])
   self.assertEqual(c['groupedIndices'],r['materialIndices']);self.assertEqual(c['textureLayerMask'],r['materialMacro']);self.assertEqual(r['memberWaterDescriptor'],r['representativeWaterDescriptor'])
   c['groupedIndices']=r['oldMemberIndices'];c['textureLayerMask']=r['oldMemberMacro']
  self.assertEqual(p,self.old)
 def test_old213_selection_payloads_unchanged(self):
  count=0
  entries=[('selection-scene-candidate-20261115','v4','candidate-package-manifest.json'),('selection-scene-inside-20261115','v1','candidate-package-manifest.json'),
   ('selection-scene-stones-20261115','v4','candidate-package-manifest.json'),('selection-scene-flowers-20261115','v2','candidate-package-manifest.json'),
   ('selection-scene-waterfalls-20261115','v2','candidate-package-manifest.json'),('selection-scene-grass-20261115','v1','candidate-package-manifest.json'),
   ('selection-scene-water-20261115','v1','candidate-package-manifest.json'),('selection-scene-water-20261115','surface-v1','surface-package-manifest.json'),('selection-scene-water-20261115','floor-v4','floor-package-manifest.json')]
  for name,version,manifest in entries:
   root=ROOT/'analysis/raw'/name
   for f in json.loads((root/manifest).read_text())['files']:
    self.assertEqual(hashlib.sha256((root/version/f['path']).read_bytes()).hexdigest(),f['sha256']);count+=1
  self.assertEqual(count,213)

if __name__=='__main__':unittest.main(verbosity=2)
