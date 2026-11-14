"""Actual worker transport and original CPU model identity, not a pose gallery."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from source_species_worker import staged_worker_source, bind_source_reset, forget_source_actor

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'analysis/raw/selection-stage-release-20261115/mac-equivalent-inputs/native-physics.json'
PROFILES = ROOT/'analysis/raw/species-world-router-20261115/profiles-v1.json'


class PublicTests(unittest.TestCase):
    def test_reviewed_worker_stays_unchanged_and_new_copy_compiles(self):
        self.assertNotIn('capstone', sys.modules)
        self.assertNotIn('source_physics_worker', sys.modules)
        before = (ROOT/'tools/source_physics_worker.py').read_bytes()
        source = staged_worker_source()
        compile(source, 'source-species-worker', 'exec')
        self.assertEqual((ROOT/'tools/source_physics_worker.py').read_bytes(), before)
        self.assertIn('SourceSpeciesQueue if cfg.get', source)

    def test_invalid_reset_cannot_remove_or_reinterpret_an_actor(self):
        class Engine:
            species_profiles = {'human-male': {}, 'elf-male': {}}
            def __init__(self): self.species_actors = {}; self.actors = {}
            def bind_species(self, identity, key):
                if identity in self.actors: raise ValueError('Cannot change an existing actor')
                self.species_actors[identity] = key
        e = Engine()
        bind_source_reset(e, {'identity': 'a', 'species': 'human-male'})
        e.actors['a'] = {'original': 'state'}
        before = copy.deepcopy((e.actors, e.species_actors))
        for data in ({'identity': 'a'}, {'identity': 'a', 'species': 'unknown'},
                     {'identity': 'a', 'species': 'elf-male'}):
            with self.assertRaises(ValueError): bind_source_reset(e, data)
            self.assertEqual((e.actors, e.species_actors), before)
        bind_source_reset(e, {'identity': 'a', 'species': 'human-male'})
        self.assertEqual((e.actors, e.species_actors), before)
        forget_source_actor(e, 'a')
        self.assertEqual((e.actors, e.species_actors), ({}, {}))


@unittest.skipUnless(CONFIG.is_file() and PROFILES.is_file(), 'Private original runtime profiles required')
class ActualWorkerTests(unittest.TestCase):
    def test_pipe_reset_movement_stop_and_restore_use_each_own_original_model(self):
        output = ROOT/'analysis/raw/played-species-routing-20261115'
        output.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='worker-', dir=output) as folder:
            path = Path(folder)/'native-physics.json'
            cfg = json.loads(CONFIG.read_text())
            cfg['sourceSpeciesProfiles'] = {'path': str(PROFILES), 'sha256': hashlib.sha256(PROFILES.read_bytes()).hexdigest()}
            path.write_text(json.dumps(cfg))
            p = subprocess.Popen([sys.executable, str(ROOT/'tools/source_species_worker.py'), str(path)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                def request(operation, **data):
                    p.stdin.write(json.dumps({'operation': operation, 'data': data})+'\n');p.stdin.flush()
                    line = p.stdout.readline()
                    if not line: raise AssertionError('Worker stopped: '+p.stderr.read()[-3000:])
                    return json.loads(line)
                info = request('init')['result']
                self.assertEqual(info['sourceSpeciesKeys'], ['elf-male', 'human-female', 'human-male'])
                positions = {k: [-2235.5, 108.55000305175781, 12] for k in ['human', 'legacy']}
                for k in positions:
                    self.assertTrue(request('reset', identity=k, position=positions[k], **({'species':'human-male'}if k=='human'else{}))['result'])
                frames = {k: [] for k in positions}
                profiles = json.loads(PROFILES.read_text())
                for velocity, count in [(4.8,24),(0,38),(4.8,7),(0,38)]:
                    for _ in range(count):
                        for k in positions:
                            result = request('tick', identity=k, position=positions[k], velocity=[velocity,0], milliseconds=50,
                                             jump=False, control={'forward':bool(velocity)})['result']
                            positions[k] = result['position'];packet = result['sourceAnimation']
                            self.assertTrue(packet['available']);self.assertTrue(packet['layerPoseAgreement'])
                            if k=='human': self.assertEqual(packet['sourceMotion']['sha256'], profiles['human-male']['sha256'])
                            else: self.assertNotIn('sourceMotion', packet)
                            frames[k].append(packet)
                self.assertEqual(positions['human'], positions['legacy'])
                stops = {k: next(i for i,pkt in enumerate(frames[k][24:62]) if pkt['current']['clip']=='idle') for k in frames}
                self.assertLess(stops['human'], stops['legacy'])
                self.assertIn('error', request('reset', identity='human', position=[0,0,0], species='unknown'))
                self.assertIn('error', request('reset', identity='human', position=[0,0,0]))
                # A legitimate position restore retains the actor's own model.
                self.assertTrue(request('reset', identity='human', position=positions['human'], species='human-male')['result'])
                pkt=request('tick', identity='human', position=positions['human'], velocity=[0,0], milliseconds=50,jump=False,control={})['result']['sourceAnimation']
                self.assertEqual(pkt['sourceMotion']['key'],'human-male')
                self.assertTrue(request('forget', identity='human')['result'])
                (output/'worker-rpc-roundtrip-v1.json').write_text(json.dumps({'originalCPU':True,'transport':'real-stdin-stdout',
                    'framesPerActor':len(frames['human']),'firstIdleAfterStop':stops,'finalPositions':positions,'frames':frames},indent=2)+'\n')
            finally:
                p.terminate()
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill();p.wait()
                p.stdin.close();p.stdout.close();p.stderr.close()


if __name__ == '__main__': unittest.main(verbosity=2)
