"""Prepare pinned private worker inputs, without importing any character store."""
import argparse
import hashlib
import json
from pathlib import Path


def prepare(output, physics, inputs):
    root = Path(__file__).resolve().parents[1]
    output = output.resolve()
    if not output.is_relative_to(root/'analysis/raw') or output.exists():
        raise ValueError('Use a fresh private worker-input directory')
    if set(inputs) != {'bodyData', 'body', 'animation', 'mask', 'queue', 'binding'}:
        raise ValueError('All six original human inputs must be explicit')
    paths = [physics, *inputs.values()]
    if any(p.is_symlink() or not p.resolve().is_relative_to(root/'analysis/raw') for p in paths):
        raise ValueError('Pinned source inputs must remain private')
    raw_inputs = {name: path.read_bytes() for name, path in inputs.items()}
    queue = json.loads(raw_inputs['queue'])
    config = json.loads(physics.read_bytes())
    if not config.get('layerQueue'):
        raise ValueError('Original two-channel physics configuration required')
    output.mkdir(parents=True)
    descriptor = {}
    for name, raw in raw_inputs.items():
        path = output/(name+('.bdae' if name in ('body', 'animation') else '.json'))
        path.write_bytes(raw)
        descriptor[name] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
    profiles = output/'profiles.json'
    profiles.write_text(json.dumps({'human-male': queue['species']}))
    config.update(sourceHumanComposition=descriptor,
                  sourceSpeciesProfiles={'path': str(profiles), 'sha256': hashlib.sha256(profiles.read_bytes()).hexdigest()},
                  worker=str(root/'tools/source_human_pose_worker.py'))
    config['config'] = str(output/'native-physics.json')
    (output/'native-physics.json').write_text(json.dumps(config, indent=2)+'\n')
    return Path(config['config'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--physics-config', type=Path, required=True)
    names = ('bodyData', 'body', 'animation', 'mask', 'queue', 'binding')
    for name in names: parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    path = prepare(args.output, args.physics_config, {name: getattr(args, name) for name in names})
    print(json.dumps({'config': str(path), 'sourceInputsPinned': 6, 'savesImported': False}))
