"""Guarded local transport patch replay; no original server equivalence claim."""
import shutil,tempfile,unittest
from pathlib import Path
from tutorial_map_geometry import ROOT
from connect_mvp_capacity import connect,PINS

RAW=ROOT/'analysis/raw/mvp-entry-20261113'
RUN=ROOT/'analysis/raw/showcase-20261110/running-preview'
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
            for name,value in before.items():self.assertEqual(value,(RUN/name).read_bytes())
            with self.assertRaises(ValueError):connect(out)
            self.assertEqual(before,{name:(out/name).read_bytes()for name in PINS})

if __name__=='__main__':unittest.main()
