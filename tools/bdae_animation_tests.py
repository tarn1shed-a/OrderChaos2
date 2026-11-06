"""Animation decoder corruption checks plus optional user-resource integration."""
import json
import math
import struct
import tempfile
import unittest
from pathlib import Path

from bdae_animation import BDAEAnimation, interpolate

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / 'game-data/extracted/model/npc/character/elf/female/anim/animations.bdae'
WOLF = ROOT / 'game-data/extracted/model/npc/creature/beast/wolf/anim/animations.bdae'


def fixture():
    """Independent two-segment fixture with absolute 30 FPS source times."""
    data = bytearray(256)
    def allocate(length):
        at = len(data)
        data.extend(bytes(length))
        return at
    def put(fmt, at, *values): struct.pack_into('<' + fmt, data, at, *values)
    def string(value):
        raw = value.encode() + b'\0'
        at = allocate(len(raw))
        data[at:at+len(raw)] = raw
        return at
    def relative(at, target): put('i', at, target - at)
    data[:8] = b'BRES\xfe\xff\0\0'
    put('I', 8, 64)
    put('Q', 40, 64)
    put('Q', 64, string('0,0,0,946'))
    node_name = string('Bip01-node')
    channel_table = allocate(80)
    put('I', 64 + 64, 2)
    relative(64 + 68, channel_table)
    for index, (kind, width) in enumerate([(1, 3), (5, 4)]):
        record = channel_table + index * 40
        prop, target = allocate(32), allocate(24)
        put('Q', record, string('channel-' + str(index)))
        put('I', record + 8, 1)
        relative(record + 12, prop)
        put('I', record + 16, 1)
        relative(record + 20, target)
        put('8I', prop, 1, 3, 1, index * 2, 6, width, index * 2 + 1, width << 18)
        put('Q', target, node_name)
        put('I', target + 8, kind)
    ranges = allocate(24)
    put('I', 64 + 84, 1)
    relative(64 + 88, ranges)
    put('Q', ranges, string('walk_forward-AUTO_Current_Range'))
    put('4I', ranges + 8, 0, 1000, 0, 0)
    segment_table = allocate(88)
    relative(64 + 76, segment_table)
    put('2I', segment_table, 2, 4)
    locations = {'ranges': ranges, 'segments': []}
    for index in range(2):
        segment = segment_table + 8 + index * 40
        put('4I', segment, index * 500, (index + 1) * 500, 0, 0x01000000)
        block = allocate(40)
        put('2I', block, 4, 4)
        buffers = []
        for source, (fmt, values) in enumerate([
            ('3H', [0, 15, 30]), ('9f', [0, 0, 0, 1, 2, 3, 0, 0, 0]),
            ('3H', [0, 15, 30]), ('12f', [0, 0, 0, 1, 0, 0, .6, .8, 0, 0, 0, 1]),
        ]):
            size = struct.calcsize('<' + fmt)
            pointer = allocate(size)
            put(fmt, pointer, *values)
            put('I', block + 8 + source * 8, size)
            relative(block + 12 + source * 8, pointer)
            buffers.append(pointer)
        put('2Q', segment + 16, block, len(data) - block)
        locations['segments'].append({'record': segment, 'block': block, 'buffers': buffers})
    put('I', 12, len(data))
    return data, locations


class AnimationFormatTests(unittest.TestCase):
    def decode(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'animation.bdae'
            path.write_bytes(data)
            return BDAEAnimation(path).parse(['walk_forward'])

    def test_two_segments_produce_local_clip_time_and_real_transforms(self):
        result = self.decode(fixture()[0])
        clip = result['clips'][0]
        self.assertEqual(clip['duration'], 1)
        self.assertEqual(clip['sourceRangeFrames'], [0, 30])
        position, rotation = clip['tracks']
        self.assertEqual(position['times'], [0, .5, 1])
        self.assertEqual(position['values'], [0, 0, 0, 1, 2, 3, 0, 0, 0])
        self.assertEqual(rotation['type'], 'quaternion')
        self.assertEqual(rotation['node'], 'Bip01-node')
        self.assertLess(result['verification']['maximumSourceQuaternionNormSquaredError'], 1e-6)

    def test_source_byte_lengths_are_not_treated_as_element_counts(self):
        data, locations = fixture()
        struct.pack_into('<I', data, locations['segments'][0]['block'] + 16, 35)
        with self.assertRaisesRegex(ValueError, 'fractional'):
            self.decode(data)

    def test_reject_nonmonotonic_source_time(self):
        data, locations = fixture()
        struct.pack_into('<3H', data, locations['segments'][0]['buffers'][0], 0, 15, 15)
        with self.assertRaisesRegex(ValueError, 'strictly increasing'):
            self.decode(data)

    def test_reject_nonunit_quaternion(self):
        data, locations = fixture()
        struct.pack_into('<f', data, locations['segments'][0]['buffers'][3] + 12, 2)
        with self.assertRaisesRegex(ValueError, 'Non-unit'):
            self.decode(data)

    def test_reject_conflicting_overlap(self):
        data, locations = fixture()
        struct.pack_into('<f', data, locations['segments'][1]['buffers'][1], .25)
        with self.assertRaisesRegex(ValueError, 'overlapping|Overlapping'):
            self.decode(data)

    def test_reject_source_pointer_outside_segment(self):
        data, locations = fixture()
        descriptor = locations['segments'][0]['block'] + 12
        struct.pack_into('<i', data, descriptor, len(data) - descriptor + 100)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.decode(data)

    def test_reject_missing_clip_boundary_samples_instead_of_inventing_holds(self):
        data, locations = fixture()
        for segment in locations['segments']:
            struct.pack_into('<3H', data, segment['buffers'][0], 1, 15, 30)
        with self.assertRaisesRegex(ValueError, 'clip boundaries'):
            self.decode(data)

    def test_reject_gap_in_declared_segment_timeline(self):
        data, locations = fixture()
        struct.pack_into('<I', data, locations['segments'][1]['record'], 501)
        with self.assertRaisesRegex(ValueError, 'gap inside'):
            self.decode(data)

    def test_quaternion_shortest_arc_interpolation_is_continuous(self):
        q = (0, 0, .6, .8)
        for amount in [0, .25, .5, .75, 1]:
            out = interpolate(q, tuple(-value for value in q), amount, True)
            self.assertAlmostEqual(sum(value * value for value in out), 1)
            self.assertAlmostEqual(abs(sum(a*b for a, b in zip(q, out))), 1)


@unittest.skipUnless(ELF.exists(), 'Requires local original elf animation bundle')
class ElfAnimationIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = BDAEAnimation(ELF).parse(['walk_forward', 'idle'])

    def test_walk_idle_named_ranges_and_timing(self):
        walk, idle = self.result['clips']
        self.assertAlmostEqual(walk['duration'], 26/30)
        self.assertEqual(walk['sourceRangeMs'], [0, 867])
        self.assertEqual(idle['duration'], 4)
        self.assertEqual(idle['sourceRangeMs'], [431000, 435000])
        self.assertEqual(len(walk['tracks']), 110)
        self.assertTrue(self.result['verification']['overlappingSamplesConsistent'])

    def test_walk_changes_leg_bones_and_closes_core_loop(self):
        tracks = self.result['clips'][0]['tracks']
        for node in ['Bip01_L_Calf-node', 'Bip01_R_Calf-node', 'Bip01_L_Thigh-node', 'Bip01_R_Thigh-node']:
            track = next(t for t in tracks if t['node'] == node and t['type'] == 'quaternion')
            rows = [track['values'][i:i+4] for i in range(0, len(track['values']), 4)]
            first, last = rows[0], rows[-1]
            self.assertGreater(abs(sum(a*b for a, b in zip(first, last))), .999999)
            self.assertGreater(max(max(abs(a-b) for a, b in zip(first, row)) for row in rows), .05)
            for row in rows:
                self.assertAlmostEqual(sum(value*value for value in row), 1, places=5)

    def test_staff_hit_and_death_source_ranges_are_readable(self):
        result = BDAEAnimation(ELF).parse([
            'combat_1h_scepter_npc_01', 'combat_2h_staff_npc_01',
            'hurt_battle_01', 'die_ground', 'dead_ground'])
        expected = [.8, 44/30, 14/30, 34/30, 1/30]
        for clip, duration in zip(result['clips'], expected):
            self.assertAlmostEqual(clip['duration'], duration)
            self.assertEqual(len(clip['tracks']), 110)
            self.assertTrue(all(track['times'][0] == 0 for track in clip['tracks']))
            self.assertTrue(all(abs(track['times'][-1] - duration) < 1e-8 for track in clip['tracks']))
        death, dead = result['clips'][-2:]
        self.assert_death_pose_continuity(death, dead)

    def assert_death_pose_continuity(self, death, dead):
        death_tracks = {(track['node'], track['type']): track for track in death['tracks']}
        for track in dead['tracks']:
            width = 4 if track['type'] == 'quaternion' else 3
            previous = death_tracks[(track['node'], track['type'])]['values'][-width:]
            first = track['values'][:width]
            if width == 4:
                self.assertGreater(abs(sum(a*b for a, b in zip(previous, first))), .99999)
            else:
                # Source clips are authored separately: body offsets differ by
                # < 0.1 mm, and the wolf's unweighted footstep locator by 9.6 mm.
                limit = .01 if track['node'] == 'Bip001_Footsteps-node' else 1e-4
                self.assertLess(max(abs(a-b) for a, b in zip(previous, first)), limit)
            self.assertLess(max(abs(value - first[index % width])
                                for index, value in enumerate(track['values'])), 1e-5)
        root = next(track for track in death['tracks'] if track['node'] == 'Bip01-node' and track['type'] == 'position')
        self.assertLess(root['values'][-2], root['values'][1] - .7)

    def test_ambiguous_source_basename_requires_full_range_name(self):
        animation = BDAEAnimation(ELF)
        with self.assertRaisesRegex(ValueError, 'Expected one animation range'):
            animation.parse(['combat_2h_polearm_npc_01'])
        result = animation.parse(['combat_2h_polearm_npc_01-skill_rg_directed_release'])
        self.assertAlmostEqual(result['clips'][0]['duration'], 20/30)

    def test_original_directed_and_omni_skill_ranges_preserve_timing(self):
        result = BDAEAnimation(ELF).parse(['skill_mg_directed_instant', 'skill_mg_omni_release'])
        for clip, duration in zip(result['clips'], [.5, .7]):
            self.assertAlmostEqual(clip['duration'], duration)
            self.assertEqual(len(clip['tracks']), 110)
            self.assertTrue(all(track['times'][0] == 0 and abs(track['times'][-1]-duration) < 1e-8 for track in clip['tracks']))


@unittest.skipUnless(WOLF.exists(), 'Requires local original wolf animation bundle')
class WolfAnimationIntegrationTests(unittest.TestCase):
    def test_true_wolf_walk_and_idle(self):
        result = BDAEAnimation(WOLF).parse(['walk_forward', 'idle'])
        walk, idle = result['clips']
        self.assertEqual(len(walk['tracks']), 58)
        self.assertAlmostEqual(walk['duration'], 32/30)
        self.assertAlmostEqual(idle['duration'], 50/30)

    def test_wolf_attack_hit_and_death_keep_original_timing(self):
        result = BDAEAnimation(WOLF).parse(['combat_01', 'hurt_battle_01', 'die_ground', 'dead_ground'])
        for clip, duration in zip(result['clips'], [38/30, .9, 1, 1]):
            self.assertAlmostEqual(clip['duration'], duration)
            self.assertEqual(len(clip['tracks']), 58)
        death, dead = result['clips'][-2:]
        ElfAnimationIntegrationTests.assert_death_pose_continuity(self, death, dead)


if __name__ == '__main__':
    unittest.main()
