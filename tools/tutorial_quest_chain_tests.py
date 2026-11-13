"""Source/CPU gates for the tutorial audit; passing is not a playable quest."""
import unittest
from pathlib import Path

from tutorial_quest_chain import link_objectives

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / 'analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so'
SOURCE = ROOT / 'game-data/com.gameloft.android.ANMP.GloftO2HM/files'


class JoinTests(unittest.TestCase):
    def test_step_order_and_two_part_join_prevent_the_tutorial_misordering(self):
        objectives = [{'id': 10, 'quest_id': 202, 'obj_idx': 2, 'step': 3},
                      {'id': 99, 'quest_id': 202, 'obj_idx': 9, 'step': 2}]
        logic = [{'quest_id': 202, 'obj_idx': 9, 'zone': 1},
                 {'quest_id': 500, 'obj_idx': 2, 'zone': 2}]
        result = link_objectives(202, objectives, logic, [{'ID': 1}, {'ID': 2}])
        self.assertEqual([r['objective']['obj_idx'] for r in result], [9, 2])
        self.assertEqual(result[1]['targets'], [])

    def test_missing_zone_and_orphan_logic_are_not_synthesised(self):
        objective = [{'quest_id': 202, 'obj_idx': 1, 'step': 1}]
        with self.assertRaisesRegex(ValueError, 'absent zone'):
            link_objectives(202, objective, [{'quest_id': 202, 'obj_idx': 1, 'zone': 8}], [])
        with self.assertRaisesRegex(ValueError, 'Orphan'):
            link_objectives(202, objective, [{'quest_id': 202, 'obj_idx': 2, 'zone': 0}], [])

    def test_duplicate_objectives_are_an_error_not_an_arbitrary_choice(self):
        row = {'quest_id': 202, 'obj_idx': 1, 'step': 1}
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            link_objectives(202, [row, row], [], [])


@unittest.skipUnless(NATIVE.is_file() and (SOURCE / 'tables.bin').is_file(),
                     'Original APK/data remain private')
class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from analyze_native_resources import NativeImage
        from map_loading_evidence import Sources
        from native_inside_collision_probe import InsidePhysicsProbe
        from tutorial_quest_chain import audit
        cls.source = Sources(SOURCE)
        cls.chain = audit(SOURCE)
        cls.engine = InsidePhysicsProbe(NativeImage(NATIVE.read_bytes()))

    def test_tutorial_has_ten_steps_but_no_proved_finish_predicate(self):
        c = self.chain
        self.assertEqual([r['objective']['obj_idx'] for r in c['steps']],
                         [1, 9, 2, 3, 4, 5, 10, 6, 7, 8])
        self.assertEqual(c['quest']['FinishGiverID'], 0)
        self.assertEqual(c['quest']['AutoShowFinish'], 1)
        self.assertIsNone(c['completionPredicate'])
        self.assertIsNone(c['acceptedQuest'])
        self.assertFalse(c['routeVerified'])

    def test_source_elevator_and_manual_spawns_prevent_static_only_certification(self):
        elevator, = self.chain['elevatorSpawns']
        self.assertEqual([elevator['id'], elevator['Entry']], [739, 209])
        self.assertAlmostEqual(elevator['elevator_star_y'] - elevator['elevator_over_y'],
                               32.96, places=3)
        hammer, = [r for r in self.chain['objectSpawns'] if r['Entry'] == 190]
        self.assertEqual(hammer['manual_spawn'], 1)
        self.assertEqual(self.chain['npcInteractions'], [])

    def test_native_inside_branch_keeps_normal_chain_when_extra_file_is_absent(self):
        for model, count in [('god_underground_palace01', 70),
                             ('god_underground_palace02', 24),
                             ('god_temple01_inside01', 20)]:
            path = 'model/scene_generator_temple_000/' + model
            for quality in (False, True):
                with self.subTest(model=model, simplified=quality):
                    result = self.engine.select(path + '.bdae', self.source, simplified=quality)
                    self.assertEqual(result['originalReturn'], 1)
                    self.assertEqual(result['shapeCount'], count)
                    self.assertEqual(result['readRequests'], [path + '.phy', path + '_inside.phy'])
                    self.assertTrue(result['normalChainUnchanged'])
                    if quality:
                        self.assertIn(path + '_inside_s.phy', result['presenceProbes'])

    def test_truncated_fourth_phy_never_turns_into_a_fabricated_floor(self):
        path = 'model/scene_generator_temple_000/god_underground_palace02_02.bdae'
        with self.assertRaisesRegex(RuntimeError, 'requested truncated bytes'):
            self.engine.select(path, self.source)


if __name__ == '__main__':
    unittest.main()
