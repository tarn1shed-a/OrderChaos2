"""Check original path links and lookup boundaries, without inventing a spawn."""
import json
import unittest
from pathlib import Path
from tutorial_waypoint_evidence import chains, probe

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'analysis/raw/showcase-20261110/running-preview'


class Links(unittest.TestCase):
    def test_links_not_row_order_and_duplicate_terminal_positions_are_preserved(self):
        def row(identifier, next_id, x):
            return dict(id=identifier, first_wp_id=4, next_wp_id=next_id, x=x, y=2, z=3)
        route, = chains([row(9, 0, 8), row(4, 7, 1), row(7, 9, 8)])
        self.assertEqual(route['order'], [4, 7, 9])
        self.assertEqual(route['positions'][-2:], [[8, 2, 3], [8, 2, 3]])
        self.assertEqual(route['termination'], 'zero')

    def test_loop_and_missing_link_stay_explicit_instead_of_being_filled(self):
        row = dict(id=1, first_wp_id=1, next_wp_id=1, x=0, y=0, z=0)
        self.assertEqual(chains([row])[0]['termination'], 'loop')
        self.assertEqual(chains([{**row, 'next_wp_id': 2}])[0]['termination'], 'missing')


@unittest.skipUnless((RUN/'prototype/native-physics.json').is_file(),
                     'Original table/native inputs remain local')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = probe(RUN)

    def test_all_source_chains_are_complete_but_not_activation_or_spawn_evidence(self):
        s = self.report['source']
        self.assertEqual(s['map5Rows'], 48)
        self.assertEqual(len(s['chains']), 20)
        self.assertTrue(all(r['termination'] == 'zero' and not r['unvisited'] for r in s['chains']))
        self.assertFalse(s['actualPathActorAndTriggerKnown'])
        self.assertFalse(s['originalFirstEntryKnown'])
        route, = [r for r in s['chains'] if r['first'] == 4768]
        self.assertEqual(route['order'], list(range(4768, 4778)))
        self.assertEqual(route['positions'][-1], route['positions'][-2])
        self.assertEqual(s['allCreatureWaypointReferences'], 934)
        self.assertEqual(s['directReferencesToAnySelectedPoint'], [])

    def test_original_lookup_copies_all_bytes_and_does_not_filter_map_phase_or_valid(self):
        r = self.report
        self.assertEqual(len(r['originalCachedLookups']), 49)
        self.assertTrue(all(x['calls'] == [{'kind': 'memcpy-adapter', 'bytes': 76}]
                            for x in r['originalCachedLookups']))
        self.assertEqual(r['explicitSyntheticFlagsCopiedWithoutFiltering'],
                         {'valid': 0, 'map_id': 999, 'phasing_id': 777})
        self.assertFalse(r['gameplayChanged'])
        self.assertEqual(r['nativeLookup']['directBOrBLToAccessor'], [])

    def test_missing_and_empty_preserve_output_uncached_body_is_not_claimed(self):
        self.assertEqual(self.report['missingIDs'], [0, 0x7fffffff])
        self.assertTrue(self.report['emptyCachePreservesOutput'])
        self.assertEqual(self.report['uncachedCalls'],
                         [{'kind': 'uncached-boundary-not-executed'}])

    def test_native_fingerprint_change_is_rejected_before_execution(self):
        from analyze_native_resources import NativeImage
        from native_waypoint_probe import NativeWaypointProbe
        cfg = json.loads((RUN/'prototype/native-physics.json').read_text())
        image = NativeImage(Path(cfg['library']).read_bytes())
        class Changed:
            elf = image.elf
            def read(self, at, size):
                raw = image.read(at, size)
                return bytes([raw[0]^1])+raw[1:] if at == 0xc9fa18 else raw
        with self.assertRaisesRegex(ValueError, 'lookup differs'):
            NativeWaypointProbe(Changed())


if __name__ == '__main__':
    unittest.main()
