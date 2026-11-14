"""Original flower geometry/custom-lightMap gate; no browser/GPU claim."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from selection_scene_flowers_probe import ROOT,MODEL,MODEL_SHA,LIGHTMAP,LIGHTMAP_SHA,IDS,FlowerLightmapProbe
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from bdae_convert import BDAE
from scene_collision import apply_scene_transforms
from selection_scene_candidate import binding_rows

OUTPUT=ROOT/'analysis/raw/selection-scene-flowers-20261115/v2'

@unittest.skipUnless((OUTPUT/'audit.json').is_file()and(Path(DEFAULT_SOURCE)/'res_scene.bin').is_file(),'Original archives and private flower candidate required')
class FlowerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.source=Sources(DEFAULT_SOURCE);cls.audit=json.loads((OUTPUT/'audit.json').read_text())
  cls.p=json.loads((OUTPUT/'assets/source-selection-flowers/overlay.json').read_text())
  cls.data=json.loads((OUTPUT/cls.p['entry']['url'].lstrip('/')).read_text())

 def test_original_geometry_and_material_keep_actual_custom_name(self):
  raw=self.source.read(MODEL);self.assertEqual(hashlib.sha256(raw).hexdigest(),MODEL_SHA)
  with tempfile.TemporaryDirectory()as td:
   p=Path(td)/'source.bdae';p.write_bytes(raw);r=BDAE(p);data=apply_scene_transforms(r,r.parse())
  for key in('meshes','materials','sceneNodes'):self.assertEqual(data[key],self.data[key])
  self.assertEqual(self.data['materials'][0]['samplers']['lightMap'],LIGHTMAP)
  self.assertEqual((self.data['meshes'][0]['vertexCount'],self.data['meshes'][0]['triangleCount']),(8,4))

 def test_original342194_rejects_custom_texture_but_accepts_placeholder_controls(self):
  from analyze_native_resources import NativeImage
  image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());probe=FlowerLightmapProbe(image)
  for row in self.p['DATRequests']:
   result=probe.run_binding(LIGHTMAP,row['DATBindings'][0]['uvTransform'])
   self.assertEqual(result,row['bindingPolicy']);self.assertFalse(result['atlasReplacedOriginal']);self.assertFalse(result['replacementAllowed'])
   self.assertEqual(result['uvTransform'],[0,0,1,1]);self.assertTrue(result['policyCached'])
   self.assertNotIn('0x13dc85c',[r['address']for r in result['originalCalls']])
  for name in('texture/lightmap.tga','',None):
   r=probe.run_binding(name,[.25,.5,.75,1]);self.assertTrue(r['atlasReplacedOriginal']);self.assertEqual(r['uvTransform'],[.25,.5,.75,1])
  r=probe.run_binding(LIGHTMAP,[.25,.5,.75,1],initial_uv=(.125,.25,.5,1))
  self.assertEqual(r['uvTransform'],[.125,.25,.5,1]);self.assertFalse(r['atlasReplacedOriginal'])

 def test_original_constant_texture_is_real_unique_file_not_a_filled_fallback(self):
  from texture_decode import decode
  self.assertEqual([c['pack']for c in self.source.candidates(LIGHTMAP)],['res_t.bin'])
  raw=self.source.read(LIGHTMAP);self.assertEqual(hashlib.sha256(raw).hexdigest(),LIGHTMAP_SHA)
  image=decode(raw);self.assertEqual(image.size,(8,8));self.assertEqual(image.convert('RGBA').tobytes(),bytes([130,130,130,255])*64)
  from PIL import Image
  png=Image.open(OUTPUT/self.p['textures'][LIGHTMAP]['url'].lstrip('/')).convert('RGBA')
  self.assertEqual(png.tobytes(),image.convert('RGBA').tobytes())

 def test_each_original_selection_dat_is_retained_but_not_applied(self):
  self.assertEqual([r['id']for r in self.p['entry']['instances']],IDS)
  for row in self.p['DATRequests']:
   path,bs=binding_rows(self.source,row['instance']);self.assertEqual(row['recordPath'],path);self.assertEqual(row['DATBindings'],bs)
   self.assertEqual(len(bs),1);self.assertTrue(bs[0]['atlas'].startswith('texture/lightmap/selection/'))
  self.assertFalse(self.data['selectionFlowers']['selectionDATTransformApplied']);self.assertFalse(self.data['selectionFlowers']['selectionAtlasApplied'])
  self.assertTrue(all(r['admission']=='admittedBeforeTypeFactory'for r in self.audit['admissions']))
  self.assertEqual(self.data['sceneAlpha']['materials'][0]['reference'],.5)

 def test_all_previous_frozen_payloads_unchanged(self):
  for folder,version in [('selection-scene-candidate-20261115','v4'),('selection-scene-inside-20261115','v1'),('selection-scene-stones-20261115','v4')]:
   base=ROOT/'analysis/raw'/folder;manifest=json.loads((base/'candidate-package-manifest.json').read_text())
   for r in manifest['files']:self.assertEqual(hashlib.sha256((base/version/r['path']).read_bytes()).hexdigest(),r['sha256'])
  self.assertFalse(self.p['lightsChanged']);self.assertFalse(self.p['savesChanged']);self.assertFalse(self.p['geometryChanged'])

if __name__=='__main__':unittest.main(verbosity=2)
