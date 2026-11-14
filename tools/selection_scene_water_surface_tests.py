"""Original selection water batch/depth/texture and frozen-payload checks."""
import hashlib,json,unittest
from pathlib import Path
from selection_scene_candidate import ROOT
from selection_scene_water_batch_native import NativeWaterBatch,capability
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE

OUT=ROOT/'analysis/raw/selection-scene-water-20261115/surface-v1'
@unittest.skipUnless((OUT/'audit.json').is_file(),'Private water surface required')
class SelectionSurfaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from analyze_native_resources import NativeImage
  cls.image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());cls.native=NativeWaterBatch(cls.image);cls.source=Sources(DEFAULT_SOURCE)
  cls.p=json.loads((OUT/'assets/source-selection-water-surface/overlay.json').read_text());cls.audit=json.loads((OUT/'audit.json').read_text())
 def test_actual_original_batch_buffers_and_depth_bytes_for_all9_selection_tiles(self):
  from PIL import Image
  count=0
  for t in self.p['tiles']:
   raw=self.source.read(t['source']);self.assertEqual(hashlib.sha256(raw).hexdigest(),t['sourceSHA256']);self.native.read(raw)
   b=self.native.buffers(self.p['sourceCommonRGB']);saved=json.loads((OUT/t['batch']['url'].lstrip('/')).read_text());self.assertEqual(b,{k:v for k,v in saved.items()if k not in('source','sourceSHA256')})
   depth,prep=self.native.source_depth();self.assertEqual(hashlib.sha256(depth).hexdigest(),t['depth']['cpuSHA256']);self.assertEqual(prep,t['depth']['sourcePreparation'])
   im=Image.open(OUT/t['depth']['url'].lstrip('/'));self.assertEqual(im.getchannel('A').tobytes(),depth);count+=len(b['wetChunks'])
  self.assertEqual(count,152)
 def test_actual_source_images_and_shader_files_retained(self):
  from texture_decode import decode
  from PIL import Image
  for path,t in self.p['textures'].items():
   raw=self.source.read(path);self.assertEqual(hashlib.sha256(raw).hexdigest(),t['sourceSHA256']);self.assertEqual(Image.open(OUT/t['url'].lstrip('/')).convert('RGBA').tobytes(),decode(raw).convert('RGBA').tobytes())
  for n,t in self.p['shaders'].items():self.assertEqual((OUT/t['url'].lstrip('/')).read_bytes(),self.source.read(n))
 def test_original_capability_producer_and_211_water_rgb_not_tutorial_inputs(self):
  actual=[capability(self.image,v)for v in(200,300)];self.assertEqual(actual,self.audit['capabilityControls']);self.assertEqual([p['driver1b5Bit5']for p in actual],[False,True])
  fresh=json.loads((ROOT/'analysis/raw/selection-scene-environment-upstream-20261115/result-v2.json').read_text())['freshStart']['nativeRGB']['submitted']
  self.assertEqual(self.p['sourceWaterSurfaceRGB'],fresh['light_waterSurface']);self.assertEqual(self.p['sourceCommonRGB'],fresh['light_common'])
  self.assertFalse(self.p['selection']['nativeAndroidCapabilityObserved']);self.assertFalse(self.p['wetFloorActivated'])
 def test_previous181_frozen_payloads_unchanged(self):
  total=0
  for f,v in [('selection-scene-candidate-20261115','v4'),('selection-scene-inside-20261115','v1'),('selection-scene-stones-20261115','v4'),('selection-scene-flowers-20261115','v2'),('selection-scene-waterfalls-20261115','v2'),('selection-scene-grass-20261115','v1'),('selection-scene-water-20261115','v1')]:
   root=ROOT/'analysis/raw'/f;m=json.loads((root/'candidate-package-manifest.json').read_text())
   for r in m['files']:self.assertEqual(hashlib.sha256((root/v/r['path']).read_bytes()).hexdigest(),r['sha256']);total+=1
  self.assertEqual(total,181);self.assertFalse(self.p['lightsChanged']);self.assertFalse(self.p['savesChanged'])

if __name__=='__main__':unittest.main(verbosity=2)
