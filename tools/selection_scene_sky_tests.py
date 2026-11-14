"""Region211 original request/channel evidence, with missing models explicit."""
import hashlib,json,unittest,zipfile
from pathlib import Path
from selection_scene_sky_probe import ROOT,EXPECTED,SelectionSkyProbe
from map_loading_evidence import Sources
from resource_packs import DEFAULT_SOURCE
from map_selection_evidence import DEFAULT_APK
from skill_attachments import decode_ftable
from scene_lighting import ZONE_SHA256,f32
from tutorial_sky_candidate import target_writes

OUTPUT=ROOT/'analysis/raw/selection-scene-sky-20261115/evidence-v1.json'

@unittest.skipUnless(OUTPUT.is_file()and(Path(DEFAULT_SOURCE)/'res_scene.bin').is_file(),'Original archives and private sky evidence required')
class SelectionSkyTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.result=json.loads(OUTPUT.read_text());cls.source=Sources(DEFAULT_SOURCE)

 def test_original211_request_block_and_mode1_duration_producer(self):
  from analyze_native_resources import NativeImage
  raw=self.source.read('tables/zones.tbl');self.assertEqual(hashlib.sha256(raw).hexdigest(),ZONE_SHA256)
  table=decode_ftable(raw,'ID');row,=[r for r in table['rows']if r['ID']==211]
  actual=SelectionSkyProbe(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes())).inspect(table,row)
  self.assertEqual(actual,self.result['native']);self.assertEqual(actual['worldMode'],1);self.assertEqual(actual['durationMs'],0)
  self.assertTrue(actual['originalDurationProducerExecuted']);self.assertEqual(actual['current'],target_writes(row,None))
  self.assertEqual({r['kind']:r['rawPath'].replace('\\','/').lower()for r in actual['requests']},EXPECTED)
  self.assertTrue(all(not r['modelCreationExecuted']for r in actual['requests']))

 def test_both_exact_and_basename_models_are_absent_in_all_source_archives_and_apk(self):
  with zipfile.ZipFile(DEFAULT_APK)as z:names=z.namelist()
  for path in EXPECTED.values():
   self.assertEqual(self.source.candidates(path),[])
   basename=Path(path).name
   self.assertEqual([r for rows in self.source.lookup.values()for r in rows if Path(r['path'].replace('\\','/')).name.lower()==basename],[])
   self.assertEqual([n for n in names if n.lower().endswith('/'+basename)or n.lower()==basename],[])
  self.assertEqual(self.result['missingOriginalModels'],list(EXPECTED.values()));self.assertFalse(self.result['runtimeReady'])

 def test_existing_similarly_named_textures_do_not_supply_model_or_material(self):
  for name,row in self.result['nearbyTexturesOnly'].items():
   self.assertEqual(hashlib.sha256(self.source.read(name)).hexdigest(),row['sha256'])
   self.assertFalse(row['boundToRequestedModels'])
  self.assertEqual(self.result['defaultShowHillInSky'],True)
  self.assertEqual(len(self.result['skyModelEntries']),16)

 def test_camera_follow_consumer_is_only_a_conditional_loaded_node_control(self):
  from native_sky_frame_probe import NativeSkyFrameProbe
  from analyze_native_resources import NativeImage
  p=NativeSkyFrameProbe(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()))
  control=self.result['conditionalCameraFollow'];point=control['camera']
  actual=p.follow(point,main=[0,0,0],hill=[1,2,3]);self.assertEqual(actual,control['result'])
  self.assertEqual(actual['positions'],{'main':list(map(f32,point)),'hill':list(map(f32,point))})
  self.assertFalse(control['proofThatMissingModelsLoaded'])

 def test_previous_all_static_payloads_unchanged(self):
  for folder,version in [('selection-scene-candidate-20261115','v4'),('selection-scene-inside-20261115','v1'),('selection-scene-stones-20261115','v4'),('selection-scene-flowers-20261115','v2')]:
   root=ROOT/'analysis/raw'/folder;m=json.loads((root/'candidate-package-manifest.json').read_text())
   for row in m['files']:self.assertEqual(hashlib.sha256((root/version/row['path']).read_bytes()).hexdigest(),row['sha256'])
  self.assertFalse(self.result['previewChanged']);self.assertFalse(self.result['savesChanged'])

if __name__=='__main__':unittest.main(verbosity=2)
