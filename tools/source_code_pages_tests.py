"""Public negative controls plus optional exact-private-library Linux tests.

Run --library /private/libOrderChaos2.so for real small-Uc checks. The library
is never changed or committed. At most two Ucs coexist; no game is loaded.
"""
import argparse
import gc
import hashlib
import json
import os
import platform
import struct
import subprocess
import sys
import tempfile
import unittest
import weakref
from pathlib import Path
from unittest.mock import patch
import source_code_pages as pages

LIBRARY = None


def collect(obj):
    reference = weakref.ref(obj)
    return reference


class PublicControls(unittest.TestCase):
    def test_disabled_and_other_platform_keep_copy(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(pages.create_code_pages(b'untrusted'))
        with patch.dict(os.environ, {'OC2_NATIVE_CODE_PAGES': '1'}):
            with patch.object(pages.platform, 'system', return_value='Darwin'):
                self.assertIsNone(pages.create_code_pages(b'untrusted'))
            with patch.object(pages.platform, 'machine', return_value='aarch64'):
                self.assertIsNone(pages.create_code_pages(b'untrusted'))

    @unittest.skipUnless(platform.system() == 'Linux' and platform.machine() == 'x86_64', 'Linux x86_64 only')
    def test_enabled_unknown_image_is_refused(self):
        with patch.dict(os.environ, {'OC2_NATIVE_CODE_PAGES': '1'}):
            with self.assertRaises(ValueError):
                pages.create_code_pages(b'untrusted')

    def test_close_failure_cannot_unmap_live_backing(self):
        class Mapping:
            def close(self):
                raise AssertionError('Must not unmap after unknown engine close')
        lifetime = pages._Lifetime(Mapping())
        before = len(pages._FAILED_FINALIZATIONS)
        pages._close_then_release(lambda handle: 7, object(), lifetime)
        self.assertFalse(lifetime.engine_closed)
        self.assertFalse(lifetime.mapping_closed)
        self.assertEqual(lifetime.order, [])
        self.assertTrue(lifetime.error)
        self.assertIs(pages._FAILED_FINALIZATIONS.pop(), lifetime)
        self.assertEqual(len(pages._FAILED_FINALIZATIONS), before)


@unittest.skipUnless(LIBRARY, 'exact private library supplied only for local Linux checks')
class PrivateLibraryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            raise unittest.SkipTest('Linux x86_64 only')
        import unicorn
        if unicorn.__version__ != '2.1.4':
            raise unittest.SkipTest('Exact official lifecycle version only')
        cls.raw = Path(LIBRARY).read_bytes()
        if hashlib.sha256(cls.raw).hexdigest() != pages.NATIVE_SHA256:
            raise AssertionError('Wrong private test library')
        cls.rx = memoryview(cls.raw)[:pages.RX_MEMORY_BYTES]

    def setUp(self):
        self.env = patch.dict(os.environ, {'OC2_NATIVE_CODE_PAGES': '1'})
        self.env.start()
        self.temp = tempfile.TemporaryDirectory(prefix='oc2-code-pages-test-')
        self.mapper = pages.create_code_pages(self.raw, cache_dir=self.temp.name)

    def tearDown(self):
        gc.collect()
        self.assertEqual(self.mapper.inspect()['liveUcMappings'], 0)
        self.mapper.close()
        self.temp.cleanup()
        self.env.stop()

    def uc(self):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
        return Uc(UC_ARCH_ARM64, UC_MODE_ARM)

    def map(self, uc):
        return self.mapper.map_segment(uc, 0, pages.RX_MEMORY_BYTES, self.rx)

    def hash_guest(self, uc):
        digest = hashlib.sha256()
        for offset in range(0, pages.RX_MEMORY_BYTES, 1024 * 1024):
            digest.update(uc.mem_read(offset, min(1024 * 1024, pages.RX_MEMORY_BYTES - offset)))
        return digest.hexdigest()

    def execute_fixture(self, uc):
        from unicorn.arm64_const import UC_ARM64_REG_X1, UC_ARM64_REG_X2, UC_ARM64_REG_X3
        # Identical small test instructions/addresses in copied and mapped Ucs.
        uc.mem_write(0x1000, struct.pack('<II', 0xf9000041, 0xf9400043))
        uc.reg_write(UC_ARM64_REG_X1, 0x1122334455667788)
        uc.reg_write(UC_ARM64_REG_X2, 0x2ffc)  # Actual cross-page native STR.
        uc.emu_start(0x1000, 0x1008, count=4)
        self.assertEqual(uc.reg_read(UC_ARM64_REG_X3), 0x1122334455667788)
        uc.mem_write(0x4ffd, b'host-cross-page')
        return self.hash_guest(uc)

    def test_shared_inode_and_no_retained_raw(self):
        other = pages.create_code_pages(self.raw, cache_dir=self.temp.name)
        self.assertEqual(self.mapper.inode, other.inode)
        self.assertFalse(any(isinstance(v, (bytes, bytearray, memoryview)) for v in vars(self.mapper).values()))
        script = ('import sys,json;sys.path.insert(0,sys.argv[1]);import source_code_pages as p;'
                  'x=p.create_code_pages(open(sys.argv[2],"rb").read(),cache_dir=sys.argv[3]);'
                  'print(json.dumps(list(x.inode)));x.close()')
        child = json.loads(subprocess.check_output([sys.executable, '-c', script,
            str(Path(pages.__file__).parent), str(LIBRARY), self.temp.name], text=True))
        self.assertEqual(tuple(child), self.mapper.inode)
        other.close()

    def test_other_segment_and_unknown_lifecycle_do_not_map(self):
        self.assertFalse(self.mapper.map_segment(object(), 0x240a9e0, 2718296, b''))
        uc = self.uc()
        original = uc._Uc__finalizer
        uc._Uc__finalizer = object()
        self.assertFalse(self.map(uc))
        self.assertEqual(list(uc.mem_regions()), [])
        uc._Uc__finalizer = original
        self.assertFalse(self.mapper.map_segment(uc, 0, pages.RX_MEMORY_BYTES, self.rx, 5))
        reference = collect(uc)
        del uc
        gc.collect()
        self.assertIsNone(reference())

    def test_changed_generated_bytes_refused_before_mapping(self):
        uc = self.uc()
        changed = bytearray(self.rx)
        changed[123] ^= 1
        with self.assertRaises(ValueError):
            self.mapper.map_segment(uc, 0, pages.RX_MEMORY_BYTES, changed)
        self.assertEqual(list(uc.mem_regions()), [])
        self.assertTrue(uc._Uc__finalizer.alive)
        reference = collect(uc)
        del uc, changed
        gc.collect()
        self.assertIsNone(reference())

    def test_copied_baseline_private_writes_tail_and_gc_lifetime(self):
        baseline = self.uc()
        baseline.mem_map(0, pages.SHARED_BYTES + pages.PAGE_BYTES, 7)
        baseline.mem_write(0, bytes(self.rx))
        expected = self.execute_fixture(baseline)
        ref = collect(baseline)
        del baseline
        gc.collect()
        self.assertIsNone(ref())  # Baseline exits before the mapped pair.
        a, b = self.uc(), self.uc()
        old_a = a._Uc__finalizer
        self.assertTrue(self.map(a))
        self.assertTrue(self.map(b))
        self.assertFalse(old_a.alive)
        self.assertTrue(all(r[2] == 7 for r in a.mem_regions()))
        original_hash = hashlib.sha256(self.rx).hexdigest()
        self.assertEqual(self.hash_guest(a), original_hash)
        self.assertEqual(self.hash_guest(b), original_hash)
        self.assertEqual(bytes(a.mem_read(pages.RX_MEMORY_BYTES, 1816)), bytes(1816))
        self.assertEqual(self.execute_fixture(a), expected)
        self.assertEqual(self.hash_guest(b), original_hash)
        self.assertEqual(hashlib.sha256(Path(self.mapper.path).read_bytes()).hexdigest(), self.mapper.full_digest)
        with self.assertRaises(ValueError):
            self.mapper.close()
        life_a, life_b = self.mapper._leases[a], self.mapper._leases[b]
        ref = collect(a)
        del a
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(life_a.order, ['uc_close', 'mmap_close'])
        self.assertTrue(life_a.mapping.memory.closed)
        self.assertEqual(self.execute_fixture(b), expected)
        ref = collect(b)
        del b
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(life_b.order, ['uc_close', 'mmap_close'])

    def test_mapper_gc_does_not_release_live_uc_mapping(self):
        other = pages.create_code_pages(self.raw, cache_dir=self.temp.name)
        uc = self.uc()
        self.assertTrue(other.map_segment(uc, 0, pages.RX_MEMORY_BYTES, self.rx))
        lifetime = other._leases[uc]
        ref_mapper = weakref.ref(other)
        del other
        gc.collect()
        self.assertIsNone(ref_mapper())
        self.assertFalse(lifetime.mapping.memory.closed)
        self.execute_fixture(uc)
        ref = collect(uc)
        del uc
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(lifetime.order, ['uc_close', 'mmap_close'])

    def test_bound_callback_cycle_is_collectible_with_ordered_cleanup(self):
        from unicorn import UC_HOOK_CODE
        class Owner:
            def observe(self, uc, address, size, data):
                pass
        owner = Owner()
        owner.uc = self.uc()
        owner.uc.hook_add(UC_HOOK_CODE, owner.observe, begin=0x1000, end=0x1000)
        self.assertTrue(self.map(owner.uc))
        lifetime = self.mapper._leases[owner.uc]
        ref_uc, ref_owner = weakref.ref(owner.uc), weakref.ref(owner)
        del owner
        gc.collect()
        self.assertIsNone(ref_uc())
        self.assertIsNone(ref_owner())
        self.assertEqual(lifetime.order, ['uc_close', 'mmap_close'])
        self.assertTrue(lifetime.mapping.memory.closed)

    def test_partial_mapping_failure_closes_uc_before_backing(self):
        uc = self.uc()
        captured = []
        lifetime_type = pages._Lifetime
        def capture(mapping):
            life = lifetime_type(mapping)
            captured.append(life)
            return life
        def fail_tail(*args, **kwargs):
            raise RuntimeError('Forced private tail mapping failure')
        uc.mem_map = fail_tail
        with patch.object(pages, '_Lifetime', capture):
            with self.assertRaisesRegex(RuntimeError, 'Forced private tail'):
                self.map(uc)
        self.assertIsNone(uc._uch)
        self.assertFalse(uc._Uc__finalizer.alive)
        self.assertEqual(captured[0].order, ['uc_close', 'mmap_close'])
        self.assertEqual(self.mapper.inspect()['liveUcMappings'], 0)
        ref = collect(uc)
        del uc
        gc.collect()
        self.assertIsNone(ref())

    def test_cache_outside_temporary_host_directory_is_refused(self):
        with self.assertRaises(ValueError):
            pages.create_code_pages(self.raw, cache_dir='/data/code-pages-must-not-exist')
        self.assertFalse(Path('/data/code-pages-must-not-exist').exists())

    def test_writable_or_corrupt_cache_is_not_reused(self):
        cache = Path(self.mapper.path)
        cache.chmod(0o644)
        with self.assertRaises(ValueError):
            pages.create_code_pages(self.raw, cache_dir=self.temp.name)
        cache.chmod(0o444)
        with tempfile.TemporaryDirectory(prefix='oc2-code-pages-corrupt-') as directory:
            other = pages.create_code_pages(self.raw, cache_dir=directory)
            target = Path(other.path)
            other.close()
            target.chmod(0o644)
            with target.open('r+b') as file:
                file.write(b'corrupt')
            target.chmod(0o444)
            with self.assertRaises(ValueError):
                pages.create_code_pages(self.raw, cache_dir=directory)
        self.assertEqual(hashlib.sha256(Path(LIBRARY).read_bytes()).hexdigest(), pages.NATIVE_SHA256)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    LIBRARY = args.library
    # unittest's decorator is evaluated at import; explicitly enable only here.
    if LIBRARY:
        PrivateLibraryControls.__unittest_skip__ = False
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'testsRun': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'skipped': len(result.skipped),
              'passed': result.wasSuccessful(), 'maximumConcurrentUc': 2,
              'gameOrServicesOrSavesLoaded': False,
              'privateOriginalLibraryReadOnly': bool(LIBRARY)}
    if args.out:
        if args.out.exists():
            raise ValueError('Preserve existing test report')
        args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
