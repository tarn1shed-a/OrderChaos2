"""638-only original idle/walk key copies, segment selection and CPU controls.

No compressed value codec, shared parser change, game actor or invented clip.
"""
import bisect
import copy
import hashlib
import json
import math
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'analysis/raw/ordinary-638-animation-complete-20261116'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
f32 = lambda v: struct.unpack('<f', struct.pack('<f', v))[0]


def source_description(reader):
    from ordinary_crocodile_animation_probe import ANIMATION, SOURCE_SHAS
    if sha(reader.path.read_bytes()) != SOURCE_SHAS[ANIMATION]:
        raise ValueError('Exact original638 animation required')
    count, table = reader.section(64)
    if count != 44:
        raise ValueError('All44 original properties required')
    channels = []
    for i in range(count):
        rec = table + i * 40
        if reader.u(rec + 8) != 1 or reader.u(rec + 16) != 1:
            raise ValueError('Original one sampler/target required')
        prop, target = reader.rel(rec + 12), reader.rel(rec + 20)
        fields = list(reader.unpack('8I', prop))
        name, kind = reader.string(reader.q(target)), reader.u(target + 8)
        if fields[:3] != [1, 3, 1] or kind not in (1, 5):
            raise ValueError('Uncovered638 property/time format')
        if (name == 'Camera01-node' and (fields[4:6] != [0, 3] or fields[7] != 3 << 16)):
            raise ValueError('Original camera compressed descriptor changed')
        if name != 'Camera01-node' and (fields[4] != 6 or fields[5] != (4 if kind == 5 else 3)):
            raise ValueError('Original float property changed')
        channels.append({'sourceIndex': i, 'node': name, 'type': 'position' if kind == 1 else 'quaternion',
                         'nativeType': kind, 'timeIndex': fields[3], 'valueIndex': fields[6],
                         'sourceDescriptor': fields})
    top = reader.rel(reader.info + 76)
    count, width = reader.unpack('2I', top)
    if (count, width) != (7, 4):
        raise ValueError('Exact original638 segment table required')
    segments = []
    for i in range(count):
        rec = top + 8 + i * 40
        begin, end, reserved, flag = reader.unpack('4i', rec)
        data, length = reader.unpack('2Q', rec + 16)
        reader.at(data, length)
        n, width = reader.unpack('2I', data)
        if reserved or flag != 0x1000000 or not begin < end or (n, width) != (88, 4):
            raise ValueError('Original638 signed segment/source table differs')
        sources = []
        for k in range(n):
            size, offset = reader.unpack('2I', data + 8 + k * 8)
            at = reader.rel(data + 12 + k * 8)
            if at < data + 8 + n * 8 or at + size > data + length:
                raise ValueError('Original source escapes its segment')
            sources.append({'bytes': size, 'at': at})
        segments.append({'index': i, 'startMs': begin, 'endMs': end, 'sources': sources})
    count, table = reader.section(84)
    ranges = []
    for i in range(count):
        rec = table + i * 24
        name = reader.string(reader.q(rec))
        if name.split('-', 1)[0] not in ('idle', 'walk_forward'):
            continue
        begin, end, origin, reserved = reader.unpack('4i', rec + 8)
        if reserved or begin >= end:
            raise ValueError('Original638 selected range differs')
        ranges.append({'name': name.split('-', 1)[0], 'sourceName': name, 'startMs': begin,
                       'endMs': end, 'originMs': origin, 'rangeRecord': rec, 'rangeIndex': i})
    if len(ranges) != 2:
        raise ValueError('Exact two638 actions required')
    if reader.u(reader.info + 0x20) != 0:
        raise ValueError('Original638 source property-cache flag changed')
    return {'channels': channels, 'segments': segments, 'ranges': ranges, 'sourcePropertyCacheFlag': 0}


def complete_type():
    from ordinary_crocodile_binding_probe import binding_type
    from unicorn import UC_HOOK_CODE
    base = binding_type()

    class Complete638(base):
        def prepare_complete(self, reader):
            self.prepare_animation(reader)
            self.description = source_description(reader)
            loaded = self.load(reader.b)
            self.selection_pair = self.resource_pair(loaded)
            info = loaded['info']
            self.selection_table = info + 0x4c + self.r(info + 0x4c, 'i')[0]
            self.contexts, self.outputs, self.key_indexes = {}, {}, {}
            self.dispatch_trace, self.current_channel = [], None
            self.copy_invocations = 0
            for at in (0x1109b7c, 0x1109ba0):
                self.uc.hook_add(UC_HOOK_CODE, self.observe_complete, begin=at, end=at)

        def observe_complete(self, uc, at, size, data):
            if self.current_channel is None:
                return
            self.dispatch_trace.append({'channel': self.current_channel, 'pc': hex(at),
                'callee': hex(self.get('X8')), 'left': self.get('W2'),
                'right': self.get('W3') if at == 0x1109b7c else None,
                'weight': struct.unpack('<f', struct.pack('<I', self.get('S0')))[0] if at == 0x1109b7c else None})

        def select_segment(self, milliseconds, range_index=None):
            # Original signed binary-search fragment. Resource pair and relocated
            # table are real; stop before refcount/cache/provider construction.
            cache_tick = int(milliseconds) & 0xffffffff
            if range_index is not None:
                record = self.invoke(0x1112e0c, X0=self.selection_pair, W1=range_index)
                self.regs()
                self.set('S8', struct.unpack('<I', struct.pack('<f', milliseconds))[0])
                self.run(0x118a6a8, 0x118a6ac)  # Actual FCVTZU, before unrelated pointer loads.
                self.set('X0', record)
                self.run(0x118a6c8, 0x118a6e8)  # FCVTZU input followed by signed CMP/LT source clamp.
                cache_tick = self.get('W8')
            self.regs()
            self.set('X20', self.selection_pair)
            self.set('W3', cache_tick)
            self.run(0x11083b0, 0x1108438)
            delta = self.get('X24') - (self.selection_table + 8)
            if delta % 40 or not 0 <= delta // 40 < 7:
                raise ValueError('Original638 segment selector escaped source table')
            return delta // 40, cache_tick

        def channel_context(self, segment, ordinal):
            key = (segment, ordinal)
            if segment not in self.segment_cache:
                stream, vt = self.alloc(16), self.alloc(32)
                self.w(stream, 'Q', vt)
                self.w(vt + 0x10, 'Q', 0x30000108)
                self.segment_cache[segment] = self.invoke(0x117c40c, X0=self.segment_table + 16 + segment * 40,
                                                          X1=stream, W2=0)
            if key not in self.contexts:
                state, ctx = self.alloc(16), self.alloc(24)
                self.w(ctx, '3Q', self.channels[ordinal]['record'], self.segment_cache[segment], state)
                self.contexts[key] = ctx
                self.outputs[key], self.key_indexes[key] = self.alloc(16), self.alloc(4)
            return self.contexts[key], self.outputs[key], self.key_indexes[key]

        def original_key(self, segment, ordinal, index):
            context, output, _ = self.channel_context(segment, ordinal)
            ch = self.channels[ordinal]
            target = self.r(self.r(ch['object'], 'Q')[0] + 0x60, 'Q')[0]
            self.invoke(target, X0=ch['object'], X1=context, W2=index, X3=output)
            values = list(self.r(output, '4f' if ch['type'] == 5 else '3f'))
            if not all(math.isfinite(v) for v in values):
                raise ValueError('Original property copy returned nonfinite values')
            self.copy_invocations += 1
            return values, hex(target)

        def sample_complete(self, milliseconds, range_index):
            segment, cache_tick = self.select_segment(milliseconds, range_index)
            self.dispatch_trace = []
            samples = []
            for i, ch in enumerate(self.channels):
                ctx, output, index = self.channel_context(segment, i)
                self.current_channel = i
                self.invoke(0x1109aec, time=milliseconds, X0=ch['object'], X1=ctx, X2=output, X3=index, W4=1)
                self.current_channel = None
                value = list(self.r(output, '4f' if ch['type'] == 5 else '3f'))
                samples.append({k: ch[k] for k in ('node', 'type', 'sourceSkinBone')} | {'value': value})
            return {'absoluteMs': milliseconds, 'segment': segment, 'actualCacheTick': cache_tick, 'samples': samples,
                    'dispatch': list(self.dispatch_trace)}

        def original_clock(self, reader, record, deltas):
            clock, table = self.alloc(0x70), self.alloc(32)
            self.invoke(0x1195f3c, X0=clock)
            self.w(table, 'Ii', 1, 4)
            self.uc.mem_write(table + 8, reader.b[record:record + 24])
            self.invoke(0x1196824, X0=clock, X1=table)
            snapshots = [{'deltaMs': 0, 'absoluteMs': self.r(clock + 8, 'f')[0],
                          'crossedEnd': bool(self.r(clock + 0x2a, 'B')[0])}]
            if self.r(clock + 0x29, 'B')[0] != 1 or self.r(clock + 0x34, 'f')[0] != 1:
                raise ValueError('Original fresh638 clock differs')
            if self.r(clock + 0x48, 'Q')[0] or self.r(clock + 0x10, 'Q')[0]:
                raise ValueError('Original638 fresh clock has an unhandled callback')
            for dt in deltas:
                self.invoke(0x11962c0, time=dt, X0=clock)
                snapshots.append({'deltaMs': dt, 'absoluteMs': self.r(clock + 8, 'f')[0],
                                  'crossedEnd': bool(self.r(clock + 0x2a, 'B')[0])})
            return snapshots

    return Complete638


def export_tracks(p, reader):
    from character_world_motion_probe import source_frame_milliseconds
    from ordinary_crocodile_animation_probe import ANIMATION, SOURCE_SHAS, NATIVE_SHA
    clips, copied = [], {}
    for clip in p.description['ranges']:
        relevant = [s for s in p.description['segments'] if s['startMs'] <= clip['endMs'] and s['endMs'] >= clip['startMs']]
        tracks = []
        for ch in p.description['channels']:
            source_segments, copy_targets = [], set()
            for segment in relevant:
                src = segment['sources'][ch['timeIndex']]
                if src['bytes'] % 2:
                    raise ValueError('Original638 time source is not uint16')
                frames = list(reader.unpack(str(src['bytes'] // 2) + 'H', src['at']))
                if not frames or any(a > b for a, b in zip(frames, frames[1:])):
                    raise ValueError('Original638 time keys decrease')
                value_source = segment['sources'][ch['valueIndex']]
                stride, offset = ch['sourceDescriptor'][7] >> 16, ch['sourceDescriptor'][7] & 0xffff
                if offset or value_source['bytes'] != len(frames) * stride:
                    raise ValueError('Original638 copied key values escape the declared source span')
                values = []
                for index, frame in enumerate(frames):
                    key = (segment['index'], ch['sourceIndex'], index)
                    if key not in copied:
                        copied[key] = p.original_key(*key)
                    value, copy_target = copied[key]
                    copy_targets.add(copy_target)
                    values.extend(value)
                source_segments.append({'index': segment['index'], 'startMs': segment['startMs'],
                    'endMs': segment['endMs'], 'frames': frames,
                    'keyMilliseconds': [source_frame_milliseconds(f) for f in frames], 'values': values})
            width = 4 if ch['nativeType'] == 5 else 3
            tracks.append({'node': ch['node'], 'type': ch['type'], 'sourceIndex': ch['sourceIndex'],
                'nativeCopyTargets': sorted(copy_targets), 'sourceDescriptor': ch['sourceDescriptor'],
                'nativeInterpolationTarget': hex(p.r(p.r(p.channels[ch['sourceIndex']]['object'], 'Q')[0] + 0x58, 'Q')[0]),
                'nativeClock': {'timeType': 3, 'components': width,
                    'msPerFrameBits': '0x42055555', 'framesPerMsBits': '0x3cf5c290'},
                'nativeSegments': source_segments})
        clips.append({k: clip[k] for k in ('name', 'sourceName', 'startMs', 'endMs', 'originMs')} |
                     {'duration': (clip['endMs'] - clip['startMs']) / 1000,
                      'sourceSegments': [s['index'] for s in relevant], 'tracks': tracks})
    return {'format': 'oc2-original638-idle-walk-native-keys-v1', 'clips': clips,
            'sourceSHA256': SOURCE_SHAS[ANIMATION], 'nativeSHA256': NATIVE_SHA,
            'allOriginal44PropertiesRetained': True, 'compressedValueCodecInvented': False,
            'valuesFromOriginalCopyVirtual60': True, 'sourceClockAndInterpolationRequired': True,
            'repeatedSourceKeysAndSegmentOrderRetained': True,
            'freshClockScope': {'loop': True, 'speed': 1, 'eventInterface': None, 'externalCallback': None},
            'originalKeyCopies': len(copied)}


def sample_track(track, absolute_ms, state, clip):
    """638's original114afcc cached-key search plus114a61c value dispatch.

    Values have already been copied by native virtual60, never decoded here.
    Repeated keys and their actual source order are preserved.
    """
    from character_world_motion_probe import source_frame_milliseconds, source_quaternion_interpolate
    ms = f32(absolute_ms)
    cache = max(0, int(ms)) & 0xffffffff
    cache = max(cache, clip['startMs'])
    cache = min(cache, clip['endMs'])
    eligible = [s for s in track['nativeSegments'] if s['startMs'] <= cache]
    segment = eligible[-1] if eligible else track['nativeSegments'][0]
    frames, values = segment['frames'], segment['values']
    width, last = track['nativeClock']['components'], len(frames) - 1
    frame = f32(ms * struct.unpack('<f', struct.pack('<I', 0x3cf5c290))[0])
    at = min(last, max(0, state.get(segment['index'], 0)))
    if frame < frames[at] and at >= 1:
        at -= 1
    elif at < last:
        if frame >= frames[at + 1]:
            if at + 1 >= last:
                at += 1
            elif frames[at + 2] > frame:
                at += 1
            else:
                at += 2
    if at < last and not frames[at] <= frame <= frames[at + 1]:
        at = max(0, bisect.bisect_right(frames, frame) - 1)
    left = source_frame_milliseconds(frames[at])
    weight = None
    if at != last and int(ms) != left:
        right = source_frame_milliseconds(frames[at + 1])
        if right != left:
            weight = max(0., min(1., f32(f32(ms - left) / f32(right - left))))
            if weight == 1:
                at += 1
                weight = None
            elif weight == 0:
                weight = None
    state[segment['index']] = at
    a = tuple(values[at * width:(at + 1) * width])
    if weight is None:
        return a
    b = tuple(values[(at + 1) * width:(at + 2) * width])
    if track['type'] == 'quaternion':
        return source_quaternion_interpolate(a, b, weight)
    if track['nativeInterpolationTarget'] == '0x116243c':
        return tuple(f32(f32(f32(1 - weight) * x) + f32(weight * y)) for x, y in zip(a, b))
    return tuple(f32(x + f32(weight * f32(y - x))) for x, y in zip(a, b))


def run(output):
    from analyze_native_resources import NativeImage
    from ordinary_crocodile_binding_probe import SO, RESOURCES
    from ordinary_crocodile_animation_probe import MODEL, ANIMATION
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from tutorial_npc_binding_probe import controller, world_matrices, host_vertices
    from bdae_character import aliases
    from bdae_skin import multiply
    output = Path(output).resolve()
    if not output.is_relative_to(AREA) or output.exists():
        raise ValueError('New638 ignored output required')
    output.mkdir(parents=True)
    write = lambda n, x: (output / n).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    image = NativeImage(SO.read_bytes())
    constants = {hex(at): hex(struct.unpack('<I', image.read(at, 4))[0]) for at in (0x1f02100, 0x1e62ca4, 0x1df7a78)}
    if list(constants.values()) != ['0x42055555', '0x3cf5c290', '0x3d4ccccd']:
        raise ValueError('Original638 shared key/quaternion constants differ')
    body, reader = BDAE(RESOURCES / MODEL), BDAEAnimation(RESOURCES / ANIMATION)
    p = complete_type()(image, body, controller(body, body.parse()))
    p.prepare_complete(reader)
    decoded = export_tracks(p, reader)
    write('animation-v1.json', decoded)
    controls = []
    for clip in decoded['clips']:
        source = next(c for c in p.description['ranges'] if c['name'] == clip['name'])
        duration = clip['endMs'] - clip['startMs']
        clock = p.original_clock(reader, source['rangeRecord'], [duration, .25, duration * 2 + .125])
        times = sorted({clip['startMs'], clip['startMs'] + .25, clip['startMs'] + 7,
            (clip['startMs'] + clip['endMs']) / 2 + .125, clip['endMs'] - .25, clip['endMs'],
            *[s['startMs'] + d for s in p.description['segments'] for d in (-.25, 0, .25)
              if clip['startMs'] <= s['startMs'] + d <= clip['endMs']],
            *[s['absoluteMs'] for s in clock]})
        cases, states, vertex_checked = [], [{} for _ in range(44)], set()
        vertex_times = {clip['startMs'], (clip['startMs'] + clip['endMs']) / 2 + .125, clip['endMs']}
        for ms in times + [s['absoluteMs'] for s in clock]:
            actual = p.sample_complete(ms, source['rangeIndex'])
            maximum = 0
            nodes = copy.deepcopy(p.skin['nodes'])
            names = aliases(nodes)
            for i, (track, sample) in enumerate(zip(clip['tracks'], actual['samples'])):
                want = sample_track(track, ms, states[i], clip)
                nodes[names[track['node']]][track['type']] = want
                err = max(abs(a - b) for a, b in zip(want, sample['value']))
                # Keep literal quaternion sign; no equivalent-sign forgiveness.
                maximum = max(maximum, err)
            if maximum > .002:
                write('sample-failure-v1.json', {'clip': clip['name'], 'maximum': maximum, 'case': actual})
                raise ValueError('Original638 interpolation differs; do not widen threshold')
            applied = p.apply_original_samples(actual)
            world = world_matrices(nodes)
            palette = [multiply(world[b['node']], b['inverse']) for b in p.skin['bones']]
            palette_error = max(abs(a - b) for row, wanted in zip(applied['actualPalette'], palette) for a, b in zip(row, wanted))
            if palette_error > .002:
                raise ValueError('Original638 sampled world/palette differs')
            receipt = {**actual, 'maximumPropertyError': maximum, 'maximumPaletteError': palette_error,
                       'actualPalette': applied['actualPalette']}
            if ms in vertex_times and ms not in vertex_checked:
                positions = body.parse()['meshes'][0]['positions']
                native = p.vertices(positions)
                expected = host_vertices(p.skin, positions, palette)
                error = max(abs(a - b) for a, b in zip(native, expected))
                if error > .002:
                    raise ValueError('Original638 sampled1266 vertex scatter differs')
                receipt.update(nativePositionOnlyVertices=native, maximumVertexError=error)
                vertex_checked.add(ms)
            cases.append(receipt)
        controls.append({'clip': clip['name'], 'clock': clock, 'cases': cases})
    result = {'format': 'oc2-original638-complete-controls-v1', 'nativeSHA256': sha(image.data),
              'originalConstants': constants, 'originalSamplerEntries': p.sampler_entries,
              'description': p.description, 'controls': controls,
              'originalKeyCopies': p.copy_invocations, 'compressedCodecOrOldParserChanged': False,
              'animationSHA256': sha((output / 'animation-v1.json').read_bytes()),
              'gameActorOrGPUOrQuestAdmission': False}
    write('controls-v1.json', result)
    return result


def edge_controls(animation_path, output):
    """Only fresh/reversed duplicate-key controls, reuse exported native values."""
    from analyze_native_resources import NativeImage
    from ordinary_crocodile_binding_probe import SO, RESOURCES
    from ordinary_crocodile_animation_probe import MODEL, ANIMATION
    from bdae_convert import BDAE
    from bdae_animation import BDAEAnimation
    from tutorial_npc_binding_probe import controller
    output = Path(output).resolve()
    animation_path = Path(animation_path).resolve()
    if not output.is_relative_to(AREA) or output.exists() or not animation_path.is_relative_to(AREA):
        raise ValueError('Existing owned animation and new638 output required')
    animation = json.loads(animation_path.read_text())
    image, body = NativeImage(SO.read_bytes()), BDAE(RESOURCES / MODEL)
    p = complete_type()(image, body, controller(body, body.parse()))
    p.prepare_complete(BDAEAnimation(RESOURCES / ANIMATION))
    controls = []
    for clip in animation['clips']:
        source = next(c for c in p.description['ranges'] if c['name'] == clip['name'])
        states, cases = [{} for _ in range(44)], []
        for ms in [clip['endMs'], clip['endMs'] - .25, clip['endMs'], clip['startMs'], clip['endMs']]:
            actual = p.sample_complete(ms, source['rangeIndex'])
            maximum = max(abs(a - b) for i, (track, sample) in enumerate(zip(clip['tracks'], actual['samples']))
                          for a, b in zip(sample_track(track, ms, states[i], clip), sample['value']))
            if maximum > .002:
                raise ValueError('Original638 cold/warm repeated-key behavior differs')
            cases.append({**actual, 'maximumPropertyError': maximum})
        controls.append({'clip': clip['name'], 'newSourceContexts': True, 'cases': cases})
    result = {'format': 'oc2-original638-native-key-edge-controls-v1', 'controls': controls,
              'animationSHA256': sha(animation_path.read_bytes()), 'nativeSHA256': sha(image.data),
              'originalSamplerEntries': p.sampler_entries, 'newKeyCopies': 0,
              'sourceKeyValuesOrOrderChanged': False}
    output.mkdir(parents=True)
    (output / 'controls-v1.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--edge-controls', type=Path)
    args = ap.parse_args()
    result = edge_controls(args.edge_controls, args.output) if args.edge_controls else run(args.output)
    print(json.dumps({'originalKeyCopies': result.get('originalKeyCopies', 0),
        'cases': [(c['clip'], len(c['cases']), max(x['maximumPropertyError'] for x in c['cases'])) for c in result['controls']]}))
