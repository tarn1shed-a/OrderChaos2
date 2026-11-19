"""Pure-host tests. Linux snapshot positive/failure controls require --run-linux.

No Unicorn import, Native, Docker, network, actor, clock or service operation.
"""
import argparse
import errno
import hashlib
import json
import mmap
import os
from pathlib import Path
import platform
import struct
import sys
import tempfile
import unittest
from unittest import mock
import weakref

import source_immutable_inputs as source

HERE = Path(__file__).resolve().parent
RUN_LINUX = '--run-linux' in sys.argv


def raw_bres(size=131173):
    data = bytearray((bytes(range(256)) * (size // 256 + 1))[:size])
    data[:8] = b'BRES\xfe\xff\x00\x00'
    struct.pack_into('<II', data, 8, 64, size)
    struct.pack_into('<Q', data, 40, 64)
    struct.pack_into('<Q', data, 64, 80)
    data[80:90] = b'0,0,0,946\0'
    return bytes(data)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='oc2-source-proof-', dir=Path('/tmp').resolve())
        self.root = Path(self.tmp.name)
        self.path = self.root / 'analysis/raw/test.bdae'
        self.path.parent.mkdir(parents=True)
        self.raw = raw_bres()
        self.path.write_bytes(self.raw)
        self.desc = {'path': str(self.path), 'sha256': hashlib.sha256(self.raw).hexdigest()}
        self.env = mock.patch.dict(os.environ, {'OC2_NATIVE_SOURCE_PAGES': '0'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class PortableTests(Fixture):
    def test_generic_stream_verification_no_bres_or_buffer_admission(self):
        self.path.write_bytes(b'\x7fELF test non-BRES input')
        desc = {'path': str(self.path), 'sha256': hashlib.sha256(self.path.read_bytes()).hexdigest()}
        self.assertEqual(source.verify_source(self.root, desc), (self.path, desc['sha256'], self.path.stat().st_size))
        self.assertEqual(source.checked_path(self.root, desc), self.path)
        self.assertFalse(source.is_verified_source(self.path.read_bytes()))

    def test_descriptor_scope_and_symlinks(self):
        for bad in [{}, {**self.desc, 'bytes': 1}, {**self.desc, 'sha256': '0'},
                    {**self.desc, 'sha256': 'G' * 64}, {**self.desc, 'path': self.root / 'outside.bdae'},
                    {**self.desc, 'path': 'analysis/raw/../test.bdae'}]:
            with self.assertRaises((ValueError, FileNotFoundError)):
                source.verify_source(self.root, bad)
        link = self.path.parent / 'link.bdae'
        link.symlink_to(self.path)
        with self.assertRaises(ValueError):
            source.verify_source(self.root, {**self.desc, 'path': link})
        folder = self.path.parent / 'linked'
        folder.symlink_to(self.path.parent, target_is_directory=True)
        with self.assertRaises(ValueError):
            source.verify_source(self.root, {**self.desc, 'path': folder / self.path.name})

    def test_bad_sha_and_changed_identity(self):
        with self.assertRaises(ValueError):
            source.verify_source(self.root, {**self.desc, 'sha256': '0' * 64})
        original = source._stream
        def replace_after_read(fd, destination=None):
            result = original(fd, destination)
            replacement = self.path.with_suffix('.replacement')
            replacement.write_bytes(self.raw)
            os.replace(replacement, self.path)
            return result
        with mock.patch.object(source, '_stream', replace_after_read), self.assertRaises(ValueError):
            source.verify_source(self.root, self.desc)

    def test_regular_file_gate(self):
        directory_desc = {**self.desc, 'path': self.path.parent}
        with self.assertRaises(ValueError):
            source.verify_source(self.root, directory_desc)
        fifo = self.path.parent / 'pipe'
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            source.verify_source(self.root, {**self.desc, 'path': fifo})

    def test_default_bytes_exact_and_not_mmap_branded(self):
        path, raw = source.open_source(self.root, self.desc)
        self.assertEqual(path, self.path)
        self.assertIs(type(raw), bytes)
        self.assertEqual(raw, self.raw)
        self.assertFalse(source.is_verified_source(raw))
        with self.assertRaises(ValueError):
            source.require_source(raw, path)

    def test_zip_header_size_and_truncation_refused(self):
        for raw in [b'PK\x03\x04' + self.raw, self.raw[:24], b'notBRES!' + self.raw[8:],
                    self.raw[:12] + struct.pack('<I', len(self.raw) + 1) + self.raw[16:]]:
            self.path.write_bytes(raw)
            desc = {**self.desc, 'sha256': hashlib.sha256(raw).hexdigest()}
            with self.assertRaises(ValueError):
                source.open_source(self.root, desc)

    def test_unregistered_mmap_and_view_cannot_claim_authentication(self):
        with self.path.open('rb') as file:
            raw = mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            self.assertFalse(source.is_verified_source(raw))
            view = memoryview(raw)
            self.assertFalse(source.is_verified_source(view))
            view.release()
            with self.assertRaises(ValueError):
                source.require_source(raw, self.path, self.desc['sha256'])
        finally:
            raw.close()

    def test_flag_invalid_and_unsupported_platform_never_falls_back(self):
        with mock.patch.dict(os.environ, {'OC2_NATIVE_SOURCE_PAGES': 'yes'}), self.assertRaises(ValueError):
            source.open_source(self.root, self.desc)
        if platform.system() != 'Linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
            with mock.patch.dict(os.environ, {'OC2_NATIVE_SOURCE_PAGES': '1'}), self.assertRaises(source.SourcePageSupportError):
                source.open_source(self.root, self.desc)

    def test_short_write_loop_and_no_zero_write_success(self):
        copied = bytearray()
        def short_write(_, value):
            count = min(7, len(value))
            copied.extend(value[:count])
            return count
        with mock.patch.object(source.os, 'write', short_write):
            source._write_all(-1, b'0123456789abcdefghijk')
        self.assertEqual(copied, b'0123456789abcdefghijk')
        with mock.patch.object(source.os, 'write', return_value=0), self.assertRaises(OSError):
            source._write_all(-1, b'not-written')


@unittest.skipUnless(RUN_LINUX and platform.system() == 'Linux' and platform.machine().lower() in ('x86_64', 'amd64'), 'pending actual Linux --run-linux; no platform emulation')
class LinuxSnapshots(Fixture):
    def setUp(self):
        super().setUp()
        self.on = mock.patch.dict(os.environ, {'OC2_NATIVE_SOURCE_PAGES': '1'})
        self.on.start()
        self.addCleanup(self.on.stop)
        self.addCleanup(self.tmp.cleanup)
        source._require_linux()

    def test_exact_snapshot_and_same_live_weak_cache(self):
        path, raw = source.open_source(self.root, self.desc)
        _, peer = source.open_source(self.root, self.desc)
        self.assertIs(raw, peer)
        self.assertTrue(source.is_verified_source(raw))
        self.assertIs(source.require_source(raw, path, self.desc['sha256'], len(self.raw)), raw)
        self.assertEqual(hashlib.sha256(raw).digest(), hashlib.sha256(self.raw).digest())
        self.assertEqual(raw.find(b'0,0,0,946', 48), self.raw.find(b'0,0,0,946', 48))
        self.assertIs(type(raw[90:110]), bytes)
        self.assertEqual(struct.unpack_from('<Q', raw, 40), (64,))
        for action in [lambda: raw.__setitem__(0, 0), lambda: raw.resize(len(raw) + 1)]:
            with self.assertRaises((TypeError, PermissionError, BufferError)):
                action()
        for args in [(self.path.with_name('other'), None, None), (path, '0' * 64, None), (path, None, len(raw) + 1)]:
            with self.assertRaises(ValueError):
                source.require_source(raw, *args)

    def test_original_rewrite_truncate_does_not_change_published_snapshot(self):
        path, raw = source.open_source(self.root, self.desc)
        self.path.write_bytes(b'original inode changed')
        self.assertEqual(raw[:], self.raw)
        self.path.write_bytes(b'')
        self.assertEqual(raw[:], self.raw)
        self.assertIs(source.require_source(raw, path, self.desc['sha256'], len(self.raw)), raw)
        with self.assertRaises(ValueError):
            source.open_source(self.root, self.desc)

    def test_weak_cache_and_exported_view_own_lifetime(self):
        _, raw = source.open_source(self.root, self.desc)
        ref = weakref.ref(raw)
        view = memoryview(raw)
        del raw
        self.assertIsNotNone(ref())
        self.assertTrue(view.readonly)
        self.assertEqual(bytes(view[:16]), self.raw[:16])
        view.release()
        del view
        self.assertIsNone(ref())  # No helper-owned strong cache/finalizer cycle.

    def test_exported_view_close_failure_keeps_provenance(self):
        path, raw = source.open_source(self.root, self.desc)
        view = memoryview(raw)
        with self.assertRaises(BufferError):
            raw.close()
        self.assertTrue(source.is_verified_source(raw))
        self.assertIs(source.require_source(raw, path), raw)
        view.release()
        raw.close()
        self.assertFalse(source.is_verified_source(raw))
        with self.assertRaises(ValueError):
            source.require_source(raw, path)

    def test_backing_has_no_name_or_rw_descriptor(self):
        import fcntl
        _, raw = source.open_source(self.root, self.desc)
        proof = source._VERIFIED[raw]
        matches = 0
        for name in os.listdir('/proc/self/fd'):
            try:
                fd = int(name)
                info = os.fstat(fd)
            except (OSError, ValueError):
                continue
            if (info.st_dev, info.st_ino) == proof.inode:
                matches += 1
                self.assertEqual(info.st_nlink, 0)
                self.assertEqual(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE, os.O_RDONLY)
                self.assertEqual(info.st_mode & 0o777, 0o400)
        self.assertGreater(matches, 0)

    def test_unsupported_filesystem_refused(self):
        with mock.patch.object(source, '_filesystem_type', return_value=0x01021994), self.assertRaises(source.SourcePageSupportError):
            source.open_source(self.root, self.desc)

    def test_all_prepublication_failures_close_fds_and_delete_names(self):
        directory_fd, _ = source._directory()
        os.close(directory_fd)
        directory = Path('/tmp').resolve() / source._DIRECTORY_NAME
        baseline_names = set(directory.iterdir())
        def failed(*_):
            raise OSError(errno.ENOSPC, 'explicit synthetic failure')
        for name in ['_reserve', '_write_all', '_map_readonly']:
            before_fds = len(os.listdir('/proc/self/fd'))
            with mock.patch.object(source, name, side_effect=failed), self.assertRaises((OSError, source.SourcePageSupportError)):
                source.open_source(self.root, self.desc)
            self.assertEqual(set(directory.iterdir()), baseline_names)
            self.assertEqual(len(os.listdir('/proc/self/fd')), before_fds)
        with mock.patch.object(source.os, 'fsync', side_effect=failed), self.assertRaises(OSError):
            source.open_source(self.root, self.desc)
        self.assertEqual(set(directory.iterdir()), baseline_names)

    def test_independent_backing_full_sha_detects_copy_corruption(self):
        original = source._write_all
        def corrupt(fd, block):
            altered = bytearray(block)
            altered[-1] ^= 1
            original(fd, altered)
        with mock.patch.object(source, '_write_all', corrupt), self.assertRaises(ValueError):
            source.open_source(self.root, self.desc)

    def test_copy_on_write_mapping_cannot_receive_snapshot_provenance(self):
        def unapproved(fd, size):
            return mmap.mmap(fd, size, access=mmap.ACCESS_COPY)
        with mock.patch.object(source, '_map_readonly', unapproved), self.assertRaises(ValueError):
            source.open_source(self.root, self.desc)

    def test_source_changed_during_copy_is_not_published(self):
        original = source._stream
        def changed(fd, destination=None):
            out = original(fd, destination)
            if destination is not None:
                self.path.write_bytes(self.raw + b'changed')
            return out
        with mock.patch.object(source, '_stream', changed), self.assertRaises(ValueError):
            source.open_source(self.root, self.desc)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-linux', action='store_true', help='Explicitly run no-Unicorn Linux disk/mmap controls')
    parser.add_argument('--output', type=Path, default=HERE / 'host-test-result.json')
    args = parser.parse_args()
    assert 'unicorn' not in sys.modules
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    assert 'unicorn' not in sys.modules
    report = {'format': 'oc2-immutable-source-pure-host-tests-v1', 'tests': result.testsRun,
        'passed': result.wasSuccessful(), 'skipped': len(result.skipped),
        'platform': platform.system(), 'linuxRequested': args.run_linux,
        'linuxSnapshotControls': 'executed' if args.run_linux and platform.system() == 'Linux' else 'pending actual Linux; not emulated',
        'NativeUcDockerServiceOrNetworkRun': False, 'UnicornImported': False}
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(not result.wasSuccessful())
