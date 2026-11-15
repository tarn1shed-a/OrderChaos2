"""Original-source regression controls for the bounded quest227 sampler."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import ordinary_crocodile_animation_probe as probe

PUBLIC = '--public-only' in sys.argv or os.environ.get('PUBLIC_ONLY') == '1'
if '--public-only' in sys.argv:
    sys.argv.remove('--public-only')
RESOURCES = probe.ROOT / 'analysis/raw/ordinary-quest-neighbors-20261116/candidate-v2/original-resources'
NATIVE = probe.ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
PRIVATE = not PUBLIC and (RESOURCES / probe.ANIMATION).is_file() and NATIVE.is_file()


class PublicImport(unittest.TestCase):
    def test_native_dependencies_are_lazy(self):
        result = subprocess.run([sys.executable, '-S', '-c',
            "import sys;sys.path.insert(0,'tools');import ordinary_crocodile_animation_probe;"
            "assert 'unicorn'not in sys.modules;assert 'capstone'not in sys.modules"],
            cwd=probe.ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(PRIVATE, 'Private original assets unavailable/public-only')
class OriginalSampler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protected = [probe.ROOT / 'tools/bdae_animation.py', NATIVE,
                         *(RESOURCES / p for p in probe.SOURCE_SHAS)]
        cls.before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.protected]
        cls.temp = tempfile.TemporaryDirectory(dir=probe.ROOT / 'analysis/raw', prefix='croc-native-test-')
        cls.result = probe.inspect(RESOURCES, NATIVE, Path(cls.temp.name))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_native_signed_walk_range_and_padded_idle_are_preserved(self):
        rows = {r['sourceName'].split('-', 1)[0]: r for r in self.result['ranges']}
        self.assertEqual(rows['walk_forward']['literalUnsignedWords'][0], 0xfffffff9)
        self.assertEqual(rows['walk_forward']['nativeClock']['startEndMs'], [-7.0, 1333.0])
        self.assertEqual(rows['idle']['nativeClock']['startEndMs'], [34993.0, 36600.0])
        self.assertEqual(rows['idle']['literalSignedWords'][2], 35000)

    def test_actual_original_sampler_is_entered_for_every_property_and_time(self):
        self.assertEqual(self.result['propertyCount'], 44)
        self.assertEqual(self.result['originalSamplerEntries'], 5 * 44)
        self.assertEqual(self.result['boneCount'], 27)
        self.assertEqual(self.result['skinBonePropertyCount'], 40)
        for case in self.result['cases']:
            self.assertEqual(len(case['samples']), 44)
            # Bip01 is an animated ancestor; it must not be dropped just
            # because it is not itself in the skin's 27-bone palette.
            self.assertEqual(len([s for s in case['samples'] if s['node'] == 'Bip01-node']), 2)

    def test_camera_byte_tracks_use_actual_original_copy_and_interpolation(self):
        calls = self.result['cameraOriginalSamplerCalls']
        targets = {(r['propertyType'], r['callee']) for r in calls}
        self.assertEqual(targets, {(1, '0x116243c'), (1, '0x1162568'),
                                   (5, '0x115c894'), (5, '0x115c95c')})
        for case in self.result['cases']:
            camera = [s for s in case['samples'] if s['node'] == 'Camera01-node']
            self.assertEqual(len(camera), 2)
            self.assertTrue(all(not s['sourceSkinBone'] for s in camera))
            self.assertEqual([len(s['value']) for s in camera], [3, 4])

    def test_source_idle_changes_without_a_new_host_codec(self):
        samples = [next(s for s in c['samples'] if s['node'] == 'Bip01-node' and s['type'] == 1)['value']
                   for c in self.result['cases']]
        self.assertEqual(samples[0], samples[1])
        self.assertNotEqual(samples[1], samples[2])
        self.assertEqual(samples[0], samples[-1])
        self.assertFalse(self.result['codecRewritten'])

    def test_unsupported_outside_idle_segment_is_not_reinterpreted(self):
        first = self.result['sourceSegments'][0]
        self.assertEqual(first['startBits'], 0xfffffff9)
        self.assertFalse(first['positiveBounds'])
        self.assertEqual(set(self.result['frozenReaderDiagnostics']), {'channels', 'ranges', 'segments'})

    def test_sources_frozen_reader_and_runtime_boundary_are_preserved(self):
        after = [hashlib.sha256(p.read_bytes()).hexdigest() for p in self.protected]
        self.assertEqual(after, self.before)
        self.assertFalse(self.result['runtimeChanged'])
        self.assertFalse(self.result['lootOrCombatApproved'])
        self.assertTrue(all(not c['settersOrPaletteExecuted'] for c in self.result['cases']))


if __name__ == '__main__':
    unittest.main()
