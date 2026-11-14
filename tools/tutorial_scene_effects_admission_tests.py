"""Keep rejected original detail layers out of the default map candidate."""
import unittest
from tutorial_scene_effects_assets import ROOT, LIB


class Public(unittest.TestCase):
    def test_import_does_not_require_unicorn_or_capstone(self):
        import tutorial_scene_effects_admission
        self.assertTrue(callable(tutorial_scene_effects_admission.analyze))


@unittest.skipUnless(LIB.is_file() and (ROOT/'analysis/raw/tutorial-scene-effects-20261114/remaining-admission-private.json').is_file(), 'Original inputs stay private')
class Original(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tutorial_scene_effects_admission import analyze
        cls.r = analyze()

    def test_all92_original_gates_match_prior_reviewed_baseline(self):
        self.assertEqual((self.r['admitted'], self.r['rejected']), (65, 27))
        self.assertEqual(sum(g['placements'] for g in self.r['groups']), 92)
        self.assertTrue(all(r['lookupAndAdmissionExecuted'] for g in self.r['groups'] for r in g['rows']))

    def test_default_layer4_does_not_force_level5_effects_visible(self):
        rejected = [g for g in self.r['groups'] if g['admission'].get('detailOrLevelRejected')]
        self.assertEqual({g['resource'].rsplit('/', 1)[-1] for g in rejected}, {
            'scene_fog003.beff', 'scene_sun_light_line_purple.beff', 'scene_cold_light_spot.beff', 'scene_crystal_blue.beff'})
        self.assertTrue(all(g['originalLookupLevels'] == [5] for g in rejected))
        self.assertFalse(self.r['actualAndroidSessionObserved']); self.assertFalse(self.r['newObjectsInserted'])

    def test_next_complete_admitted_group_is_ten_fire_placements(self):
        remaining = [g for g in self.r['groups'] if g['resource'] != 'effects/scene/scene_fire_smoke.beff']
        complete = [g for g in remaining if g['decoded'] and g['admission'].get('admittedBeforeTypeFactory')]
        self.assertEqual((complete[0]['resource'], complete[0]['placements'], complete[0]['originalLookupLevels']),
            ('effects/scene/scene_fire.beff', 10, [2]))
        self.assertEqual(sum(g['placements'] for g in complete), 19)


if __name__ == '__main__': unittest.main()
