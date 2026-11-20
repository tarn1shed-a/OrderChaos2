"""Actual worker transport and original CPU model identity, not a pose gallery."""
import ast
import copy
from contextlib import contextmanager
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
import source_species_worker as worker
from pathlib import Path
from source_species_worker import staged_worker_source, bind_source_reset, forget_source_actor

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT/'analysis/raw/selection-stage-release-20261115/mac-equivalent-inputs/native-physics.json'
PROFILES = ROOT/'analysis/raw/species-world-router-20261115/profiles-v1.json'


@contextmanager
def worker_fixture(raw=None, *, declaration=True):
    """Local source/declaration fixture only; never starts a worker or Uc."""
    worker_bytes = Path(worker.__file__).read_bytes()
    original = (ROOT/'tools/source_physics_worker.py').read_bytes()
    current = json.loads((ROOT/'tools/source_world_python.json').read_text())
    if hashlib.sha256(original).hexdigest() != current['files']['tools/source_physics_worker.py']:
        raise AssertionError('Actual current worker must match the installed declaration')
    with tempfile.TemporaryDirectory(prefix='species-source-control-') as folder:
        tools = Path(folder)/'tools'
        tools.mkdir()
        physics = tools/'source_physics_worker.py'
        fixture_worker = tools/'source_species_worker.py'
        fixture_worker.write_bytes(worker_bytes)
        physics.write_bytes(original if raw is None else raw)
        # Derive from the real current declaration; only candidate self identity
        # and an explicitly requested source fixture are rebound in this fixture.
        current['files']['tools/source_species_worker.py'] = hashlib.sha256(worker_bytes).hexdigest()
        current['files']['tools/source_physics_worker.py'] = hashlib.sha256(physics.read_bytes()).hexdigest()
        manifest = tools/'source_world_python.json'
        if declaration:
            manifest.write_text(json.dumps(current))
        with mock.patch.object(worker, '__file__', str(fixture_worker)):
            yield SimpleNamespace(physics=physics, worker=fixture_worker,
                                  manifest=manifest, declaration=current)


def legacy_worker_bytes():
    """Reverse exactly three reviewed host additions, then require old full SHA."""
    source = (ROOT/'tools/source_physics_worker.py').read_text()
    edits = [
        ("    image=NativeImage.from_file(root,{'path':cfg['library'],'sha256':NATIVE_SHA256})",
         "    image=NativeImage(Path(cfg['library']).read_bytes())"),
        ("    from source_guest_pages import reclaim_guest_pages\n    if not engine.actors:reclaim_guest_pages(engine.uc)\n", ''),
        ("            elif op=='forget':\n                engine.actors.pop(data['identity'],None);result=True\n"
         "                if not engine.actors:reclaim_guest_pages(engine.uc)",
         "            elif op=='forget':engine.actors.pop(data['identity'],None);result=True"),
    ]
    for before, after in edits:
        if source.count(before) != 1:
            raise AssertionError('Known host-only reverse fixture anchor differs')
        source = source.replace(before, after)
    raw = source.encode()
    if hashlib.sha256(raw).hexdigest() != worker.WORKER_SHA256:
        raise AssertionError('Historical fixture bytes differ from the exact old worker')
    return raw


class PublicTests(unittest.TestCase):
    def test_reviewed_worker_stays_unchanged_and_new_copy_compiles(self):
        self.assertNotIn('capstone', sys.modules)
        self.assertNotIn('source_physics_worker', sys.modules)
        before = (ROOT/'tools/source_physics_worker.py').read_bytes()
        with worker_fixture():
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


class CurrentDeclarationControls(unittest.TestCase):
    def test_old_exact_contract_does_not_read_current_manifest(self):
        with worker_fixture(legacy_worker_bytes(), declaration=False):
            source = staged_worker_source()
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),
                         '5fcdd9367cb73d83f3cb719c9f38adced9a4ba303bdb7c4ea1eda714143321f8')
        compile(source, 'historical-exact-staged-worker', 'exec')
        self.assertNotIn('reclaim_guest_pages', source)

    def test_current_source_compiles_and_preserves_original_host_additions(self):
        with worker_fixture():
            source = staged_worker_source()
        compile(source, 'current-declared-staged-worker', 'exec')
        self.assertIn("NativeImage.from_file(root,{'path':cfg['library'],'sha256':NATIVE_SHA256})", source)
        self.assertEqual(source.count('if not engine.actors:reclaim_guest_pages(engine.uc)'), 2)
        self.assertIn("            elif op=='forget':\n"
                      "                forget_source_actor(engine,data['identity']);result=True\n"
                      "                if not engine.actors:reclaim_guest_pages(engine.uc)", source)

    def test_mutated_target_does_not_derive_its_own_expected_digest(self):
        with worker_fixture() as case:
            case.physics.write_bytes(case.physics.read_bytes()+b'\n# unreviewed target\n')
            with self.assertRaisesRegex(ValueError, 'current worker identity differs: tools/source_physics_worker.py'):
                staged_worker_source()

    def test_mutated_wrapper_self_identity_is_rejected(self):
        with worker_fixture() as case:
            case.worker.write_bytes(case.worker.read_bytes()+b'\n# unreviewed wrapper\n')
            with self.assertRaisesRegex(ValueError, 'current worker identity differs: tools/source_species_worker.py'):
                staged_worker_source()

    def test_missing_declaration_cannot_admit_current_source(self):
        with worker_fixture(declaration=False):
            with self.assertRaises(FileNotFoundError):
                staged_worker_source()

    def test_wrong_declaration_shape_and_fixed_target_pins_are_rejected(self):
        for malformed in ([], {'format':'unknown', 'files':{}},
                          {'format':'oc2-source-world-python-closure-v1', 'files':[]},
                          {'format':'oc2-source-world-python-closure-v1', 'files':{}},
                          {'format':'oc2-source-world-python-closure-v1', 'files':{
                              'tools/source_physics_worker.py':'f'*64}},
                          {'format':'oc2-source-world-python-closure-v1', 'files':{
                              'tools/source_physics_worker.py':'F'*64}}):
            with self.subTest(declaration=malformed):
                with worker_fixture() as case:
                    case.manifest.write_text(json.dumps(malformed))
                    with self.assertRaises(ValueError):
                        staged_worker_source()

    def test_declared_but_unknown_or_duplicate_transform_anchors_are_rejected(self):
        raw = (ROOT/'tools/source_physics_worker.py').read_bytes()
        for changed in (raw.replace(b'        engine_type=SourceLayerQueue',
                                    b'        engine_type=UnreviewedQueue', 1),
                        raw+b'\n# duplicate exact staged anchor\n        engine_type=SourceLayerQueue\n',
                        raw.replace(b'                if not engine.actors:reclaim_guest_pages(engine.uc)',
                                    b'                if not engine.actors:unknown_reclaim(engine.uc)',1)):
            with self.subTest(sourceSHA=hashlib.sha256(changed).hexdigest()):
                with worker_fixture(changed):
                    with self.assertRaisesRegex(ValueError, 'Source species worker anchor differs'):
                        staged_worker_source()

    def test_current_forget_preserves_peer_and_reclaims_only_last_actor(self):
        with worker_fixture():
            source = staged_worker_source()
        tree = ast.parse(source)
        blocks = [node for node in ast.walk(tree) if isinstance(node,ast.If)
                  and isinstance(node.test,ast.Compare)
                  and isinstance(node.test.left,ast.Name) and node.test.left.id=='op'
                  and len(node.test.comparators)==1
                  and isinstance(node.test.comparators[0],ast.Constant)
                  and node.test.comparators[0].value=='forget']
        self.assertEqual(len(blocks),1)
        # Execute only the exact generated forget branch against host fixtures.
        # This is not Native replay or proof of original actor internals.
        function=ast.parse('def projected_forget(engine,data):\n    pass\n').body[0]
        function.body=blocks[0].body+[ast.Return(value=ast.Name(id='result',ctx=ast.Load()))]
        module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
        reclaimed=[]
        namespace={'forget_source_actor':forget_source_actor,
                   'reclaim_guest_pages':lambda uc:reclaimed.append(uc)}
        exec(compile(module,'exact-generated-forget-host-control','exec'),namespace)
        token=object();engine=SimpleNamespace(actors={'a':object(),'b':object()},
                  species_actors={'a':'human-male','b':'elf-male'},uc=token)
        peer=engine.actors['b']
        self.assertIs(namespace['projected_forget'](engine,{'identity':'a'}),True)
        self.assertEqual(reclaimed,[]);self.assertIs(engine.actors['b'],peer)
        self.assertEqual(engine.species_actors,{'b':'elf-male'})
        self.assertIs(namespace['projected_forget'](engine,{'identity':'b'}),True)
        self.assertEqual(reclaimed,[token]);self.assertEqual(engine.actors,{})
        self.assertEqual(engine.species_actors,{})


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
