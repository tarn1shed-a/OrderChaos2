"""Original map7 final layer consumers, wet CPU geometry and frozen payloads."""
import hashlib,json,unittest
from selection_scene_candidate import ROOT
from selection_scene_water_floor_native import SelectionWaterFloorNative
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

RAW=ROOT/'analysis/raw/selection-scene-water-20261115';BASE=ROOT/'analysis/raw/selection-scene-candidate-20261115/v4';OUT=RAW/'floor-v4'
@unittest.skipUnless((OUT/'audit.json').is_file(),'Private floor source candidate required')
class FloorTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from analyze_native_resources import NativeImage
  cls.image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());cls.n=SelectionWaterFloorNative(cls.image)
  cls.p=json.loads((OUT/'assets/source-selection-water-floor/overlay.json').read_text());cls.audit=json.loads((OUT/'audit.json').read_text())
 def test_original_all9_final_group_consumers_and152_wet_descriptors(self):
  s=Sources(DEFAULT_SOURCE);total=0
  for tile in self.p['tiles']:
   self.n.read(s.read(tile['source']));proof=self.n.layers(s,tile['tile']);saved=next(r for r in self.audit['nativeLayerGroups']if r['tile']==tile['tile'])
   self.assertEqual(proof,{k:v for k,v in saved.items()if k!='tile'});self.assertTrue(proof['native355f28Executed'])
   for c in tile['chunks']:
    j=c['chunk'][1]*8+c['chunk'][0];self.assertEqual({k:c[k]for k in proof['rows'][j]},proof['rows'][j])
    self.assertEqual({k:c[k]for k in self.n.descriptor(j)},self.n.descriptor(j));total+=1
  self.assertEqual(total,152)
 def test_pruned_base_is_restored_by_original_group_not_invented_fallback(self):
  t=next(t for t in self.p['tiles']if t['tile']==[-41,-3]);c=next(c for c in t['chunks']if c['chunk']==[2,7])
  self.assertEqual(c['rawIndices'],[1,6,3,-1,-1]);self.assertEqual(c['prunedIndices'],[-1,-1,3,-1,-1])
  self.assertEqual(c['groupedIndices'],[1,2,3,-1,-1]);self.assertEqual(c['textureLayerMask'],7)
 def test_original_indices_border_state_and_color_table(self):
  self.assertEqual(self.n.triangle_indices(),self.p['triangleIndices']);self.assertEqual(self.n.quad(),{k:v for k,v in self.p['quad'].items()if k!='colors'})
  from PIL import Image
  for key,row in self.p['tables'].items():
   data=self.n.color_table(int(key));self.assertEqual(hashlib.sha256(data).hexdigest(),row['rgbaSHA256'])
   self.assertEqual(Image.open(OUT/row['url'].lstrip('/')).tobytes(),data)
  self.assertEqual(self.p['quad']['colors'],[0,0,0,255]*4)
  self.assertEqual(self.p['borderProfiles'][0]['state']['depthWriteEnabled'],False)
  self.assertIn('gl_Position.z = gl_Position.w;',(OUT/self.p['shaders']['water_border_vs.glsl']['url'].lstrip('/')).read_text())
 def test_previous207_frozen_payloads_unchanged(self):
  total=0
  entries=[('selection-scene-candidate-20261115','v4','candidate-package-manifest.json'),('selection-scene-inside-20261115','v1','candidate-package-manifest.json'),
   ('selection-scene-stones-20261115','v4','candidate-package-manifest.json'),('selection-scene-flowers-20261115','v2','candidate-package-manifest.json'),
   ('selection-scene-waterfalls-20261115','v2','candidate-package-manifest.json'),('selection-scene-grass-20261115','v1','candidate-package-manifest.json'),
   ('selection-scene-water-20261115','v1','candidate-package-manifest.json'),('selection-scene-water-20261115','surface-v1','surface-package-manifest.json')]
  for folder,v,fn in entries:
   root=ROOT/'analysis/raw'/folder
   for r in json.loads((root/fn).read_text())['files']:
    self.assertEqual(hashlib.sha256((root/v/r['path']).read_bytes()).hexdigest(),r['sha256']);total+=1
  self.assertEqual(total,207)
  for k in('lightsChanged','savesChanged','sourceGeometryChanged'):self.assertFalse(self.p[k])

if __name__=='__main__':unittest.main(verbosity=2)
