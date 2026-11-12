"""Guarded local transport patch replay; no original server equivalence claim."""
import hashlib,shutil,tempfile,unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from connect_mvp_capacity import connect,PINS

RAW=ROOT/'analysis/raw/mvp-entry-20261113'
# Pin the reviewed capacity-patch output. The current private preview may
# legitimately contain later independent rendering fixes.
OUTPUTS={
 'prototype/server.mjs':'3dcb69fed7f05eb5a38027a1bc440361832a873db93e5ad95f3dbe923997b7eb',
 'prototype/public/explore-map.js':'a524d8052643bf3a706acb3e641860b3a003e1d96ea2435008ecd0950d5faf97',
}
class Public(unittest.TestCase):
    def test_refuses_live_project(self):
        with self.assertRaises(ValueError):connect(ROOT)

@unittest.skipUnless((RAW/'before-runtime/prototype/server.mjs').is_file(),'Reviewed historical runtime stays local')
class Local(unittest.TestCase):
    def test_replays_exact_two_files_and_preserves_repeat_or_unknown_changes(self):
        with tempfile.TemporaryDirectory(dir=RAW)as d:
            out=Path(d)
            for name in PINS:
                p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(RAW/'before-runtime'/name,p)
            self.assertEqual(connect(out)['minimumPlayersToJoin'],1)
            before={name:(out/name).read_bytes()for name in PINS}
            for name,value in before.items():self.assertEqual(hashlib.sha256(value).hexdigest(),OUTPUTS[name])
            with self.assertRaises(ValueError):connect(out)
            self.assertEqual(before,{name:(out/name).read_bytes()for name in PINS})

if __name__=='__main__':unittest.main()
