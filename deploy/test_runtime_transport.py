"""Small synthetic build-transport checks; no original resources or services."""
import copy
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
import zlib

import runtime_transport as transport


def descriptor(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def stored_bytes(raw):
    target = io.BytesIO()
    writer = transport._StoredWriter(target)
    # Uneven pieces prove that caller/XZ boundaries do not reset DEFLATE blocks.
    for offset in range(0, len(raw), 17011):
        writer.feed(raw[offset:offset + 17011])
    row = writer.finish()
    result = target.getvalue()
    assert descriptor(result) == row
    return result


def synthetic_tar(payload=None):
    import tarfile
    payload = bytes(range(256)) * 600 if payload is None else payload
    target = io.BytesIO()
    with tarfile.open(fileobj=target, mode='w') as archive:
        for name, raw in [('bundle-manifest.json', b'{"localSavesImported":false}'),
                          ('original/' + 'long-name-' * 16 + '.data', payload)]:
            member = tarfile.TarInfo(name)
            member.mode, member.mtime, member.size = 0o600, 0, len(raw)
            archive.addfile(member, io.BytesIO(raw))
    return target.getvalue()


def make_fixture(root, split_points=(), raw_tar=None):
    """Shared pure-host fixture for package tests; no second encoder needed."""
    directory = Path(root) / 'deploy'
    directory.mkdir(parents=True, exist_ok=True)
    raw = synthetic_tar() if raw_tar is None else raw_tar
    offsets = [0, *split_points, len(raw)]
    packed = b''.join(lzma.compress(raw[left:right], format=lzma.FORMAT_XZ, preset=0)
                      for left, right in zip(offsets, offsets[1:]))
    stored = stored_bytes(raw)
    plan = {'format': transport.FORMAT, 'encoding': transport.ENCODING,
            'canonicalGzip': descriptor(gzip.compress(raw, mtime=0)),
            'xz': descriptor(packed), 'tar': descriptor(raw), 'storedGzip': descriptor(stored)}
    (directory / transport.XZ_NAME).write_bytes(packed)
    (directory / transport.PLAN_NAME).write_text(json.dumps(plan) + '\n')
    (directory / transport.SIDECAR_NAME).write_text(plan['storedGzip']['sha256'] + '  ' + transport.GZIP_NAME + '\n')
    return {'plan': plan, 'tar': raw, 'xz': packed, 'storedGzip': stored, 'directory': directory}


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.fixture = make_fixture(self.root)
        self.directory = self.fixture['directory']

    def plan(self):
        return copy.deepcopy(self.fixture['plan'])

    def save_plan(self, plan):
        (self.directory / transport.PLAN_NAME).write_text(json.dumps(plan) + '\n')
        (self.directory / transport.SIDECAR_NAME).write_text(plan['storedGzip']['sha256'] + '  ' + transport.GZIP_NAME + '\n')

    def clean_failure(self, operation=transport.reconstruct):
        with self.assertRaises((transport.TransportError, ValueError, OSError)):
            operation(self.root)
        self.assertFalse((self.directory / transport.GZIP_NAME).exists())
        self.assertEqual(list(self.directory.glob('.private-runtime.transport-*')), [])
        self.assertTrue((self.directory / transport.XZ_NAME).is_file())
        self.assertTrue((self.directory / transport.PLAN_NAME).is_file())

    def test_exact_single_xz_output_is_standard_gzip(self):
        canonical = self.directory / 'canonical-evidence.gz'
        canonical.write_bytes(gzip.compress(self.fixture['tar'], mtime=0))
        canonical_before = canonical.read_bytes()
        report = transport.reconstruct(self.root)
        raw = (self.directory / transport.GZIP_NAME).read_bytes()
        self.assertEqual(raw, self.fixture['storedGzip'])
        self.assertEqual(gzip.decompress(raw), self.fixture['tar'])
        self.assertTrue(report['reconstructed'])
        self.assertEqual(report['members'], 2)
        self.assertEqual((self.directory / transport.GZIP_NAME).stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.directory / transport.XZ_NAME).exists())
        self.assertFalse((self.directory / transport.PLAN_NAME).exists())
        self.assertTrue((self.directory / transport.SIDECAR_NAME).is_file())
        self.assertEqual(canonical.read_bytes(), canonical_before)

    def test_block_bits_lengths_crc_and_isize_are_exact(self):
        raw, original = self.fixture['storedGzip'], self.fixture['tar']
        self.assertEqual(raw[:10], bytes.fromhex('1f8b08000000000000ff'))
        cursor, restored, lengths = 10, bytearray(), []
        while raw[cursor] == 0:
            size, complement = struct.unpack_from('<HH', raw, cursor + 1)
            self.assertEqual(complement, size ^ 0xffff)
            self.assertLessEqual(size, 65535)
            lengths.append(size)
            restored.extend(raw[cursor + 5:cursor + 5 + size])
            cursor += 5 + size
        self.assertEqual(lengths[:-1], [65535] * (len(lengths) - 1))
        self.assertEqual(raw[cursor:cursor + 5], bytes.fromhex('010000ffff'))
        self.assertEqual(raw[cursor + 5:], struct.pack('<II', zlib.crc32(original), len(original) & 0xffffffff))
        self.assertEqual(restored, original)

    def test_multiple_xz_streams_keep_global_block_offsets(self):
        fixture = make_fixture(self.root, split_points=(123, 80001, 131079))
        transport.reconstruct(self.root)
        self.assertEqual((self.directory / transport.GZIP_NAME).read_bytes(), self.fixture['storedGzip'])
        self.assertEqual(fixture['tar'], self.fixture['tar'])

    def test_unknown_missing_bool_and_ambiguous_identity_rejected(self):
        variants = []
        value = self.plan(); value['extra'] = 1; variants.append(value)
        value = self.plan(); del value['tar']; variants.append(value)
        value = self.plan(); value['xz']['bytes'] = True; variants.append(value)
        value = self.plan(); value['xz']['sha256'] = 'F' * 64; variants.append(value)
        value = self.plan(); value['xz']['path'] = 'https://invalid'; variants.append(value)
        value = self.plan(); value['storedGzip']['bytes'] += 1; variants.append(value)
        value = self.plan(); value['xz']['sha256'] = value['tar']['sha256']; variants.append(value)
        for plan in variants:
            with self.subTest(plan=plan):
                with self.assertRaises(transport.TransportError):
                    transport.validate_plan(plan)

    def test_duplicate_json_keys_refused(self):
        path = self.directory / transport.PLAN_NAME
        path.write_text('{"format":"a","format":"b"}')
        self.clean_failure()

    def test_bad_xz_sha_or_size_refused(self):
        for field, value in [('sha256', '0' * 64), ('bytes', 1)]:
            plan = self.plan(); plan['xz'][field] = value; self.save_plan(plan)
            self.clean_failure()

    def test_corrupt_xz_with_matching_input_sha_is_refused(self):
        raw = bytearray(self.fixture['xz']); raw[len(raw) // 2] ^= 128
        plan = self.plan(); plan['xz'] = descriptor(raw); self.save_plan(plan)
        (self.directory / transport.XZ_NAME).write_bytes(raw)
        self.clean_failure()

    def test_truncated_xz_and_trailing_garbage_refused(self):
        for raw in [self.fixture['xz'][:-8], self.fixture['xz'] + b'not-another-xz']:
            plan = self.plan(); plan['xz'] = descriptor(raw); self.save_plan(plan)
            (self.directory / transport.XZ_NAME).write_bytes(raw)
            self.clean_failure()

    def test_corrupt_tar_even_with_matching_declared_hashes_refused(self):
        raw = bytearray(self.fixture['tar']); raw[0] ^= 1
        make_fixture(self.root, raw_tar=bytes(raw))
        self.clean_failure()

    def test_wrong_tar_identity_and_short_expected_length_refused(self):
        plan = self.plan(); plan['tar']['sha256'] = '0' * 64; self.save_plan(plan)
        self.clean_failure()
        plan = self.plan(); plan['tar']['bytes'] -= 512
        plan['storedGzip']['bytes'] = transport.stored_gzip_size(plan['tar']['bytes']); self.save_plan(plan)
        self.clean_failure()

    def test_wrong_expected_output_sha_refused(self):
        plan = self.plan(); plan['storedGzip']['sha256'] = '0' * 64; self.save_plan(plan)
        self.clean_failure()

    def test_existing_target_preserved(self):
        path = self.directory / transport.GZIP_NAME; path.write_bytes(b'preserve')
        with self.assertRaises(transport.TransportError): transport.reconstruct(self.root)
        self.assertEqual(path.read_bytes(), b'preserve')
        self.assertEqual(list(self.directory.glob('.private-runtime.transport-*')), [])

    def test_symlink_input_and_bad_sidecar_refused(self):
        path = self.directory / transport.XZ_NAME; other = self.directory / 'original.xz'
        path.rename(other); path.symlink_to(other)
        self.clean_failure()
        path.unlink(); other.rename(path)
        (self.directory / transport.SIDECAR_NAME).write_text('0' * 64 + '  ' + transport.GZIP_NAME + '\n')
        self.clean_failure()

    def test_changed_source_identity_leaves_no_target(self):
        original = transport._same_file
        def fail_after_decode(path, stream, identity):
            original(path, stream, identity)
            if Path(path).name == transport.XZ_NAME and stream.tell() == len(self.fixture['xz']):
                # First complete hash finishes here; the original failure is
                # propagated, not silently copied/retried as another format.
                raise transport.TransportError('fixture changed identity')
        with mock.patch.object(transport, '_same_file', side_effect=fail_after_decode):
            self.clean_failure()

    def test_uri_api_and_arbitrary_cli_refused(self):
        with self.assertRaises(transport.TransportError):
            transport.verify_file('https://invalid/input', self.plan()['xz'])
        with mock.patch.object(transport.sys, 'argv', ['runtime_transport.py', '--plan', '/other']):
            with self.assertRaises(transport.TransportError): transport.main()


if __name__ == '__main__':
    unittest.main()
