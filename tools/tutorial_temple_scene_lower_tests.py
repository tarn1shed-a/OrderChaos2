"""Original archive/inside-consumer checks; no source assets are distributed."""
import unittest

from tutorial_temple_scene_lower_probe import DEFAULT_NATIVE, OLD_MODEL, POINTS, investigate


class OriginalLower(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not DEFAULT_NATIVE.exists():
            raise unittest.SkipTest('Original local resources are not distributed')
        try:
            import capstone  # noqa: F401
            import elftools  # noqa: F401
            import unicorn  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('Optional original-instruction dependencies unavailable')
        from resource_packs import DEFAULT_SOURCE
        cls.result = investigate(DEFAULT_SOURCE, DEFAULT_NATIVE)

    def test_all_original_inside_references_are_in_the_existing_room_route(self):
        inv = self.result['inventory']
        self.assertEqual(inv['allTutorialITMTypeCounts'], {'2': 1258, '8': 92, '15': 4})
        self.assertEqual(len(inv['insideRows']), 4)
        self.assertTrue(all(-65 < r['position'][2] < -63 for r in inv['insideRows']))
        old, = [r for r in inv['selectedOriginalRows'] if r['model'] == OLD_MODEL]
        self.assertEqual(old['sourceType'], 2)
        self.assertEqual(old['id'], 715733128)
        self.assertFalse(any('god_temple06' in r['model'] for r in inv['selectedOriginalRows']))

    def test_no_extra_inside_files_are_fabricated(self):
        inv = self.result['inventory']
        self.assertFalse(inv['originalOldModelInsideCompanionPresent'])
        self.assertTrue(all(r['companionCandidates'] == r['insidePHYCandidates'] == 0 for r in inv['insideRows']))
        self.assertFalse(any(r['containsOldModelStem'] or r['containsInsideWord'] for r in inv['tutorialXML']))

    def test_actual_source_shapes_drive_the_original_point_query(self):
        for case in self.result['originalInsideConsumer']:
            flags = [r['flags'] for r in case['preparedOriginalPHY']['runtimeShapeFlags']]
            # The original transform adds bit30; no source low-bit inside flags
            # are supplied merely to make the state consumer request a change.
            self.assertTrue(all(v in (0x40000000, 0x40000800) for v in flags))
            for row in case['consumer'][:-1]:
                self.assertFalse(row['selectedThisInsideOwner'])
                self.assertEqual(row['presentationRequests'], [])
            center = case['consumer'][-1]
            self.assertTrue(center['selectedThisInsideOwner'])
            self.assertEqual(center['ownerStateAfter'], 1)
            self.assertEqual(center['presentationRequests'], [{'kind': 'companion-visibility-request',
                                                              'visible': True, 'propagate': 1}])

    def test_explicit_boundaries_do_not_claim_live_inside_or_spawn(self):
        scope = self.result['scope']
        self.assertTrue(scope['resourceWrapperAndHeroPositionAreInputs'])
        self.assertTrue(scope['presentationSinksAreNotLoadedCompanionModels'])
        for key in ('originalLiveInsideStateRecovered', 'productionChanged', 'savesChanged',
                    'sourceShapeFlagsChanged', 'originalSpawnRecovered'):
            self.assertFalse(scope[key])


if __name__ == '__main__':
    unittest.main()
