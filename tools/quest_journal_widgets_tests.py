"""Source widget export replay and lazy public import; no rendering."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
import quest_journal_widgets_probe as probe
PUBLIC='--public-only'in sys.argv or os.environ.get('PUBLIC_ONLY')=='1'
if'--public-only'in sys.argv:sys.argv.remove('--public-only')
SOURCE=probe.AREA/'source-v1/source-program.json'


class Public(unittest.TestCase):
    def test_import_without_source_dependencies(self):
        r=subprocess.run([sys.executable,'-S','-c',"import sys;sys.path.insert(0,'tools');import quest_journal_widgets_probe;assert 'capstone'not in sys.modules;assert 'unicorn'not in sys.modules"],cwd=probe.ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)


@unittest.skipUnless(not PUBLIC and SOURCE.is_file(),'Private source unavailable/public-only')
class Original(unittest.TestCase):
    def test_original_export_replays_byte_for_byte(self):
        with tempfile.TemporaryDirectory(prefix='replay-',dir=probe.AREA)as path:
            r=probe.recover(__import__('pathlib').Path(path)/'export')
            self.assertEqual(r['sha256'],'4b4c88e6cc7edcc7aaee351dbb01533c4e7f9e2f83fbc17821c7990407492171')
            self.assertEqual(__import__('pathlib').Path(r['path']).read_bytes(),SOURCE.read_bytes())
            self.assertEqual(r['sharedMethodsMatched'],13)
            with self.assertRaises(ValueError):probe.recover(__import__('pathlib').Path(path)/'export')


if __name__=='__main__':unittest.main()
