"""Source-independent ZIP boundaries; private source audit skips when absent."""
import io
import json
import struct
import unittest
import warnings
import zipfile

from tutorial_script_bdae_audit import RAW, inspect_zip, bres_header, payload_shape


def make_zip(members, method=zipfile.ZIP_STORED):
    stream = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', UserWarning)
        with zipfile.ZipFile(stream, 'w', compression=method) as archive:
            for name, data in members:
                archive.writestr(name, data)
    return stream.getvalue()


def mock_bres():
    # Header fixture only, never treated as a complete parsed game model.
    return b'BRES\xfe\xff\0\0' + struct.pack('<II', 64, 64) + bytes(48)


class BDAEContainerTests(unittest.TestCase):
    def test_source_named_stored_bres_header(self):
        d = inspect_zip(make_zip([('little_endian_not_quantized.bdae', mock_bres())]))
        self.assertEqual(d['members'][0]['classification'], 'original-named-BRES-model')
        self.assertFalse(d['ordinaryModelBodySearchPerformed'])
        self.assertFalse(d['members'][0]['decodedCRCValidated'])

    def test_extension_alone_does_not_hide_script(self):
        d = inspect_zip(make_zip([('little_endian_not_quantized.bdae', b'\x1bLua tutorial_quest202')]))
        self.assertEqual(d['anomalies'][0]['shape'], 'Lua-bytecode-magic')
        self.assertEqual(d['anomalyHits'][0]['hits'][0]['name'], 'tutorial_quest202')
        self.assertTrue(d['anomalies'][0]['decodedCRCValidated'])

    def test_unexpected_member_compression_and_crc(self):
        d = inspect_zip(make_zip([('extra.dat', b'tutorial_npc972_ai')], zipfile.ZIP_DEFLATED))
        self.assertEqual(d['anomalies'][0]['method'], zipfile.ZIP_DEFLATED)
        self.assertTrue(d['anomalies'][0]['decodedCRCValidated'])

    def test_unexpected_crc_failure_is_not_false_negative(self):
        data = bytearray(make_zip([('extra.dat', b'tutorial_quest202')]))
        pos = data.find(b'tutorial_quest202')
        data[pos] ^= 1
        with self.assertRaises(zipfile.BadZipFile):
            inspect_zip(bytes(data))

    def test_local_central_name_disagreement_rejected(self):
        data = bytearray(make_zip([('extra.dat', b'{}')]))
        data[30] ^= 1
        with self.assertRaisesRegex(ValueError, 'local/central'):
            inspect_zip(bytes(data))

    def test_local_central_size_disagreement_rejected(self):
        data = bytearray(make_zip([('extra.dat', b'{}')]))
        struct.pack_into('<I', data, 18, 200)
        with self.assertRaisesRegex(ValueError, 'CRC or sizes'):
            inspect_zip(bytes(data))

    def test_duplicate_names_not_silently_selected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            inspect_zip(make_zip([('same.dat', b'a'), ('same.dat', b'b')]))

    def test_nested_container_remains_explicit(self):
        inner = make_zip([('tutorial.lua', b'print(1)')])
        d = inspect_zip(make_zip([('extra.bin', inner)]))
        self.assertEqual(d['anomalies'][0]['shape'], 'nested-ZIP-magic')

    def test_unknown_encoding_is_not_transformed(self):
        self.assertEqual(payload_shape(b'\0\xff\x85'), 'unknown-binary')
        self.assertFalse(bres_header(b'file.bdae' + bytes(64), 64))

    @unittest.skipUnless((RAW / 'audit-v1.json').is_file(), 'private original BDAE audit is not present')
    def test_private_actual_coverage(self):
        d = json.loads((RAW / 'audit-v1.json').read_text())
        self.assertEqual(d['scope']['selectedOuterBDAE'], 10224)
        self.assertEqual(d['summary']['outerClasses'], {'raw-BRES-already-in-old-scan': 44, 'real-ZIP': 10180})
        self.assertEqual(d['summary']['innerMembers'], 34579)
        self.assertEqual(d['summary']['innerMethods'], {'0': 34579})
        self.assertEqual(d['summary']['currentTutorialOuterRecords'], 179)
        self.assertEqual(d['summary']['errors'], 0)
        self.assertEqual(d['summary']['anomalyNameHits'], 0)
        self.assertEqual({r['name']: r['count'] for r in d['anomalyContentMatrix']},
                         {'metadata.xml': 9683, 'thumbnail.txt': 4536})
        self.assertFalse(d['scriptBodyRecovered'])
        self.assertFalse(d['gameRuntimeSaveOrDeploymentChanges'])


if __name__ == '__main__':
    unittest.main()
