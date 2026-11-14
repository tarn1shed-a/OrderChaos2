"""Check the original paths/string reader; never turn a table into a script."""
import unittest

from tutorial_script_entry_probe import ROOT, RAW, SO, private_output


class OutputBoundaryTests(unittest.TestCase):
    def test_original_rows_cannot_be_exported_to_public_assets(self):
        with self.assertRaises(ValueError):
            private_output(ROOT / 'prototype/public/scripts.json')


@unittest.skipUnless(SO.is_file(), 'Original ARM64 library/tables stay private')
class OriginalEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tutorial_script_entry_probe import run
        cls.r = run()

    def test_original_default_and_debug_table_paths_are_separate(self):
        for name in ('quests', 'scripts'):
            controls = [r for r in self.r['pathRequests'] if r['table'] == name]
            self.assertEqual(controls[0]['requestedPaths'], ['tables/' + name + '.tbl'])
            self.assertEqual(controls[1]['requestedPaths'], ['tables_test/' + name + '.tbl'])

    def test_explicit_path_is_not_an_invented_script_extension(self):
        for name in ('quests', 'scripts'):
            control = [r for r in self.r['pathRequests'] if r['table'] == name][2]
            self.assertEqual(control['requestedPaths'], ['research/explicit-table.tbl'])

    def test_loaded_table_early_return_and_force_bit_are_original_branches(self):
        for name in ('quests', 'scripts'):
            controls = [r for r in self.r['pathRequests'] if r['table'] == name]
            self.assertEqual(controls[3]['requestedPaths'], [])
            self.assertTrue(controls[3]['completeAlreadyLoadedEarlyReturn'])
            self.assertEqual(controls[4]['requestedPaths'], ['tables/' + name + '.tbl'])
            self.assertTrue(all(not r['fileOpenSuccessSupplied'] for r in controls))

    def test_real_records_preserve_script_name_fields_and_all_other_values(self):
        quest, scripts = self.r['rows']
        self.assertEqual((len(quest['fields']), quest['sourceBytes'], quest['runtimeBytes']), (52, 218, 228))
        self.assertEqual(quest['fields']['script'], {'offset': 0x70, 'value': 'tutorial_quest202'})
        self.assertEqual((len(scripts['fields']), scripts['sourceBytes'], scripts['runtimeBytes']), (3, 16, 20))
        self.assertEqual(scripts['fields']['scriptFile'], {'offset': 4, 'value': 'quest_test_ai'})
        self.assertTrue(all(r['allFieldsEqual'] and r['originalStringSpanBodyExecuted'] for r in self.r['rows']))

    def test_actual_string_body_seeks_reads_and_rejects_the_past_end_span(self):
        for row in self.r['rows']:
            spans = [r for r in row['stringSpans'] if r['length']]
            expected = [item for r in spans for item in
                        ({'operation': 'seek', 'offset': r['offset']},
                         {'operation': 'read', 'offset': r['offset'], 'length': r['length']})]
            self.assertEqual(row['sourceStreamCalls'], expected)
        empty, overflow = self.r['originalStringSpanControls']
        self.assertEqual((empty['result'], overflow['result']), (1, 0))
        self.assertTrue(all(r['holderUnchanged'] and r['textUnchanged'] and not r['fileCalls']
                            for r in (empty, overflow)))

    def test_quest_name_read_is_reference_release_not_a_body_load(self):
        release = self.r['rows'][0]['scriptReferenceRelease']
        self.assertEqual(release['reads'], [{'pc': '0x3e78d0', 'bytes': 8}])
        self.assertEqual((release['researchRefcountBefore'], release['researchRefcountAfter']), (1000, 999))
        self.assertFalse(release['bodyLoadedOrCalled'])
        self.assertFalse(self.r['originalScriptsLoaded'])
        self.assertFalse(self.r['savesOrProductionAccessed'])


if __name__ == '__main__':
    unittest.main()
