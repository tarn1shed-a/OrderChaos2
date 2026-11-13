"""Replay identical original-physics requests on Mac and Linux for migration QA.

Explicit geometric test positions are not original spawn positions. No server
or character save is edited. Full results belong in private QA output only.
"""
import argparse
import json
import subprocess
from pathlib import Path


def replay(config):
    cfg = json.loads(Path(config).read_text())
    process = subprocess.Popen([cfg['python'], cfg['worker'], str(config)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def request(operation, **data):
        process.stdin.write(json.dumps({'operation': operation, 'data': data}) + '\n')
        process.stdin.flush()
        line = process.stdout.readline()
        if not line:
            raise RuntimeError('Original physics worker exited: ' + process.stderr.read()[-2000:])
        reply = json.loads(line)
        if 'error' in reply:
            raise RuntimeError(reply['error'])
        return reply['result']

    try:
        info = request('init')
        assert info['sourceNative'] is True
        result = {'nativeSHA256': info['nativeSHA256'],
                  'world': {key: info[key] for key in ['tiles', 'instances', 'shapes']}, 'cases': {}}
        for name, position, velocity, count, jump in [
            ('wall', [-2617, 143.68184, 173], [0, 4.8], 45, False),
            ('stairs', [-2617, 141.759, 162], [0, 4.8], 65, False),
            ('jump', [-2533, 136.53165, 203], [0, 0], 60, True),
            ('bridge-fall', [-2533, 136.53165, 203], [-4.8, 0], 90, False),
            ('tile-seam', [-2560.6, 132.35, 182], [4.8, 0], 15, False),
        ]:
            frames = []
            for index in range(count):
                frame = request('tick', identity='migration-' + name, position=position,
                                velocity=velocity, milliseconds=50, jump=jump and index == 0,
                                control={'forward': False})
                frames.append({key: frame.get(key) for key in ['position', 'grounded', 'velocityY',
                                                               'lastPosture', 'swimming', 'waterState',
                                                               'sourceAnimation']})
            result['cases'][name] = frames
        assert result['cases']['wall'][-1]['position'][2] < 175, 'Source wall must still block movement'
        frames = result['cases']['jump']
        assert max(f['position'][1] for f in frames) > 137
        assert frames[-1]['grounded'], 'Source jump must land'
        frames = result['cases']['bridge-fall']
        assert any(not f['grounded'] for f in frames) and frames[-1]['grounded']
        assert result['cases']['tile-seam'][-1]['position'][0] > -2560, 'Loaded tile seam must remain traversable'
        return result
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def compare(a, b, path='root'):
    if isinstance(a, dict):
        assert a.keys() == b.keys(), path
        for key in a:
            compare(a[key], b[key], path + '.' + key)
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for index, (x, y) in enumerate(zip(a, b)):
            compare(x, y, path + '[' + str(index) + ']')
    elif isinstance(a, float):
        assert abs(a - b) <= 1e-4, (path, a, b)
    else:
        assert a == b, (path, a, b)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    report = replay(args.config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2))
    if args.compare:
        compare(json.loads(args.compare.read_text()), report)
    print(json.dumps({'originalPhysics': True, 'world': report['world'], 'cases': list(report['cases']),
                      'frames': sum(map(len, report['cases'].values())), 'matchesBaseline': bool(args.compare)}))
