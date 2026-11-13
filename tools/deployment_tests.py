"""Source-only regression for the deployment boundary; no game resource required."""
import importlib.util
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deployment_bootstrap', ROOT / 'deploy/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)
from package_deployment import python_closure


class DeploymentTests(unittest.TestCase):
    def archive(self, directory, name, kind=None):
        path = Path(directory) / 'private.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            member = tarfile.TarInfo(name)
            if kind:
                member.type = kind
                member.linkname = '/etc/passwd'
                archive.addfile(member)
            else:
                member.size = 2
                archive.addfile(member, io.BytesIO(b'{}'))
        return path

    def test_archive_digest_checked_before_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.archive(directory, 'bundle-manifest.json')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                bootstrap.extract_verified(path, '0' * 64, Path(directory) / 'out')
            self.assertFalse((Path(directory) / 'out').exists())

    def test_parent_absolute_and_noncanonical_names_rejected(self):
        for name in ['../save.json', '/data/saves/characters.json', 'a/../save', 'a\\b', './file', 'a//b']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = self.archive(directory, name)
                with self.assertRaisesRegex(ValueError, 'Unsafe'):
                    bootstrap.extract_verified(path, bootstrap.sha(path), Path(directory) / 'out')

    def test_links_are_never_extracted(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE]:
            with tempfile.TemporaryDirectory() as directory:
                path = self.archive(directory, 'link', kind)
                with self.assertRaisesRegex(ValueError, 'regular files'):
                    bootstrap.extract_verified(path, bootstrap.sha(path), Path(directory) / 'out')

    def test_empty_or_wrong_manifest_is_not_a_replacement_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.archive(directory, 'bundle-manifest.json')
            with self.assertRaisesRegex(ValueError, 'member set'):
                bootstrap.extract_verified(path, bootstrap.sha(path), Path(directory) / 'out')

    def test_docker_build_allowlist_covers_exact_native_import_closure(self):
        rules = (ROOT / '.dockerignore').read_text().splitlines()
        self.assertIn('**', rules)
        for name in python_closure():
            self.assertIn('!' + name, rules)
        for forbidden in ['!analysis/raw/', '!game-data/', '!runtime/', '!backups/', '!.env', '!tools/native_character_entry.py', '!tools/standard_abc.py']:
            self.assertNotIn(forbidden, rules)

    def test_deployment_has_no_dependency_on_mac_paths_or_local_saves(self):
        for name in ['deploy/server.mjs', 'deploy/bootstrap.py', 'Dockerfile', 'compose.yaml']:
            source = (ROOT / name).read_text()
            self.assertNotIn('/Users/', source)
            self.assertNotIn('runtime/mvp/characters.json', source)
        self.assertIn('/data/saves/characters.json', (ROOT / 'deploy/server.mjs').read_text())

    def test_deployment_dependency_update_does_not_rewrite_reviewed_runtime(self):
        deployment = json.loads((ROOT / 'deploy/package.json').read_text())
        self.assertEqual(deployment['dependencies'], {'three': '0.187.0', 'ws': '8.23.0'})
        manifest = json.loads((ROOT / 'tools/local_mvp_runtime.json').read_text())
        self.assertNotIn('prototype/native-physics.json', manifest['files'])

    def test_build_context_includes_required_ui_retirement_stylesheet(self):
        self.assertIn('!deploy/retired_ui.css', (ROOT / '.dockerignore').read_text().splitlines())
        self.assertIn('retired_ui.css', (ROOT / 'deploy/static_delivery.mjs').read_text())
        self.assertIn('display: none !important', (ROOT / 'deploy/retired_ui.css').read_text())

    def test_railway_uses_current_iac_and_preserves_unmanaged_variables(self):
        source = (ROOT / '.railway/railway.ts').read_text()
        self.assertIn('variables: { managed: false }', source)
        self.assertIn('"/data": data', source)
        self.assertNotIn('env:', source)
        self.assertFalse((ROOT / 'railway.toml').exists())


if __name__ == '__main__':
    unittest.main()
