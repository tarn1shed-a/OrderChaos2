"""Inventory boundaries: package presence is not whole-map restoration."""
import unittest
from pathlib import Path

from map_restoration_inventory import group_world_records, map_availability, inventory

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class InventoryBoundaryTests(unittest.TestCase):
    def test_basic_terrain_and_phase_variants_are_separate_without_filling_holes(self):
        rows = [{'path': p} for p in ['world/alpha.wld',
                'world/alpha/terrain/-002_0001.trn',
                'world/alpha/terrain/-004_0001.trn',
                'world/alpha/terrain/phasing/-002_0001_2.trn',
                'model/world/not-a-world.bdae']]
        result = group_world_records(rows)
        self.assertEqual(set(result), {'alpha'})
        self.assertEqual(result['alpha']['baseTerrainCount'], 2)
        self.assertEqual(result['alpha']['otherTerrainCount'], 1)
        self.assertEqual(result['alpha']['filesBySuffix']['.trn'], 3)

    def test_record_and_unique_path_counts_do_not_hide_duplicate_candidates(self):
        rows = [{'path': 'world/alpha.wld'}, {'path': 'WORLD/ALPHA.WLD'}]
        result = group_world_records(rows)['alpha']
        self.assertEqual([result['resourceRecordCount'], result['uniquePathCount']], [2,1])
        available = map_availability({'file':'world/alpha.wld'},
                                      {'world/alpha.wld':rows}, {'alpha':result})
        self.assertFalse(available['containerPresent'])
        self.assertEqual(available['containerCandidates'],2)

    def test_similar_world_name_does_not_supply_a_missing_map(self):
        groups = group_world_records([{'path':'world/dawnwatch.wld'}])
        available = map_availability({'file':'world/dawnwatch_2.wld'},
                                      {'world/dawnwatch.wld':[{}]}, groups)
        self.assertFalse(available['containerPresent'])
        self.assertIsNone(available['worldGroup'])


@unittest.skipUnless((SOURCE/'tables.bin').is_file(), 'Original map archives remain private')
class CurrentSourceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = inventory(SOURCE)

    def test_table_definitions_and_received_asset_sets_remain_distinct(self):
        r = self.report
        self.assertEqual(r['totals']['mapDefinitions'],45)
        self.assertEqual(set(r['assetGroups']),{'tutorial','dawnwatch','selection'})
        self.assertEqual(r['totals']['definitionsWithContainer'],3)
        self.assertEqual(r['totals']['definitionsMissingContainer'],42)
        self.assertEqual(r['totals']['wholeMapsAccepted'],0)

    def test_tutorial_nonordinary_records_are_not_claimed_as_visible_models(self):
        g = self.report['assetGroups']['tutorial']
        self.assertEqual(g['placementTypes'],{2:1258,8:92,15:4})
        self.assertEqual(g['decodedPlacementRows'],1354)
        self.assertEqual(g['baseTerrainCount'],251)
        self.assertEqual(g['placementDecodeErrors'],[])

    def test_every_map_keeps_all_acceptance_gates_unpassed(self):
        for row in self.report['definitions']:
            self.assertNotEqual(row['status'],'已验收')
            self.assertFalse(row['routeVerified'])
            self.assertTrue(all(v=='未验收' for v in row['gates'].values()))


if __name__ == '__main__':
    unittest.main()
