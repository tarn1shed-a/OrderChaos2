"""Read-only original-CPU diagnostics at tutorial task checkpoints.

Straight segments below are deliberately inspection inputs, not recovered
navigation paths. Success cannot certify the playable chain or dynamic floor.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from analyze_native_resources import NativeImage, NATIVE_SHA256
from native_phy_stream import NativePHYStreamPhysics
from tutorial_map_geometry import local_output
from tutorial_quest_chain import audit


class DiagnosticPhysics(NativePHYStreamPhysics):
    """Attribute shapes to their actual load input, even if source IDs repeat."""
    def __init__(self, image):
        super().__init__(image)
        self.shape_sources = {}

    def transform(self, head, instance):
        head = super().transform(head, instance)
        pointer = head
        while pointer:
            self.shape_sources[pointer] = instance
            pointer = self.r(pointer + 8, 'Q')[0]
        return head


def probe(config, source, input_root=None, walk=False):
    config = Path(config).resolve()
    local_output(config)
    cfg = json.loads(config.read_text())
    if cfg['nativeSHA256'] != NATIVE_SHA256:
        raise ValueError('Different original native build')

    def path(original):
        if input_root is None:
            return Path(original)
        # Explicit relocation of a copied deployment input folder. Never search
        # by basename or substitute a similarly named model.
        suffix = str(original).split('/native-inputs/', 1)
        if len(suffix) != 2:
            raise ValueError('Input is outside the copied native-inputs tree')
        root = Path(input_root).resolve(); target = (root / suffix[1]).resolve()
        if not target.is_relative_to(root):
            raise ValueError('Native input path escapes copied tree')
        return target

    library = path(cfg['library']).read_bytes()
    if hashlib.sha256(library).hexdigest() != NATIVE_SHA256:
        raise ValueError('Original library identity differs')
    engine = DiagnosticPhysics(NativeImage(library))
    terrain = json.loads(path(cfg['terrain']).read_text())
    profile = json.loads(path(cfg['collision']).read_text())
    lighting = json.loads(path(cfg['terrainLighting']).read_text())

    def read(name):
        row = cfg['sourceFiles'][name]; raw = path(row['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Private PHY identity differs')
        return raw

    loaded = engine.load_world(terrain, profile, read,
                 {tuple(t['tile']): t['runtimeFlags'] for t in lighting['tiles']})
    chain = audit(source)
    givers = chain['startGiverSameEntryCandidates']
    if len(givers) != 1:
        raise ValueError('No unique starting giver candidate for inspection')
    checkpoints = [{'step': 0, 'kind': 'startGiverCandidate',
                    'point': [givers[0][k] for k in ('position_x', 'position_y', 'position_z')]}]
    for step in chain['steps']:
        for target in step['targets']:
            zone = target['zone']
            if zone is not None:
                checkpoints.append({'step': step['objective']['step'],
                    'kind': 'objectiveZoneCentre', 'zoneId': zone['ID'],
                    'point': [zone[k] for k in ('x', 'y', 'z')]})
    for row in checkpoints:
        x, y, z = row['point']; row['available'] = engine.available(x, z)
        if not row['available']:
            continue
        row['ground'] = engine.ground(x, z, y + 5)
        row['terrain'] = engine.sample(x, z)
        row['sourceYMinusSupportY'] = y - row['ground']['height']
        candidates = []
        for pointer, ident in engine.objects.items():
            bounds = list(engine.r(pointer + 0x20, '6f'))
            if bounds[0] <= x <= bounds[3] and bounds[2] <= z <= bounds[5]:
                instance = engine.shape_sources[pointer]
                candidates.append({'instanceId': ident, 'bounds': bounds,
                                   'sourcePHY': instance['sourcePHY'],
                                   'ownerTile': instance['tile']})
        row['xzBoundingCandidates'] = candidates
    segments = []
    if walk:
        # These numbers bound the probe only. They are not quest radii, source
        # speed recovery or a navigation algorithm added to the game.
        dt = 50; speed = 4.8
        for i, (start, target) in enumerate(zip(checkpoints, checkpoints[1:])):
            position = list(start['point']); endpoint = target['point']
            distance = math.hypot(endpoint[0] - position[0], endpoint[2] - position[2])
            frames = []; stalled = 0
            for _ in range(min(2000, math.ceil(distance / (speed * dt / 1000)) + 100)):
                dx, dz = endpoint[0] - position[0], endpoint[2] - position[2]
                left = math.hypot(dx, dz)
                if left <= .1:
                    break
                velocity = [dx / left * min(speed, left / (dt / 1000)),
                            dz / left * min(speed, left / (dt / 1000))]
                frame = engine.actor_tick('route-probe-' + str(i), position, velocity, dt)
                moved = math.hypot(frame['position'][0] - position[0],
                                   frame['position'][2] - position[2])
                position = frame['position']; frames.append(frame)
                stalled = stalled + 1 if moved < .0001 else 0
                if stalled >= 8 or frame.get('pendingSourceCell'):
                    break
            segments.append({'fromStep': start['step'], 'toStep': target['step'],
                'endPosition': position, 'frames': frames,
                'horizontalRemaining': math.hypot(endpoint[0] - position[0], endpoint[2] - position[2]),
                'sourceTargetYMinusEndY': endpoint[1] - position[1]})
    return {'format': 'oc2-tutorial-route-diagnostics-v1', 'loaded': loaded,
            'checkpoints': checkpoints, 'straightInspectionSegments': segments,
            'configSHA256': hashlib.sha256(config.read_bytes()).hexdigest(),
            'physicsHostSHA256': hashlib.sha256(Path(__file__).with_name('source_physics.py').read_bytes()).hexdigest(),
            'routeVerified': False, 'dynamicActorsSupplied': False,
            'gameplayOrSaveChanged': False,
            'limits': ['Original static ground/motion queries in an explicit host container.',
                       'Original quest-state scripts, dynamic elevator and live server are absent.',
                       'Each straight segment is independently seeded from a table checkpoint; '
                       'this is not a continuous traversal or recovered path.',
                       'A checkpoint centre can differ from a walkable surface. '
                       'Ground height mismatch identifies work, not a rule to teleport the player.']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--input-root', type=Path)
    p.add_argument('--walk', action='store_true')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); output = local_output(args.output)
    report = probe(args.config, args.source, args.input_root, args.walk)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'output': str(output), 'checkpoints': len(report['checkpoints']),
                       'inspectionSegments': len(report['straightInspectionSegments']),
                       'routeVerified': False, 'gameplayChanged': False}))
