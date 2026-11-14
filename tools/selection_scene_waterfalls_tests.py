"""Original waterfall files/numeric consumers and frozen-payload checks."""
import hashlib,io,json,tempfile,unittest,zipfile
from pathlib import Path
from selection_scene_waterfalls_candidate import ROOT,MODELS,EFFECT,FX_SHA,SHADERS,defaults,overrides
from selection_scene_waterfalls_native import numeric_material,context
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from bdae_convert import BDAE
from scene_collision import apply_scene_transforms

OUTPUT=ROOT/'analysis/raw/selection-scene-waterfalls-20261115/v2'
@unittest.skipUnless((OUTPUT/'audit.json').is_file()and(Path(DEFAULT_SOURCE)/'res_scene.bin').is_file(),'Original private sources/candidate required')
class WaterfallTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.source=Sources(DEFAULT_SOURCE);cls.p=json.loads((OUTPUT/'assets/source-selection-waterfalls/overlay.json').read_text());cls.audit=json.loads((OUTPUT/'audit.json').read_text())
 def model(self,e):return json.loads((OUTPUT/e['url'].lstrip('/')).read_text())

 def test_original_geometry_uv_nodes_and_identity_are_retained(self):
  with tempfile.TemporaryDirectory()as td:
   for e in self.p['models']:
    raw=self.source.read(e['model']);self.assertEqual(hashlib.sha256(raw).hexdigest(),MODELS[e['model']][0]);p=Path(td)/'m';p.write_bytes(raw);r=BDAE(p);original=apply_scene_transforms(r,r.parse());data=self.model(e)
    for key in('meshes','materials','sceneNodes'):self.assertEqual(data[key],original[key])
    self.assertEqual((data['meshes'][0]['vertexCount'],data['meshes'][0]['triangleCount']),(42,60))

 def test_original_default_copy_and_typed_overrides_preserve_sparse_rate(self):
  from analyze_native_resources import NativeImage
  im=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())
  with tempfile.TemporaryDirectory()as td:
   p=Path(td)/'fx';raw=self.source.read(EFFECT);self.assertEqual(hashlib.sha256(raw).hexdigest(),FX_SHA);p.write_bytes(raw);df=defaults(BDAE(p))
   for e in self.p['models']:
    p.write_bytes(self.source.read(e['model']));ov,_=overrides(BDAE(p));actual=numeric_material(im,df,ov)
    self.assertEqual(actual,self.model(e)['selectionWaterfall']['numeric']);self.assertEqual(actual['result']['light_affected_rate'],[.5])
    if e['model'].endswith('002.bdae'):self.assertNotIn('light_affected_rate',ov)

 def test_actual_rgb_and_alpha_pvr_images_are_separate_without_generated_mask(self):
  from texture_decode import decode
  from PIL import Image
  for name,row in self.p['textures'].items():
   raw=self.source.read(name);self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sourceSHA256'])
   with zipfile.ZipFile(io.BytesIO(raw))as z:
    for key,pvr in [('rgb','rgb.pvr'),('alpha','alpha.pvr')]:
     original=decode(z.read(pvr));png=Image.open(OUTPUT/row['parts'][key]['url'].lstrip('/'))
     self.assertEqual(png.convert('RGBA').tobytes(),original.convert('RGBA').tobytes())
     self.assertEqual(hashlib.sha256(z.read(pvr)).hexdigest(),row['parts'][key]['sourcePartSHA256'])

 def test_original_shader_context_and_draw_state_not_generic_lightmap(self):
  from analyze_native_resources import NativeImage
  im=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())
  for e in self.p['models']:
   f=self.model(e)['selectionWaterfall'];self.assertEqual(context(im,True),f['context']);self.assertFalse(f['context']['waterMacro']);self.assertFalse(f['sourceDATApplied'])
  for n,digest in SHADERS.items():self.assertEqual(hashlib.sha256(self.source.read(n)).hexdigest(),digest)
  state=self.p['pass']['state'];self.assertTrue(state['blendEnabled']);self.assertFalse(state['depthWriteEnabled']);self.assertTrue(state['depthTestEnabled']);self.assertFalse(state['cullEnabled'])
  calls=state['originalGLCallsRecordedWithoutGPU'];blend=[c['args'][:2]for c in calls if c['name']=='glBlendFunc'];self.assertEqual(blend,[[770,771]])
  self.assertEqual(self.p['sourceGlobalLightCommon'],self.audit['nativeRGB']['submitted']['light_common'])
  self.assertEqual(self.audit['originalClock'][-1]['seconds'],1.)

 def test_previous169_payloads_and_existing_saves_not_changed(self):
  count=0
  for folder,version in [('selection-scene-candidate-20261115','v4'),('selection-scene-inside-20261115','v1'),('selection-scene-stones-20261115','v4'),('selection-scene-flowers-20261115','v2')]:
   root=ROOT/'analysis/raw'/folder;m=json.loads((root/'candidate-package-manifest.json').read_text())
   for r in m['files']:self.assertEqual(hashlib.sha256((root/version/r['path']).read_bytes()).hexdigest(),r['sha256']);count+=1
  self.assertEqual(count,169);self.assertFalse(self.p['lightsChanged']);self.assertFalse(self.p['savesChanged']);self.assertFalse(self.p['geometryChanged'])

if __name__=='__main__':unittest.main(verbosity=2)
