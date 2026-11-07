import json
import struct
import unittest
from pathlib import Path
from native_gameplay import verify_native, LIB_SHA256, CONSTANTS

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'analysis/raw/beff-native/library.so'
PROFILE=ROOT/'game-data/converted/gameplay/native.json'

class NativeGameplayTests(unittest.TestCase):
    def test_changed_build_never_reuses_traced_parameters(self):
        with self.assertRaisesRegex(ValueError,'retrace'):verify_native(b'not-the-source-library')

    @unittest.skipUnless(LIB.is_file(),'Original native library remains local')
    def test_native_instruction_spans_and_float_constants_match_the_traced_build(self):
        report=verify_native(LIB.read_bytes())
        self.assertEqual(report['librarySHA256'],LIB_SHA256)
        self.assertEqual(len(report['routines']),8)
        self.assertEqual(report['constants']['0x250b8d4'],-75)
        self.assertEqual(report['constants']['0x250b8d8'],struct.unpack('<f',struct.pack('<f',-6.7))[0])
        self.assertEqual(len(report['constants']),len(CONSTANTS))

    @unittest.skipUnless(PROFILE.is_file(),'Original combo tables remain local')
    def test_converted_profile_uses_verified_item_types_and_exact_animation_links(self):
        profile=json.loads(PROFILE.read_text())
        self.assertEqual(profile['weapons']['trainingSword']['word'],0)
        self.assertTrue(profile['weapons']['trainingSword']['legacy'])
        self.assertEqual(profile['weapons']['trainingStaff']['word'],0x30001)
        self.assertEqual(profile['weapons']['trainingStaff']['allowedProfessions'],[2,4])
        self.assertEqual(profile['weapons']['trainingGreatsword']['word'],0x60001)
        self.assertFalse(profile['jump']['stationaryAnimationAvailable'])
        for skill,animation in [(4,'combat_double_knuckle_01'),(84,'combat_unarmed_fireball_01'),(424,'combat_2h_staff_mk_01'),(66,'combat_2h_sword_01')]:
            entry=profile['skills'][str(skill)]
            self.assertEqual(entry['sourceAnimation'],animation)
            self.assertTrue(entry['clip'])
        self.assertTrue(all(r['isNormalAttack']==1 for r in profile['comboRows']))
        self.assertNotIn('79',profile['skills'],'Bank-0 legacy starter is not silently treated as normal bank 1')

if __name__=='__main__':unittest.main()
