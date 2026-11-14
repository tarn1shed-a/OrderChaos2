"""Original all251 group consumers and frozen published-cache preservation."""
import hashlib,json,tarfile,unittest
from pathlib import Path
from selection_scene_candidate import ROOT
from tutorial_terrain_grouping_probe import analyze
from tutorial_terrain_grouping_samples import analyze as compare
RAW=ROOT/'analysis/raw/tutorial-terrain-grouping-20261115';RUNTIME=ROOT/'analysis/raw/creation-stage-transform-20261115/entry-runtime'
@unittest.skipUnless((RAW/'evidence-v3.json').is_file(),'Private original tutorial group evidence required')
class TutorialGroupsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  from analyze_native_resources import NativeImage
  cls.image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());cls.e=json.loads((RAW/'evidence-v3.json').read_text())
 def test_all16064_chunk_consumers_match_original_execution(self):
  result=analyze(self.image,RUNTIME);self.assertEqual(result,self.e)
  self.assertEqual(result['counts'],{'chunks':16064,'wet':4098,'dry':11966,'differentChunks':2178,'differentDry':1789,'currentMissingBase':118,'differentWet':389})
  for tile in result['tiles']:
   for c in tile['chunks']:
    self.assertGreaterEqual(c['finalIndices'][0],0);self.assertEqual(c['textureLayerMask'],sum(1<<i for i,v in enumerate(c['finalIndices'])if v>=0))
 def test_index_changes_not_automatically_visual_errors(self):
  r=compare(RUNTIME,RAW/'evidence-v3.json');self.assertEqual(r,json.loads((RAW/'samples-v3.json').read_text()))
  self.assertEqual(r['comparedChunks'],2178);self.assertEqual(r['sampleCount'],696960);self.assertEqual(r['chunksOverOneRGBUnit'],84)
  nearest=r['nearEntrySamples'][0];self.assertEqual((nearest['tile'],nearest['chunk']),([-41,-2],[4,3]));self.assertEqual(nearest['interiorMaxRGBDelta255'],0)
  self.assertGreater(nearest['boundaryMaxRGBDelta255'],6)
 def test_original_representative_transfer_and_all4098_water_inputs(self):
  r=self.e['nativeMaterialCopy'];self.assertTrue(r['fullOriginal35127cExecuted']);self.assertTrue(r['memberIndexFieldsUnchanged'])
  self.assertEqual(r['effectRefcount'],[100,101]);self.assertEqual(r['tableRefcount'],[100,101]);self.assertFalse(r['resourceOrGPUCreated'])
  wet=0
  for tile in self.e['tiles']:
   self.assertTrue(tile['native35650cRepresentativeExecuted'])
   for c in tile['chunks']:
    rep=tile['chunks'][c['representativeChunk'][1]*8+c['representativeChunk'][0]]
    self.assertEqual(c['actualMaterialBinding'],rep['actualMaterialBinding'])
    if c['nativeFlags']&0x10000:self.assertEqual(c['waterDescriptor'],c['representativeWaterDescriptor']);wet+=1
  self.assertEqual(wet,4098)
 def test_candidate_only_contains_source_final_group_changes(self):
  p=json.loads((RAW/'v2/assets/source-tutorial-terrain-groups/overlay.json').read_text());count=0
  for tile in p['tiles']:
   source=next(t for t in self.e['tiles']if t['tile']==tile['tile'])
   for c in tile['chunks']:
    row=source['chunks'][c['chunk'][1]*8+c['chunk'][0]]
    self.assertEqual(c['current'],row['currentEffectiveIndices']);self.assertEqual(c['material'],row['actualMaterialBinding']);self.assertEqual(c['material']['macro'],row['textureLayerMask']);count+=1
  self.assertEqual(count,2178)
  for k in('sourceGeometryChanged','sourceLightingChanged','savesChanged'):self.assertFalse(p[k])
 def test_available2955_old_payloads_match_the_complete_frozen_archive(self):
  archive=ROOT/'analysis/raw/creation-stage-transform-20261115/creation-preview-complete-v1.tar.gz';count=0
  pending={str(p.relative_to(RUNTIME)):p for p in RUNTIME.rglob('*')if p.is_file()}
  # Stream the compressed archive once; random seeks repeatedly decompress it.
  with tarfile.open(archive,mode='r|gz')as tar:
   for member in tar:
    p=pending.pop(member.name,None)
    if p is None:continue
    self.assertTrue(member.isfile());self.assertEqual(hashlib.sha256(p.read_bytes()).digest(),hashlib.sha256(tar.extractfile(member).read()).digest());count+=1
  self.assertEqual(pending,{});self.assertEqual(count,2955)

if __name__=='__main__':unittest.main(verbosity=2)
