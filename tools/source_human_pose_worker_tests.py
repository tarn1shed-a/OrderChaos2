"""Real worker integration; no character store or original server messages."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from source_human_pose_worker import load_human_pose, read_input, human_pose_queue_type, staged_human_worker_source

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT/'analysis/raw/human-pose-worker-20261115'
CONFIG = Path(os.environ.get('OC2_HUMAN_POSE_QA_CONFIG', str(AREA/'runtime-v1/native-physics.json')))


class PublicTests(unittest.TestCase):
    def test_optional_runtime_dependencies_are_shipped_without_changing_base_manifest_scope(self):
        from package_deployment import python_closure
        rules = (ROOT/'.dockerignore').read_text().splitlines()
        basic = python_closure()
        extra = python_closure('source_human_pose_worker')
        self.assertEqual(basic, python_closure('source_physics_worker'))
        self.assertNotIn('tools/source_human_pose_worker.py', basic)
        self.assertIn('tools/source_human_pose_worker.py', extra)
        for name in extra: self.assertIn('!'+name, rules)

    def test_source_worker_unchanged_and_explicit_inputs_required(self):
        path = ROOT/'tools/source_physics_worker.py'
        before = path.read_bytes()
        compile(staged_human_worker_source(), 'checked-human-worker', 'exec')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(load_human_pose(object(), {}, ROOT), {})
        for value in ({}, None, 'auto', {'path': str(path), 'sha256': '0'*64}):
            with self.assertRaises(ValueError):
                read_input(ROOT, value)
        with self.assertRaises(ValueError):
            load_human_pose(object(), {'sourceHumanComposition': {}}, ROOT)

    def test_absent_human_composition_does_not_advance_or_reinterpret_actor(self):
        class Base:
            species_actors = {'human': 'human-male'}
            def __init__(self): self.called = []
            def actor_tick(self, identity, *args, **kwargs):
                self.called.append(identity)
                return {'actualOriginalResult': identity}
        engine = human_pose_queue_type(Base)()
        with self.assertRaises(ValueError): engine.actor_tick('human')
        self.assertEqual(engine.called, [])
        self.assertEqual(engine.actor_tick('legacy'), {'actualOriginalResult': 'legacy'})
        self.assertEqual(engine.called, ['legacy'])


@unittest.skipUnless(os.environ.get('OC2_PUBLIC_ONLY') != '1' and CONFIG.is_file(),
                     'Private original runtime and composition inputs required')
class ActualWorkerTests(unittest.TestCase):
    def test_portable_loader_keeps_every_original_property_after_releasing_unused_json(self):
        from analyze_native_resources import NativeImage
        cfg = json.loads(CONFIG.read_text())
        queue = json.loads(Path(cfg['sourceHumanComposition']['queue']['path']).read_text())
        binding = json.loads(Path(cfg['sourceHumanComposition']['binding']['path']).read_text())
        reference = ROOT/'analysis/raw/character-human-queue-composition-20261115/composition-evidence-v1.json'
        if not reference.exists(): self.skipTest('Frozen full original 33-pose reference is absent')
        class Engine: pass
        engine = Engine()
        engine.image = NativeImage(Path(cfg['library']).read_bytes())
        engine.species_profiles = {'human-male': queue['species']}
        summary = load_human_pose(engine, cfg, ROOT)
        vm, transport = engine.human_pose
        self.assertEqual(set(vm.data), {'rig'})
        self.assertEqual(set(vm.data['rig']), {'skins'})
        self.assertEqual(summary['sourceHumanPose']['bindingId'], transport.binding_id)
        for row in json.loads(reference.read_text())['cases']:
            pose = vm.compose_bound_packet(row['pose']['sourceQueuePacket'])
            self.assertEqual(pose, row['pose'])
            self.assertEqual(transport.project(pose, 'exact-loader')['valueBytes'], 1992)

    def test_actual_original_tick_transports_two_owned_poses_and_preserves_legacy_result(self):
        AREA.mkdir(parents=True, exist_ok=True)
        processes = []
        with tempfile.TemporaryDirectory(prefix='rpc-', dir=AREA) as folder:
            out = Path(folder)
            configured = json.loads(CONFIG.read_text())
            self.assertIn('sourceHumanComposition', configured)
            baselines = []
            records = []
            memory = {}
            tick_times = []
            identities = ['human-a', 'human-b', 'legacy']
            try:
                # Replay the same complete stream sequentially. Two comparison
                # VMs at once are not the production single-worker topology.
                for mode, worker in [('old', 'source_species_worker.py'), ('pose', 'source_human_pose_worker.py')]:
                    cfg = json.loads(CONFIG.read_text())
                    if mode == 'old': cfg.pop('sourceHumanComposition')
                    config = out/(mode+'.json'); config.write_text(json.dumps(cfg))
                    p = subprocess.Popen([sys.executable, str(ROOT/'tools'/worker), str(config)],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    processes.append(p)
                    def request(operation, **data):
                        p.stdin.write(json.dumps({'operation': operation, 'data': data})+'\n'); p.stdin.flush()
                        line = p.stdout.readline()
                        if not line:
                            p.poll()
                            raise AssertionError('Original worker stopped ('+str(p.returncode)+'): '+p.stderr.read()[-1800:])
                        result = json.loads(line)
                        self.assertNotIn('error', result)
                        return result['result']
                    info = request('init')
                    if mode == 'old': self.assertNotIn('sourceHumanPose', info)
                    else:
                        self.assertEqual(info['sourceHumanPose']['valueBytes'], 1992)
                        self.assertFalse(info['sourceHumanPose']['originalGPUExecuted'])
                    positions = {name: [-2235.5, 108.55000305175781, 12] for name in identities}
                    for name in identities:
                        self.assertTrue(request('reset', identity=name, position=positions[name],
                            **({'species': 'human-male'} if name.startswith('human-') else {})))
                    for tick in range(48):
                        started = time.perf_counter()
                        for index, name in enumerate(identities):
                            speed = (4.8 if tick < (12 if name == 'human-b' else 24) else 0)
                            data = {'identity': name, 'position': positions[name], 'velocity': [speed, 0],
                                    'milliseconds': 50, 'jump': False, 'control': {'forward': bool(speed)}}
                            result = request('tick', **data)
                            pose = result.pop('sourceHumanPose', None)
                            if mode == 'old': baselines.append(result)
                            else: self.assertEqual(result, baselines[tick*3+index], (name, tick))
                            positions[name] = result['position']
                            if mode == 'pose' and name.startswith('human-'):
                                self.assertEqual(pose['actorKey'], name)
                                self.assertEqual(pose['bindingId'], info['sourceHumanPose']['bindingId'])
                                self.assertEqual(len(pose['values']), 2656)
                                records.append({'tick': tick, 'actor': name, 'queue': result['sourceAnimation'], 'pose': pose})
                            else: self.assertIsNone(pose)
                        if mode == 'pose': tick_times.append((time.perf_counter()-started)*1000)
                    for name in identities: self.assertTrue(request('forget', identity=name))
                    if mode == 'pose':
                        self.assertTrue(request('reset', identity='human-c', position=positions['human-a'], species='human-male'))
                        fresh = request('tick', identity='human-c', position=positions['human-a'], velocity=[0, 0], milliseconds=50, jump=False, control={})
                        self.assertEqual(fresh['sourceHumanPose']['actorKey'], 'human-c')
                    status = Path('/proc')/str(p.pid)/'status'
                    if status.exists():
                        memory[mode] = {line.split(':')[0]: line.split(':',1)[1].strip()
                            for line in status.read_text().splitlines() if line.startswith(('VmRSS:', 'VmHWM:'))}
                    p.terminate(); p.wait(timeout=10)
                receipt = {'format': 'oc2-human-pose-worker-rpc-acceptance-v1',
                    'realOriginalWorkerRPC': True, 'actualHumanActors': 2, 'ticksPerActor': 48,
                    'exactOriginalResultsAgainstOldWorker': 144, 'poseRecords': records,
                    'legacyResultUnchanged': True, 'freshIdentityAfterForget': True,
                    'threeActorRPCMilliseconds': {'mean': sum(tick_times)/len(tick_times),
                        'p95': sorted(tick_times)[int(len(tick_times)*.95)], 'maximum': max(tick_times)},
                    'workerProcessMemory': memory,
                    'noCharacterStoreLoaded': True, 'originalGPUExecuted': False,
                    'formalCreationAdmitted': False}
                target = AREA/'rpc-current.json'
                target.write_text(json.dumps(receipt, indent=2)+'\n')
            finally:
                for p in processes:
                    p.terminate()
                    try: p.wait(timeout=10)
                    except subprocess.TimeoutExpired: p.kill(); p.wait()
                    p.stdin.close(); p.stdout.close(); p.stderr.close()


if __name__ == '__main__': unittest.main(verbosity=2)
