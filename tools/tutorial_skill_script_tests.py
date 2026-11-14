"""Original event-record and indicator consumers; no script-body grant."""
import unittest

from resource_packs import DEFAULT_SOURCE
from tutorial_skill_script_probe import SO


@unittest.skipUnless(SO.is_file() and (DEFAULT_SOURCE / 'tables.bin').is_file(),
                     'Original native library and tables remain private')
class SkillScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tutorial_skill_script_probe import run as records
        from tutorial_skill_script_getter_probe import run as getter
        cls.records, cls.getter = records(), getter()

    def test_original_readers_preserve_both_named_event_records(self):
        rows = self.records['records']
        self.assertEqual([(r['decoded']['ID'], r['decoded']['scriptFunc']) for r in rows],
                         [(291, 'Skill228_OnSkillHit'), (317, 'Skill240_OnSkillHit')])
        self.assertTrue(all(r['return'] == 1 and r['nativeOutputBytes'] == 44 for r in rows))
        self.assertTrue(all(r['originalStringReader'] == '0xe881dc' for r in rows))
        self.assertFalse(self.records['scriptNamesInterpretedOrResolved'])

    def test_actual_manager_getter_returns_the_supplied_pointer_without_dereference(self):
        rows = self.getter['getterControls']
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['explicitPointer'] == r['returned'] and not r['pointeeDereferenced'] for r in rows))

    def test_eight_original_zero_indicator_fields_do_not_load_hit_events(self):
        rows = self.getter['actualRuneControls']
        self.assertEqual([r['rune'] for r in rows], list(range(912, 916)) + list(range(960, 964)))
        self.assertTrue(all(r['sourceIndicatorId'] == 0 and not r['allocationOrTableLookupSites']
                            and r['cache58SentinelsUnchanged'] for r in rows))
        self.assertFalse(self.getter['scriptNameExecutionFound'])
        self.assertFalse(self.getter['sharedOrProductionOrSaveChanged'])


if __name__ == '__main__':
    unittest.main()
