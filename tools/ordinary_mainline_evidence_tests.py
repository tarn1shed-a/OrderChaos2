"""Guards against inventing task edges, source objectives or dialogue text."""
import unittest
from pathlib import Path

from ordinary_mainline_evidence import id_list, objective_refs, references, audit
from resource_packs import DEFAULT_SOURCE


class ReferenceTests(unittest.TestCase):
    def test_source_space_separated_exclusions_are_not_lost(self):
        self.assertEqual(id_list('186 463'), [186, 463])
        self.assertEqual(id_list('186, 463'), [186, 463])
        self.assertEqual(id_list('0'), [])
        for value in ['186 186', '0 186', '-186', '186;463']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                id_list(value)

    def test_exclusion_is_not_a_prerequisite_and_other_quests_do_not_join(self):
        rows = [{'entry': 208, 'RequiredQuest': '0', 'RequiredOneOfQuest': '', 'RemoveQuests': '186 463'},
                {'entry': 447, 'RequiredQuest': '208', 'RequiredOneOfQuest': '', 'RemoveQuests': ''},
                {'entry': 461, 'RequiredQuest': '0', 'RequiredOneOfQuest': '', 'RemoveQuests': '186'}]
        self.assertEqual(references(rows), [{'from': 208, 'to': 447, 'sourceField': 'RequiredQuest'}])

    def test_orphan_is_reported_without_becoming_a_second_step(self):
        objectives = [{'quest_id': 208, 'obj_idx': 1, 'step': 1}]
        logic = [{'id': 443, 'quest_id': 208, 'obj_idx': 2},
                 {'id': 444, 'quest_id': 208, 'obj_idx': 1},
                 {'id': 99, 'quest_id': 461, 'obj_idx': 1}]
        result = objective_refs(208, objectives, logic)
        self.assertEqual([r['id'] for r in result['orphanLogic']], [443])
        self.assertEqual(len(result['steps']), 1)
        self.assertEqual([r['id'] for r in result['steps'][0]['logic']], [444])


@unittest.skipUnless((Path(DEFAULT_SOURCE)/'tables.bin').is_file(), 'Original resource tables stay private')
class OriginalSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = audit()

    def test_original_chain_and_461_separation(self):
        edges = self.report['dependencyReferences']
        self.assertIn({'from': 208, 'to': 447, 'sourceField': 'RequiredQuest'}, edges)
        self.assertIn({'from': 447, 'to': 209, 'sourceField': 'RequiredQuest'}, edges)
        self.assertFalse(any(e['from'] == 461 for e in edges))
        q = next(r for r in self.report['quests'] if r['quest']['entry'] == 208)
        self.assertEqual([r['id'] for r in q['orphanLogic']], [443])

    def test_empty_quest_script_does_not_remove_dialogue_and_object_gaps(self):
        tasks = {r['quest']['entry']: r for r in self.report['quests']}
        self.assertEqual(tasks[447]['quest']['script'], '')
        self.assertEqual(self.report['box202']['proto']['script'], 'quest208_obj202_ai')
        d = self.report['dialogue208']
        self.assertEqual([r['menu']['id'] for r in d['staticPages']], [64, 65, 66])
        self.assertEqual(len(d['unavailableTextReferences']), 6)
        self.assertEqual({r['value'] for r in d['unavailableTextReferences']}, {'test'})
        self.assertFalse(d['receivedMenuOrTextIdsKnown'])
        self.assertFalse(self.report['runtimeEnabled'])


if __name__ == '__main__':
    unittest.main()
