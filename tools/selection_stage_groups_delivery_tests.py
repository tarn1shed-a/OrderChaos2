"""The correction changes only the reviewed floor route, never old resources."""
import copy
import unittest
from selection_stage_groups_delivery import revised_stage, FORMAT


class RouteTests(unittest.TestCase):
    def test_corrected_profile_preserves_camera_characters_and_other_parts(self):
        before = {'format': 'oc2-source-creation-preview-delivery-v2', 'mapId': 7,
                  'createsPlayableRole': False, 'stage': 'original-stage',
                  'previews': {'0:0': {'baseURL': 'original-human'}},
                  'extensions': [{'kind': k, 'url': 'original-'+k} for k in
                                 ['dry', 'flowers', 'grass', 'waterfalls', 'waterSurface', 'wetFloor']]}
        saved = copy.deepcopy(before); actual = revised_stage(before)
        self.assertEqual(before, saved)
        self.assertEqual(actual['format'], FORMAT)
        self.assertTrue(actual['originalGroupRepresentativeMaterialCopies'])
        self.assertEqual(actual['extensions'][:-1], saved['extensions'][:-1])
        self.assertEqual(actual['extensions'][-1]['url'], '/assets/source-selection-water-floor-groups/overlay.json')
        self.assertEqual(actual['stage'], saved['stage'])
        self.assertEqual(actual['previews'], saved['previews'])
        self.assertFalse(actual['createsPlayableRole'])

    def test_unknown_predecessor_or_changed_role_policy_cannot_be_upgraded(self):
        for value in ({}, {'format': 'oc2-source-creation-preview-delivery-v2', 'mapId': 5},
                      {'format': 'oc2-source-creation-preview-delivery-v2', 'mapId': 7, 'createsPlayableRole': True}):
            with self.assertRaises(ValueError): revised_stage(value)


if __name__ == '__main__': unittest.main()
