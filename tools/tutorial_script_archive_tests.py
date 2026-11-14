"""Format/integrity boundaries for the original script-container audit."""
import json
import struct
import unittest
import zlib
from pathlib import Path

from tutorial_script_archive_audit import RAW, ROOT, AUDIT_NAME, expand_swf, swf_actions, vox_directory

SETUP_AUDIO = ROOT / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files/sound2/setup.voxpack'
HAS_SETUP_AUDIO = SETUP_AUDIO.is_file()
HAS_PRIVATE_REPORT = (RAW / AUDIT_NAME).is_file()


class ContainerTests(unittest.TestCase):
    def test_cws_exact_length_and_checksum(self):
        body = bytes(20)
        source = b'CWS\x0b' + struct.pack('<I', len(body) + 8) + zlib.compress(body)
        self.assertEqual(expand_swf(source), b'FWS' + source[3:8] + body)

    def test_cws_trailing_data_rejected(self):
        body = bytes(20)
        source = b'CWS\x0b' + struct.pack('<I', len(body) + 8) + zlib.compress(body) + b'extra'
        with self.assertRaises(ValueError):
            expand_swf(source)

    def test_cws_declared_length_rejected(self):
        source = b'CWS\x0b' + struct.pack('<I', 100) + zlib.compress(bytes(20))
        with self.assertRaises(ValueError):
            expand_swf(source)

    def test_unknown_encoding_not_guessed(self):
        with self.assertRaises(ValueError):
            expand_swf(b'ZWS\x0b' + bytes(32))

    def test_fws_truncation_rejected(self):
        with self.assertRaises(ValueError):
            expand_swf(b'FWS\x0b' + struct.pack('<I', 30) + bytes(20))

    @unittest.skipUnless(HAS_SETUP_AUDIO, 'private original setup.voxpack is not present')
    def test_audio_range_rejected(self):
        from resource_packs import DEFAULT_SOURCE
        data = bytearray((DEFAULT_SOURCE / 'sound2/setup.voxpack').read_bytes())
        a, b = struct.unpack_from('<II', data, 24)
        for at in (a, b):
            struct.pack_into('<I', data, at + 12, len(data))
        with self.assertRaises(ValueError):
            vox_directory(data)

    @unittest.skipUnless(HAS_SETUP_AUDIO, 'private original setup.voxpack is not present')
    def test_audio_name_bounds_rejected(self):
        from resource_packs import DEFAULT_SOURCE
        data = bytearray((DEFAULT_SOURCE / 'sound2/setup.voxpack').read_bytes())
        a, b = struct.unpack_from('<II', data, 32)
        for at in (a, b):
            struct.pack_into('<I', data, at, 0xffffffff)
        with self.assertRaises(ValueError):
            vox_directory(data)

    @unittest.skipUnless(HAS_SETUP_AUDIO, 'private original setup.voxpack is not present')
    def test_audio_copies_not_silently_merged(self):
        from resource_packs import DEFAULT_SOURCE
        data = bytearray((DEFAULT_SOURCE / 'sound2/setup.voxpack').read_bytes())
        a, = struct.unpack_from('<I', data, 24)
        data[a] ^= 1
        with self.assertRaises(ValueError):
            vox_directory(data)

    @unittest.skipUnless(HAS_PRIVATE_REPORT, 'private original v2 audit report is not present')
    def test_actual_v2_coverage_not_total_script_absence(self):
        d = json.loads((RAW / AUDIT_NAME).read_text())
        self.assertEqual([d['GBMP'][k] for k in ('packCount', 'records', 'fileCount')], [41, 40979, 39665])
        self.assertEqual(d['SWF']['magicCounts'], {'FWS': 415, 'CWS': 5})
        self.assertEqual(d['SWF']['hits'], [])
        self.assertGreater(d['SWF']['filesWithOptimizedABC'], 8)
        self.assertEqual(d['SWF']['filesWithStandardActionTags'], 8)
        self.assertEqual(d['SWF']['optimizedABCMetadataFailures'], [])
        self.assertEqual(d['SWF']['optimizedABCNamePoolHits'], [])
        self.assertEqual(d['localConfig']['lineCount'], 3)
        self.assertTrue(d['localConfig']['roundTripMatchesOriginal'])
        self.assertFalse(d['scriptBodyRecovered'])
        self.assertIsNone(d['externalOBB']['containsQuestScripts'])
        self.assertGreater(len(d['unknown']), 0)

    @unittest.skipUnless((RAW / 'vox-directories-v1.json').is_file(), 'private original audio report is not present')
    def test_actual_audio_native_lookup(self):
        d = json.loads((RAW / 'vox-directories-v1.json').read_text())
        self.assertEqual({k: v['count'] for k, v in d.items()}, {'Initial_soundpack.voxpack': 1525, 'setup.voxpack': 1})
        for row in d.values():
            native = row['native']
            self.assertEqual(native['allMemberNamesOrdinalsAndRangesNativeVerified'], row['count'])
            self.assertTrue(native['badMagicRejected'] and native['shortHeaderRejected'] and native['missingNameRejected'])
            self.assertFalse(row['CRCValidated'])

    @unittest.skipUnless(HAS_PRIVATE_REPORT, 'private original v2 DLC report is not present')
    def test_tutorial_dlc_has_no_extra_packages(self):
        d = json.loads((RAW / AUDIT_NAME).read_text())
        self.assertEqual(d['DLCWorldDependencies']['DLC10'], {'worldname': ['tutorial.wld'], 'files': []})
        self.assertEqual(d['DLCWorldDependencies']['DLC9']['files'], [])

    def test_no_source_or_save_output_destination(self):
        # Evidence destinations are ignored raw paths; no runtime/production output.
        self.assertTrue(RAW.is_relative_to(ROOT / 'analysis/raw'))
        self.assertNotEqual(RAW, ROOT / 'game-data')

    def test_original_optimized_tag300_is_counted(self):
        # Minimal framing fixture only; no assertion of executable ABC content.
        tag = struct.pack('<HI', 300 << 6 | 63, 8) + bytes(8)
        swf = b'FWS\x0b' + struct.pack('<I', 13 + len(tag) + 2) + bytes(5) + tag + bytes(2)
        self.assertEqual(swf_actions(swf), {300: 1})


if __name__ == '__main__':
    unittest.main()
