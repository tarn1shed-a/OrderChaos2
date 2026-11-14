"""Original25 selection TRN bounds, water gates, dry append and preservation."""
import hashlib,json,unittest
from pathlib import Path
from selection_scene_candidate import ROOT
from selection_scene_water_probe import analyze

RAW=ROOT/'analysis/raw/selection-scene-water-20261115'
BASE=ROOT/'analysis/raw/selection-scene-candidate-20261115/v4'
@unittest.skipUnless((RAW/'v1/audit.json').is_file(),'Private original water candidate required')
class SelectionWaterTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from analyze_native_resources import NativeImage
  cls.evidence,cls.depths,cls.tables=analyze(NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes()),BASE)
  cls.export=json.loads((RAW/'v1/evidence.json').read_text());cls.p=json.loads((RAW/'v1/assets/source-selection-water/overlay.json').read_text())
 def test_all1600_original_chunk_minima_flags_and_source_water_descriptors(self):
  self.assertEqual(self.evidence,self.export);self.assertEqual(sum(len(r['chunks'])for r in self.evidence['tiles']),1600)
  self.assertEqual(sum(len(r['restoredDry'])for r in self.evidence['tiles']),192)
  wet=[c for r in self.evidence['tiles']for c in r['wet']];self.assertEqual(len(wet),152)
  self.assertEqual({c['waterHeight']for c in wet},{0.,110.,128.,135.});self.assertEqual({r['type']for r in self.evidence['tiles']if r['wet']},{0})
  self.assertEqual(len(self.depths),9);self.assertTrue(all(len(b)==16384 for b in self.depths.values()));self.assertTrue(all(len(b)==1024 for b in self.tables.values()))
 def test_original_water_gate_does_not_exclude_map7_and_batching_is_capability_conditional(self):
  p=self.evidence;self.assertEqual(p['nativeFreshWaterGlobal'],{'2509330':1,'2509342':1})
  self.assertEqual([r['passed']for r in p['drawGates']],[True,False,False])
  self.assertEqual([r['calls'][-1]['waterDrawBoundary']for r in p['dispatch']],['0x360b48','0x3624cc'])
  self.assertEqual([r['global2509330']for r in p['capabilityControls']],[0,1]);self.assertFalse(p['originalGPUObserved'])
 def test_only_originally_omitted_but_originally_dry_chunks_are_added(self):
  mats=json.loads((BASE/'assets/source-selection-scene/terrain-materials.json').read_text());seen=set()
  for row in self.p['rows']:
   source,=[r for r in self.evidence['tiles']if r['tile']==row['tile']];mat,=[r for r in mats['tiles']if r['tile']==row['tile']]
   self.assertEqual(row['chunks'],source['restoredDry'])
   for c in row['chunks']:
    i=c[1]*8+c[0];self.assertTrue(mat['chunks'][i]['sourceWaterPending']);self.assertFalse(source['chunks'][i]['flags']&0x10000)
    key=(*row['tile'],*c);self.assertNotIn(key,seen);seen.add(key)
  self.assertEqual(len(seen),192);self.assertFalse(self.p['sourceWaterSurfaceActivated']);self.assertFalse(self.p['sourceWetFloorActivated'])
 def test_previous180_frozen_payloads_unchanged(self):
  total=0
  for folder,v in [('selection-scene-candidate-20261115','v4'),('selection-scene-inside-20261115','v1'),('selection-scene-stones-20261115','v4'),('selection-scene-flowers-20261115','v2'),('selection-scene-waterfalls-20261115','v2'),('selection-scene-grass-20261115','v1')]:
   root=ROOT/'analysis/raw'/folder;m=json.loads((root/'candidate-package-manifest.json').read_text())
   for r in m['files']:self.assertEqual(hashlib.sha256((root/v/r['path']).read_bytes()).hexdigest(),r['sha256']);total+=1
  self.assertEqual(total,180)
  for key in('lightsChanged','savesChanged','geometrySourceChanged'):self.assertFalse(self.p[key])

if __name__=='__main__':unittest.main(verbosity=2)
