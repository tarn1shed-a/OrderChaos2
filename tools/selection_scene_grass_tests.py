"""Original missing grass DAT, source default mount and preservation checks."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from selection_scene_grass_candidate import ROOT,MODEL,MODEL_SHA,OBJECT,LIGHTMAP,LIGHTMAP_SHA
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE,read_entry
from bdae_convert import BDAE
from scene_collision import apply_scene_transforms

OUTPUT=ROOT/'analysis/raw/selection-scene-grass-20261115/v1'
@unittest.skipUnless((OUTPUT/'audit.json').is_file(),'Private candidate required')
class GrassTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.source=Sources(DEFAULT_SOURCE);cls.p=json.loads((OUTPUT/'assets/source-selection-grass/overlay.json').read_text());cls.audit=json.loads((OUTPUT/'audit.json').read_text())
 def test_source_missing_record_does_not_filter_loaded_model_or_substitute_atlas(self):
  from analyze_native_resources import NativeImage
  from native_missing_records import MissingRecordProbe
  from scene_lightmaps import read_records,object_records
  raw=self.source.read(self.p['recordPath']);self.assertEqual(object_records(read_records(raw),OBJECT),[])
  p=MissingRecordProbe(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()));actual=p.no_record(raw,OBJECT)
  self.assertEqual(actual,self.p['nativeEmptyRecords']);self.assertTrue(actual['noAtlasReplacement']);self.assertTrue(actual['freshVectorsUnchanged'])
  self.assertEqual(self.audit['admission'],'admittedBeforeTypeFactory')
 def test_original_mesh_uv_nodes_and_exact_itm_reused_without_change(self):
  from terrain_convert import read_instances
  raw=self.source.read(MODEL);self.assertEqual(hashlib.sha256(raw).hexdigest(),MODEL_SHA)
  with tempfile.TemporaryDirectory()as td:
   f=Path(td)/'m';f.write_bytes(raw);r=BDAE(f);orig=apply_scene_transforms(r,r.parse());old=json.loads((ROOT/'analysis/raw/selection-scene-candidate-20261115/v4'/self.p['entry']['url'].lstrip('/')).read_text())
   for k in('meshes','materials','sceneNodes'):self.assertEqual(orig[k],old[k])
   f.write_bytes(self.source.read(self.audit['sourceITM']));inst,=[r for r in read_instances(f)if r['id']==OBJECT];self.assertEqual(inst,self.p['entry']['instances'][0])
   self.assertEqual((orig['meshes'][0]['vertexCount'],orig['meshes'][0]['triangleCount']),(227,165))
 def test_original_fresh_mount_selects_update130_instead_of_base200(self):
  from analyze_native_resources import NativeImage
  from native_missing_records import MissingRecordProbe
  from texture_decode import decode
  from PIL import Image
  cs=self.source.candidates(LIGHTMAP);packs=[n for n in['res_t.bin',*[f'res_t_upd{i}.bin'for i in range(10,16)]]if(DEFAULT_SOURCE/n).is_file()]
  actual=MissingRecordProbe(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())).fresh_archives(packs,[r['pack']for r in cs]);self.assertEqual(actual,self.p['nativeTextureMount'])
  pixels={r['pack']:decode(read_entry(r,DEFAULT_SOURCE)).getpixel((0,0))for r in cs};self.assertEqual(pixels,{'res_t.bin':(200,200,200,255),'res_t_upd10.bin':(130,130,130,255)})
  raw=read_entry(next(r for r in cs if r['pack']==actual['selected']),DEFAULT_SOURCE);self.assertEqual(hashlib.sha256(raw).hexdigest(),LIGHTMAP_SHA)
  png=Image.open(OUTPUT/self.p['textures'][LIGHTMAP]['url'].lstrip('/'));self.assertEqual(png.convert('RGBA').tobytes(),decode(raw).convert('RGBA').tobytes())
 def test_previous178_payloads_unchanged_and_no_saves_lights_or_geometry_modified(self):
  count=0
  for folder,v in [('selection-scene-candidate-20261115','v4'),('selection-scene-inside-20261115','v1'),('selection-scene-stones-20261115','v4'),('selection-scene-flowers-20261115','v2'),('selection-scene-waterfalls-20261115','v2')]:
   root=ROOT/'analysis/raw'/folder;manifest=json.loads((root/'candidate-package-manifest.json').read_text())
   for r in manifest['files']:self.assertEqual(hashlib.sha256((root/v/r['path']).read_bytes()).hexdigest(),r['sha256']);count+=1
  self.assertEqual(count,178)
  for k in('savesChanged','lightsChanged','geometryChanged','selectionAtlasApplied','selectionDATTransformApplied'):self.assertFalse(self.p[k])

if __name__=='__main__':unittest.main(verbosity=2)
