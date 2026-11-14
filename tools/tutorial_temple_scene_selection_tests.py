"""Exact original gate/filename checks for the reviewed temple instances."""
import unittest

from tutorial_temple_scene_selection_probe import DEFAULT_NATIVE, MODELS, investigate


class OriginalSelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DEFAULT_NATIVE.exists():
            raise unittest.SkipTest('Original local resources are not distributed')
        try:
            import unicorn  # noqa: F401
            import capstone  # noqa: F401
            import elftools  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional original-instruction dependencies unavailable')
        from resource_packs import DEFAULT_SOURCE
        cls.result = investigate(DEFAULT_SOURCE, DEFAULT_NATIVE)

    def test_dynamic_word_is_not_misreported_as_map_phase(self):
        rows = self.result['records']
        self.assertEqual(len(rows), 10)
        self.assertEqual({r['model'] for r in rows}, set(MODELS))
        self.assertEqual(sum(r['sourceType'] == 2 for r in rows), 9)
        self.assertEqual(sum(r['sourceType'] == 15 for r in rows), 1)
        self.assertTrue(all(r['detailWord0x38'] == r['dynamicIDWord0x3c'] == 0xffffffff for r in rows))
        self.assertEqual(sum(len(r['gateCases']) for r in rows), 480)
        self.assertTrue(all(c['result'] == 'admittedBeforeTypeFactory' for r in rows for c in r['gateCases']))

    def test_current_source_map_phase_does_not_choose_other_tutorial_items(self):
        phase = self.result['mapPhase']
        self.assertEqual(phase['sourceTutorialRows'], [])
        self.assertTrue(phase['cases'])
        self.assertTrue(all(r['selectedPhase'] == 0 for r in phase['cases']))
        self.assertFalse(self.result['alternateTutorialITMPathsPresent'])

    def test_default_primary_requests_are_the_reviewed_files(self):
        self.assertEqual(self.result['staticCallerInitialSlot'],
                         {'incomingSlot': 0, 'requestedSlot': 0, 'forceSingleSlot': True})
        for row in self.result['records']:
            self.assertEqual(row['originalLevelLookup'], 0)
            self.assertEqual(row['originalEntityDistanceBinding'], -1)
            self.assertEqual(row['defaultPrimaryFilenameRequests'],
                             {'requests': [{'slot': 0, 'path': row['model']}], 'existsQueries': []})
            self.assertEqual(row['type15CompanionSeparate'], row['sourceType'] == 15)
        self.assertFalse(self.result['scope']['liveResourceCompletionOrVisibilityProved'])
        self.assertFalse(self.result['scope']['productionChanged'])
        self.assertFalse(self.result['scope']['savesChanged'])


if __name__ == '__main__':
    unittest.main()
