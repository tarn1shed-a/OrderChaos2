"""638 original key/segment identities and frozen native finite controls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import ordinary_638_animation_complete_probe as probe

PUBLIC = '--public-only' in sys.argv or os.environ.get('PUBLIC_ONLY') == '1'
if '--public-only' in sys.argv:
    sys.argv.remove('--public-only')
FINAL = probe.AREA / 'cpu-final-v1'
PRIVATE = not PUBLIC and (FINAL / 'animation-v1.json').is_file()
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


class PublicImport(unittest.TestCase):
    def test_native_import_is_lazy(self):
        r = subprocess.run([sys.executable, '-S', '-c',
            "import sys;sys.path.insert(0,'tools');import ordinary_638_animation_complete_probe;"
            "assert 'unicorn'not in sys.modules;assert 'capstone'not in sys.modules"],
            cwd=probe.ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipUnless(PRIVATE, 'Private original638 sources/CPU receipts unavailable or public-only')
class OriginalKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bdae_animation import BDAEAnimation
        from ordinary_crocodile_binding_probe import RESOURCES
        from ordinary_crocodile_animation_probe import ANIMATION
        cls.reader = BDAEAnimation(RESOURCES / ANIMATION)
        cls.source = probe.source_description(cls.reader)
        cls.animation = read(FINAL / 'animation-v1.json')
        cls.native = read(FINAL / 'controls-v1.json')

    def test_signed_range_segment_and_fresh_original_loop_remain_literal(self):
        clips = {c['name']: c for c in self.animation['clips']}
        self.assertEqual((clips['idle']['startMs'], clips['idle']['endMs'], clips['idle']['duration']), (34993, 36600, 1.607))
        self.assertEqual((clips['walk_forward']['startMs'], clips['walk_forward']['endMs'], clips['walk_forward']['duration']), (-7, 1333, 1.34))
        self.assertEqual(clips['idle']['sourceSegments'], [4, 5])
        self.assertEqual(clips['walk_forward']['sourceSegments'], [0])
        self.assertEqual(self.source['segments'][0]['startMs'], -7)
        for control in self.native['controls']:
            clock = control['clock']
            clip = clips[control['clip']]
            self.assertEqual(clock[0]['absoluteMs'], clip['startMs'])
            self.assertEqual(clock[1]['absoluteMs'], clip['endMs'])
            self.assertFalse(clock[1]['crossedEnd'])
            self.assertEqual(clock[2]['absoluteMs'], clip['startMs'] + .25)
            self.assertTrue(clock[2]['crossedEnd'])

    def test_all_source_keys_and_repeated_values_keep_original_order_and_float_bits(self):
        copied, unequal_duplicates = set(), 0
        for clip in self.animation['clips']:
            for channel, track in zip(self.source['channels'], clip['tracks']):
                self.assertEqual((channel['node'], channel['type']), (track['node'], track['type']))
                self.assertEqual(channel['sourceDescriptor'], track['sourceDescriptor'])
                for actual in track['nativeSegments']:
                    segment = self.source['segments'][actual['index']]
                    timing = segment['sources'][channel['timeIndex']]
                    frames = list(self.reader.unpack(str(timing['bytes'] // 2) + 'H', timing['at']))
                    self.assertEqual(actual['frames'], frames)
                    width = track['nativeClock']['components']
                    self.assertEqual(len(actual['values']), len(frames) * width)
                    stride = channel['sourceDescriptor'][7] >> 16
                    source = segment['sources'][channel['valueIndex']]
                    self.assertEqual(source['bytes'], len(frames) * stride)
                    if channel['node'] != 'Camera01-node':
                        literal = list(self.reader.unpack(str(source['bytes'] // 4) + 'f', source['at']))
                        self.assertEqual(actual['values'], literal)
                    for i, frame in enumerate(frames):
                        copied.add((actual['index'], channel['sourceIndex'], i))
                        if i and frames[i - 1] == frame and actual['values'][(i - 1) * width:i * width] != actual['values'][i * width:(i + 1) * width]:
                            unequal_duplicates += 1
        self.assertEqual(len(copied), 11432)
        self.assertGreater(unequal_duplicates, 0)
        self.assertTrue(self.animation['repeatedSourceKeysAndSegmentOrderRetained'])

    def test_camera_is_copied_by_original_byte_functions_and_has_four_rotation_values(self):
        for clip in self.animation['clips']:
            camera = [c for c in clip['tracks'] if c['node'] == 'Camera01-node']
            self.assertEqual(len(camera), 2)
            for track in camera:
                self.assertEqual(track['sourceDescriptor'][4:6], [0, 3])
                self.assertEqual(track['nativeCopyTargets'], ['0x1162568'] if track['type'] == 'position' else ['0x115c95c'])
                self.assertEqual(track['nativeInterpolationTarget'], '0x116243c' if track['type'] == 'position' else '0x115c894')
                self.assertEqual(track['nativeClock']['components'], 3 if track['type'] == 'position' else 4)
        self.assertFalse(self.animation['compressedValueCodecInvented'])

    def test_actual_native_selector_uses_correct_chunks_and_keeps_source_sample_time(self):
        clips = {c['name']: c for c in self.animation['clips']}
        for control in self.native['controls']:
            self.assertEqual(len({r['segment'] for r in control['cases']}), 2 if control['clip'] == 'idle' else 1)
            for row in control['cases']:
                self.assertEqual(len(row['dispatch']), 44)
                if control['clip'] == 'walk_forward':
                    # Original FCVTZU then signed clamp is separate from original
                    # property time. Negative clock does not select a huge chunk.
                    self.assertEqual(row['actualCacheTick'], max(0, int(row['absoluteMs'])))
                    self.assertEqual(row['segment'], 0)
                clip = clips[control['clip']]
                self.assertLessEqual(clip['startMs'], row['absoluteMs'])
                self.assertLessEqual(row['absoluteMs'], clip['endMs'])

    def test_python_continuous_consumer_matches_native_warm_and_cold_callbacks(self):
        extras = read(probe.AREA / 'native-edges-final-v1/controls-v1.json')
        for report in (self.native, extras):
            for control in report['controls']:
                clip = next(c for c in self.animation['clips'] if c['name'] == control['clip'])
                states = [{} for _ in range(44)]
                for case in control['cases']:
                    for i, (track, sample) in enumerate(zip(clip['tracks'], case['samples'])):
                        value = probe.sample_track(track, case['absoluteMs'], states[i], clip)
                        self.assertLess(max(abs(a - b) for a, b in zip(value, sample['value'])), .002)
        self.assertEqual(self.native['originalSamplerEntries'], 1100)
        self.assertEqual(extras['originalSamplerEntries'], 440)
        self.assertEqual(extras['newKeyCopies'], 0)

    def test_true_setter_world_palette_and_six_full_vertex_controls_pass(self):
        cases = [row for c in self.native['controls'] for row in c['cases']]
        self.assertEqual(len(cases), 25)
        self.assertEqual(sum('nativePositionOnlyVertices' in row for row in cases), 6)
        for row in cases:
            self.assertEqual(len(row['actualPalette']), 27)
            self.assertLess(row['maximumPaletteError'], .002)
            if 'nativePositionOnlyVertices' in row:
                self.assertEqual(len(row['nativePositionOnlyVertices']), 1266 * 3)
                self.assertLess(row['maximumVertexError'], .002)
        self.assertFalse(self.native['gameActorOrGPUOrQuestAdmission'])

    def test_sources_and_all_previous_frozen_binding_files_are_unchanged(self):
        for row in read(probe.AREA / 'protected-v1.json'):
            self.assertEqual(sha(probe.ROOT / row['path']), row['sha256'], row['path'])
        self.assertEqual(self.native['animationSHA256'], sha(FINAL / 'animation-v1.json'))
        self.assertFalse(self.native['compressedCodecOrOldParserChanged'])
        self.assertEqual(self.source['sourcePropertyCacheFlag'], 0)


if __name__ == '__main__':
    unittest.main()
