"""Verify the creation-scene append preserves old world/assets and save boundaries."""
import json
import unittest
from pathlib import Path
from selection_stage_delivery import ROOT, BASE, PACKS, additions
from creation_preview_delivery import safe_members


class Public(unittest.TestCase):
    def test_no_character_or_world_runtime_is_replaced_by_the_append_contract(self):
        self.assertEqual([p[0] for p in PACKS], ['dry', 'flowers', 'grass', 'waterfalls', 'waterSurface', 'wetFloor'])
        self.assertEqual(sum(p[3] for p in PACKS), 47)
        for _, name, _, _, namespace, module in PACKS:
            self.assertTrue(name.startswith('selection-scene-'))
            self.assertTrue(namespace.startswith('source-selection-'))
            self.assertFalse('..' in Path(module).parts)


@unittest.skipUnless(BASE.is_file(), 'Verified source append packages remain private')
class Private(unittest.TestCase):
    def test_only_new_source_runtime_payloads_are_admitted(self):
        previous = safe_members(BASE)
        added = additions(previous)
        self.assertEqual(len(added), 54)
        self.assertFalse(set(added) & set(previous))
        self.assertFalse(any('save' in n or n.endswith(('.tbl', '.so', '.c', '.html')) or '-private.json' in n for n in added))
        p = json.loads(added['game-data/converted/source-creation-stage/manifest-v2.json'])
        self.assertFalse(p['createsPlayableRole'])
        self.assertFalse(p['wholeCreationRestored'])
        self.assertTrue(p['originalWetFloorRestored'])
        self.assertEqual(p['originalStaticInstances'], 151)
        old = json.loads(previous['game-data/converted/source-creation-stage/manifest.json'])
        for key in ['stage', 'environment', 'scene', 'inside', 'stones', 'previews']:
            self.assertEqual(p[key], old[key])


if __name__ == '__main__': unittest.main()
