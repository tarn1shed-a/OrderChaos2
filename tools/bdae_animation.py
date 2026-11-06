"""Read verified unquantized 946 animation bundles without running game code.

Unlike earlier BDAE revisions, the observed bundles store named clip ranges and
overlapping time segments. Source descriptors contain byte lengths (not element
counts), uint16 absolute frame numbers, and float3/float4 transformation values.
Quaternion components are exported in their original XYZW convention; coordinate
conversion and binding to a particular skeleton belong to the model adapter.
"""
import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path

from bdae_convert import BDAE

TYPES = {1: ('position', 3), 5: ('quaternion', 4), 10: ('scale', 3)}


def interpolate(a, b, weight, quaternion=False):
    """Interpolate source samples, preserving quaternion shortest-arc rotation."""
    if not quaternion:
        return tuple(x + (y - x) * weight for x, y in zip(a, b))
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0:
        b, dot = tuple(-x for x in b), -dot
    dot = min(1.0, max(-1.0, dot))
    if dot > .9995:
        result = [x + (y - x) * weight for x, y in zip(a, b)]
    else:
        angle = math.acos(dot)
        divisor = math.sin(angle)
        left, right = math.sin((1 - weight) * angle) / divisor, math.sin(weight * angle) / divisor
        result = [x * left + y * right for x, y in zip(a, b)]
    length = math.sqrt(sum(x * x for x in result))
    if length < 1e-8:
        raise ValueError('Cannot interpolate a zero quaternion')
    return tuple(x / length for x in result)


def sample(frames, values, frame, quaternion=False):
    at = bisect.bisect_left(frames, frame)
    if at == 0:
        return values[0]
    if at == len(frames):
        return values[-1]
    if frames[at] == frame:
        return values[at]
    return interpolate(values[at - 1], values[at],
                       (frame - frames[at - 1]) / (frames[at] - frames[at - 1]), quaternion)


class BDAEAnimation(BDAE):
    def ranges(self):
        count, table = self.section(84)
        self.at(table, count * 24)
        ranges = []
        for index in range(count):
            record = table + index * 24
            full_name = self.string(self.q(record))
            start, end, origin, reserved = self.unpack('4I', record + 8)
            if end <= start or reserved != 0:
                raise ValueError('Unsupported or empty animation range')
            ranges.append({'name': full_name.split('-', 1)[0], 'sourceName': full_name,
                           'startMs': start, 'endMs': end, 'originMs': origin})
        return ranges

    def channels(self):
        count, table = self.section(64)
        self.at(table, count * 40)
        channels = []
        targets = set()
        for index in range(count):
            record = table + index * 40
            if self.u(record + 8) != 1 or self.u(record + 16) != 1:
                raise ValueError('Only one sampler and target per channel are supported')
            prop, target = self.rel(record + 12), self.rel(record + 20)
            interpolation, time_type, time_components, time_index, value_type, components, value_index, stride = self.unpack('8I', prop)
            channel_type = self.u(target + 8)
            if channel_type not in TYPES or TYPES[channel_type][1] != components:
                raise ValueError('Unsupported animation channel type/components')
            if interpolation != 1 or time_type != 3 or time_components != 1 or value_type != 6 or stride != components << 18:
                raise ValueError('Unsupported animation encoding/interpolation')
            node_name = self.string(self.q(target))
            kind = TYPES[channel_type][0]
            if (node_name, kind) in targets:
                raise ValueError('Duplicate animation target/property')
            targets.add((node_name, kind))
            channels.append({'node': node_name, 'type': kind, 'components': components,
                             'timeIndex': time_index, 'valueIndex': value_index})
        return channels

    def segments(self):
        table = self.rel(self.info + 76)
        count, descriptor_width = self.unpack('2I', table)
        if not 0 < count < 10000 or descriptor_width != 4:
            raise ValueError('Unsupported animation segment table')
        self.at(table + 8, count * 40)
        segments = []
        previous = -1
        for index in range(count):
            record = table + 8 + index * 40
            start, end, reserved, flags = self.unpack('4I', record)
            data, size = self.unpack('2Q', record + 16)
            if end <= start or start < previous or reserved != 0 or flags != 0x01000000:
                raise ValueError('Unsupported animation segment layout')
            self.at(data, size)
            source_count, source_width = self.unpack('2I', data)
            if source_width != 4 or not 0 < source_count < 10000:
                raise ValueError('Unsupported animation source table')
            if 8 + source_count * 8 > size:
                raise ValueError('Animation source table escapes its segment')
            self.at(data + 8, source_count * 8)
            segments.append({'startMs': start, 'endMs': end, 'data': data,
                             'size': size, 'sourceCount': source_count})
            previous = start
        return segments

    def _source(self, segment, index):
        if not 0 <= index < segment['sourceCount']:
            raise ValueError('Animation source index outside table')
        descriptor = segment['data'] + 8 + index * 8
        size, pointer = self.u(descriptor), self.rel(descriptor + 4)
        payload_start = segment['data'] + 8 + segment['sourceCount'] * 8
        if pointer < payload_start or pointer + size > segment['data'] + segment['size']:
            raise ValueError('Animation source escapes its segment')
        self.at(pointer, size)
        return size, pointer

    def parse(self, clips=('walk_forward', 'idle')):
        channels, segments, ranges = self.channels(), self.segments(), self.ranges()
        selected = []
        for name in clips:
            matches = [record for record in ranges if record['name'] == name or record['sourceName'] == name]
            if len(matches) != 1:
                raise ValueError(f'Expected one animation range for {name}, found {len(matches)}')
            selected.append(matches[0])
        output = []
        source_quaternion_error = 0.0
        for clip in selected:
            start_frame, end_frame = round(clip['startMs'] * .03), round(clip['endMs'] * .03)
            if max(abs(start_frame / .03 - clip['startMs']), abs(end_frame / .03 - clip['endMs'])) > .501:
                raise ValueError('Clip range does not match the observed 30 FPS timeline')
            relevant = [segment for segment in segments if segment['startMs'] <= clip['endMs'] and segment['endMs'] >= clip['startMs']]
            if not relevant:
                raise ValueError('Clip has no data segments')
            covered_until = clip['startMs']
            for segment in relevant:
                if segment['startMs'] > covered_until:
                    raise ValueError('Animation segments leave a gap inside the clip')
                covered_until = max(covered_until, segment['endMs'])
            if covered_until < clip['endMs']:
                raise ValueError('Animation segments do not cover the complete clip')
            tracks = []
            for channel in channels:
                merged = {}
                components = channel['components']
                for segment in relevant:
                    time_bytes, time_pointer = self._source(segment, channel['timeIndex'])
                    value_bytes, value_pointer = self._source(segment, channel['valueIndex'])
                    if time_bytes % 2 or value_bytes % (components * 4):
                        raise ValueError('Animation source has fractional elements')
                    count = time_bytes // 2
                    if not count or count != value_bytes // (components * 4):
                        raise ValueError('Animation time/value sample counts differ')
                    frames = self.unpack('H' * count, time_pointer)
                    values = self.unpack('f' * (count * components), value_pointer)
                    if any(a >= b for a, b in zip(frames, frames[1:])):
                        raise ValueError('Animation frames are not strictly increasing')
                    for index, frame in enumerate(frames):
                        value = values[index * components:(index + 1) * components]
                        if not all(math.isfinite(v) for v in value):
                            raise ValueError('Non-finite animation value')
                        if channel['type'] == 'quaternion':
                            error = abs(sum(v * v for v in value) - 1)
                            source_quaternion_error = max(source_quaternion_error, error)
                            if error > .002:
                                raise ValueError('Non-unit source animation quaternion')
                        if frame in merged and max(abs(a - b) for a, b in zip(merged[frame], value)) > 1e-5:
                            raise ValueError('Overlapping animation segments disagree')
                        merged[frame] = value
                frames = sorted(merged)
                values = [merged[frame] for frame in frames]
                if frames[0] > start_frame or frames[-1] < end_frame:
                    raise ValueError('Animation samples do not cover the clip boundaries')
                selected_frames = [start_frame] + [frame for frame in frames if start_frame < frame < end_frame] + [end_frame]
                selected_values = [sample(frames, values, frame, channel['type'] == 'quaternion') for frame in selected_frames]
                tracks.append({'node': channel['node'], 'type': channel['type'], 'interpolation': 'linear',
                               'times': [round((frame - start_frame) / 30, 9) for frame in selected_frames],
                               'values': [value for row in selected_values for value in row]})
            output.append({'name': clip['name'], 'sourceName': clip['sourceName'],
                           'duration': (end_frame - start_frame) / 30,
                           'sourceRangeMs': [clip['startMs'], clip['endMs']],
                           'sourceRangeFrames': [start_frame, end_frame], 'tracks': tracks})
        return {'format': 'bdae946-animation-v1', 'source': self.path.as_posix(),
                'sourceSHA256': hashlib.sha256(self.path.read_bytes()).hexdigest(),
                'sampleRate': 30, 'quaternionConvention': 'source XYZW; not converted',
                'clips': output, 'verification': {'channels': len(channels), 'segments': len(segments),
                    'maximumSourceQuaternionNormSquaredError': source_quaternion_error,
                    'overlappingSamplesConsistent': True}}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('source', type=Path)
    cli.add_argument('output', type=Path)
    cli.add_argument('--clips', nargs='+', default=['walk_forward', 'idle'])
    args = cli.parse_args()
    result = BDAEAnimation(args.source).parse(args.clips)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
    print(json.dumps({'clips': [{'name': clip['name'], 'duration': clip['duration'], 'tracks': len(clip['tracks'])} for clip in result['clips']],
                      'verification': result['verification']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
