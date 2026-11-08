import json
import struct
import unittest
from pathlib import Path
from native_gameplay import verify_native, LIB_SHA256, CONSTANTS,ROUTINES

ROOT=Path(__file__).resolve().parents[1]
LIB=ROOT/'analysis/raw/beff-native/library.so'

class NativeGameplayTests(unittest.TestCase):
    def test_changed_build_never_reuses_traced_parameters(self):
        with self.assertRaisesRegex(ValueError,'retrace'):verify_native(b'not-the-source-library')

    @unittest.skipUnless(LIB.is_file(),'Original native library remains local')
    def test_native_instruction_spans_and_float_constants_match_the_traced_build(self):
        report=verify_native(LIB.read_bytes())
        self.assertEqual(report['librarySHA256'],LIB_SHA256)
        self.assertEqual(len(report['routines']),len(ROUTINES))
        self.assertEqual(report['constants']['0x250b8d4'],-75)
        self.assertEqual(report['constants']['0x250b8d8'],struct.unpack('<f',struct.pack('<f',-6.7))[0])
        self.assertEqual(len(report['constants']),len(CONSTANTS))


if __name__=='__main__':unittest.main()
