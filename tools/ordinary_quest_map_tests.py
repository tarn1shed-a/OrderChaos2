"""Bounded-area guards and optional private replay/source-route assertions."""
import json
import unittest
from pathlib import Path

from ordinary_quest_map import area_inputs,COORDINATES,NAMESPACE

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'analysis/raw/ordinary-mainline-route-20261115'


class OrdinaryMapAreaTests(unittest.TestCase):
    def test_default_area_keeps_original461_namespace_and_order(self):
        self.assertEqual(area_inputs(),(COORDINATES,NAMESPACE,'quest461'))

    def test_mainline_uses_its_own_original_cells_and_namespace(self):
        self.assertEqual(area_inputs(source_area='mainline208'),([(-5,0),(-4,0)],'source-mainline208-map1','mainline208'))
        self.assertEqual(area_inputs([[-4,0],[-5,0]],source_area='mainline208')[0],[(-5,0),(-4,0)])

    def test_missing_duplicate_other_map_or_arbitrary_expansion_is_rejected(self):
        for coordinates in [[],[[-5,0]],[[-5,0],[-5,0]],[[-5,0],[-4,0],[-3,0]],[[0,0],[1,0]],[[-5.0,0],[-4,0]]]:
            with self.subTest(coordinates=coordinates),self.assertRaises(ValueError):area_inputs(coordinates,source_area='mainline208')
        with self.assertRaises(ValueError):area_inputs(source_area='map2')

    def test_namespace_cannot_escape_or_replace_current461_payload(self):
        for namespace in ['../source-old','/absolute','two/parts','source x',NAMESPACE]:
            with self.subTest(namespace=namespace),self.assertRaises(ValueError):area_inputs(namespace=namespace,source_area='mainline208')

    def test_polygon_offsets_cannot_execute_on_another_original_build(self):
        from ordinary_mainline_zone_probe import MainlineZoneProbe
        class Changed:
            data=b'other original build'
        with self.assertRaisesRegex(ValueError,'native build differs'):MainlineZoneProbe(Changed())

    @unittest.skipUnless((RAW/'default461-replay-v1/audit.json').is_file(),'Original private461 replay stays local')
    def test_actual_default_export_bytes_match_frozen461_payload(self):
        old=ROOT/'analysis/raw/plain-quest-map1-20261115/candidate-v3';new=RAW/'default461-replay-v1'
        paths=[Path('audit.json')]+[p.relative_to(old)for name in('assets','native-source')for p in(old/name).rglob('*')if p.is_file()]
        self.assertGreater(len(paths),100)
        for path in paths:
            with self.subTest(path=str(path)):self.assertEqual((old/path).read_bytes(),(new/path).read_bytes())

    @unittest.skipUnless((RAW/'map-candidate-v1/assets/source-mainline208-map1/manifest.json').is_file(),'Original private208 context stays local')
    def test_actual208_geometry_and_region_do_not_reuse461_coordinates_or_overlay(self):
        folder=RAW/'map-candidate-v1/assets/source-mainline208-map1'
        manifest=json.loads((folder/'manifest.json').read_text());terrain=json.loads((folder/'terrain.json').read_text());environment=json.loads((folder/'environment.json').read_text())
        self.assertEqual(manifest['sourceArea']['questId'],208);self.assertEqual(terrain['tileOrigin'],[-5,0]);self.assertEqual(terrain['tileCount'],[2,1])
        self.assertEqual([terrain['bounds']['min'][0],terrain['bounds']['max'][0],terrain['bounds']['min'][2],terrain['bounds']['max'][2]],[-320,-192,0,64])
        self.assertEqual([environment['sourceRegionId'],environment['sourceOverlayId']],[3,5])
        evidence=environment['sourceRouteRegionEvidence'];self.assertTrue(evidence['originalContainmentAndPolygonPreparationExecuted']);self.assertFalse(evidence['originalFull4c4de4Executed'])
        self.assertEqual({(p['baseId'],p['overlayId'])for p in evidence['points']},{(3,5)})


if __name__=='__main__':unittest.main()
