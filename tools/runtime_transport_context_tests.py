"""Synthetic full-XZ context integration; no Docker, original archive or Native."""
import gzip
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'deploy/runtime_transport.py'
spec = importlib.util.spec_from_file_location('package_transport_under_test', ROOT / 'tools/package_deployment.py')
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def row(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


class ContextTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HELPER.is_file():
            raise RuntimeError('The shared reconstructor candidate is required; do not replace its validator with a stub')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.change = patch.object(candidate, 'ROOT', self.root)
        self.change.start()
        self.addCleanup(self.change.stop)
        (self.root / 'deploy').mkdir()
        shutil.copyfile(HELPER, self.root / 'deploy/runtime_transport.py')
        self.context = self.root / 'backups/deployment/new-context'
        self.deploy = self.context / 'deploy'
        self.deploy.mkdir(parents=True)
        shutil.copyfile(HELPER, self.deploy / 'runtime_transport.py')
        self.inputs = self.root / 'analysis/raw/full-transport'
        self.inputs.mkdir(parents=True)
        self.canonical = self.inputs / 'canonical.tar.gz'
        self.tar = b'x'
        self.gz = gzip.compress(self.tar, mtime=0)
        self.xz = lzma.compress(self.tar, preset=6)
        # Fixed one-byte RFC1951 STORED test vector, not a production encoder.
        self.stored = bytes.fromhex('1f8b08000000000000ff000100feff78010000ffff8316dc8c01000000')
        self.assertEqual(gzip.decompress(self.stored), self.tar)
        self.canonical.write_bytes(self.gz)
        self.original = self.deploy / 'private-runtime.tar.gz'
        self.original.write_bytes(self.gz)
        self.sidecar = self.deploy / 'private-runtime.sha256'
        self.old_sidecar = (row(self.gz)['sha256'] + '  private-runtime.tar.gz\n').encode()
        self.sidecar.write_bytes(self.old_sidecar)
        self.source_xz = self.inputs / 'private-runtime.tar.xz'
        self.source_xz.write_bytes(self.xz)
        self.plan_path = self.inputs / 'private-runtime.transport.json'
        self.plan = {'format': 'oc2-private-runtime-xz-transport-v1', 'encoding': 'gzip-stored-65535-v1',
                     'canonicalGzip': row(self.gz), 'xz': row(self.xz), 'tar': row(self.tar),
                     'storedGzip': row(self.stored)}
        self.save_plan()

    def save_plan(self):
        self.raw_plan = (json.dumps(self.plan, sort_keys=True, indent=2) + '\n').encode()
        self.plan_path.write_bytes(self.raw_plan)

    def apply(self):
        return candidate.apply_runtime_transport(self.canonical, self.context, self.plan_path)

    def unchanged(self):
        self.assertEqual(self.canonical.read_bytes(), self.gz)
        self.assertEqual(self.original.read_bytes(), self.gz)
        self.assertEqual(self.sidecar.read_bytes(), self.old_sidecar)
        self.assertFalse((self.deploy / 'private-runtime.tar.xz').exists())
        self.assertFalse((self.deploy / 'private-runtime.transport.json').exists())

    def test_success_only_replaces_context_duplicate_and_uses_stored_sha(self):
        result = self.apply()
        self.assertFalse(self.original.exists())
        self.assertEqual(self.canonical.read_bytes(), self.gz)
        self.assertEqual(self.source_xz.read_bytes(), self.xz)
        self.assertEqual((self.deploy / 'private-runtime.tar.xz').read_bytes(), self.xz)
        self.assertEqual((self.deploy / 'private-runtime.transport.json').read_bytes(), self.raw_plan)
        self.assertEqual(self.sidecar.read_text(), row(self.stored)['sha256'] + '  private-runtime.tar.gz\n')
        self.assertFalse(result['canonicalArchiveWritten'])
        self.assertTrue(result['duplicateContextGzipRemoved'])

    def test_shared_validator_rejects_unknown_field_before_mutation(self):
        self.plan['arbitraryTarget'] = '/data/saves/characters.json'
        self.save_plan()
        with self.assertRaises(ValueError):
            self.apply()
        self.unchanged()

    def test_shared_plan_reader_rejects_duplicate_json_key(self):
        duplicate = self.raw_plan.replace(b'{', b'{"format":"oc2-private-runtime-xz-transport-v1",', 1)
        self.plan_path.write_bytes(duplicate)
        with self.assertRaises(ValueError):
            self.apply()
        self.unchanged()

    def test_corrupt_xz_rejected_before_mutation(self):
        self.source_xz.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):
            self.apply()
        self.unchanged()

    def test_wrong_canonical_refused_without_touching_context(self):
        self.plan['canonicalGzip']['sha256'] = '0' * 64
        self.save_plan()
        with self.assertRaises(ValueError):
            self.apply()
        self.unchanged()

    def test_wrong_sidecar_refused(self):
        self.sidecar.write_bytes(b'wrong\n')
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.original.read_bytes(), self.gz)
        self.assertFalse((self.deploy / 'private-runtime.tar.xz').exists())

    def test_existing_output_preserved(self):
        target = self.deploy / 'private-runtime.tar.xz'
        target.write_bytes(b'existing')
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(target.read_bytes(), b'existing')
        self.assertEqual(self.original.read_bytes(), self.gz)
        self.assertEqual(self.sidecar.read_bytes(), self.old_sidecar)

    def test_failed_copy_rolls_back_new_outputs_and_keeps_canonical(self):
        def corrupt_copy(source, output):
            output.write(b'bad-copy')
        with patch.object(candidate.shutil, 'copyfileobj', corrupt_copy):
            with self.assertRaises(ValueError):
                self.apply()
        self.unchanged()

    def test_context_helper_identity_is_checked(self):
        (self.deploy / 'runtime_transport.py').write_bytes(b'# different helper\n')
        with self.assertRaises(ValueError):
            self.apply()
        self.unchanged()

    def test_last_unlink_failure_restores_old_sidecar_and_new_outputs(self):
        original_unlink = Path.unlink
        def fail_original(path, *args, **kwargs):
            if path == self.original:
                raise PermissionError('synthetic context unlink failure')
            return original_unlink(path, *args, **kwargs)
        with patch.object(Path, 'unlink', fail_original):
            with self.assertRaises(PermissionError):
                self.apply()
        self.unchanged()

    def test_canonical_must_not_be_the_context_file(self):
        with self.assertRaises(ValueError):
            candidate.apply_runtime_transport(self.original, self.context, self.plan_path)
        self.unchanged()


if __name__ == '__main__':
    unittest.main()
