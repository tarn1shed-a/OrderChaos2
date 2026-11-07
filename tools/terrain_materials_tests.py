import json,struct,tempfile,unittest
from pathlib import Path
from terrain_materials import tile_materials,mask_channels,effective_indices,verify_native,recover_materials,ROUTINES
from texture_sampling import verify_sampling,mask_upload_profile,FORMAT_ADDRESS
from resource_packs import DEFAULT_SOURCE,index,ResourceArchive
ROOT=Path(__file__).resolve().parents[1]

def tile(version=9,indices=(0,1,-1,2,-1)):
 stride=16 if version==9 else 24;body=struct.pack('<Ih5h',65536,0,*indices)+bytes(stride-16)
 raw=struct.pack('<4s5i',b'ATIL',version,-41,2,1,65535)+body*64+bytes(29575)+b'\0'
 names=[b'texture/zero.tga\0',b'texture/one.tga\0',b'texture/two.tga\0'];ends=[];n=0
 for name in names:n+=len(name);ends.append(n)
 return raw+struct.pack('<I3I',3,*ends)+b''.join(names)

class TerrainMaterialsTests(unittest.TestCase):
 def test_native_tile_stride_signed_indices_and_exact_string_extent(self):
  for version in (9,10):
   p=tile_materials(tile(version));self.assertEqual(p['tile'],[-41,2]);self.assertEqual(p['recordStride'],16 if version==9 else 24)
   self.assertEqual(p['chunks'][-1]['chunk'],[7,7]);self.assertEqual(p['chunks'][0]['indices'],[0,1,-1,2,-1]);self.assertEqual(p['chunks'][0]['flags'],65536)
  for raw in [b'bad',tile(11),tile()[:-1],tile()+b'\0',tile(indices=(3,-1,-1,-1,-1)),tile(indices=(-2,-1,-1,-1,-1))]:
   with self.assertRaises((ValueError,struct.error)):tile_materials(raw)
 def test_masks_interleave_raw_channels_without_flip_and_reject_inconsistent_size(self):
  green=bytes(range(64));image,classes=mask_channels([None,green,None,None]);self.assertEqual(image.size,(8,8))
  self.assertEqual(image.getpixel((3,4)),(0,35,0,0));self.assertEqual(classes[0],[0,0,0,0]);self.assertEqual(classes[8],[0,2,0,0])
  self.assertEqual(mask_channels([None]*4),(None,[[0]*4 for _ in range(64)]))
  for channels in [[b'123',None,None,None],[bytes(64),bytes(256),None,None],[bytes(100),None,None,None]]:
   with self.assertRaises(ValueError):mask_channels(channels)
 def test_red_blue_and_alpha_lanes_keep_distinct_values_in_source_rgba8_order(self):
  image,_=mask_channels([bytes([17])*64,bytes([67])*64,bytes([149])*64,bytes([239])*64])
  self.assertEqual(image.getpixel((0,0)),(17,67,149,239));self.assertEqual(image.getpixel((7,7)),(17,67,149,239))
  p=mask_upload_profile();self.assertEqual(p['channelToByteLane'],[0,1,2,3]);self.assertEqual(p['sourceFormatName'],'RGBA8')
  self.assertFalse(p['textureDefaults']['appliedAsActiveQualityPreset'])
 def test_upper_five_bits_classify_zero_full_and_mixed_chunks(self):
  for value,expected in [(0,0),(7,0),(8,2),(247,2),(248,1),(255,1)]:
   _,classes=mask_channels([bytes([value])*256,None,None,None]);self.assertTrue(all(c[0]==expected for c in classes))
 def test_native_high_layer_prunes_lower_layers_only_after_zero_layers_above(self):
  self.assertEqual(effective_indices([0,1,2,3,4],[2,1,0,2]),[-1,-1,2,-1,4])
  self.assertEqual(effective_indices([0,1,2,3,4],[0,0,0,0]),[0,-1,-1,-1,-1])
  with self.assertRaises(ValueError):effective_indices([0]*5,[3]*4)
 def test_changed_native_routines_fail_before_claiming_recovery(self):
  class Changed:
   def read(self,a,n):return bytes(n)
  with self.assertRaisesRegex(ValueError,'retrace'):verify_native(Changed())
 @unittest.skipUnless((ROOT/'analysis/raw/beff-native/library.so').is_file(),'Original native library stays local')
 def test_real_native_material_and_uv_fingerprints(self):
  from analyze_native_resources import NativeImage
  image=NativeImage((ROOT/'analysis/raw/beff-native/library.so').read_bytes());self.assertEqual(len(verify_native(image)),len(ROUTINES))
  class ChangedDescriptor:
   elf=image.elf
   def read(self,address,size):return bytes(size) if address==FORMAT_ADDRESS else image.read(address,size)
  with self.assertRaisesRegex(ValueError,'descriptor changed'):verify_sampling(ChangedDescriptor())
 @unittest.skipUnless((DEFAULT_SOURCE/'tutorial.bin').is_file(),'Original terrain stays local')
 def test_real_region_links_source_chunks_to_raw_mask_and_shader(self):
  rows=index(DEFAULT_SOURCE);archives={}
  def extract(path):
   found=[r for r in rows if r['path']==path and r['pack'] in ['tutorial.bin','tutorial_layer.bin','res.bin']];self.assertEqual(len(found),1,path)
   pack=found[0]['pack']
   if pack not in archives:archives[pack]=ResourceArchive(DEFAULT_SOURCE/pack)
   return archives[pack].read(path)
  names={r['path'] for r in rows};sources=[]
  for z in range(2,5):
   for x in range(-43,-40):
    p=tile_materials(extract(f'world/tutorial/terrain/{x:04d}_{z:04d}.trn'));sources.append({'tile':[x,z],'textures':p['textures']})
  with tempfile.TemporaryDirectory() as temp:
   p=recover_materials(extract,lambda v:v in names,temp,{'world':'tutorial','sourceTextures':sources},lambda path:'/assets/textures/'+path+'.png')
   self.assertEqual(len(p['tiles']),9);self.assertEqual(sum(t['mask'] is not None for t in p['tiles']),1)
   t=next(t for t in p['tiles'] if t['tile']==[-41,2]);self.assertEqual(t['mask']['channels'],[None,'world/tutorial/layers/-041_0002_1.msk',None,None])
   self.assertEqual(sum(c['maskClasses'][1]==2 for c in t['chunks']),1)
   self.assertEqual(sum(c['effectiveIndices'][2]>=0 for c in t['chunks']),1)
   self.assertEqual(json.loads((Path(temp)/'maps/terrain-materials.json').read_text()),p)

if __name__=='__main__':unittest.main()
