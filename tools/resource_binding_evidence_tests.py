"""Fail-closed checks for original completion/binding evidence, without GL mocks."""
import json
import tempfile
import unittest
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from resource_binding_evidence import ROOT, verify_native
from terrain_draw_evidence import verify_mcp_record

NATIVE = ROOT/'analysis/raw/beff-native/library.so'


@unittest.skipUnless(NATIVE.is_file(), 'Original native input stays private')
class ResourceBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = NATIVE.read_bytes()
        cls.image = NativeImage(cls.raw)

    def test_original_checks_do_not_claim_every_return_is_a_draw_gate(self):
        report = verify_native(self.image)
        self.assertEqual(report['sha256'], NATIVE_SHA256)
        self.assertFalse(report['vertexBinderReturnIsUniversalDrawGate'])
        self.assertFalse(report['materialSelectionReturnIsCheckedByObservedMeshCaller'])

    def test_changed_native_build_is_refused(self):
        changed = bytearray(self.raw)
        changed[-1] ^= 1
        with self.assertRaises(ValueError):
            NativeImage(changed)

    def test_changed_task_publish_bind_or_guard_bytes_are_refused(self):
        image = self.image
        for changed in (0x142bf98, 0x142bfdc, 0x141b298, 0x1474328,
                        0x14741b0, 0x1414850, 0x14779ac, 0x142477c):
            class Changed:
                elf = image.elf
                disassembler = image.disassembler
                imports = image.imports
                routine = image.routine

                def read(self, at, size):
                    raw = image.read(at, size)
                    return bytes([raw[0] ^ 1])+raw[1:] if at == changed else raw
            with self.subTest(address=hex(changed)), self.assertRaises(ValueError):
                verify_native(Changed())

    def test_short_guard_is_not_the_following_batch_function(self):
        guard, _ = self.image.routine(0x1477984)
        batch, _ = self.image.routine(0x1477a08)
        self.assertEqual(int(guard['start'], 16)+guard['size'], int(batch['start'], 16))
        self.assertEqual(guard['size'], 132)

    def test_untrusted_mcp_identity_and_memory_are_rejected(self):
        # Deliberately invalid validation fixtures, never research observations.
        baseline = {'program': {'sha256': NATIVE_SHA256, 'image_base': '00000000',
                                'language_id': 'AARCH64:LE:64:v8A'},
                    'queries': [{'request': {'tool': 'read_memory',
                                 'args': {'address': '02494f30', 'length': 8}},
                                 'result': {'gaps': [], 'hex': '00 '*8}}]}
        with tempfile.TemporaryDirectory(prefix='oc2-invalid-evidence-') as tmp:
            p = Path(tmp)/'invalid.json'
            for field, value in (('sha256', '0'*64), ('image_base', '00001000'),
                                 ('language_id', 'x86:LE:64:default'), (None, None)):
                record = json.loads(json.dumps(baseline))
                if field is not None:
                    record['program'][field] = value
                p.write_text(json.dumps(record))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    verify_mcp_record(self.image, p, relative_relocations=True)


if __name__ == '__main__':
    unittest.main()
