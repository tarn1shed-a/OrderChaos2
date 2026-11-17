"""Image archive selection only; no runtime, save directory or /data writes."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('bootstrap_under_test', Path(__file__).with_name('bootstrap.py'))
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class ImageArchiveTests(unittest.TestCase):
    def source_code(self, root):
        path = root / 'tools/actor/worker.py'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'# reviewed worker\n')
        index = {'format': 'oc2-source-world-python-closure-v1', 'files': {
            'tools/actor/worker.py': hashlib.sha256(path.read_bytes()).hexdigest()}}
        (root / 'tools/source_world_python.json').write_text(json.dumps(index))
        return path

    def test_image_requires_actual_reviewed_worker_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.source_code(root)
            self.assertEqual(len(bootstrap.verify_source_world_code(root)['files']), 1)
            path.write_bytes(b'# different worker\n')
            with self.assertRaisesRegex(ValueError, 'Python bytes differ'):
                bootstrap.verify_source_world_code(root)
            path.unlink()
            with self.assertRaisesRegex(ValueError, 'Python bytes differ'):
                bootstrap.verify_source_world_code(root)

    def test_source_worker_cannot_escape_image_allowlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.source_code(root)
            index = root / 'tools/source_world_python.json'
            value = json.loads(index.read_text())
            value['files'] = {'tools/../../other.py': '0' * 64}
            index.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, 'Unsafe bundle member'):
                bootstrap.verify_source_world_code(root)

    def test_repository_image_includes_its_complete_code_closure(self):
        # This catches an actual COPY-context failure without requiring any
        # private native image, original resource, saved role or /data access.
        root = Path(__file__).resolve().parents[1]
        source = bootstrap.verify_source_world_code(root)
        required = set(source['files']) | {'tools/source_world_python.json'}
        required.update('deploy/world_admission/' + name + '.mjs' for name in
                        ['contracts', 'pending', 'first_pose', 'gate', 'human_female'])
        required.update('deploy/world_route/' + name + '.mjs' for name in
                        ['assembly', 'route', 'eight_domain', 'selector'])
        ignore = (root / '.dockerignore').read_text()
        _, block = ignore.split('# BEGIN REVIEWED SOURCE WORLD\n')
        block, tail = block.split('# END REVIEWED SOURCE WORLD\n')
        self.assertFalse(tail.strip(), 'Later Docker rules could exclude reviewed code again')
        rules = {line.strip() for line in block.splitlines() if line.strip() and not line.lstrip().startswith('#')}
        for name in required:
            self.assertTrue((root / name).is_file(), name)
            self.assertIn('!' + name, rules)
            for parent in Path(name).parents:
                if str(parent) != '.':
                    self.assertIn('!' + parent.as_posix() + '/', rules)
        self.assertTrue(all(line.startswith('!') and not any(c in line for c in '*?[') for line in rules))

    def archive(self, root, delta=False):
        path = root / 'private.tar.gz'
        entries = {'bundle-manifest.json': json.dumps({'format': bootstrap.FORMAT, 'localSavesImported': False}).encode()}
        if delta:
            entries['bundle-base.json'] = b'{}'
        with tarfile.open(path, 'w:gz') as packed:
            for name, data in entries.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                packed.addfile(info, io.BytesIO(data))
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_exact_complete_image_is_read_without_creating_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path, digest = self.archive(root)
            before = path.read_bytes()
            with patch.dict(os.environ, {'OC2_BUNDLE_CACHE': '0', 'OC2_BUNDLE_PATH': str(path), 'OC2_BUNDLE_SHA256': digest}, clear=True):
                self.assertEqual(bootstrap.archive_from_env(), (path, digest))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['private.tar.gz'])

    def test_image_hash_mismatch_has_no_cache_or_download_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.archive(Path(directory))
            with patch.dict(os.environ, {'OC2_BUNDLE_CACHE': '0', 'OC2_BUNDLE_PATH': str(path), 'OC2_BUNDLE_SHA256': '0' * 64}, clear=True):
                with self.assertRaisesRegex(ValueError, 'exact bundled'):
                    bootstrap.archive_from_env()

    def test_delta_cannot_depend_on_unstated_image_side_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest = self.archive(Path(directory), delta=True)
            with patch.dict(os.environ, {'OC2_BUNDLE_CACHE': '0', 'OC2_BUNDLE_PATH': str(path), 'OC2_BUNDLE_SHA256': digest}, clear=True):
                with self.assertRaisesRegex(ValueError, 'complete private archive'):
                    bootstrap.archive_from_env()

    def test_original_path_index_is_copied_once_and_checked_on_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / 'private-runtime'
            source = runtime / 'native-inputs/world-own-air-v1/root-support/matrix.json'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'original lookup input')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            target = bootstrap.install_world_path_index(runtime, root, digest)
            self.assertEqual(target.read_bytes(), source.read_bytes())
            before = target.stat().st_mtime_ns
            self.assertEqual(bootstrap.install_world_path_index(runtime, root, digest), target)
            self.assertEqual(target.stat().st_mtime_ns, before)
            target.write_bytes(b'other work')
            with self.assertRaisesRegex(ValueError, 'Existing world'):
                bootstrap.install_world_path_index(runtime, root, digest)
            self.assertEqual(target.read_bytes(), b'other work')

    def test_bad_path_index_does_not_create_a_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / 'private-runtime'
            source = runtime / 'native-inputs/world-own-air-v1/root-support/matrix.json'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'different input')
            with self.assertRaisesRegex(ValueError, 'Original world'):
                bootstrap.install_world_path_index(runtime, root)
            self.assertFalse((root / 'analysis').exists())

    def test_gather_helpers_keep_existing_different_work(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runtime, root = base / 'runtime', base / 'image'
            rows = {}
            for i in range(3):
                name, raw = f'analysis/raw/frozen/helper{i}.py', f'# helper {i}\n'.encode()
                source = runtime / 'native-inputs/world-gather-v1/root-support' / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(raw)
                rows[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            plan = runtime / 'native-inputs/world-gather-v1/append-plan.json'
            plan.write_text(json.dumps({'newRootFiles': rows}))
            digest = hashlib.sha256(plan.read_bytes()).hexdigest()
            self.assertEqual(bootstrap.install_world_gather_support(runtime, root, digest), rows)
            for name in rows:
                self.assertTrue((root / name).is_file())
            target = root / next(iter(rows))
            target.write_bytes(b'# existing other work\n')
            with self.assertRaisesRegex(ValueError, 'Existing world helper differs'):
                bootstrap.install_world_gather_support(runtime, root, digest)
            self.assertEqual(target.read_bytes(), b'# existing other work\n')

    def test_latest_plan_projects_code_and_original_data_through_one_checked_index(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runtime, root = base / 'runtime', base / 'image'
            name, raw = 'analysis/raw/original/matrix.json', b'{"original":true}'
            source = runtime / 'native-inputs/world-latest-v1/root-support' / name
            source.parent.mkdir(parents=True)
            source.write_bytes(raw)
            plan = {'actualFactsHostCompiled': True, 'normalRepairIndependentOfGatherFlag': True,
                    'explicitRootSupport': {name: {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}}}
            path = runtime / 'native-inputs/world-latest-v1/append-plan.json'
            path.write_text(json.dumps(plan))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(bootstrap.install_world_latest_support(runtime, root, digest), plan)
            self.assertEqual((root / name).read_bytes(), raw)
            source.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Original world helper differs'):
                bootstrap.install_world_latest_support(runtime, root, digest)

    def test_latest_plan_identity_is_required_before_support_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runtime, root = base / 'runtime', base / 'image'
            path = runtime / 'native-inputs/world-latest-v1/append-plan.json'
            path.parent.mkdir(parents=True)
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Common world source plan differs'):
                bootstrap.install_world_latest_support(runtime, root)
            self.assertFalse(root.exists())


if __name__ == '__main__':
    unittest.main()
