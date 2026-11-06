"""Join recovered geometry, skinning and compatible source locomotion clips."""
import math

from bdae_convert import BDAE
from bdae_skin import recover_skin, read_nodes
from bdae_animation import BDAEAnimation


def quaternion_product(a, b):
    x, y, z, w = a
    xx, yy, zz, ww = b
    return [w*xx + x*ww + y*zz - z*yy,
            w*yy - x*zz + y*ww + z*xx,
            w*zz + x*yy - y*xx + z*ww,
            w*ww - x*xx - y*yy - z*zz]


def aliases(nodes):
    result = {}
    for index, node in enumerate(nodes):
        for name in [node['name'], *node['aliases']]:
            if name in result and result[name] != index:
                raise ValueError(f'Ambiguous rest node alias: {name}')
            result[name] = index
    return result


def convert_character(model_path, animation_path, animation_model_path):
    reader = BDAE(model_path)
    result = reader.parse()
    rig = recover_skin(reader, result)
    source_nodes = read_nodes(BDAE(animation_model_path))
    animation = BDAEAnimation(animation_path).parse(['idle', 'walk_forward'])
    target_map, source_map = aliases(rig['nodes']), aliases(source_nodes)
    skipped, clips = set(), []
    for clip in animation['clips']:
        tracks = []
        for track in clip['tracks']:
            name, kind = track['node'], track['type']
            if name not in target_map:
                skipped.add(name)
                continue
            if name not in source_map:
                raise ValueError(f'Animation has no source rest node: {name}')
            node_index = target_map[name]
            target, source = rig['nodes'][node_index], source_nodes[source_map[name]]
            values = []
            components = 4 if kind == 'quaternion' else 3
            previous = None
            for at in range(0, len(track['values']), components):
                value = track['values'][at:at + components]
                if kind == 'position':
                    value = [target['position'][axis] + value[axis] - source['position'][axis] for axis in range(3)]
                    if target['parent'] == -1:
                        # Server-authoritative movement owns horizontal translation.
                        value[0], value[2] = target['position'][0], target['position'][2]
                elif kind == 'quaternion':
                    inverse = [-v for v in source['quaternion'][:3]] + [source['quaternion'][3]]
                    value = quaternion_product(quaternion_product(target['quaternion'], inverse), value)
                    length = math.sqrt(sum(v*v for v in value))
                    if length < 1e-8:
                        raise ValueError('Invalid rebased animation quaternion')
                    value = [v / length for v in value]
                    if previous is not None and sum(a*b for a, b in zip(previous, value)) < 0:
                        value = [-v for v in value]
                elif kind == 'scale':
                    value = [target['scale'][axis] * value[axis] / source['scale'][axis] for axis in range(3)]
                else:
                    raise ValueError(f'Unsupported animation property: {kind}')
                if not all(math.isfinite(v) for v in value):
                    raise ValueError('Non-finite rebased animation value')
                previous = value
                values.extend(value)
            tracks.append({'node': node_index, 'type': kind, 'times': track['times'],
                           'values': values, 'interpolation': track['interpolation']})
        if not tracks:
            raise ValueError('No animation channels bind to the target skeleton')
        clips.append({'name': clip['name'], 'duration': clip['duration'], 'tracks': tracks})
    result.update({'format': 'bdae946-character-v1', 'rig': rig, 'clips': clips,
                   'animationBinding': {'sourceSHA256': animation['sourceSHA256'],
                       'sampleRate': animation['sampleRate'], 'verification': animation['verification'],
                       'boundNodes': len({track['node'] for clip in clips for track in clip['tracks']}),
                       'ignoredSourceNodes': sorted(skipped),
                       'adaptation': 'Local rest TRS rebasing; horizontal root motion removed; source timing and Y motion retained.'}})
    result['warnings'] = [warning for warning in result['warnings'] if not warning.startswith('Static source geometry only;')]
    result['warnings'].append('Original auxiliary animation channels without target nodes are omitted; original shaders are not evaluated.')
    return result
