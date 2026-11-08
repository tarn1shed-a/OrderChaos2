import json,struct,unittest
from pathlib import Path
from beff_particles import ParticleReader
from beff_effects import decode_effect
from player_spell_effects import recover_player_effects
from resource_packs import ResourceArchive,DEFAULT_SOURCE
ROOT=Path(__file__).resolve().parents[1]

def node_bytes():
 words=[2,0,0,0,0,0,7,0,-1,0,1,0,0,0,0,1,1,0,0]
 raw=bytearray(struct.pack('<I19i3i',0,*words,0,1,1))
 for offset,value in [(8,.37),(12,2.09),(20,15),(24,4)]:struct.pack_into('<f',raw,offset,value)
 for i in range(19):raw.extend(struct.pack('<IIi',1,0,0)+struct.pack('<i' if 9<=i<16 else '<f',255 if 9<=i<16 else .1))
 return bytes(raw)
class PlayerSpellEffectsTests(unittest.TestCase):
 def test_procedural_native_record_consumes_all_fields_and_curves(self):
  b=node_bytes();r=ParticleReader(b,['dian3.tga','.']);v=r.model_node()
  self.assertEqual(r.at,len(b));self.assertEqual((v['type'],v['radialSegments'],v['rings']),(2,15,4));self.assertEqual(len(v['curves']),19);self.assertEqual(v['texture'],'texture/dian3.tga');self.assertTrue(v['uvScroll'])
 def test_procedural_truncation_bad_shape_dimensions_texture_and_colors_reject(self):
  raw=node_bytes()
  for b in [raw[:-1],raw[:70]]:
   with self.assertRaises(ValueError):ParticleReader(b,['dian3.tga','.']).model_node()
  for at,value in [(4,3),(8,0),(80,9)]:
   b=bytearray(raw);struct.pack_into('<i',b,at,value)
   with self.assertRaises(ValueError):ParticleReader(b,['dian3.tga','.']).model_node()
 @unittest.skipUnless((DEFAULT_SOURCE/'tables.bin').is_file(),'Original player spell sources remain local')
 def test_exact_player_chain_resolves_group_without_masking_it_to_an_unrelated_effect(self):
  archive=ResourceArchive(DEFAULT_SOURCE/'tables.bin');p=recover_player_effects(lambda path:archive.read(path))
  self.assertEqual(p['effects']['playerFireHit']['sourceReference'],0x90000023)
  self.assertEqual([r['effectId'] for r in p['effects']['playerFireHit']['groupRows']],[27,39])
  self.assertEqual([r['effectId'] for r in p['unresolvedReferences']],[39]);self.assertEqual(p['effects']['arcaneMissile']['missileType'],0x20001)
if __name__=='__main__':unittest.main()
