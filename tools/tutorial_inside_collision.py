"""Build an isolated collision candidate for the omitted original inside items.

No runtime, deployment bundle or existing save is overwritten. Only instances
whose original two quality branches preserve the same parsed PHY chain qualify.
"""
import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

from analyze_native_resources import NativeImage
from map_loading_evidence import Sources
from native_inside_collision_probe import InsidePhysicsProbe
from resource_packs import DEFAULT_SOURCE
from scene_collision import decode_phy
from terrain_convert import read_instances
from tutorial_map_geometry import ROOT, local_output


def build(config, input_root, output, source=DEFAULT_SOURCE):
    config = local_output(config); input_root = local_output(input_root)
    output = local_output(output)
    if output.exists():
        raise ValueError('Preserve existing candidate; choose a fresh output')
    cfg = json.loads(config.read_text()); sources = Sources(source)

    def relocate(value):
        if isinstance(value, dict):
            return {k: relocate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [relocate(v) for v in value]
        if isinstance(value, str) and '/native-inputs/' in value:
            path = (input_root / value.split('/native-inputs/', 1)[1]).resolve()
            if not path.is_relative_to(input_root):
                raise ValueError('Copied input escapes source tree')
            return str(path)
        return value

    cfg = relocate(cfg)
    original = Path(cfg['collision']).read_bytes()
    profile = json.loads(original); candidate = copy.deepcopy(profile)
    engine = InsidePhysicsProbe(NativeImage(Path(cfg['library']).read_bytes()))
    rows = []; failed = []; proven = []
    for gap in profile['gaps']:
        if gap.get('reason') != 'inside factory/collision not restored':
            continue
        x, z = gap['tile']; name = f'world/tutorial/items/{x:04d}_{z:04d}.itm'
        raw = sources.read(name)

        class Buffer:
            def read_bytes(self):
                return raw

        row, = [r for r in read_instances(Buffer()) if r['id'] == gap['id']]
        if row['sourceType'] != 15:
            raise ValueError('Original inside item type differs')
        # The original record's detail and phase pass the two static admission
        # checks for this archive under every supported detail threshold 0..3.
        import struct
        count = struct.unpack_from('<I', raw, 16)[0]
        records = [raw[24 + i * 76:24 + (i + 1) * 76] for i in range(count)]
        record, = [r for r in records if struct.unpack_from('<I', r, 4)[0] == row['id']]
        detail, phase = struct.unpack_from('<II', record, 56)
        if detail & 3 != 3 or phase != 0xffffffff:
            raise ValueError('Original inside admission needs a different branch')
        cases = []
        try:
            for quality in (False, True):
                result = engine.select(row['model'], sources, simplified=quality)
                result.pop('head')
                if result['originalReturn'] != 1:
                    raise ValueError('Original loader did not report a resource')
                cases.append(result)
        except (ValueError, RuntimeError) as error:
            failed.append({'id': row['id'], 'model': row['model'], 'reason': str(error)})
            continue
        if cases[0]['selected'] != cases[1]['selected']:
            raise ValueError('Original quality choices disagree')
        row.update(sourcePHY=cases[0]['selected'],
                   admission='admittedBeforeTypeFactory',
                   insideCollisionEvidence='original-a85cb0-normal-chain-extra-inside-file-absent')
        stream = cases[0]['nativeStream']
        shape = decode_phy(sources.read(row['sourcePHY']), retained_at_eof=(
            stream['retainedShapeCount'] if stream['descriptorError'] else None))
        candidate['sources'][row['sourcePHY']] = shape
        candidate['instances'].append(row); rows.append(row)
        proven.append({'id': row['id'], 'model': row['model'], 'cases': cases})
    resolved = {r['id'] for r in rows}
    candidate['gaps'] = [r for r in candidate['gaps'] if r.get('id') not in resolved]
    # Preserve old research gap metadata; do not add/remove a movement barrier.
    candidate['insideCandidateEvidence'] = {'resolved': sorted(resolved),
        'remaining': failed, 'originalCollisionSHA256': hashlib.sha256(original).hexdigest(),
        'automaticRuntimeReplacement': False}
    output.mkdir(parents=True); (output / 'phy').mkdir()
    for row in rows:
        name = row['sourcePHY']; raw = sources.read(name)
        digest = hashlib.sha256(raw).hexdigest(); path = output / 'phy' / (digest + '.phy')
        path.write_bytes(raw); cfg['sourceFiles'][name] = {'path': str(path), 'sha256': digest}
    collision = output / 'collision.json'
    collision.write_text(json.dumps(candidate, ensure_ascii=False, separators=(',', ':')))
    cfg.update(collision=str(collision), config=str(output / 'native-physics.json'),
               nativeArchiveStream=True,
               python=sys.executable, worker=str(ROOT / 'tools/source_physics_worker.py'))
    (output / 'native-physics.json').write_text(json.dumps(cfg, indent=2) + '\n')
    report = {'format': 'oc2-inside-collision-candidate-v1',
        'sourceInstancesAdded': rows, 'nativeCases': proven, 'unresolved': failed,
        'sourceProofs': sources.proofs, 'originalConfigSHA256': hashlib.sha256(config.read_bytes()).hexdigest(),
        'sourceTypeDispatch': 'a61030 passes record.type==15 as a85cb0 inside argument',
        'scope': 'isolated candidate using existing original static container; no dynamic elevator',
        'gameplayOrSaveChanged': False, 'productionUpdated': False, 'routeVerified': False}
    (output / 'evidence.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--input-root', type=Path, required=True)
    p.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); result = build(args.config, args.input_root, args.output, args.source)
    print(json.dumps({'added': len(result['sourceInstancesAdded']),
                      'unresolved': len(result['unresolved']), 'productionUpdated': False}))
