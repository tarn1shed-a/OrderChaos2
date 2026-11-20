"""Small host mappings and explicit Uc mocks; no original library/game needed.

Linux-only tests additionally use tiny official ARM64 Ucs, never original code.
The mock tests exercise storage/lifetime/order on other development platforms;
they do not claim Linux/Unicorn residency or game-computation equivalence.
"""
import ctypes
import errno
import gc
import mmap
import os
import platform
import stat
import tempfile
import threading
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch

import source_code_pages as code
import source_guest_pages as guest


class MockUc:
    def __init__(self, events):
        self._uch = object()
        self.events = events
        self.regs = {'pc': 0x1234, 'sp': 0x20008000}
        self.regions = []
        self.ordinary = []
        self.fail_map = False
        # The finalizer deliberately retains no Uc or bound method.
        def close(handle):
            events.append(('uc_close', handle))
            return 0
        self.close_handle = close
        self._Uc__finalizer = weakref.finalize(self, close, self._uch)

    def mem_regions(self):
        return [(start, start + size - 1, permissions)
                for start, size, permissions, _ in self.regions]

    def mem_map(self, address, size, permissions=7):
        self.ordinary.append((address, size, permissions))

    def mem_map_ptr(self, address, size, permissions, pointer):
        if self.fail_map:
            raise RuntimeError('mock mem_map_ptr failed')
        self.regions.append((address, size, permissions, pointer))

    def mem_read(self, address, size):
        for start, length, _, pointer in self.regions:
            if start <= address and address + size <= start + length:
                return ctypes.string_at(pointer + address - start, size)
        raise AssertionError('Unmapped mock read')

    def mem_write(self, address, value):
        for start, length, _, pointer in self.regions:
            if start <= address and address + len(value) <= start + length:
                ctypes.memmove(pointer + address - start, value, len(value))
                return
        raise AssertionError('Unmapped mock write')


def mock_lifecycle(uc):
    finalizer = getattr(uc, '_Uc__finalizer', None)
    if not isinstance(uc, MockUc) or not finalizer.alive:
        return None
    return finalizer, uc.close_handle, uc._uch


class DefaultAndSupportTests(unittest.TestCase):
    def test_default_wrapper_uses_original_mem_map_and_no_storage(self):
        uc = MockUc([])
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(guest, '_private_file', side_effect=AssertionError):
            self.assertFalse(guest.map_guest_region(uc, 0x1000, 4096, 3))
            self.assertIsNone(guest.map_native_region(uc, 0x1000, 4096, 3))
            self.assertEqual(uc.ordinary, [(0x1000, 4096, 3)])
            self.assertEqual(guest.inspect_guest_pages(uc)['actualMappingCount'], 0)
            self.assertFalse(guest.reclaim_guest_pages(uc)['attempted'])
        uc._Uc__finalizer()

    def test_explicit_on_unsupported_host_never_falls_back(self):
        uc = MockUc([])
        with patch.dict(os.environ, {'OC2_NATIVE_GUEST_PAGES': '1'}), \
                patch.object(guest.platform, 'system', return_value='Darwin'):
            with self.assertRaises(guest.GuestPageSupportError):
                guest.map_native_region(uc, 0x1000, 4096)
        self.assertEqual(uc.ordinary, [])
        uc._Uc__finalizer()

    def test_wrong_page_arch_and_version_are_explicit_errors(self):
        import types
        for system, machine, pagesize, version in [
                ('Linux', 'aarch64', 4096, '2.1.4'),
                ('Linux', 'x86_64', 16384, '2.1.4'),
                ('Linux', 'x86_64', 4096, '2.1.3')]:
            with self.subTest(machine=machine, pagesize=pagesize, version=version), \
                    patch.object(guest.platform, 'system', return_value=system), \
                    patch.object(guest.platform, 'machine', return_value=machine), \
                    patch.object(guest.os, 'sysconf', return_value=pagesize), \
                    patch.dict('sys.modules', {'unicorn': types.SimpleNamespace(__version__=version)}):
                with self.assertRaises(guest.GuestPageSupportError):
                    guest._require_supported()


class MappedHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='oc2-guest-pages-test-', dir='/tmp')
        self.patches = [patch.dict(os.environ, {'OC2_NATIVE_GUEST_PAGES': '1'}),
                        patch.object(guest, '_DIRECTORY', self.temp.name),
                        patch.object(guest, '_require_supported'),
                        patch.object(guest, '_filesystem_type', return_value=0xef53),
                        # Portable host-port fixture only; real Linux reservation
                        # is checked separately without constructing any Uc.
                        patch.object(guest.os, 'posix_fallocate', create=True,
                                     return_value=None),
                        patch.object(code, '_original_finalizer', new=mock_lifecycle),
                        patch.object(guest, '_original_finalizer', new=mock_lifecycle)]
        for item in self.patches:
            item.start()
        self.ucs = []
        self.events = []
        self.quarantine_before = len(code._FAILED_FINALIZATIONS)

    def tearDown(self):
        for uc in self.ucs:
            uc._Uc__finalizer()
        self.ucs.clear()
        gc.collect()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()
        self.assertEqual(len(code._FAILED_FINALIZATIONS), self.quarantine_before)

    def uc(self):
        uc = MockUc(self.events)
        self.ucs.append(uc)
        return uc

    def mapping(self, uc):
        return code._existing_lifetime(uc).mappings[-1]

    def test_private_zeroed_unlinked_0600_files_and_exact_permissions(self):
        a, b = self.uc(), self.uc()
        self.assertIsNone(guest.map_native_region(a, 0x1000, 8192, 3))
        self.assertTrue(guest.map_guest_region(b, 0x1000, 8192, 5))
        ma, mb = self.mapping(a), self.mapping(b)
        self.assertNotEqual(ma.inode, mb.inode)
        self.assertNotEqual(ma.pointer, mb.pointer)
        for item in (ma, mb):
            info = os.fstat(item.fd)
            self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
            self.assertEqual(info.st_nlink, 0)
            self.assertEqual(info.st_size, 8192)
            self.assertEqual(bytes(item.memory), bytes(8192))
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        a.mem_write(0x1010, b'own heap')
        self.assertEqual(b.mem_read(0x1010, 8), bytes(8))
        self.assertEqual(a.mem_regions(), [(0x1000, 0x2fff, 3)])
        self.assertEqual(b.mem_regions(), [(0x1000, 0x2fff, 5)])
        self.assertEqual(a.ordinary + b.ordinary, [])

    def test_reservation_covers_exact_extent_before_pointer_exposure(self):
        uc = self.uc()
        calls = []
        def reserve(fd, offset, length):
            info = os.fstat(fd)
            self.assertEqual((offset, length, info.st_size, info.st_nlink),
                             (0, 8192, 8192, 0))
            self.assertEqual(uc.regions + uc.ordinary, [])
            self.assertIsNone(code._existing_lifetime(uc))
            calls.append((offset, length))
        with patch.object(guest.os, 'posix_fallocate', new=reserve):
            guest.map_native_region(uc, 0x1000, 8192)
        self.assertEqual(calls, [(0, 8192)])
        self.assertEqual(bytes(self.mapping(uc).memory), bytes(8192))

    def test_reservation_failure_closes_unlinked_file_without_mapping_or_fallback(self):
        cases = [None, NotImplementedError('no allocation interface'),
                 OSError(errno.ENOSPC, 'full'),
                 OSError(errno.EOPNOTSUPP, 'unsupported filesystem'),
                 OSError(errno.ENOSYS, 'unsupported operation')]
        real_close = os.close
        for failure in cases:
            with self.subTest(failure=repr(failure)):
                uc = self.uc()
                replacement = (patch.object(guest.os, 'posix_fallocate', new=None)
                               if failure is None else
                               patch.object(guest.os, 'posix_fallocate',
                                            side_effect=failure))
                with replacement, patch.object(guest.os, 'close',
                                                wraps=real_close) as closed:
                    with self.assertRaises(guest.GuestPageSupportError) as caught:
                        guest.map_native_region(uc, 0x1000, 4096)
                if failure is not None:
                    self.assertIs(caught.exception.__cause__, failure)
                self.assertGreaterEqual(closed.call_count, 2)  # file + directory
                for call in closed.call_args_list:
                    with self.assertRaises(OSError) as error:
                        os.fstat(call.args[0])
                    self.assertEqual(error.exception.errno, errno.EBADF)
                self.assertEqual(list(Path(self.temp.name).iterdir()), [])
                self.assertEqual(uc.regions + uc.ordinary, [])
                self.assertIsNone(code._existing_lifetime(uc))
                self.assertTrue(uc._Uc__finalizer.alive)

    def test_reclaim_preserves_exact_bytes_pointer_object_and_registers(self):
        uc = self.uc()
        guest.map_native_region(uc, 0x1000, 8192)
        guest.map_native_region(uc, 0x10000, 4096)
        uc.mem_write(0x1000, bytes(range(256)) * 32)
        uc.mem_write(0x10020, b'live queue/rng/clock bytes')
        owner = code._existing_lifetime(uc)
        mappings = tuple(owner.mappings)
        pointers = [item.pointer for item in mappings]
        snapshots = [bytes(item.memory) for item in mappings]
        regs = dict(uc.regs)
        handle = uc._uch
        for _ in range(2):
            result = guest.reclaim_guest_pages(uc)
            self.assertTrue(result['reclaimed'])
            self.assertEqual(len(result['flushed']), 2)
            self.assertEqual(len(result['advised']), 2)
            self.assertIs(code._existing_lifetime(uc), owner)
            self.assertIs(uc._uch, handle)
            self.assertEqual(uc.regs, regs)
            self.assertEqual([item.pointer for item in mappings], pointers)
            self.assertEqual([bytes(item.memory) for item in mappings], snapshots)
        self.assertEqual(guest.inspect_guest_pages(uc)['actualMappingCount'], 2)
        self.assertEqual([item.reclaims for item in mappings], [2, 2])
        uc.mem_write(0x1000, b'after reclaim')
        self.assertEqual(uc.mem_read(0x1000, 13), b'after reclaim')
        self.assertEqual(self.events, [])  # Reclaim did not close/reset the Uc.

    def test_all_flushes_precede_any_advice_and_failure_keeps_storage(self):
        uc = self.uc()
        guest.map_native_region(uc, 0x1000, 4096)
        guest.map_native_region(uc, 0x2000, 4096)
        mappings = code._existing_lifetime(uc).mappings
        events = []
        class Memory:
            def __init__(self, original, number, failure=None):
                self.original, self.number, self.failure = original, number, failure
            def flush(self):
                events.append(('flush', self.number))
                if self.failure == 'flush':
                    raise OSError('synthetic flush failure')
                self.original.flush()
            def madvise(self, advice):
                events.append(('madvise', self.number))
                if self.failure == 'madvise':
                    raise OSError('synthetic advice failure')
                self.original.madvise(advice)
            def close(self):
                self.original.close()
        originals = [item.memory for item in mappings]
        for stage in ('flush', 'madvise', None):
            events.clear()
            for index, item in enumerate(mappings):
                item.memory = Memory(originals[index], index,
                                     stage if index == 1 else None)
            if stage is None:
                self.assertTrue(guest.reclaim_guest_pages(uc)['reclaimed'])
            else:
                with self.assertRaises(guest.GuestPageReclaimError) as caught:
                    guest.reclaim_guest_pages(uc)
                self.assertEqual(caught.exception.stage, stage)
                self.assertFalse(caught.exception.receipt['reclaimed'])
                self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertEqual(events[:2], [('flush', 0), ('flush', 1)])
            self.assertEqual(events[2:], [] if stage == 'flush' else
                             [('madvise', 0), ('madvise', 1)])
            self.assertFalse(any(item.closed for item in mappings))
            self.assertEqual(self.events, [])
        for item, original in zip(mappings, originals):
            item.memory = original

    def test_one_official_close_then_all_rx_and_guest_backings(self):
        uc = self.uc()
        closed = []
        class Rx:
            def close(self):
                self.assert_engine_closed = bool(self_events)
                closed.append(self.assert_engine_closed)
        self_events = self.events
        rx = Rx()
        owner = code._attach_mapping(uc, rx)
        finalizer = uc._Uc__finalizer
        guest.map_native_region(uc, 0x1000, 4096)
        guest.map_native_region(uc, 0x2000, 4096)
        self.assertIs(uc._Uc__finalizer, finalizer)
        self.assertEqual(len(owner.mappings), 3)
        finalizer()
        finalizer()
        code._close_then_release(uc.close_handle, uc._uch, owner)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(closed, [True])
        self.assertEqual(owner.order, ['uc_close'] + ['mmap_close'] * 3)
        self.assertTrue(owner.mapping_closed)
        for item in owner.mappings[1:]:
            self.assertTrue(item.memory.closed)
            with self.assertRaises(OSError):
                os.fstat(item.fd)

    def test_guest_first_then_second_backing_uses_same_owner(self):
        uc = self.uc()
        guest.map_native_region(uc, 0x1000, 4096)
        owner = code._existing_lifetime(uc)
        class OtherBacking:
            def close(self):
                pass
        self.assertIs(code._attach_mapping(uc, OtherBacking()), owner)
        self.assertEqual(len(owner.mappings), 2)

    def test_changed_handle_or_finalizer_is_refused_without_touching_mapping(self):
        uc = self.uc()
        guest.map_native_region(uc, 0x1000, 4096)
        handle, finalizer = uc._uch, uc._Uc__finalizer
        uc.mem_write(0x1000, b'keep exact bytes')
        uc._uch = object()
        try:
            with self.assertRaisesRegex(ValueError, 'lifetime'):
                guest.reclaim_guest_pages(uc)
        finally:
            uc._uch = handle
        uc._Uc__finalizer = object()
        try:
            with self.assertRaisesRegex(ValueError, 'lifetime'):
                guest.map_native_region(uc, 0x2000, 4096)
        finally:
            uc._Uc__finalizer = finalizer
        self.assertEqual(uc.mem_read(0x1000, 16), b'keep exact bytes')
        self.assertEqual(guest.inspect_guest_pages(uc)['actualMappingCount'], 1)
        self.assertEqual(self.events, [])

    def test_unknown_lifecycle_bad_shape_overlap_and_cross_thread_refused(self):
        with self.assertRaises(guest.GuestPageSupportError):
            guest.map_native_region(object(), 0x1000, 4096)
        uc = self.uc()
        for address, size, permissions in [(True, 4096, 7), (1, 4096, 7),
                (0, 0, 7), (0, 4095, 7), (0, 4096, 8), (1 << 64, 4096, 7)]:
            with self.subTest(address=address, size=size, permissions=permissions):
                with self.assertRaises(ValueError):
                    guest.map_native_region(uc, address, size, permissions)
        guest.map_native_region(uc, 0x1000, 4096)
        with self.assertRaisesRegex(ValueError, 'overlap'):
            guest.map_native_region(uc, 0x1000, 4096)
        errors = []
        def other_thread():
            try:
                guest.reclaim_guest_pages(uc)
            except Exception as error:
                errors.append(error)
        thread = threading.Thread(target=other_thread)
        thread.start()
        thread.join()
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ValueError)
        self.assertEqual(guest.inspect_guest_pages(uc)['actualMappingCount'], 1)

    def test_failed_pointer_map_closes_entire_owner_without_fallback(self):
        uc = self.uc()
        guest.map_native_region(uc, 0x1000, 4096)
        owner = code._existing_lifetime(uc)
        uc.fail_map = True
        with self.assertRaisesRegex(RuntimeError, 'mem_map_ptr'):
            guest.map_native_region(uc, 0x2000, 4096)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(uc.ordinary, [])
        self.assertIsNone(uc._uch)
        self.assertTrue(owner.mapping_closed)
        self.assertEqual(owner.order, ['uc_close', 'mmap_close', 'mmap_close'])

    def test_unsupported_filesystem_and_directory_rejected_before_mapping(self):
        uc = self.uc()
        for filesystem in guest._MEMORY_FILESYSTEMS:
            with self.subTest(filesystem=filesystem), \
                    patch.object(guest, '_filesystem_type', return_value=filesystem):
                with self.assertRaises(guest.GuestPageSupportError):
                    guest.map_native_region(uc, 0x1000, 4096)
        with patch.object(guest, '_DIRECTORY', '/data/must-not-create'):
            with self.assertRaises(ValueError):
                guest.map_native_region(uc, 0x1000, 4096)
        Path(self.temp.name).chmod(0o755)
        try:
            with self.assertRaisesRegex(ValueError, 'owner-only'):
                guest.map_native_region(uc, 0x1000, 4096)
        finally:
            Path(self.temp.name).chmod(0o700)
        self.assertEqual(uc.mem_regions(), [])
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_bound_callback_cycle_has_no_strong_registry_uc_reference(self):
        uc = self.uc()
        guest.map_native_region(uc, 0x1000, 4096)
        guest.map_native_region(uc, 0x2000, 4096)
        owner = code._existing_lifetime(uc)
        uc.callback = uc.mem_read  # Explicit cycle, like a bound Uc hook owner.
        reference = weakref.ref(uc)
        self.ucs.remove(uc)
        del uc
        gc.collect()
        self.assertIsNone(reference())
        self.assertTrue(owner.engine_closed)
        self.assertTrue(owner.mapping_closed)
        self.assertEqual(len(self.events), 1)


class AggregateFailureTests(unittest.TestCase):
    def test_failed_engine_close_quarantines_all_and_never_retries(self):
        events, quarantine = [], []
        class Mapping:
            def close(self):
                events.append('mapping')
        owner = code._Lifetime(Mapping())
        owner.add(Mapping())
        def fail(handle):
            events.append('uc')
            return 3
        for _ in range(2):
            code._close_then_release(fail, object(), owner, quarantine)
        self.assertEqual(events, ['uc'])
        self.assertEqual(quarantine, [owner])
        self.assertEqual(len(owner.mappings), 2)
        self.assertFalse(owner.engine_closed)
        self.assertFalse(owner.mapping_closed)

    def test_backing_failure_quarantines_group_and_preserves_remaining(self):
        events, quarantine = [], []
        class Mapping:
            def __init__(self, name, failure=False):
                self.name, self.failure = name, failure
            def close(self):
                events.append(self.name)
                if self.failure:
                    raise OSError('synthetic mapping close failure')
        owner = code._Lifetime(Mapping('first'))
        owner.add(Mapping('failure', True))
        owner.add(Mapping('must remain'))
        code._close_then_release(lambda handle: 0, object(), owner, quarantine)
        self.assertEqual(events, ['first', 'failure'])
        self.assertEqual(quarantine, [owner])
        self.assertTrue(owner.engine_closed)
        self.assertFalse(owner.mapping_closed)
        self.assertEqual(owner.closed_mappings, 1)


@unittest.skipUnless(platform.system() == 'Linux',
                     'actual posix_fallocate storage check requires Linux')
class LinuxReservationTests(unittest.TestCase):
    def test_real_reserved_range_is_zeroed_private_and_closed(self):
        if not hasattr(os, 'posix_fallocate'):
            self.skipTest('Linux Python has no posix_fallocate interface')
        with tempfile.TemporaryDirectory(prefix='oc2-guest-reserve-', dir='/tmp') as directory, \
                patch.object(guest, '_DIRECTORY', directory):
            fd, inode, filesystem = guest._private_file(8192)
            try:
                info = os.fstat(fd)
                self.assertEqual((info.st_dev, info.st_ino), inode)
                self.assertNotIn(filesystem, guest._MEMORY_FILESYSTEMS)
                self.assertEqual((info.st_size, info.st_nlink), (8192, 0))
                self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
                self.assertGreaterEqual(info.st_blocks * 512, 8192)
                self.assertEqual(os.pread(fd, 8192, 0), bytes(8192))
                self.assertEqual(list(Path(directory).iterdir()), [])
            finally:
                os.close(fd)
            with self.assertRaises(OSError) as error:
                os.fstat(fd)
            self.assertEqual(error.exception.errno, errno.EBADF)


@unittest.skipUnless(platform.system() == 'Linux' and
                     platform.machine().lower() in ('amd64', 'x86_64'),
                     'real tiny Uc control requires supported Linux amd64')
class TinyOfficialUcTests(unittest.TestCase):
    def test_same_real_uc_peer_isolation_registers_bytes_and_cleanup(self):
        try:
            import unicorn
        except ImportError:
            self.skipTest('Unicorn not installed')
        if unicorn.__version__ != '2.1.4':
            self.skipTest('Official Unicorn 2.1.4 required')
        if os.sysconf('SC_PAGE_SIZE') != 4096:
            self.skipTest('4 KiB host pages required')
        from unicorn import arm64_const as reg
        with patch.dict(os.environ, {'OC2_NATIVE_GUEST_PAGES': '1'}), \
                tempfile.TemporaryDirectory(prefix='oc2-guest-tiny-', dir='/tmp') as directory, \
                patch.object(guest, '_DIRECTORY', directory):
            a = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
            b = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
            guest.map_native_region(a, 0x1000, 4096)
            guest.map_native_region(a, 0x10000, 8192)
            guest.map_native_region(b, 0x1000, 4096)
            # Real tiny ARM64 instructions only: mov x0,#42; ret.
            a.mem_write(0x1000, bytes.fromhex('400580d2c0035fd6'))
            a.reg_write(reg.UC_ARM64_REG_X30, 0x1008)
            a.emu_start(0x1000, 0x1008)
            a.mem_write(0x10020, b'exact live heap')
            before = a.context_save()
            snapshots = (bytes(a.mem_read(0x1000, 4096)),
                         bytes(a.mem_read(0x10000, 8192)))
            owner = code._existing_lifetime(a)
            pointers = [item.pointer for item in owner.mappings]
            self.assertTrue(guest.reclaim_guest_pages(a)['reclaimed'])
            self.assertEqual(a.reg_read(reg.UC_ARM64_REG_X0), 42)
            self.assertEqual(bytes(a.context_save()), bytes(before))
            self.assertEqual(snapshots, (bytes(a.mem_read(0x1000, 4096)),
                                        bytes(a.mem_read(0x10000, 8192))))
            self.assertEqual([item.pointer for item in owner.mappings], pointers)
            self.assertEqual(bytes(b.mem_read(0x1000, 4096)), bytes(4096))
            b.mem_write(0x1000, b'peer remains')
            ref = weakref.ref(a)
            del a
            gc.collect()
            self.assertIsNone(ref())
            self.assertEqual(owner.order, ['uc_close', 'mmap_close', 'mmap_close'])
            self.assertEqual(bytes(b.mem_read(0x1000, 12)), b'peer remains')
            del b
            gc.collect()


if __name__ == '__main__':
    unittest.main()
