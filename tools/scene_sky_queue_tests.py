import random
import unittest
from pathlib import Path

from scene_sky_queue import FORMAT, ROUTINES, analyze_queue, queue_route, technique_selection, verify_native

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT/'analysis/raw/beff-native/library.so'
SOURCE = ROOT/'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class SkyQueueTests(unittest.TestCase):
    def test_technique_shift_wrap_sentinel_and_fixture_bounds(self):
        self.assertEqual(technique_selection(7, 1, 0x803, 2, 4, bytes(range(64))),
                         {'returnWord': 79, 'queueIndex': 79, 'mapIndex': 9, 'lockCalls': 2})
        result = technique_selection(255, 1, 31, 0, 0, bytes([1]))
        self.assertEqual(result['returnWord'], 0x800000ff)
        self.assertEqual(result['queueIndex'], 255)
        self.assertEqual(technique_selection(7, 0, 32, 0xffffffff, 0, None)['lockCalls'], 0)
        self.assertEqual(technique_selection(7, 0, 32, 0, 0, bytes(range(8)))['queueIndex'], 7)
        self.assertEqual(technique_selection(7, 0, 0, 0, 0, None)['lockCalls'], 2)
        for args in [(True, 0, 0, 0, 0, None), (0, 0, 0, -1, 0, None), (4, 0, 0, 0, 0, b'\0')]:
            with self.assertRaises(ValueError): technique_selection(*args)

    def test_queue_precedence_bit_tests_and_source_record_widths(self):
        self.assertEqual(queue_route(8)['recordBytes'], 16)
        self.assertEqual(queue_route(3, False, node_word_210=3, node_word_200=3)['queueOffset'], None)
        self.assertEqual(queue_route(3, False, node_word_210=2, node_word_200=3)['queueOffset'], 0x130)
        self.assertEqual(queue_route(3, True, 1, 0x40)['queueOffset'], 0x160)
        self.assertFalse(queue_route(3, True, 1, 0x40)['completed'])
        self.assertEqual(queue_route(3, True, 1, 0x40, 2, 1, 1)['queueOffset'], 0x148)
        for args in [(4,), (3.0,), (3, 1), (3, True, 256)]:
            with self.assertRaises(ValueError): queue_route(*args)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_technique_resolver_matches_explicit_small_lookup_states(self):
        from analyze_native_resources import NativeImage
        from native_sky_queue_probe import NativeSkyQueueProbe
        p = NativeSkyQueueProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x13ed140)
        states = [(255, 1, 31, 0, 0, b'\1'), (7, 1, 0x803, 2, 4, bytes(range(64))),
                  (11, 0, 0, 0xffffffff, 0, None), (11, 0, 0, 0, 0, None)]
        for _ in range(120):
            states.append((rng.randrange(256), rng.randrange(4), rng.randrange(1 << 16),
                           rng.randrange(3), rng.randrange(4), rng.randbytes(4096)))
        for state in states:
            expected = technique_selection(*state); actual = p.select(*state)
            self.assertEqual(actual, {k: expected[k] for k in actual})

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_queue3_and8_write_and_grow_exact_records(self):
        from analyze_native_resources import NativeImage
        from native_sky_queue_probe import NativeSkyQueueProbe
        p = NativeSkyQueueProbe(NativeImage(NATIVE.read_bytes())); rng = random.Random(0x12f368c)
        for _ in range(128):
            code = rng.choice([3, 8]); material = bool(rng.randrange(2))
            tech, pb, scene = 0, rng.randrange(256), rng.randrange(256)
            n = rng.randrange(9); cap = n if rng.randrange(2) else n+rng.randrange(1, 5)
            part, context = rng.getrandbits(64), rng.getrandbits(64)
            priority = rng.choice([0x7fffffff, rng.getrandbits(32)]); np, tag = rng.getrandbits(32), rng.getrandbits(32)
            old = [[rng.getrandbits(64), rng.getrandbits(64)] if code == 8 else
                   [rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(64), rng.getrandbits(32), rng.getrandbits(32)] for _ in range(n)]
            actual = p.insert(code, material, tech, pb, scene, old=old, capacity=cap,
                              part=part, context_word=context, priority=priority, node_priority=np, tag=tag,
                              lookup=(7, 1, 0x803, 2, 4, bytes(range(64))))
            route = queue_route(code, material, tech, pb, scene)
            record = [p.BASE+0x2000, part] if code == 8 else [p.BASE+0x2000, part, p.BASE+0x4000 if material else 0,
                                                                       np if priority == 0x7fffffff else priority, tag]
            self.assertEqual(actual['records'], old+[record])
            self.assertEqual(actual['queueOffset'], route['queueOffset'])
            self.assertEqual(actual['selectorCalls'], route['selectorCalls'])
            self.assertEqual(actual['lockCalls'], route['selectorCalls']*2)
            self.assertEqual(actual['returnWord'], 1)
            growth = n == cap; expected_capacity = n+max(n, 1) if growth else cap
            self.assertEqual(actual['capacity'], expected_capacity)
            self.assertEqual(actual['allocationBytes'], [expected_capacity*route['recordBytes']] if growth else [])
            self.assertEqual(actual['freedOld'], growth and cap > 0)

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_original_skip_and_distance_frontier_do_not_claim_insertion(self):
        from analyze_native_resources import NativeImage
        from native_sky_queue_probe import NativeSkyQueueProbe
        p = NativeSkyQueueProbe(NativeImage(NATIVE.read_bytes()))
        for material in (False, True):
            for first, second in [(1, 1), (3, 3), (2, 1), (1, 2)]:
                result = p.insert(3, material, node_word_210=first, node_word_200=second)
                self.assertEqual(bool(result['records']), not bool(first & second & 1))
        for flags in (1, 3, 255):
            result = p.insert(3, True, flags, 0x40, 0)
            self.assertFalse(result['completed']); self.assertIsNone(result['returnWord'])
            self.assertEqual(result['selectorCalls'], 1)
            self.assertEqual(result['allocationBytes'], []); self.assertEqual(result['records'], [])

    @unittest.skipUnless(NATIVE.is_file(), 'Original native sample is local only')
    def test_new_technique_and_append_code_fingerprints_fail_closed(self):
        from analyze_native_resources import NativeImage
        image = NativeImage(NATIVE.read_bytes()); read = image.read
        for target in ROUTINES:
            def changed(at, size, target=target):
                data = read(at, size)
                return bytes([data[0] ^ 1])+data[1:] if at == target else data
            image.read = changed
            with self.assertRaises(ValueError): verify_native(image)

    @unittest.skipUnless(NATIVE.is_file() and SOURCE.is_dir(), 'Original sky sources stay local')
    def test_source_declarations_do_not_become_runtime_queue_flags(self):
        from analyze_native_resources import NativeImage
        from resource_packs import ResourceArchive, index, normalize_resource_name
        entries, packs = {}, {}
        for entry in index(SOURCE): entries.setdefault(normalize_resource_name(entry['path']), []).append(entry)
        def extract(name):
            entry, = entries[normalize_resource_name(name)]; pack = entry['pack']
            if pack not in packs: packs[pack] = ResourceArchive(SOURCE/pack)
            return packs[pack].read(name)
        report = analyze_queue(NativeImage(NATIVE.read_bytes()), extract)
        self.assertEqual(report['format'], FORMAT); self.assertFalse(report['appliedAsLiveState'])
        self.assertEqual(report['sourceDeclaration']['techniqueByName']['name'], 'solid')
        self.assertFalse(report['sourceDeclaration']['usedAsRuntimeQueueFlags'])
        self.assertFalse(report['techniqueSelector']['argumentProducersRecovered'])
        self.assertEqual(report['records']['16'], ['node64', 'part64'])
        self.assertIn('frontier', report['queues']['3']['techBit0WithoutSceneByte_40'])


if __name__ == '__main__': unittest.main()
