"""Check route evidence boundaries, without inventing traversal or activity."""
import copy
import hashlib
import json
import unittest

from tutorial_mainline_route_probe import ROOT, RAW, mainline_order, private_path, zone_samples


class RouteBoundaryTests(unittest.TestCase):
    def test_source_box_sampling_is_not_a_rotated_or_public_export_fallback(self):
        z = {'x': 0, 'z': 0, 'box_x': 2, 'box_y': 8, 'box_z': 2, 'box_orientation': 0}
        self.assertEqual(len(zone_samples(z)), 9)
        with self.assertRaises(ValueError):
            zone_samples({**z, 'box_orientation': 1})
        with self.assertRaises(ValueError):
            private_path(ROOT / 'prototype/public/route.json')


@unittest.skipUnless((RAW / 'route-v2.json').is_file(), 'Private source mainline report unavailable')
class OriginalMainlineRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = json.loads((RAW / 'route-v2.json').read_text())
        cls.a = {x['step']: x for x in cls.r['areas']}

    def test_all_ten_source_steps_preserve_actual_objective_order(self):
        self.assertEqual(self.r['sourceOrder'], [1, 9, 2, 3, 4, 5, 10, 6, 7, 8])
        self.assertEqual([self.a[n]['zone']['ID'] for n in range(1, 11)],
                         [341, 252, 644, 253, 253, 256, 1819, 255, 257, 258])
        chain = {'quest': {'entry': 202}, 'mapId': 5,
                 'steps': [{'objective': a['objective'], 'targets': [{'zone': a['zone']}]}
                           for a in self.r['areas']]}
        self.assertEqual(len(mainline_order(chain)), 10)
        changed = copy.deepcopy(chain); changed['steps'][1]['objective']['obj_idx'] = 2
        with self.assertRaises(ValueError):
            mainline_order(changed)

    def test_exact_current_static_source_payloads_and_native_world_are_reused(self):
        self.assertEqual((self.r['formalManifest']['models'], self.r['formalManifest']['staticPlacements']), (162, 1262))
        self.assertEqual([self.r['staticQuerySet'][k] for k in ('tiles', 'instances', 'shapes')], [251, 1044, 2827])
        self.assertTrue(self.r['reusedFrozenSourceGeometryAudit']['all162ModelPayloadIdentitiesEqual'])
        self.assertTrue(self.r['productionSnapshot']['all162ModelPayloadIdentitiesEqualFrozenSourceFaceAudit'])
        self.assertEqual(self.r['productionSnapshot']['staticModelsMissingFromPublicPlan'], [])

    def test_first_uncovered_carrier_is_source_lift_not_a_fabricated_floor(self):
        for n in (4, 5):
            self.assertEqual(self.a[n]['sampledSupportsInsideOriginalZone'], 0)
            for s in self.a[n]['sourceFootprintSamples']:
                self.assertAlmostEqual(s['support']['height'], 107.64344787597656)
                self.assertEqual(s['support']['instanceId'], 684990760)
                self.assertTrue(s['support']['ownerInOriginal25TileRequestAtQuery'])
        c = self.r['firstConfirmedCarrierDependency']
        self.assertEqual((c['sourceSpawn']['id'], c['sourceSpawn']['Entry'], c['sourceProtoType']), (739, 209, 14))
        self.assertTrue(c['sourceModelAvailable'] and c['sourcePHYAvailable'])
        self.assertEqual(c['staticPlacementCountForThisModel'], 0)
        self.assertFalse(c['staticModelPlanAlreadySaysLiftRestored'])
        for k in ('originalActivityGUID', 'originalCreateMoveMessages', 'originalStartReverseClock'):
            self.assertIsNone(c[k])

    def test_original_lower_rooms_are_already_present_and_resident_for_queries(self):
        expected = {6: ('god_hammer_holder_01.bdae', 109.53375244140625),
                    7: ('god_underground_palace03.bdae', 108.72386932373047),
                    8: ('god_underground_palace02.bdae', 106.10337829589844),
                    9: ('god_underground_palace02.bdae', 106.10337829589844),
                    10: ('god_underground_palace02_02.bdae', 112.32329559326172)}
        for n, (model, height) in expected.items():
            g = self.a[n]['anchorSupport']; self.assertTrue(g['model'].endswith(model))
            self.assertAlmostEqual(g['height'], height)
            self.assertTrue(g['inCurrentFormalStaticInventory'])
            self.assertTrue(g['ownerInOriginal25TileRequestAtQuery'])

    def test_zone_overlap_and_tiny_floor_difference_do_not_complete_or_repair_tasks(self):
        self.assertEqual(self.a[3]['orderedOriginalZoneAtAnchor'], 252)
        self.assertEqual(self.a[3]['zone']['ID'], 644)
        self.assertEqual(self.a[4]['zone'], self.a[5]['zone'])
        self.assertEqual(self.a[5]['logic']['entry'], 732)
        self.assertEqual(self.a[7]['logic']['name'], 'tutorial_npc972_ai')
        self.assertEqual(self.a[7]['logic']['entry'], 0)
        d = self.a[7]['zone']['y'] - self.a[7]['anchorSupport']['height']
        self.assertGreater(d, 0); self.assertLess(d, .0002)
        self.assertEqual(self.r['confirmedStaticPayloadOmissions'], [])

    def test_triggers_walls_and_servers_object_state_are_not_interchanged(self):
        objects = {a['entry']: a for a in self.r['sourceActivityObjectCatalogue']}
        self.assertEqual(objects[188]['sourceType'], 6)
        self.assertTrue(objects[188]['sourceModel'].endswith('quest_trigger.bdae'))
        self.assertEqual(objects[237]['sourceType'], 4)
        self.assertEqual(objects[399]['sourceType'], 11)
        self.assertTrue(objects[237]['sourceModel'].endswith('tutorial_ice_wall.bdae'))
        self.assertEqual(objects[237]['sourceModel'], objects[399]['sourceModel'])
        self.assertTrue(all(not a['originalActiveGUIDAndStateKnown'] for a in objects.values()))

    def test_native_queries_do_not_claim_a_continuous_walk_or_change_game(self):
        self.assertEqual(sum(len(a['sourceFootprintSamples']) for a in self.a.values()), 90)
        self.assertTrue(all(a['continuousRouteProved'] is False and a['originalObjectiveCompletion'] is None for a in self.a.values()))
        self.assertTrue(all(s['pathRecovered'] is False and s['originalNavigationPath'] is None for s in self.r['adjacentAreaInspection']))
        self.assertIsNone(self.r['newGeometryCandidate'])
        for k in ('savesOpened', 'sharedWorkersChanged', 'deploymentChanged', 'dockerUsed', 'browserOrGPUExecuted'):
            self.assertFalse(self.r[k])

    def test_prior_frozen_batches_and_user_work_are_preserved(self):
        for row in json.loads((RAW / 'frozen-prior-files.json').read_text()):
            self.assertEqual(hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest(), row['sha256'], row['path'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
