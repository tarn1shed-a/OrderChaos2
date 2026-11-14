"""Package boundaries and private append replay; no save is opened."""
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from creation_preview_delivery import ROOT, safe_members, payload


class Guards(unittest.TestCase):
    def test_noncanonical_paths_and_links_are_never_accepted(self):
        for name in ['../save', '/data/saves/characters.json', 'a/../save', 'a\\b', './a', 'a//b']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                p = Path(td)/'bad.tar.gz'
                with tarfile.open(p, 'w:gz') as archive:
                    m = tarfile.TarInfo(name);m.size = 1;archive.addfile(m, io.BytesIO(b'x'))
                with self.assertRaises(ValueError): safe_members(p)


STAGE = ROOT/'analysis/raw/creation-stage-transform-20261115/source-stage-v2.json'
ENV = ROOT/'analysis/raw/selection-scene-environment-upstream-20261115/result-v2-fresh-inputs.json'
@unittest.skipUnless(STAGE.is_file() and ENV.is_file(), 'Private source candidates absent')
class Private(unittest.TestCase):
    def test_only_admitted_runtime_assets_and_modules_are_copied(self):
        import json
        data = payload(STAGE, ENV)
        self.assertEqual(len(data), 225)
        self.assertTrue(all(k.startswith(('game-data/converted/source-', 'prototype/public/')) for k in data))
        self.assertFalse(any(k.endswith(('.so', '.tbl', '.c', '.html')) or 'saves/' in k or '-private.json' in k for k in data))
        profile = json.loads(data['game-data/converted/source-creation-stage/manifest.json'])
        self.assertFalse(profile['createsPlayableRole']);self.assertFalse(profile['wholeCreationRestored'])
        self.assertEqual(profile['stages'], ['CharacterChooseRace'])
        stage = json.loads(data['game-data/converted/source-creation-stage/stage.json'])
        self.assertEqual(stage['racePanel']['panel'], 0)
        self.assertTrue(all('frames' not in row for row in stage['cameraGroups']))


if __name__ == '__main__': unittest.main()
